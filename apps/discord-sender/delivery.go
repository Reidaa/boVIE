package main

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log/slog"
	"math"
	"net/http"
	"net/url"
	"strconv"
	"time"
	"unicode/utf8"

	"github.com/Reidaa/boVIE/packages/discordstore"
	"github.com/Reidaa/boVIE/packages/mysqlcommon"
	"github.com/Reidaa/boVIE/packages/offerevents"
)

// SourceLabels maps internal source identifiers to human-readable Discord card footers.
var SourceLabels = map[offerevents.Source]string{
	offerevents.SourceBusinessFrance: "Business France",
	offerevents.SourceWTTJ:           "Welcome to the Jungle",
	offerevents.SourceWorkday:        "Workday",
}

// AllowedMentions disables pings in webhook messages.
type AllowedMentions struct {
	Parse []string `json:"parse"`
}

// EmbedFooter names the offer source at the bottom of a Discord card.
type EmbedFooter struct {
	Text string `json:"text"`
}

// EmbedField represents one field in a Discord webhook embed.
type EmbedField struct {
	Name   string `json:"name"`
	Value  string `json:"value"`
	Inline bool   `json:"inline,omitempty"`
}

// Embed represents a Discord webhook embed card.
type Embed struct {
	Title  string       `json:"title"`
	URL    string       `json:"url"`
	Color  int          `json:"color"`
	Fields []EmbedField `json:"fields"`
	Footer EmbedFooter  `json:"footer"`
}

// WebhookPayload is the JSON payload POSTed to a Discord webhook.
type WebhookPayload struct {
	Username        string          `json:"username"`
	AllowedMentions AllowedMentions `json:"allowed_mentions"`
	Embeds          []Embed         `json:"embeds"`
}

// DiscordStatusError records a non-2xx HTTP status from Discord without including the webhook URL.
type DiscordStatusError struct {
	StatusCode int
}

func (e *DiscordStatusError) Error() string {
	return fmt.Sprintf("Discord webhook returned HTTP %d", e.StatusCode)
}

// DeliveryStore abstracts queue operations on the discord deliveries table for testing.
type DeliveryStore interface {
	Claim(ctx context.Context) (*mysqlcommon.Claim, error)
	Finish(ctx context.Context, work mysqlcommon.Claim) (bool, error)
	RetryLater(ctx context.Context, work mysqlcommon.Claim, delaySeconds *float64) (bool, error)
}

type sqlDeliveryStore struct {
	db *sql.DB
}

func (s sqlDeliveryStore) Claim(ctx context.Context) (*mysqlcommon.Claim, error) {
	return discordstore.ClaimDelivery(ctx, s.db, nil, 120)
}

func (s sqlDeliveryStore) Finish(ctx context.Context, work mysqlcommon.Claim) (bool, error) {
	return discordstore.FinishDelivery(ctx, s.db, work, nil)
}

func (s sqlDeliveryStore) RetryLater(ctx context.Context, work mysqlcommon.Claim, delaySeconds *float64) (bool, error) {
	return discordstore.RetryDeliveryLater(ctx, s.db, work, nil, delaySeconds)
}

// NewDiscordHTTPClient returns an HTTP client with a 15-second timeout that does not follow redirects.
func NewDiscordHTTPClient() *http.Client {
	return &http.Client{
		Timeout: 15 * time.Second,
		CheckRedirect: func(_ *http.Request, _ []*http.Request) error {
			return http.ErrUseLastResponse
		},
	}
}

