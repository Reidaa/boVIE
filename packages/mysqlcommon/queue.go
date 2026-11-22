package mysqlcommon

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"time"

	"github.com/google/uuid"
)

// Claim represents a leased row from a MySQL-backed work queue.
type Claim struct {
	EventID  string
	Token    string
	Payload  json.RawMessage
	Attempts int
}

// DatabaseNow returns the MySQL server's current UTC timestamp with microsecond precision.
func DatabaseNow(ctx context.Context, tx *sql.Tx) (time.Time, error) {
	var now time.Time
	if err := tx.QueryRowContext(ctx, "SELECT UTC_TIMESTAMP(6)").Scan(&now); err != nil {
		return time.Time{}, err
	}
	return now.UTC(), nil
}

// ClaimNext leases the next eligible work row from table using FOR UPDATE SKIP LOCKED.
// If now is nil, MySQL's UTC_TIMESTAMP(6) governs the lease.
func ClaimNext(ctx context.Context, db *sql.DB, table string, now *time.Time, leaseSeconds int) (*Claim, error) {
	if leaseSeconds <= 0 {
		leaseSeconds = 120
	}
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return nil, err
	}
	defer func() { _ = tx.Rollback() }()

	currentTime, err := resolveNow(ctx, tx, now)
	if err != nil {
		return nil, err
	}

	quoted := QuoteIdentifier(table)
	selectSQL := fmt.Sprintf(`
SELECT event_id, payload, attempts
FROM %s
WHERE completed_at IS NULL
  AND available_at <= ?
  AND (lease_until IS NULL OR lease_until <= ?)
ORDER BY available_at, event_id
LIMIT 1
FOR UPDATE SKIP LOCKED`, quoted)

	var (
		eventID  string
		payload  []byte
		attempts int
	)
	err = tx.QueryRowContext(ctx, selectSQL, currentTime, currentTime).Scan(&eventID, &payload, &attempts)
	if errors.Is(err, sql.ErrNoRows) {
		if err := tx.Commit(); err != nil {
			return nil, err
		}
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	token := uuid.NewString()
	attempts++
	leaseUntil := currentTime.Add(time.Duration(leaseSeconds) * time.Second)

	updateSQL := fmt.Sprintf(`
UPDATE %s
SET claim_token = ?, lease_until = ?, attempts = ?
WHERE event_id = ?`, quoted)
	if _, err := tx.ExecContext(ctx, updateSQL, token, leaseUntil, attempts, eventID); err != nil {
		return nil, err
	}
	if err := tx.Commit(); err != nil {
		return nil, err
	}
	return &Claim{
		EventID:  eventID,
		Token:    token,
		Payload:  json.RawMessage(payload),
		Attempts: attempts,
	}, nil
}

// Finish marks a claimed row complete if the claim token still holds an unexpired lease.
func Finish(ctx context.Context, db *sql.DB, table string, work Claim, now *time.Time) (bool, error) {
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return false, err
	}
	defer func() { _ = tx.Rollback() }()

	currentTime, err := resolveNow(ctx, tx, now)
	if err != nil {
		return false, err
	}

	updateSQL := fmt.Sprintf(`
UPDATE %s
SET completed_at = ?, claim_token = NULL, lease_until = NULL
WHERE event_id = ?
  AND claim_token = ?
  AND completed_at IS NULL
  AND lease_until > ?`, QuoteIdentifier(table))
	res, err := tx.ExecContext(ctx, updateSQL, currentTime, work.EventID, work.Token, currentTime)
	if err != nil {
		return false, err
	}
	affected, err := res.RowsAffected()
	if err != nil {
		return false, err
	}
	if err := tx.Commit(); err != nil {
		return false, err
	}
	return affected == 1, nil
}

// RetryLater releases the claim and schedules the work row for retry after delaySeconds.
// When delaySeconds is nil, backoff doubles from 10s up to 3600s: min(3600, 5 * 2^min(attempts, 10)).
func RetryLater(ctx context.Context, db *sql.DB, table string, work Claim, now *time.Time, delaySeconds *float64) (bool, error) {
	var delay time.Duration
	if delaySeconds != nil {
		delay = time.Duration(math.Round(*delaySeconds * float64(time.Second)))
	} else {
		exp := min(max(work.Attempts, 0), 10)
		secs := min(3600, 5*(1<<exp))
		delay = time.Duration(secs) * time.Second
	}

	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return false, err
	}
	defer func() { _ = tx.Rollback() }()

	currentTime, err := resolveNow(ctx, tx, now)
	if err != nil {
		return false, err
	}

	availableAt := currentTime.Add(delay)
	updateSQL := fmt.Sprintf(`
UPDATE %s
SET available_at = ?, claim_token = NULL, lease_until = NULL
WHERE event_id = ?
  AND claim_token = ?
  AND completed_at IS NULL
  AND lease_until > ?`, QuoteIdentifier(table))
	res, err := tx.ExecContext(ctx, updateSQL, availableAt, work.EventID, work.Token, currentTime)
	if err != nil {
		return false, err
	}
	affected, err := res.RowsAffected()
	if err != nil {
		return false, err
	}
	if err := tx.Commit(); err != nil {
		return false, err
	}
	return affected == 1, nil
}

func resolveNow(ctx context.Context, tx *sql.Tx, override *time.Time) (time.Time, error) {
	if override != nil {
		return override.UTC().Truncate(time.Microsecond), nil
	}
	return DatabaseNow(ctx, tx)
}
