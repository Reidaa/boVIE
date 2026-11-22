package main

import (
	"context"
	"fmt"
	"os"
	"time"

	"github.com/Reidaa/boVIE/packages/clicommon"
	"github.com/Reidaa/boVIE/packages/discordstore"
	"github.com/Reidaa/boVIE/packages/mysqlcommon"
	"github.com/spf13/pflag"
)

func main() {
	var waitTimeout float64
	flags := pflag.NewFlagSet("discord-store-migrate", pflag.ContinueOnError)
	flags.Float64Var(&waitTimeout, "wait-timeout", 0, "Seconds to wait for database readiness before migrating.")
	flags.Usage = func() {
		fmt.Fprintf(os.Stderr, "Usage: discord-store-migrate [OPTIONS]\n\nApply this schema's migrations to DATABASE_URL.\n\nOptions:\n%s", flags.FlagUsages())
	}
	if err := flags.Parse(os.Args[1:]); err != nil {
		if err == pflag.ErrHelp {
			os.Exit(0)
		}
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	if waitTimeout < 0 {
		fmt.Fprintln(os.Stderr, "Error: --wait-timeout must be >= 0")
		os.Exit(2)
	}

	clicommon.ConfigureLogging(false)
	cfg, err := mysqlcommon.LoadEnv()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	db, err := mysqlcommon.OpenDB(cfg)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	defer func() { _ = db.Close() }()

	timeout := time.Duration(waitTimeout * float64(time.Second))
	if err := discordstore.Upgrade(context.Background(), cfg, db, timeout); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
