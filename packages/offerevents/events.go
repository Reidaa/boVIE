// Package offerevents defines the version-1 OfferEvent contract exchanged over NATS.
package offerevents

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net/url"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/google/uuid"
)

// EventNamespace is the UUIDv5 namespace for stable event IDs.
// Changing this namespace changes every event ID and defeats republish deduplication.
var EventNamespace = uuid.MustParse("a29ccd0b-e431-445f-8881-a6ad4aa872bf")

// EventType identifies what happened to an offer.
type EventType string

const (
	EventDiscovered EventType = "discovered"
	EventUpdated    EventType = "updated"
	EventClosed     EventType = "closed"
)

// Source identifies the upstream job board.
type Source string

const (
	SourceBusinessFrance Source = "business_france"
	SourceWTTJ           Source = "wttj"
	SourceWorkday        Source = "workday"
)

// DisplayField is a rendered key-value field included in an offer event.
type DisplayField struct {
	Name   string `json:"name"`
	Value  string `json:"value"`
	Inline bool   `json:"inline"`
}

// NewDisplayField creates an inline DisplayField (matching the schema default inline=true).
func NewDisplayField(name, value string) DisplayField {
	return DisplayField{
		Name:   name,
		Value:  value,
		Inline: true,
	}
}

// UnmarshalJSON defaults Inline to true when omitted, matching the v1 contract.
func (f *DisplayField) UnmarshalJSON(data []byte) error {
	type rawField struct {
		Name   string `json:"name"`
		Value  string `json:"value"`
		Inline *bool  `json:"inline"`
	}
	var raw rawField
	if err := json.Unmarshal(data, &raw); err != nil {
		return err
	}
	inline := true
	if raw.Inline != nil {
		inline = *raw.Inline
	}
	f.Name = raw.Name
	f.Value = raw.Value
	f.Inline = inline
	return nil
}

// Validate checks DisplayField length bounds.
func (f DisplayField) Validate() error {
	nameLen := utf8.RuneCountInString(f.Name)
	if nameLen < 1 || nameLen > 256 {
		return fmt.Errorf("display field name length %d out of range [1, 256]", nameLen)
	}
	valLen := utf8.RuneCountInString(f.Value)
	if valLen < 1 || valLen > 1024 {
		return fmt.Errorf("display field value length %d out of range [1, 1024]", valLen)
	}
	return nil
}

// OfferDetails holds normalized offer fields.
type OfferDetails struct {
	Title        string         `json:"title"`
	Organization string         `json:"organization"`
	Country      string         `json:"country"`
	City         string         `json:"city"`
	URL          string         `json:"url"`
	Fields       []DisplayField `json:"fields"`
}

// Validate checks OfferDetails constraints.
func (o OfferDetails) Validate() error {
	titleLen := utf8.RuneCountInString(o.Title)
	if titleLen < 1 || titleLen > 256 {
		return fmt.Errorf("offer title length %d out of range [1, 256]", titleLen)
	}
	if err := validateHTTPURL(o.URL); err != nil {
		return fmt.Errorf("offer url: %w", err)
	}
	if len(o.Fields) > 25 {
		return fmt.Errorf("offer fields count %d exceeds max 25", len(o.Fields))
	}
	for i, field := range o.Fields {
		if err := field.Validate(); err != nil {
			return fmt.Errorf("offer fields[%d]: %w", i, err)
		}
	}
	return nil
}

// MarshalCompactJSON encodes v as compact JSON without HTML escaping.
func MarshalCompactJSON(v any) ([]byte, error) {
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(v); err != nil {
		return nil, err
	}
	return bytes.TrimSuffix(buf.Bytes(), []byte("\n")), nil
}

// ContentHash returns the SHA-256 hex digest of the canonical compact OfferDetails JSON.
func (o OfferDetails) ContentHash() (string, error) {
	normalized := o
	if normalized.Fields == nil {
		normalized.Fields = []DisplayField{}
	}
	raw, err := MarshalCompactJSON(normalized)
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:]), nil
}