// DiscordPayload renders an OfferEvent into a Discord webhook payload within the 6000-char embed limit.
func DiscordPayload(event offerevents.OfferEvent) WebhookPayload {
	offer := event.Offer
	fields := make([]EmbedField, 0, len(offer.Fields))
	for _, f := range offer.Fields {
		fields = append(fields, EmbedField{
			Name:   f.Name,
			Value:  f.Value,
			Inline: f.Inline,
		})
	}
	if len(fields) == 0 {
		org := offerevents.TruncateRunes(offer.Organization, 1024)
		if org == "" {
			org = "N/A"
		}
		fields = []EmbedField{
			{Name: "Entreprise", Value: org, Inline: true},
			{Name: "Lieu", Value: offerevents.TruncateRunes(fmt.Sprintf("%s, %s", offer.City, offer.Country), 1024), Inline: true},
		}
	}

	footer := SourceLabels[event.Source]
	// Discord's aggregate embed text limit is 6000 characters.
	remaining := 6000 - utf8.RuneCountInString(offer.Title) - utf8.RuneCountInString(footer)
	bounded := make([]EmbedField, 0, len(fields))
	for _, field := range fields {
		nameLen := utf8.RuneCountInString(field.Name)
		available := remaining - nameLen
		if available <= 0 {
			break
		}
		field.Value = offerevents.TruncateRunes(field.Value, available)
		remaining -= nameLen + utf8.RuneCountInString(field.Value)
		bounded = append(bounded, field)
	}

	return WebhookPayload{
		Username:        "boVIE",
		AllowedMentions: AllowedMentions{Parse: []string{}},
		Embeds: []Embed{
			{
				Title:  offer.Title,
				URL:    offer.URL,
				Color:  341401,
				Fields: bounded,
				Footer: EmbedFooter{Text: footer},
			},
		},
	}
}

func sleepContext(ctx context.Context, d time.Duration) error {
	if d <= 0 {
		return nil
	}
	timer := time.NewTimer(d)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-timer.C:
		return nil
	}
}

func webhookURLWithWait(raw string) (string, error) {
	parsed, err := url.Parse(raw)
	if err != nil {
		return "", fmt.Errorf("invalid webhook url")
	}
	q := parsed.Query()
	q.Set("wait", "true")
	parsed.RawQuery = q.Encode()
	return parsed.String(), nil
}

// DeliverOne claims one pending delivery, posts it to Discord, and completes or reschedules it.
func DeliverOne(
	ctx context.Context,
	store DeliveryStore,
	httpClient *http.Client,
	webhookURL string,
	sleepFn func(context.Context, time.Duration) error,
) (bool, error) {
	if sleepFn == nil {
		sleepFn = sleepContext
	}
	work, err := store.Claim(ctx)
	if err != nil || work == nil {
		return false, err
	}

	event, err := offerevents.ParseOfferEvent(work.Payload)
	if err != nil {
		_, _ = store.RetryLater(ctx, *work, nil)
		return false, err
	}

	body, err := json.Marshal(DiscordPayload(event))
	if err != nil {
		_, _ = store.RetryLater(ctx, *work, nil)
		return false, err
	}

	// wait=true makes Discord confirm the message was saved before it answers.
	target, err := webhookURLWithWait(webhookURL)
	if err != nil {
		_, _ = store.RetryLater(ctx, *work, nil)
		return false, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, target, bytes.NewReader(body))
	if err != nil {
		_, _ = store.RetryLater(ctx, *work, nil)
		return false, err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := httpClient.Do(req)
	if err != nil {
		_, _ = store.RetryLater(ctx, *work, nil)
		return false, err
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode == http.StatusTooManyRequests {
		// Wait as long as Discord asks; sending sooner only extends the limit.
		waitSeconds := 1.0
		if header := resp.Header.Get("Retry-After"); header != "" {
			if parsed, parseErr := strconv.ParseFloat(header, 64); parseErr == nil && parsed >= 0 {
				waitSeconds = parsed
			}
		}
		_, _ = store.RetryLater(ctx, *work, &waitSeconds)
		slog.Warn(fmt.Sprintf("Discord answered HTTP 429; waiting %g s", waitSeconds))
		waitDur := time.Duration(math.Round(waitSeconds * float64(time.Second)))
		if err := sleepFn(ctx, waitDur); err != nil {
			return false, err
		}
		return true, nil
	}

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		// Log only the status: error messages must never expose the webhook URL.
		slog.Warn(fmt.Sprintf("Discord answered HTTP %d", resp.StatusCode))
		_, _ = store.RetryLater(ctx, *work, nil)
		return false, &DiscordStatusError{StatusCode: resp.StatusCode}
	}

	finished, err := store.Finish(ctx, *work)
	if err != nil {
		return false, err
	}
	if !finished {
		slog.Warn("Delivery was sent after its lease expired; Discord may show it twice", "event_id", work.EventID)
	}
	return true, nil
}
