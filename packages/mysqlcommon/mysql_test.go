package mysqlcommon

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"

	"github.com/go-sql-driver/mysql"
)

func TestMySQLConfiguration(t *testing.T) {
	cfg, err := ParseDatabaseURL("mysql+pymysql://worker:secret@localhost/source")
	if err != nil {
		t.Fatalf("ParseDatabaseURL: %v", err)
	}
	if cfg.User() != "worker" || cfg.Password() != "secret" || cfg.Database() != "source" {
		t.Fatalf("unexpected parsed config: %+v", cfg)
	}
	if strings.Contains(cfg.String(), "secret") || strings.Contains(cfg.GoString(), "secret") {
		t.Fatalf("password leaked in redacted representation: %s", cfg.String())
	}

	railway, err := ParseDatabaseURL("mysql://worker:p%40ss@localhost/source")
	if err != nil {
		t.Fatalf("ParseDatabaseURL railway: %v", err)
	}
	if railway.Password() != "p@ss" {
		t.Fatalf("expected decoded password p@ss, got %q", railway.Password())
	}

	invalid := []string{
		"postgresql://u:p@host/db",
		"sqlite://",
		"mysql://u:p@host",
		"not a url",
		"mysql://u:p@host:port/db",
	}
	for _, raw := range invalid {
		if _, err := ParseDatabaseURL(raw); err == nil {
			t.Fatalf("expected error for invalid URL %q", raw)
		}
	}
}

type fakePinger struct {
	errs  []error
	calls int
}

func (f *fakePinger) PingContext(_ context.Context) error {
	idx := f.calls
	f.calls++
	if idx < len(f.errs) {
		return f.errs[idx]
	}
	return nil
}

func TestDatabaseReadinessRetriesConnectionFailures(t *testing.T) {
	pinger := &fakePinger{errs: []error{errors.New("refused"), nil}}
	var pauses []time.Duration
	now := func() time.Time { return time.Unix(0, 0) }
	sleep := func(_ context.Context, d time.Duration) error {
		pauses = append(pauses, d)
		return nil
	}

	err := waitForDatabaseWithClock(context.Background(), pinger, 10*time.Second, now, sleep)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if pinger.calls != 2 {
		t.Fatalf("expected 2 ping calls, got %d", pinger.calls)
	}
	if len(pauses) != 1 || pauses[0] != 2*time.Second {
		t.Fatalf("expected single 2s pause, got %v", pauses)
	}
}

func TestDatabaseReadinessDeadlineIsBounded(t *testing.T) {
	pinger := &fakePinger{errs: []error{errors.New("refused"), errors.New("refused")}}
	times := []time.Time{time.Unix(0, 0), time.Unix(2, 0), time.Unix(3, 0)}
	idx := 0
	now := func() time.Time {
		v := times[idx]
		idx++
		return v
	}
	var pauses []time.Duration
	sleep := func(_ context.Context, d time.Duration) error {
		pauses = append(pauses, d)
		return nil
	}

	err := waitForDatabaseWithClock(context.Background(), pinger, 3*time.Second, now, sleep)
	if err == nil {
		t.Fatal("expected deadline error")
	}
	if pinger.calls != 2 {
		t.Fatalf("expected 2 calls, got %d", pinger.calls)
	}
	if len(pauses) != 1 || pauses[0] != time.Second {
		t.Fatalf("expected single 1s pause, got %v", pauses)
	}
}

func TestDatabaseReadinessReturnsUnknownDatabaseImmediately(t *testing.T) {
	pinger := &fakePinger{errs: []error{&mysql.MySQLError{Number: UnknownDatabaseCode, Message: "Unknown database"}}}
	var pauses []time.Duration
	sleep := func(_ context.Context, d time.Duration) error {
		pauses = append(pauses, d)
		return nil
	}

	err := waitForDatabaseWithClock(context.Background(), pinger, 10*time.Second, time.Now, sleep)
	if !IsUnknownDatabase(err) {
		t.Fatalf("expected UnknownDatabase error, got %v", err)
	}
	if pinger.calls != 1 || len(pauses) != 0 {
		t.Fatalf("expected immediate return without retries, calls=%d pauses=%v", pinger.calls, pauses)
	}
}