// StableEventID derives a deterministic UUIDv5 so consumers can drop republished events.
func StableEventID(source Source, sourceOfferID string, eventType EventType, offer OfferDetails) (string, error) {
	identity := fmt.Sprintf("%s:%s:%s", source, sourceOfferID, eventType)
	if eventType == EventUpdated {
		hash, err := offer.ContentHash()
		if err != nil {
			return "", err
		}
		identity += ":" + hash
	}
	return uuid.NewSHA1(EventNamespace, []byte(identity)).String(), nil
}

// OfferEvent is the version-1 message exchanged on offers.<source>.v1.
type OfferEvent struct {
	Version       int          `json:"version"`
	Type          EventType    `json:"type"`
	Source        Source       `json:"source"`
	SourceOfferID string       `json:"source_offer_id"`
	Offer         OfferDetails `json:"offer"`
	EventID       string       `json:"event_id"`
	ObservedAt    time.Time    `json:"observed_at"`
}

// NewOfferEvent constructs and validates a version-1 OfferEvent with a stable EventID.
func NewOfferEvent(eventType EventType, source Source, sourceOfferID string, offer OfferDetails) (OfferEvent, error) {
	if offer.Fields == nil {
		offer.Fields = []DisplayField{}
	}
	eventID, err := StableEventID(source, sourceOfferID, eventType, offer)
	if err != nil {
		return OfferEvent{}, err
	}
	event := OfferEvent{
		Version:       1,
		Type:          eventType,
		Source:        source,
		SourceOfferID: sourceOfferID,
		Offer:         offer,
		EventID:       eventID,
		ObservedAt:    time.Now().UTC().Truncate(time.Microsecond),
	}
	if err := event.Validate(); err != nil {
		return OfferEvent{}, err
	}
	return event, nil
}

// Validate checks every OfferEvent invariant.
func (e OfferEvent) Validate() error {
	if e.Version != 1 {
		return fmt.Errorf("unsupported event version: %d", e.Version)
	}
	switch e.Type {
	case EventDiscovered, EventUpdated, EventClosed:
	default:
		return fmt.Errorf("invalid event type: %q", e.Type)
	}
	switch e.Source {
	case SourceBusinessFrance, SourceWTTJ, SourceWorkday:
	default:
		return fmt.Errorf("invalid event source: %q", e.Source)
	}
	idLen := utf8.RuneCountInString(e.SourceOfferID)
	if idLen < 1 || idLen > 255 {
		return fmt.Errorf("source_offer_id length %d out of range [1, 255]", idLen)
	}
	if e.SourceOfferID != strings.TrimSpace(e.SourceOfferID) {
		return errors.New("source identity cannot have surrounding whitespace")
	}
	if err := e.Offer.Validate(); err != nil {
		return err
	}
	if _, err := uuid.Parse(e.EventID); err != nil {
		return fmt.Errorf("invalid event_id: %w", err)
	}
	if e.ObservedAt.IsZero() {
		return errors.New("observed_at is required")
	}
	return nil
}

// MarshalBytes serializes OfferEvent as compact UTF-8 JSON without HTML escaping.
func (e OfferEvent) MarshalBytes() ([]byte, error) {
	normalized := e
	if normalized.Offer.Fields == nil {
		normalized.Offer.Fields = []DisplayField{}
	}
	normalized.ObservedAt = normalized.ObservedAt.UTC()
	return MarshalCompactJSON(normalized)
}

var allowedTopLevelFields = map[string]struct{}{
	"version":         {},
	"type":            {},
	"source":          {},
	"source_offer_id": {},
	"offer":           {},
	"event_id":        {},
	"observed_at":     {},
}

