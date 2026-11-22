package main

import (
	"context"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/Reidaa/boVIE/packages/clicommon"
	"github.com/Reidaa/boVIE/packages/discordstore"
	"github.com/Reidaa/boVIE/packages/mysqlcommon"
	"github.com/Reidaa/boVIE/packages/natsclient"
	"github.com/Reidaa/boVIE/packages/offerevents"
	"github.com/nats-io/nats.go"
	"github.com/nats-io/nats.go/jetstream"
	"github.com/spf13/pflag"
)

const (
	// MaxRetryDelay caps the exponential backoff for failing messages.
	MaxRetryDelay = 3600 * time.Second
	// DefaultStreamWait is the interval between checks when waiting for OFFERS stream creation.
	DefaultStreamWait = 30 * time.Second
)

// ConsumerConfig returns the durable pull consumer settings for discord-intake.
// Setting Name ensures JetStream uses CONSUMER.CREATE.OFFERS.discord-intake, matching deploy/nats.conf.
func ConsumerConfig() jetstream.ConsumerConfig {
	return jetstream.ConsumerConfig{
		Name:          natsclient.Consumer,
		Durable:       natsclient.Consumer,
		AckPolicy:     jetstream.AckExplicitPolicy,
		AckWait:       120 * time.Second,
		MaxAckPending: 1000,
	}
}

// AcceptFunc persists an OfferEvent into the Discord inbox/deliveries tables.
type AcceptFunc func(ctx context.Context, event offerevents.OfferEvent) (bool, error)

// IntakeMessage abstracts the JetStream message operations needed by ReceiveMessage and Handle.
type IntakeMessage interface {
	Subject() string
	Data() []byte
	Metadata() (*jetstream.MsgMetadata, error)
	DoubleAck(ctx context.Context) error
	NakWithDelay(delay time.Duration) error
}

// EnsureConsumer creates the discord-intake consumer when missing and never changes an existing one.
// When the stream does not exist yet and wait is true, it waits until a collector creates it.
// When wait is false (used by --once), it returns (nil, false, nil) if the stream does not exist.
func EnsureConsumer(ctx context.Context, js jetstream.JetStream, wait bool, streamWait time.Duration) (jetstream.Consumer, bool, error) {
	if streamWait <= 0 {
		streamWait = DefaultStreamWait
	}
	for {
		consumer, err := js.Consumer(ctx, natsclient.Stream, natsclient.Consumer)
		if err == nil {
			return consumer, true, nil
		}
		if !errors.Is(err, jetstream.ErrConsumerNotFound) && !errors.Is(err, jetstream.ErrStreamNotFound) {
			return nil, false, err
		}

		if errors.Is(err, jetstream.ErrConsumerNotFound) {
			consumer, err = js.CreateConsumer(ctx, natsclient.Stream, ConsumerConfig())
			if err == nil {
				return consumer, true, nil
			}
			if !errors.Is(err, jetstream.ErrStreamNotFound) {
				return nil, false, err
			}
		}

		if !wait {
			return nil, false, nil
		}
		slog.Info("Stream does not exist yet; checking again",
			"stream", natsclient.Stream,
			"wait_seconds", streamWait.Seconds(),
		)
		timer := time.NewTimer(streamWait)
		select {
		case <-ctx.Done():
			timer.Stop()
			return nil, false, ctx.Err()
		case <-timer.C:
		}
	}
}

// ReceiveMessage validates the event and subject, commits inbox + delivery, and synchronously acks NATS.
func ReceiveMessage(ctx context.Context, accept AcceptFunc, msg IntakeMessage) error {
	event, err := offerevents.ParseOfferEvent(msg.Data())
	if err != nil {
		return err
	}
	if msg.Subject() != natsclient.Subject(event.Source) {
		return errors.New("event source does not match its NATS subject")
	}
	if _, err := accept(ctx, event); err != nil {
		return err
	}
	ackCtx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()
	return msg.DoubleAck(ackCtx)
}

// RetryDelay computes exponential backoff from 30s up to MaxRetryDelay (1 hour).
func RetryDelay(deliveries uint64) time.Duration {
	if deliveries <= 1 {
		return 30 * time.Second
	}
	shift := deliveries - 1
	if shift >= 10 {
		return MaxRetryDelay
	}
	delay := time.Duration(30<<shift) * time.Second
	if delay > MaxRetryDelay {
		return MaxRetryDelay
	}
	return delay
}

