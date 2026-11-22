package main

import (
	"bytes"
	"context"
	"errors"
	"io"
	"log/slog"
	"net/http"
	"strings"
	"testing"
	"time"
	"unicode/utf8"

	"github.com/Reidaa/boVIE/packages/clicommon"
	"github.com/Reidaa/boVIE/packages/mysqlcommon"
	"github.com/Reidaa/boVIE/packages/offerevents"
)

type roundTripFunc func(*http.Request) (*http.Response, error)

func (f roundTripFunc) RoundTrip(r *http.Request) (*http.Response, error) { return f(r) }

func sampleEvent(t *testing.T, source offerevents.Source, fields []offerevents.DisplayField) offerevents.OfferEvent {
	t.Helper()
	ev, err := offerevents.NewOfferEvent(
		offerevents.EventDiscovered,
		source,
		"ABC",
		offerevents.OfferDetails{
			Title:        "Engineer",
			Organization: "Example",
			Country:      "France",
			City:         "Paris",
			URL:          "https://example.com/jobs/abc",
			Fields:       fields,
		},
	)
	if err != nil {
		t.Fatal(err)
	}
	return ev
}

func TestCardFooterNamesTheSource(t *testing.T) {
	cases := []struct {
		source offerevents.Source
		label  string
	}{
		{offerevents.SourceBusinessFrance, "Business France"},
		{offerevents.SourceWTTJ, "Welcome to the Jungle"},
		{offerevents.SourceWorkday, "Workday"},
	}
	for _, tc := range cases {
		payload := DiscordPayload(sampleEvent(t, tc.source, nil))
		if got := payload.Embeds[0].Footer.Text; got != tc.label {
			t.Fatalf("source %s footer = %q, want %q", tc.source, got, tc.label)
		}
	}
}

func TestCardWithFooterFitsDiscordTextLimit(t *testing.T) {
	fields := make([]offerevents.DisplayField, 10)
	for i := range fields {
		fields[i] = offerevents.NewDisplayField("Notes", strings.Repeat("x", 1024))
	}
	embed := DiscordPayload(sampleEvent(t, offerevents.SourceBusinessFrance, fields)).Embeds[0]
	total := utf8.RuneCountInString(embed.Title) + utf8.RuneCountInString(embed.Footer.Text)
	for _, f := range embed.Fields {
		total += utf8.RuneCountInString(f.Name) + utf8.RuneCountInString(f.Value)
	}
	if total > 6000 {
		t.Fatalf("embed text length %d exceeds 6000", total)
	}
}

type fakeDeliveryStore struct {
	claim      *mysqlcommon.Claim
	finishOK   bool
	finished   bool
	retried    bool
	retryDelay *float64
}

func (s *fakeDeliveryStore) Claim(_ context.Context) (*mysqlcommon.Claim, error) {
	c := s.claim
	s.claim = nil
	return c, nil
}
func (s *fakeDeliveryStore) Finish(_ context.Context, _ mysqlcommon.Claim) (bool, error) {
	s.finished = true
	return s.finishOK, nil
}
func (s *fakeDeliveryStore) RetryLater(_ context.Context, _ mysqlcommon.Claim, delay *float64) (bool, error) {
	s.retried = true
	s.retryDelay = delay
	return true, nil
}

func makeClaim(t *testing.T) *mysqlcommon.Claim {
	t.Helper()
	ev := sampleEvent(t, offerevents.SourceBusinessFrance, nil)
	raw, _ := ev.MarshalBytes()
	return &mysqlcommon.Claim{EventID: ev.EventID, Token: "tok-1", Payload: raw, Attempts: 1}
}

