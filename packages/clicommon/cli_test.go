package clicommon_test

import (
	"bytes"
	"errors"
	"log/slog"
	"strings"
	"testing"

	"github.com/Reidaa/boVIE/packages/clicommon"
)

func TestErrorsGoToStderrAndRestToStdout(t *testing.T) {
	var stdout, stderr bytes.Buffer
	logger := clicommon.NewLogger(&stdout, &stderr, true)

	logger.Debug("debug message")
	logger.Info("info message")
	logger.Error("error message")

	if !strings.Contains(stdout.String(), "debug message") {
		t.Fatalf("expected debug message on stdout, got %q", stdout.String())
	}
	if !strings.Contains(stdout.String(), "info message") {
		t.Fatalf("expected info message on stdout, got %q", stdout.String())
	}
	if strings.Contains(stdout.String(), "error message") {
		t.Fatalf("error message leaked to stdout: %q", stdout.String())
	}
	if !strings.Contains(stderr.String(), "error message") {
		t.Fatalf("expected error message on stderr, got %q", stderr.String())
	}
	if strings.Contains(stderr.String(), "info message") {
		t.Fatalf("info message leaked to stderr: %q", stderr.String())
	}
}

func TestDebugMessagesAreHiddenByDefault(t *testing.T) {
	var stdout, stderr bytes.Buffer
	logger := clicommon.NewLogger(&stdout, &stderr, false)

	logger.Debug("debug message")

	if strings.Contains(stdout.String(), "debug message") {
		t.Fatalf("expected debug message to be suppressed, got %q", stdout.String())
	}
}

func TestLogFailureRedactsErrorMessage(t *testing.T) {
	var stdout, stderr bytes.Buffer
	prev := slog.Default()
	slog.SetDefault(clicommon.NewLogger(&stdout, &stderr, false))
	defer slog.SetDefault(prev)

	clicommon.LogFailure(errors.New("https://discord.invalid/secret-token"), "Discord delivery")

	if strings.Contains(stderr.String(), "secret-token") {
		t.Fatalf("LogFailure leaked secret error message: %q", stderr.String())
	}
	if !strings.Contains(stderr.String(), "Discord delivery failed") {
		t.Fatalf("expected operation in stderr, got %q", stderr.String())
	}
}