// Handle processes one JetStream message; on failure it logs without leaking payload and naks with backoff.
func Handle(ctx context.Context, accept AcceptFunc, msg IntakeMessage) bool {
	if err := ReceiveMessage(ctx, accept, msg); err != nil {
		var seq, deliveries uint64
		if meta, metaErr := msg.Metadata(); metaErr == nil && meta != nil {
			seq = meta.Sequence.Stream
			deliveries = meta.NumDelivered
		}
		if deliveries == 0 {
			deliveries = 1
		}
		clicommon.LogFailure(
			err,
			fmt.Sprintf("Discord intake of stream message %d (delivery %d)", seq, deliveries),
		)
		if nakErr := msg.NakWithDelay(RetryDelay(deliveries)); nakErr != nil {
			clicommon.LogFailure(nakErr, fmt.Sprintf("Discord intake nak of stream message %d", seq))
		}
		return false
	}
	return true
}

func runCLI(args []string, stdout, stderr io.Writer) int {
	var once bool
	flags := pflag.NewFlagSet("discord-intake", pflag.ContinueOnError)
	flags.SetOutput(stderr)
	flags.BoolVar(&once, "once", false, "Drain currently available messages and exit.")
	flags.Usage = func() {
		fmt.Fprintf(stderr, "Usage: discord-intake [OPTIONS]\n\nCommit events and pending Discord deliveries before acknowledging NATS.\n\nOptions:\n%s", flags.FlagUsages())
	}
	if err := flags.Parse(args); err != nil {
		if err == pflag.ErrHelp {
			return 0
		}
		return 2
	}

	clicommon.LoadDotEnv()
	slog.SetDefault(clicommon.NewLogger(stdout, stderr, false))

	cfg, err := mysqlcommon.LoadEnv()
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	db, err := mysqlcommon.OpenDB(cfg)
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	defer func() { _ = db.Close() }()

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	nc, err := natsclient.Connect()
	if err != nil {
		clicommon.LogFailure(err, "NATS connection")
		return 1
	}
	defer nc.Close()

	js, err := jetstream.New(nc)
	if err != nil {
		clicommon.LogFailure(err, "JetStream initialization")
		return 1
	}

	// With --once, a missing stream means there is nothing to drain.
	consumer, exists, err := EnsureConsumer(ctx, js, !once, DefaultStreamWait)
	if err != nil {
		if errors.Is(err, context.Canceled) {
			return 0
		}
		clicommon.LogFailure(err, "Ensure JetStream consumer")
		return 1
	}
	if !exists {
		return 0
	}

	accept := func(ctx context.Context, event offerevents.OfferEvent) (bool, error) {
		return discordstore.Accept(ctx, db, event)
	}

	for {
		if ctx.Err() != nil {
			return 0
		}
		batch, err := consumer.Fetch(1, jetstream.FetchMaxWait(2*time.Second))
		if err != nil {
			if errors.Is(err, nats.ErrTimeout) || errors.Is(err, context.DeadlineExceeded) {
				if once {
					return 0
				}
				continue
			}
			if errors.Is(err, context.Canceled) {
				return 0
			}
			clicommon.LogFailure(err, "Fetch JetStream batch")
			if once {
				fmt.Fprintln(stderr, "Error: Ingestion failed; message retained")
				return 1
			}
			continue
		}

		received := 0
		for msg := range batch.Messages() {
			received++
			if !Handle(ctx, accept, msg) && once {
				fmt.Fprintln(stderr, "Error: Ingestion failed; message retained")
				return 1
			}
		}
		if err := batch.Error(); err != nil && !errors.Is(err, nats.ErrTimeout) && !errors.Is(err, context.DeadlineExceeded) {
			clicommon.LogFailure(err, "Read JetStream batch")
			if once {
				fmt.Fprintln(stderr, "Error: Ingestion failed; message retained")
				return 1
			}
		}
		if received == 0 && once {
			return 0
		}
	}
}

func main() {
	os.Exit(runCLI(os.Args[1:], os.Stdout, os.Stderr))
}
