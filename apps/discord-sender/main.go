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
	"github.com/Reidaa/boVIE/packages/mysqlcommon"
	"github.com/spf13/pflag"
)

type cliDeps struct {
	openStore func() (DeliveryStore, func(), error)
}

func defaultDeps() cliDeps {
	return cliDeps{
		openStore: func() (DeliveryStore, func(), error) {
			cfg, err := mysqlcommon.LoadEnv()
			if err != nil {
				return nil, nil, err
			}
			db, err := mysqlcommon.OpenDB(cfg)
			if err != nil {
				return nil, nil, err
			}
			return sqlDeliveryStore{db: db}, func() { _ = db.Close() }, nil
		},
	}
}

func runCLI(args []string, stdout, stderr io.Writer, deps cliDeps) int {
	var once bool
	flags := pflag.NewFlagSet("discord-sender", pflag.ContinueOnError)
	flags.SetOutput(stderr)
	flags.BoolVar(&once, "once", false, "Drain currently available deliveries and exit.")
	flags.Usage = func() {
		fmt.Fprintf(stderr, "Usage: discord-sender [OPTIONS]\n\nSend queued Discord messages using only Discord database credentials.\n\nOptions:\n%s", flags.FlagUsages())
	}
	if err := flags.Parse(args); err != nil {
		if err == pflag.ErrHelp {
			return 0
		}
		return 2
	}

	clicommon.LoadDotEnv()
	slog.SetDefault(clicommon.NewLogger(stdout, stderr, false))

	webhook := os.Getenv("DISCORD_WEBHOOK_URL")
	if webhook == "" {
		// PR environments have no webhook: Railway does not copy sealed variables.
		// Messages stay queued, and exiting cleanly stops Railway from restarting.
		slog.Warn("DISCORD_WEBHOOK_URL is not set; Discord delivery is off")
		return 0
	}

	store, cleanup, err := deps.openStore()
	if err != nil {
		clicommon.LogFailure(err, "Discord store initialization")
		return 1
	}
	defer cleanup()

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	httpClient := NewDiscordHTTPClient()
	for {
		if ctx.Err() != nil {
			return 0
		}
		processed, err := DeliverOne(ctx, store, httpClient, webhook, sleepContext)
		if err != nil {
			if errors.Is(err, context.Canceled) {
				return 0
			}
			clicommon.LogFailure(err, "Discord delivery")
			if once {
				fmt.Fprintln(stderr, "Error: Delivery failed; pending work retained")
				return 1
			}
			processed = false
		}
		if !processed {
			if once {
				return 0
			}
			if err := sleepContext(ctx, time.Second); err != nil {
				return 0
			}
		}
	}
}

func main() {
	os.Exit(runCLI(os.Args[1:], os.Stdout, os.Stderr, defaultDeps()))
}
