// Package clicommon provides entrypoint environment loading and redacted failure logging.
package clicommon

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"runtime/debug"
	"strings"
	"sync"
	"time"

	"github.com/joho/godotenv"
)

// LoadDotEnv loads .env from the working directory without overriding existing environment variables.
func LoadDotEnv() {
	_ = godotenv.Load(".env")
}

// ConfigureLogging sends errors to stderr and everything else to stdout.
// Railway marks every stderr line as an error, so normal logs must not use stderr.
func ConfigureLogging(debugMode bool) {
	LoadDotEnv()
	slog.SetDefault(NewLogger(os.Stdout, os.Stderr, debugMode))
}

// NewLogger builds a logger that routes < ERROR to stdout and >= ERROR to stderr.
func NewLogger(stdout, stderr io.Writer, debugMode bool) *slog.Logger {
	minLevel := slog.LevelInfo
	if debugMode {
		minLevel = slog.LevelDebug
	}
	return slog.New(&splitHandler{
		stdout:   stdout,
		stderr:   stderr,
		minLevel: minLevel,
	})
}

// LogFailure logs the operation name, error type, and stack trace without error messages
// that could contain secrets such as webhook URLs or database credentials.
func LogFailure(err error, operation string) {
	slog.Error(
		fmt.Sprintf("%s failed (%T).\n%s", operation, err, string(debug.Stack())),
	)
}

type splitHandler struct {
	mu       sync.Mutex
	stdout   io.Writer
	stderr   io.Writer
	minLevel slog.Level
	attrs    []slog.Attr
	group    string
}

func (h *splitHandler) Enabled(_ context.Context, level slog.Level) bool {
	return level >= h.minLevel
}

func (h *splitHandler) Handle(_ context.Context, r slog.Record) error {
	var b strings.Builder
	ts := r.Time
	if ts.IsZero() {
		ts = time.Now().UTC()
	} else {
		ts = ts.UTC()
	}
	fmt.Fprintf(&b, "%s | %-8s | %s", ts.Format(time.RFC3339), levelLabel(r.Level), r.Message)
	for _, a := range h.attrs {
		writeAttr(&b, h.group, a)
	}
	r.Attrs(func(a slog.Attr) bool {
		writeAttr(&b, h.group, a)
		return true
	})
	b.WriteByte('\n')

	dst := h.stdout
	if r.Level >= slog.LevelError {
		dst = h.stderr
	}
	h.mu.Lock()
	defer h.mu.Unlock()
	_, err := io.WriteString(dst, b.String())
	return err
}

func (h *splitHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	next := make([]slog.Attr, 0, len(h.attrs)+len(attrs))
	next = append(next, h.attrs...)
	next = append(next, attrs...)
	return &splitHandler{
		stdout:   h.stdout,
		stderr:   h.stderr,
		minLevel: h.minLevel,
		attrs:    next,
		group:    h.group,
	}
}

func (h *splitHandler) WithGroup(name string) slog.Handler {
	g := name
	if h.group != "" && name != "" {
		g = h.group + "." + name
	} else if h.group != "" {
		g = h.group
	}
	return &splitHandler{
		stdout:   h.stdout,
		stderr:   h.stderr,
		minLevel: h.minLevel,
		attrs:    append([]slog.Attr(nil), h.attrs...),
		group:    g,
	}
}

func levelLabel(level slog.Level) string {
	switch {
	case level >= slog.LevelError:
		return "ERROR"
	case level >= slog.LevelWarn:
		return "WARNING"
	case level >= slog.LevelInfo:
		return "INFO"
	default:
		return "DEBUG"
	}
}

func writeAttr(b *strings.Builder, group string, a slog.Attr) {
	if a.Equal(slog.Attr{}) {
		return
	}
	key := a.Key
	if group != "" {
		key = group + "." + key
	}
	fmt.Fprintf(b, " %s=%v", key, a.Value.Any())
}
