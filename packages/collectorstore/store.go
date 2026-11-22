// Package collectorstore owns published offers, content hashes, sightings, checkpoints, and collector migrations.
package collectorstore

import (
	"context"
	"database/sql"
	_ "embed"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/Reidaa/boVIE/packages/mysqlcommon"
	"github.com/Reidaa/boVIE/packages/offerevents"
)

// MaxSilence is the maximum time a scan may return no results before failing.
// Collectors run every 2 hours, so this is 6 consecutive empty runs.
const MaxSilence = 12 * time.Hour

// ErrSourceSilent indicates the upstream source has returned no results for too long.
var ErrSourceSilent = errors.New("source silent")

// SourceSilentError wraps ErrSourceSilent with diagnostic context.
type SourceSilentError struct {
	Message string
}

func (e *SourceSilentError) Error() string { return e.Message }
func (e *SourceSilentError) Unwrap() error { return ErrSourceSilent }

//go:embed migrations/0001_initial.sql
var migration0001 string

//go:embed migrations/0002_results_seen_at.sql
var migration0002 string

// Migrations lists all collector schema migrations in execution order.
var Migrations = []mysqlcommon.Migration{
	{
		Version:        "0001_initial",
		LegacyRevision: "collector_store_0001",
		SQL:            migration0001,
	},
	{
		Version:        "0002_results_seen_at",
		LegacyRevision: "collector_store_0002",
		SQL:            migration0002,
	},
}

// Store provides collector persistence operations over a MySQL connection pool.
type Store struct {
	DB *sql.DB
}

// New wraps db as a collector Store.
func New(db *sql.DB) *Store {
	return &Store{DB: db}
}

// Upgrade creates the collector database if missing and applies all schema migrations.
func Upgrade(ctx context.Context, cfg *mysqlcommon.Config, db *sql.DB, waitTimeout time.Duration) error {
	return mysqlcommon.UpgradeSchema(ctx, cfg, db, Migrations, waitTimeout)
}

// Seen reports whether sourceOfferID has already been recorded.
func (s *Store) Seen(ctx context.Context, sourceOfferID string) (bool, error) {
	return Seen(ctx, s.DB, sourceOfferID)
}

// RecordPage records published offers, refreshes last_seen_at for observed IDs, and updates the checkpoint atomically.
func (s *Store) RecordPage(ctx context.Context, published []offerevents.OfferEvent, observed []string, scan string, offset int) error {
	return RecordPage(ctx, s.DB, published, observed, scan, offset)
}

// RequireRecentResults returns ErrSourceSilent unless scan returned results within MaxSilence.
func (s *Store) RequireRecentResults(ctx context.Context, scan string) error {
	return RequireRecentResults(ctx, s.DB, scan)
}

// Seen reports whether sourceOfferID has already been recorded in offers.
func Seen(ctx context.Context, db *sql.DB, sourceOfferID string) (bool, error) {
	var exists int
	err := db.QueryRowContext(ctx, "SELECT 1 FROM offers WHERE source_offer_id = ?", sourceOfferID).Scan(&exists)
	if errors.Is(err, sql.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	return true, nil
}

// RecordPage records published offers, refreshes last_seen_at for observed IDs, and updates the checkpoint.
// Call only after the broker has acknowledged every event in published.
func RecordPage(ctx context.Context, db *sql.DB, published []offerevents.OfferEvent, observed []string, scan string, offset int) error {
	now := time.Now().UTC().Truncate(time.Microsecond)
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback() }()

	for _, event := range published {
		payload, err := event.MarshalBytes()
		if err != nil {
			return fmt.Errorf("marshal offer event %s: %w", event.SourceOfferID, err)
		}
		contentHash, err := event.Offer.ContentHash()
		if err != nil {
			return fmt.Errorf("hash offer %s: %w", event.SourceOfferID, err)
		}
		// A concurrent run may have recorded the same offer first; keep its row.
		_, err = tx.ExecContext(
			ctx,
			`INSERT INTO offers (source_offer_id, observed_at, event_id, payload, content_hash, last_seen_at)
			 VALUES (?, ?, ?, ?, ?, ?)
			 ON DUPLICATE KEY UPDATE source_offer_id = source_offer_id`,
			event.SourceOfferID,
			event.ObservedAt.UTC().Truncate(time.Microsecond),
			event.EventID,
			string(payload),
			contentHash,
			now,
		)
		if err != nil {
			return fmt.Errorf("insert offer %s: %w", event.SourceOfferID, err)
		}
	}

	if len(observed) > 0 {
		placeholders := strings.Repeat("?,", len(observed))
		placeholders = placeholders[:len(placeholders)-1]
		args := make([]any, 0, len(observed)+1)
		args = append(args, now)
		for _, id := range observed {
			args = append(args, id)
		}
		query := fmt.Sprintf("UPDATE offers SET last_seen_at = ? WHERE source_offer_id IN (%s)", placeholders)
		if _, err := tx.ExecContext(ctx, query, args...); err != nil {
			return fmt.Errorf("refresh sightings: %w", err)
		}
	}

	if len(observed) > 0 {
		_, err = tx.ExecContext(
			ctx,
			`INSERT INTO checkpoints (scan, offset, results_seen_at)
			 VALUES (?, ?, ?)
			 ON DUPLICATE KEY UPDATE offset = VALUES(offset), results_seen_at = VALUES(results_seen_at)`,
			scan,
			offset,
			now,
		)
	} else {
		_, err = tx.ExecContext(
			ctx,
			`INSERT INTO checkpoints (scan, offset, results_seen_at)
			 VALUES (?, ?, NULL)
			 ON DUPLICATE KEY UPDATE offset = VALUES(offset)`,
			scan,
			offset,
		)
	}
	if err != nil {
		return fmt.Errorf("upsert checkpoint: %w", err)
	}

	return tx.Commit()
}

// RequireRecentResults fails with ErrSourceSilent unless scan returned results within MaxSilence.
func RequireRecentResults(ctx context.Context, db *sql.DB, scan string) error {
	var seenAt sql.NullTime
	err := db.QueryRowContext(ctx, "SELECT results_seen_at FROM checkpoints WHERE scan = ?", scan).Scan(&seenAt)
	if errors.Is(err, sql.ErrNoRows) || (err == nil && !seenAt.Valid) {
		return &SourceSilentError{Message: "The source has not returned any results yet"}
	}
	if err != nil {
		return err
	}
	if time.Since(seenAt.Time.UTC()) > MaxSilence {
		return &SourceSilentError{
			Message: fmt.Sprintf("The source has returned no results since %s", seenAt.Time.UTC().Format(time.RFC3339)),
		}
	}
	return nil
}