func TestDeliverOneWaitTrueRateLimitLostLeaseAndRedactedErrors(t *testing.T) {
	// wait=true query parameter is sent.
	var gotWait string
	store := &fakeDeliveryStore{claim: makeClaim(t), finishOK: true}
	client := NewDiscordHTTPClient()
	client.Transport = roundTripFunc(func(r *http.Request) (*http.Response, error) {
		gotWait = r.URL.Query().Get("wait")
		return &http.Response{StatusCode: 200, Body: io.NopCloser(strings.NewReader(`{"id":"1"}`)), Header: make(http.Header)}, nil
	})
	ok, err := DeliverOne(context.Background(), store, client, "https://discord.invalid/webhook", nil)
	if err != nil || !ok || gotWait != "true" || !store.finished {
		t.Fatalf("ok=%v err=%v wait=%q finished=%v", ok, err, gotWait, store.finished)
	}

	// 429 rate limit waits Retry-After seconds and reschedules.
	var stdout, stderr bytes.Buffer
	prev := slog.Default()
	slog.SetDefault(clicommon.NewLogger(&stdout, &stderr, false))
	defer slog.SetDefault(prev)

	store429 := &fakeDeliveryStore{claim: makeClaim(t), finishOK: true}
	var slept []time.Duration
	client429 := NewDiscordHTTPClient()
	client429.Transport = roundTripFunc(func(_ *http.Request) (*http.Response, error) {
		return &http.Response{
			StatusCode: 429,
			Body:       io.NopCloser(strings.NewReader("")),
			Header:     http.Header{"Retry-After": []string{"7"}},
		}, nil
	})
	ok, err = DeliverOne(context.Background(), store429, client429, "https://discord.invalid/webhook", func(_ context.Context, d time.Duration) error {
		slept = append(slept, d)
		return nil
	})
	if err != nil || !ok || !store429.retried || store429.retryDelay == nil || *store429.retryDelay != 7 {
		t.Fatalf("429: ok=%v err=%v retried=%v delay=%v", ok, err, store429.retried, store429.retryDelay)
	}
	if len(slept) != 1 || slept[0] != 7*time.Second {
		t.Fatalf("slept = %v, want [7s]", slept)
	}
	if !strings.Contains(stdout.String(), "429") {
		t.Fatalf("expected 429 warning, got %q", stdout.String())
	}

	// Lost lease after sending logs warning.
	stdout.Reset()
	storeLost := &fakeDeliveryStore{claim: makeClaim(t), finishOK: false}
	ok, err = DeliverOne(context.Background(), storeLost, client, "https://discord.invalid/webhook", nil)
	if err != nil || !ok || !strings.Contains(stdout.String(), "lease") {
		t.Fatalf("lost lease: ok=%v err=%v log=%q", ok, err, stdout.String())
	}

	// Rejected status (400 and 302) logs HTTP status without leaking webhook URL.
	for _, status := range []int{400, 302} {
		stdout.Reset()
		stderr.Reset()
		storeErr := &fakeDeliveryStore{claim: makeClaim(t), finishOK: true}
		clientErr := NewDiscordHTTPClient()
		clientErr.Transport = roundTripFunc(func(_ *http.Request) (*http.Response, error) {
			return &http.Response{
				StatusCode: status,
				Body:       io.NopCloser(strings.NewReader("")),
				Header:     http.Header{"Location": []string{"https://evil.invalid"}},
			}, nil
		})
		_, err := DeliverOne(context.Background(), storeErr, clientErr, "https://discord.invalid/secret-webhook", nil)
		var statusErr *DiscordStatusError
		if !errors.As(err, &statusErr) || statusErr.StatusCode != status {
			t.Fatalf("status %d: expected DiscordStatusError, got %v", status, err)
		}
		if strings.Contains(err.Error(), "discord.invalid") || strings.Contains(stdout.String(), "discord.invalid") {
			t.Fatalf("webhook URL leaked for status %d: err=%q log=%q", status, err.Error(), stdout.String())
		}
		if !storeErr.retried {
			t.Fatalf("expected delivery to be retried on status %d", status)
		}
	}
}

func TestSenderWithoutWebhookTurnsDeliveryOff(t *testing.T) {
	t.Setenv("DISCORD_WEBHOOK_URL", "")
	var stdout, stderr bytes.Buffer
	opened := false
	code := runCLI(nil, &stdout, &stderr, cliDeps{
		openStore: func() (DeliveryStore, func(), error) {
			opened = true
			return nil, func() {}, nil
		},
	})
	if code != 0 || opened {
		t.Fatalf("code=%d opened=%v", code, opened)
	}
	if !strings.Contains(stdout.String(), "Discord delivery is off") {
		t.Fatalf("expected disabled warning, got %q", stdout.String())
	}
}
