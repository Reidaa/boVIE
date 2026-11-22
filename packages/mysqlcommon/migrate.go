package mysqlcommon

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"log/slog"
	"strings"
	"time"

	"github.com/go-sql-driver/mysql"
)

// UnknownDatabaseCode is MySQL error 1049: the server answered, so it is ready,
// but the requested database does not exist yet.
const UnknownDatabaseCode uint16 = 1049

// Migration describes one forward-only SQL schema migration.
type Migration struct {
	Version        string
	LegacyRevision string
	SQL            string
}

// Pinger abstracts database readiness checks for testing.
type Pinger interface {
	PingContext(ctx context.Context) error
}

// IsUnknownDatabase reports whether err is MySQL error 1049 (Unknown database).
func IsUnknownDatabase(err error) bool {
	var mysqlErr *mysql.MySQLError
	return errors.As(err, &mysqlErr) && mysqlErr.Number == UnknownDatabaseCode
}

// QuoteIdentifier quotes a MySQL identifier safely using backticks.
func QuoteIdentifier(name string) string {
	return "`" + strings.ReplaceAll(name, "`", "``") + "`"
}

// WaitForDatabase retries PingContext until the server answers or timeout elapses.
// MySQL error 1049 (Unknown database) is returned immediately because the server is up.
func WaitForDatabase(ctx context.Context, pinger Pinger, timeout time.Duration) error {
	return waitForDatabaseWithClock(ctx, pinger, timeout, time.Now, sleepWithContext)
}

func waitForDatabaseWithClock(
	ctx context.Context,
	pinger Pinger,
	timeout time.Duration,
	now func() time.Time,
	sleep func(context.Context, time.Duration) error,
) error {
	deadline := now().Add(timeout)
	for {
		err := pinger.PingContext(ctx)
		if err == nil {
			return nil
		}
		if IsUnknownDatabase(err) {
			return err
		}
		remaining := deadline.Sub(now())
		if remaining <= 0 {
			return err
		}
		wait := min(2*time.Second, remaining)
		if sleepErr := sleep(ctx, wait); sleepErr != nil {
			return sleepErr
		}
	}
}

func sleepWithContext(ctx context.Context, d time.Duration) error {
	timer := time.NewTimer(d)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-timer.C:
		return nil
	}
}

// CreateDatabase creates the database named in cfg with utf8mb4_0900_bin collation.
func CreateDatabase(ctx context.Context, cfg *Config) error {
	name := cfg.Database()
	if name == "" {
		return errors.New("the database URL names no database")
	}
	serverDB, err := OpenDB(cfg.WithoutDatabase())
	if err != nil {
		return err
	}
	defer func() { _ = serverDB.Close() }()

	query := fmt.Sprintf(
		"CREATE DATABASE IF NOT EXISTS %s CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin",
		QuoteIdentifier(name),
	)
	if _, err := serverDB.ExecContext(ctx, query); err != nil {
		return err
	}
	slog.Info("Created database", "database", name)
	return nil
}

// UpgradeSchema ensures the target database exists and applies all pending migrations in order.
// Connection attempts retry up to waitTimeout; migration SQL errors are never retried.
func UpgradeSchema(ctx context.Context, cfg *Config, db *sql.DB, migrations []Migration, waitTimeout time.Duration) error {
	if err := WaitForDatabase(ctx, db, waitTimeout); err != nil {
		if !IsUnknownDatabase(err) {
			return err
		}
		if err := CreateDatabase(ctx, cfg); err != nil {
			return err
		}
		if err := db.PingContext(ctx); err != nil {
			return err
		}
	}
	return applyMigrations(ctx, db, migrations)
}

func applyMigrations(ctx context.Context, db *sql.DB, migrations []Migration) error {
	const createTableSQL = `
CREATE TABLE IF NOT EXISTS schema_migrations (
	version VARCHAR(64) NOT NULL PRIMARY KEY,
	applied_at DATETIME(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin`
	if _, err := db.ExecContext(ctx, createTableSQL); err != nil {
		return fmt.Errorf("create schema_migrations table: %w", err)
	}

	applied, err := loadAppliedVersions(ctx, db)
	if err != nil {
		return err
	}

	// Seamless transition from existing Python Alembic-managed databases:
	// if schema_migrations is empty and alembic_version exists, seed applied revisions.
	if len(applied) == 0 {
		if err := bootstrapFromAlembic(ctx, db, migrations, applied); err != nil {
			return err
		}
	}

	for _, m := range migrations {
		if applied[m.Version] {
			continue
		}
		for _, stmt := range splitSQLStatements(m.SQL) {
			if _, err := db.ExecContext(ctx, stmt); err != nil {
				return fmt.Errorf("migration %s failed: %w", m.Version, err)
			}
		}
		if _, err := db.ExecContext(
			ctx,
			"INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
			m.Version,
			time.Now().UTC().Truncate(time.Microsecond),
		); err != nil {
			return fmt.Errorf("record migration %s: %w", m.Version, err)
		}
		applied[m.Version] = true
	}
	return nil
}

func loadAppliedVersions(ctx context.Context, db *sql.DB) (map[string]bool, error) {
	rows, err := db.QueryContext(ctx, "SELECT version FROM schema_migrations")
	if err != nil {
		return nil, fmt.Errorf("query schema_migrations: %w", err)
	}
	defer func() { _ = rows.Close() }()

	applied := make(map[string]bool)
	for rows.Next() {
		var version string
		if err := rows.Scan(&version); err != nil {
			return nil, err
		}
		applied[version] = true
	}
	return applied, rows.Err()
}

func bootstrapFromAlembic(ctx context.Context, db *sql.DB, migrations []Migration, applied map[string]bool) error {
	var revision string
	err := db.QueryRowContext(ctx, "SELECT version_num FROM alembic_version LIMIT 1").Scan(&revision)
	if err != nil {
		var mysqlErr *mysql.MySQLError
		// Table doesn't exist (1146) or empty table: fresh database, nothing to bootstrap.
		if errors.Is(err, sql.ErrNoRows) || (errors.As(err, &mysqlErr) && mysqlErr.Number == 1146) {
			return nil
		}
		return fmt.Errorf("read alembic_version: %w", err)
	}

	matchIdx := -1
	for i, m := range migrations {
		if m.LegacyRevision != "" && m.LegacyRevision == revision {
			matchIdx = i
			break
		}
	}
	if matchIdx < 0 {
		return fmt.Errorf("unrecognized alembic_version revision %q", revision)
	}
	now := time.Now().UTC().Truncate(time.Microsecond)
	for i := 0; i <= matchIdx; i++ {
		version := migrations[i].Version
		if _, err := db.ExecContext(
			ctx,
			"INSERT IGNORE INTO schema_migrations (version, applied_at) VALUES (?, ?)",
			version,
			now,
		); err != nil {
			return fmt.Errorf("bootstrap migration %s from alembic: %w", version, err)
		}
		applied[version] = true
	}
	return nil
}

func splitSQLStatements(script string) []string {
	parts := strings.Split(script, ";")
	statements := make([]string, 0, len(parts))
	for _, part := range parts {
		trimmed := strings.TrimSpace(part)
		if trimmed != "" {
			statements = append(statements, trimmed)
		}
	}
	return statements
}
