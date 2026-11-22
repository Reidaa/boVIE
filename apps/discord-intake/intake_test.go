package main

import (
	"context"
	"testing"
	"time"

	"github.com/Reidaa/boVIE/packages/offerevents"
	"github.com/nats-io/nats.go/jetstream"
)

func TestFailedMessagesBackOffUpToAnHour(t *testing.T) {
	cases := []struct {
		deliveries uint64
		want       time.Duration
	}{
		{1, 30 * time.Second},
		{2, 60 * time.Second},
		{5, 480 * time.Second},
		{8, 3600 * time.Second},
		{50, 3600 * time.Second},
	}
	for _, tc := range cases {
		if got := RetryDelay(tc.deliveries); got != tc.want {
			t.Fatalf("RetryDelay(%d) = %v, want %v", tc.deliveries, got, tc.want)
		}
	}
}

type fakeMsg struct {
	subject    string
	data       []byte
	deliveries uint64
	streamSeq  uint64
	acked      int
	nakDelays  []time.Duration
	onAck      func()
}

func (m *fakeMsg) Subject() string { return m.subject }
func (m *fakeMsg) Data() []byte    { return m.data }
func (m *fakeMsg) Metadata() (*jetstream.MsgMetadata, error) {
	return &jetstream.MsgMetadata{
		NumDelivered: m.deliveries,
		Sequence:     jetstream.SequencePair{Stream: m.streamSeq},
	}, nil
}
func (m *fakeMsg) DoubleAck(_ context.Context) error {
	if m.onAck != nil {
		m.onAck()
	}
	m.acked++
	return nil
}
func (m *fakeMsg) NakWithDelay(d time.Duration) error {
	m.nakDelays = append(m.nakDelays, d)
	return nil
}

func TestFailedMessageIsRetainedWithBackoff(t *testing.T) {
	msg := &fakeMsg{
		subject:    "offers.wttj.v1",
		data:       []byte(`{"version": 1}`),
		deliveries: 3,
		streamSeq:  42,
	}
	called := false
	ok := Handle(context.Background(), func(_ context.Context, _ offerevents.OfferEvent) (bool, error) {
		called = true
		return true, nil
	}, msg)
	if ok {
		t.Fatal("expected Handle to return false for invalid event")
	}
	if called {
		t.Fatal("invalid event must never reach database accept")
	}
	if len(msg.nakDelays) != 1 || msg.nakDelays[0] != 120*time.Second {
		t.Fatalf("nakDelays = %v, want [120s]", msg.nakDelays)
	}
}

func TestReceiveMessageCommitsBeforeAckAndChecksSubject(t *testing.T) {
	ev, err := offerevents.NewOfferEvent(
		offerevents.EventDiscovered,
		offerevents.SourceBusinessFrance,
		"ABC",
		offerevents.OfferDetails{
			Title:        "Engineer",
			Organization: "Example",
			Country:      "France",
			City:         "Paris",
			URL:          "https://example.com/jobs/abc",
		},
	)
	if err != nil {
		t.Fatal(err)
	}
	raw, _ := ev.MarshalBytes()

	committed := false
	msg := &fakeMsg{
		subject: "offers.business_france.v1",
		data:    raw,
		onAck: func() {
			if !committed {
				t.Fatal("DoubleAck called before accept committed")
			}
		},
	}
	accept := func(_ context.Context, _ offerevents.OfferEvent) (bool, error) {
		committed = true
		return true, nil
	}
	if err := ReceiveMessage(context.Background(), accept, msg); err != nil {
		t.Fatalf("ReceiveMessage: %v", err)
	}
	if msg.acked != 1 {
		t.Fatalf("acked = %d, want 1", msg.acked)
	}

	// Wrong subject is rejected.
	wrong := &fakeMsg{subject: "offers.wttj.v1", data: raw}
	if err := ReceiveMessage(context.Background(), accept, wrong); err == nil {
		t.Fatal("expected error for mismatched subject")
	}
}