// ParseOfferEvent strictly parses and validates a version-1 OfferEvent JSON payload.
// Unknown top-level fields are rejected, matching Pydantic's extra="forbid".
func ParseOfferEvent(data []byte) (OfferEvent, error) {
	var rawMap map[string]json.RawMessage
	if err := json.Unmarshal(data, &rawMap); err != nil {
		return OfferEvent{}, fmt.Errorf("invalid json object: %w", err)
	}
	if rawMap == nil {
		return OfferEvent{}, errors.New("offer event cannot be null")
	}
	for key := range rawMap {
		if _, ok := allowedTopLevelFields[key]; !ok {
			return OfferEvent{}, fmt.Errorf("unknown top-level field %q", key)
		}
	}

	version := 1
	if rawVersion, ok := rawMap["version"]; ok {
		if err := json.Unmarshal(rawVersion, &version); err != nil {
			return OfferEvent{}, fmt.Errorf("invalid version: %w", err)
		}
	}

	rawType, ok := rawMap["type"]
	if !ok {
		return OfferEvent{}, errors.New("missing required field: type")
	}
	var eventType EventType
	if err := json.Unmarshal(rawType, &eventType); err != nil {
		return OfferEvent{}, fmt.Errorf("invalid type: %w", err)
	}

	rawSource, ok := rawMap["source"]
	if !ok {
		return OfferEvent{}, errors.New("missing required field: source")
	}
	var source Source
	if err := json.Unmarshal(rawSource, &source); err != nil {
		return OfferEvent{}, fmt.Errorf("invalid source: %w", err)
	}

	rawSourceOfferID, ok := rawMap["source_offer_id"]
	if !ok {
		return OfferEvent{}, errors.New("missing required field: source_offer_id")
	}
	var sourceOfferID string
	if err := json.Unmarshal(rawSourceOfferID, &sourceOfferID); err != nil {
		return OfferEvent{}, fmt.Errorf("invalid source_offer_id: %w", err)
	}

	rawOffer, ok := rawMap["offer"]
	if !ok {
		return OfferEvent{}, errors.New("missing required field: offer")
	}
	var offer OfferDetails
	if err := json.Unmarshal(rawOffer, &offer); err != nil {
		return OfferEvent{}, fmt.Errorf("invalid offer: %w", err)
	}
	if offer.Fields == nil {
		offer.Fields = []DisplayField{}
	}

	observedAt := time.Now().UTC().Truncate(time.Microsecond)
	if rawObservedAt, ok := rawMap["observed_at"]; ok {
		var ts string
		if err := json.Unmarshal(rawObservedAt, &ts); err != nil {
			return OfferEvent{}, fmt.Errorf("invalid observed_at: %w", err)
		}
		parsed, err := time.Parse(time.RFC3339Nano, ts)
		if err != nil {
			return OfferEvent{}, fmt.Errorf("observed_at must be timezone-aware RFC3339: %w", err)
		}
		observedAt = parsed.UTC()
	}

	var eventID string
	if rawEventID, ok := rawMap["event_id"]; ok {
		if err := json.Unmarshal(rawEventID, &eventID); err != nil {
			return OfferEvent{}, fmt.Errorf("invalid event_id: %w", err)
		}
	} else {
		derived, err := StableEventID(source, sourceOfferID, eventType, offer)
		if err != nil {
			return OfferEvent{}, err
		}
		eventID = derived
	}

	event := OfferEvent{
		Version:       version,
		Type:          eventType,
		Source:        source,
		SourceOfferID: sourceOfferID,
		Offer:         offer,
		EventID:       eventID,
		ObservedAt:    observedAt,
	}
	if err := event.Validate(); err != nil {
		return OfferEvent{}, err
	}
	return event, nil
}

// TruncateRunes truncates s to at most maxRunes Unicode code points.
func TruncateRunes(s string, maxRunes int) string {
	if maxRunes <= 0 {
		return ""
	}
	if utf8.RuneCountInString(s) <= maxRunes {
		return s
	}
	runes := []rune(s)
	return string(runes[:maxRunes])
}

func validateHTTPURL(raw string) error {
	parsed, err := url.Parse(raw)
	if err != nil {
		return err
	}
	if (parsed.Scheme != "http" && parsed.Scheme != "https") || parsed.Host == "" {
		return errors.New("must be an http or https URL with a host")
	}
	return nil
}
