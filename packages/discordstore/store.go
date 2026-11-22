// Package discordstore owns the Discord inbox, retryable deliveries queue, and Discord schema migrations.
package discordstore

import (
	"context"
	"database/sql"
	_ "embed"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/Reidaa/boVIE/packages/mysqlcommon"
	"github.com/Reidaa/boVIE/packages/offerevents"
)

// DeliveriesTable is the queue table name for pending Discord webhook deliveries.
const DeliveriesTable = "deliveries"

//go:embed migrations/0001_initial.sql
var migration0001 string

// Migrations lists all Discord schema migrations in execution order.
var Migrations = []mysqlcommon.Migration{
	{
		Version:        "0001_initial",
		LegacyRevision: "discord_store_0001",
		SQL:            migration0001,
	},
}

// Upgrade creates the discord database if missing and applies all schema migrations.
func Upgrade(ctx context.Context, cfg *mysqlcommon.Config, db *sql.DB, waitTimeout time.Duration) error {
	return mysqlcommon.UpgradeSchema(ctx, cfg, db, Migrations, waitTimeout)
}

type offerIdentity struct {
	Source        offerevents.Source    `json:"source"`
	SourceOfferID string                `json:"source_offer_id"`
	Type          offerevents.EventType `json:"type"`
}

// Accept stores the event once in inbox and queues a Discord delivery for new discoveries.
// A republished event keeps its ID but can carry a later observed_at, so duplicates are
// matched on offer identity rather than the whole payload.
func Accept(ctx context.Context, db *sql.DB, event offerevents.OfferEvent) (bool, error) {
	payload, err := event.MarshalBytes()
	if err != nil {
		return false, fmt.Errorf("marshal offer event: %w", err)
	}
	now := time.Now().UTC().Truncate(time.Microsecond)

	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return false, err
	}
	defer func() { _ = tx.Rollback() }()

	_, err = tx.ExecContext(
		ctx,
		`INSERT INTO inbox (event_id, payload, received_at)
		 VALUES (?, ?, ?)
		 ON DUPLICATE KEY UPDATE event_id = VALUES(event_id)`,
		event.EventID,
		string(payload),
		now,
	)
	if err != nil {
		return false, fmt.Errorf("insert inbox: %w", err)
	}

	var savedPayload []byte
	if err := tx.QueryRowContext(ctx, "SELECT payload FROM inbox WHERE event_id = ?", event.EventID).Scan(&savedPayload); err != nil {
		return false, fmt.Errorf("read inbox: %w", err)
	}
	var savedID offerIdentity
	if err := json.Unmarshal(savedPayload, &savedID); err != nil {
		return false, fmt.Errorf("decode inbox payload: %w", err)
	}
	expectedID := offerIdentity{
		Source:        event.Source,
		SourceOfferID: event.SourceOfferID,
		Type:          event.Type,
	}
	if savedID != expectedID {
		return false, errors.New("event ID already belongs to a different offer")
	}

	if event.Type != offerevents.EventDiscovered {
		if err := tx.Commit(); err != nil {
			return false, err
		}
		return false, nil
	}

	var exists int
	err = tx.QueryRowContext(ctx, "SELECT 1 FROM deliveries WHERE event_id = ?", event.EventID).Scan(&exists)
	if err == nil {
		if err := tx.Commit(); err != nil {
			return false, err
		}
		return false, nil
	}
	if !errors.Is(err, sql.ErrNoRows) {
		return false, fmt.Errorf("check delivery: %w", err)
	}

	_, err = tx.ExecContext(
		ctx,
		`INSERT INTO deliveries (event_id, payload, attempts, available_at)
		 VALUES (?, ?, 0, ?)`,
		event.EventID,
		string(payload),
		now,
	)
	if err != nil {
		return false, fmt.Errorf("insert delivery: %w", err)
	}
	if err := tx.Commit(); err != nil {
		return false, err
	}
	return true, nil
}

// ClaimDelivery leases the next eligible Discord delivery.
func ClaimDelivery(ctx context.Context, db *sql.DB, now *time.Time, leaseSeconds int) (*mysqlcommon.Claim, error) {
	return mysqlcommon.ClaimNext(ctx, db, DeliveriesTable, now, leaseSeconds)
}

// FinishDelivery marks a leased delivery complete.
func FinishDelivery(ctx context.Context, db *sql.DB, work mysqlcommon.Claim, now *time.Time) (bool, error) {
	return mysqlcommon.Finish(ctx, db, DeliveriesTable, work, now)
}

// RetryDeliveryLater releases a leased delivery and schedules its next attempt.
func RetryDeliveryLater(ctx context.Context, db *sql.DB, work mysqlcommon.Claim, now *time.Time, delaySeconds *float64) (bool, error) {
	return mysqlcommon.RetryLater(ctx, db, DeliveriesTable, work, now, delaySeconds)
}
