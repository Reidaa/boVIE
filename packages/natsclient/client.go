// Package natsclient provides shared NATS JetStream connection, stream setup, and offer publishing.
package natsclient

import (
	"context"
	"errors"
	"fmt"
	"os"
	"time"

	"github.com/Reidaa/boVIE/packages/offerevents"
	"github.com/nats-io/nats.go"
	"github.com/nats-io/nats.go/jetstream"
)

const (
	// Stream is the shared JetStream stream carrying all v1 offer events.
	Stream = "OFFERS"
	// Consumer is the durable pull consumer owned by discord-intake.
	Consumer = "discord-intake"
)

// StreamConfig returns the OFFERS stream configuration.
// Limits retention keeps acknowledged messages so multiple consumers can read and replay history.
func StreamConfig() jetstream.StreamConfig {
	return jetstream.StreamConfig{
		Name:       Stream,
		Subjects:   []string{"offers.*.v1"},
		Storage:    jetstream.FileStorage,
		Retention:  jetstream.LimitsPolicy,
		MaxAge:     90 * 24 * time.Hour,
		Discard:    jetstream.DiscardNew,
		MaxBytes:   1024 * 1024 * 1024,
		MaxMsgSize: 131072,
		Duplicates: 120 * time.Second,
		Replicas:   1,
	}
}

// Subject returns the JetStream publish subject for a source.
func Subject(source offerevents.Source) string {
	return fmt.Sprintf("offers.%s.v1", source)
}

// Connect opens a NATS connection configured from NATS_URL, NATS_USER, and NATS_PASSWORD.
// When NATS_USER is set, the inbox prefix is scoped to _INBOX.<user> to match deploy/nats.conf.
func Connect(extraOpts ...nats.Option) (*nats.Conn, error) {
	rawURL := os.Getenv("NATS_URL")
	if rawURL == "" {
		rawURL = "nats://127.0.0.1:4222"
	}
	user := os.Getenv("NATS_USER")
	password := os.Getenv("NATS_PASSWORD")

	opts := []nats.Option{
		nats.Timeout(5 * time.Second),
	}
	if user != "" {
		opts = append(opts,
			nats.UserInfo(user, password),
			nats.CustomInboxPrefix("_INBOX."+user),
		)
	} else {
		opts = append(opts, nats.CustomInboxPrefix("_INBOX"))
	}
	opts = append(opts, extraOpts...)
	return nats.Connect(rawURL, opts...)
}

// EnsureStream creates the OFFERS stream when it is missing and never modifies an existing stream.
// Collector accounts can create the stream but not update it.
func EnsureStream(ctx context.Context, js jetstream.JetStream) error {
	_, err := js.Stream(ctx, Stream)
	if err == nil {
		return nil
	}
	if !errors.Is(err, jetstream.ErrStreamNotFound) {
		return err
	}
	_, err = js.CreateStream(ctx, StreamConfig())
	return err
}

// Publisher publishes OfferEvents synchronously and waits for JetStream acknowledgments.
type Publisher struct {
	nc      *nats.Conn
	js      jetstream.JetStream
	timeout time.Duration
}

// NewPublisher connects to NATS, ensures the OFFERS stream exists, and returns a Publisher.
func NewPublisher(ctx context.Context, timeout time.Duration) (*Publisher, error) {
	if timeout <= 0 {
		timeout = 10 * time.Second
	}
	nc, err := Connect()
	if err != nil {
		return nil, err
	}
	js, err := jetstream.New(nc)
	if err != nil {
		nc.Close()
		return nil, err
	}
	initCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	if err := EnsureStream(initCtx, js); err != nil {
		nc.Close()
		return nil, err
	}
	return &Publisher{
		nc:      nc,
		js:      js,
		timeout: timeout,
	}, nil
}

// Publish sends an OfferEvent with Nats-Msg-Id deduplication and waits for the JetStream ack.
func (p *Publisher) Publish(ctx context.Context, event offerevents.OfferEvent) error {
	data, err := event.MarshalBytes()
	if err != nil {
		return fmt.Errorf("marshal event: %w", err)
	}
	pubCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()
	_, err = p.js.Publish(pubCtx, Subject(event.Source), data, jetstream.WithMsgID(event.EventID))
	return err
}

// Close closes the underlying NATS connection.
func (p *Publisher) Close() {
	if p.nc != nil {
		p.nc.Close()
	}
}
