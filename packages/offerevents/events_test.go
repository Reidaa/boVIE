package offerevents_test

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/Reidaa/boVIE/packages/offerevents"
)

func loadContractSamples(t *testing.T) []string {
	t.Helper()
	pattern := filepath.Join("..", "..", "tests", "contracts", "offer_event_v1", "*.json")
	matches, err := filepath.Glob(pattern)
	if err != nil {
		t.Fatalf("glob contract samples: %v", err)
	}
	if len(matches) == 0 {
		t.Fatalf("no contract samples found at %s", pattern)
	}
	return matches
}

func TestPublishedV1MessagesStillParseAndKeepStableEventIDs(t *testing.T) {
	samples := loadContractSamples(t)
	seenTypes := make(map[offerevents.EventType]bool)

	for _, samplePath := range samples {
		name := filepath.Base(samplePath)
		t.Run(name, func(t *testing.T) {
			raw, err := os.ReadFile(samplePath)
			if err != nil {
				t.Fatalf("read sample: %v", err)
			}
			parsed, err := offerevents.ParseOfferEvent(raw)
			if err != nil {
				t.Fatalf("parse frozen v1 sample: %v", err)
			}
			seenTypes[parsed.Type] = true

			// Remove event_id and re-parse: derived UUIDv5 must match stored frozen ID exactly.
			var obj map[string]any
			if err := json.Unmarshal(raw, &obj); err != nil {
				t.Fatalf("unmarshal sample map: %v", err)
			}
			storedID, ok := obj["event_id"].(string)
			if !ok {
				t.Fatalf("missing event_id in sample")
			}
			delete(obj, "event_id")
			withoutID, err := json.Marshal(obj)
			if err != nil {
				t.Fatalf("marshal without event_id: %v", err)
			}
			derived, err := offerevents.ParseOfferEvent(withoutID)
			if err != nil {
				t.Fatalf("parse without event_id: %v", err)
			}
			if derived.EventID != storedID {
				t.Fatalf("derived event_id = %q, want %q", derived.EventID, storedID)
			}
		})
	}

	for _, want := range []offerevents.EventType{
		offerevents.EventDiscovered,
		offerevents.EventUpdated,
		offerevents.EventClosed,
	} {
		if !seenTypes[want] {
			t.Fatalf("contract samples missing event type %q", want)
		}
	}
}

func sampleEvent(t *testing.T, sourceOfferID string, eventType offerevents.EventType, source offerevents.Source) offerevents.OfferEvent {
	t.Helper()
	ev, err := offerevents.NewOfferEvent(
		eventType,
		source,
		sourceOfferID,
		offerevents.OfferDetails{
			Title:        "Engineer",
			Organization: "Example",
			Country:      "France",
			City:         "Paris",
			URL:          "https://example.com/jobs/abc",
		},
	)
	if err != nil {
		t.Fatalf("NewOfferEvent: %v", err)
	}
	return ev
}

func TestEventIDsAreStableAcrossRepublishing(t *testing.T) {
	first := sampleEvent(t, "ABC", offerevents.EventDiscovered, offerevents.SourceBusinessFrance)
	second := sampleEvent(t, "ABC", offerevents.EventDiscovered, offerevents.SourceBusinessFrance)
	if second.EventID != first.EventID {
		t.Fatalf("expected identical event ID, got %s vs %s", second.EventID, first.EventID)
	}
	second.ObservedAt = time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	derived, err := offerevents.StableEventID(second.Source, second.SourceOfferID, second.Type, second.Offer)
	if err != nil {
		t.Fatalf("StableEventID: %v", err)
	}
	if derived != first.EventID {
		t.Fatalf("observed_at changed event ID: %s vs %s", derived, first.EventID)
	}
	if other := sampleEvent(t, "other", offerevents.EventDiscovered, offerevents.SourceBusinessFrance); other.EventID == first.EventID {
		t.Fatal("different source_offer_id produced same event ID")
	}
	if closed := sampleEvent(t, "ABC", offerevents.EventClosed, offerevents.SourceBusinessFrance); closed.EventID == first.EventID {
		t.Fatal("different type produced same event ID")
	}
	if wttj := sampleEvent(t, "ABC", offerevents.EventDiscovered, offerevents.SourceWTTJ); wttj.EventID == first.EventID {
		t.Fatal("different source produced same event ID")
	}
}

func TestUpdateEventIDsFollowOfferContent(t *testing.T) {
	update := sampleEvent(t, "ABC", offerevents.EventUpdated, offerevents.SourceBusinessFrance)
	same := sampleEvent(t, "ABC", offerevents.EventUpdated, offerevents.SourceBusinessFrance)
	if same.EventID != update.EventID {
		t.Fatalf("identical update content produced different event IDs")
	}
	changedOffer := update.Offer
	changedOffer.Title = "Lead"
	changedID, err := offerevents.StableEventID(update.Source, update.SourceOfferID, offerevents.EventUpdated, changedOffer)
	if err != nil {
		t.Fatalf("StableEventID: %v", err)
	}
	if changedID == update.EventID {
		t.Fatal("changed update content produced same event ID")
	}
}

func TestValidationAndStrictParsing(t *testing.T) {
	// Rejects unknown top-level field (extra="forbid").
	_, err := offerevents.ParseOfferEvent([]byte(`{
		"version": 1,
		"type": "discovered",
		"source": "wttj",
		"source_offer_id": "1",
		"extra_field": true,
		"offer": {"title": "Eng", "organization": "Ex", "country": "FR", "city": "Paris", "url": "https://example.com/1"}
	}`))
	if err == nil || !strings.Contains(err.Error(), "unknown") {
		t.Fatalf("expected unknown field error, got %v", err)
	}

	// Rejects surrounding whitespace on source_offer_id.
	_, err = offerevents.ParseOfferEvent([]byte(`{
		"version": 1,
		"type": "discovered",
		"source": "wttj",
		"source_offer_id": " 1 ",
		"offer": {"title": "Eng", "organization": "Ex", "country": "FR", "city": "Paris", "url": "https://example.com/1"}
	}`))
	if err == nil {
		t.Fatal("expected error for surrounding whitespace")
	}

	// Rejects naive observed_at without timezone.
	_, err = offerevents.ParseOfferEvent([]byte(`{
		"version": 1,
		"type": "discovered",
		"source": "wttj",
		"source_offer_id": "1",
		"observed_at": "2026-10-18T22:16:00",
		"offer": {"title": "Eng", "organization": "Ex", "country": "FR", "city": "Paris", "url": "https://example.com/1"}
	}`))
	if err == nil {
		t.Fatal("expected error for naive timestamp")
	}

	// Defaults DisplayField.Inline to true when omitted, and does not HTML-escape & in JSON.
	ev, err := offerevents.ParseOfferEvent([]byte(`{
		"version": 1,
		"type": "discovered",
		"source": "wttj",
		"source_offer_id": "1",
		"offer": {
			"title": "R&D Engineer",
			"organization": "Ex",
			"country": "FR",
			"city": "Paris",
			"url": "https://example.com/1?a=1&b=2",
			"fields": [{"name": "Role", "value": "R&D"}]
		}
	}`))
	if err != nil {
		t.Fatalf("ParseOfferEvent: %v", err)
	}
	if !ev.Offer.Fields[0].Inline {
		t.Fatal("expected omitted DisplayField.Inline to default to true")
	}
	raw, err := ev.MarshalBytes()
	if err != nil {
		t.Fatalf("MarshalBytes: %v", err)
	}
	if strings.Contains(string(raw), `\u0026`) {
		t.Fatalf("JSON escaped ampersand unexpectedly: %s", raw)
	}
}
