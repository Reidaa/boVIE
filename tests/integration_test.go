package tests

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/Reidaa/boVIE/packages/collectorstore"
	"github.com/Reidaa/boVIE/packages/discordstore"
	"github.com/Reidaa/boVIE/packages/mysqlcommon"
	"github.com/Reidaa/boVIE/packages/natsclient"
	"github.com/Reidaa/boVIE/packages/offerevents"
	"github.com/google/uuid"
	"github.com/nats-io/nats.go"
	"github.com/nats-io/nats.go/jetstream"
)

func mysqlAdmin(t *testing.T) (*mysqlcommon.Config, *sql.DB) {
	t.Helper()
	raw := os.Getenv("MYSQL_TEST_ADMIN_URL")
	if raw == "" {
		t.Skip("Set MYSQL_TEST_ADMIN_URL to a disposable MySQL server")
	}
	cfg, err := mysqlcommon.ParseDatabaseURL(raw)
	if err != nil {
		t.Fatalf("parse MYSQL_TEST_ADMIN_URL: %v", err)
	}
	db, err := mysqlcommon.OpenDB(cfg)
	if err != nil {
		t.Fatalf("open admin db: %v", err)
	}
	t.Cleanup(func() { _ = db.Close() })
	return cfg, db
}

func createTestDB(t *testing.T, adminCfg *mysqlcommon.Config, adminDB *sql.DB, domain string) (*mysqlcommon.Config, *sql.DB) {
	t.Helper()
	ctx := context.Background()
	name := "bovie_test_" + strings.ReplaceAll(uuid.NewString(), "-", "")
	if _, err := adminDB.ExecContext(ctx, fmt.Sprintf("CREATE DATABASE %s CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin", mysqlcommon.QuoteIdentifier(name))); err != nil {
		t.Fatalf("create test db: %v", err)
	}
	cfg := adminCfg.WithDatabase(name)
	db, err := mysqlcommon.OpenDB(cfg)
	if err != nil {
		t.Fatalf("open test db: %v", err)
	}
	t.Cleanup(func() {
		_ = db.Close()
		_, _ = adminDB.ExecContext(context.Background(), "DROP DATABASE IF EXISTS "+mysqlcommon.QuoteIdentifier(name))
	})

	switch domain {
	case "collector":
		if err := collectorstore.Upgrade(ctx, cfg, db, 0); err != nil {
			t.Fatalf("upgrade collector db: %v", err)
		}
	case "discord":
		if err := discordstore.Upgrade(ctx, cfg, db, 0); err != nil {
			t.Fatalf("upgrade discord db: %v", err)
		}
	default:
		t.Fatalf("unknown domain %q", domain)
	}
	return cfg, db
}

func makeEvent(t *testing.T, offerID string, eventType offerevents.EventType, source offerevents.Source) offerevents.OfferEvent {
	t.Helper()
	ev, err := offerevents.NewOfferEvent(
		eventType,
		source,
		offerID,
		offerevents.OfferDetails{
			Title:        "Engineer",
			Organization: "Example",
			Country:      "France",
			City:         "Paris",
			URL:          "https://example.com/jobs/" + offerID,
		},
	)
	if err != nil {
		t.Fatalf("NewOfferEvent: %v", err)
	}
	return ev
}

func TestMigrationCreatesMissingDatabaseAndSupportsExistingAlembicSchema(t *testing.T) {
	adminCfg, adminDB := mysqlAdmin(t)
	ctx := context.Background()

	// Hyphenated name proves identifier quoting in CREATE DATABASE.
	name := "bovie-test-" + strings.ReplaceAll(uuid.NewString(), "-", "")
	t.Cleanup(func() {
		_, _ = adminDB.ExecContext(context.Background(), "DROP DATABASE IF EXISTS "+mysqlcommon.QuoteIdentifier(name))
	})

	cfg := adminCfg.WithDatabase(name)
	db, err := mysqlcommon.OpenDB(cfg)
	if err != nil {
		t.Fatal(err)
	}
	defer func() { _ = db.Close() }()

	start := time.Now()
	if err := collectorstore.Upgrade(ctx, cfg, db, 20*time.Second); err != nil {
		t.Fatalf("Upgrade missing DB: %v", err)
	}
	if time.Since(start) >= 20*time.Second {
		t.Fatalf("Upgrade took too long: %v", time.Since(start))
	}

	var charset, collation string
	if err := adminDB.QueryRowContext(
		ctx,
		"SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = ?",
		name,
	).Scan(&charset, &collation); err != nil {
		t.Fatalf("query schemata: %v", err)
	}
	if charset != "utf8mb4" || collation != "utf8mb4_0900_bin" {
		t.Fatalf("charset=%q collation=%q", charset, collation)
	}

	var count int
	if err := adminDB.QueryRowContext(ctx, fmt.Sprintf("SELECT COUNT(*) FROM %s.offers", mysqlcommon.QuoteIdentifier(name))).Scan(&count); err != nil {
		t.Fatalf("query offers: %v", err)
	}
	if count != 0 {
		t.Fatalf("offers count = %d", count)
	}

	// Simulate an existing Alembic-migrated production database and verify Go upgrade is idempotent.
	alembicName := "bovie_alembic_" + strings.ReplaceAll(uuid.NewString(), "-", "")
	t.Cleanup(func() {
		_, _ = adminDB.ExecContext(context.Background(), "DROP DATABASE IF EXISTS "+mysqlcommon.QuoteIdentifier(alembicName))
	})
	if _, err := adminDB.ExecContext(ctx, fmt.Sprintf("CREATE DATABASE %s CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin", mysqlcommon.QuoteIdentifier(alembicName))); err != nil {
		t.Fatal(err)
	}
	alembicCfg := adminCfg.WithDatabase(alembicName)
	alembicDB, err := mysqlcommon.OpenDB(alembicCfg)
	if err != nil {
		t.Fatal(err)
	}
	defer func() { _ = alembicDB.Close() }()
	// Apply 0001 SQL manually and record alembic_version = collector_store_0001.
	for _, stmt := range strings.Split(collectorstore.Migrations[0].SQL, ";") {
		if strings.TrimSpace(stmt) != "" {
			if _, err := alembicDB.ExecContext(ctx, stmt); err != nil {
				t.Fatal(err)
			}
		}
	}
	if _, err := alembicDB.ExecContext(ctx, "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"); err != nil {
		t.Fatal(err)
	}
	if _, err := alembicDB.ExecContext(ctx, "INSERT INTO alembic_version (version_num) VALUES ('collector_store_0001')"); err != nil {
		t.Fatal(err)
	}

	// Go upgrade should skip 0001 (already in alembic_version) and apply 0002 (results_seen_at).
	if err := collectorstore.Upgrade(ctx, alembicCfg, alembicDB, 0); err != nil {
		t.Fatalf("Upgrade from alembic_version failed: %v", err)
	}
	// Running Upgrade a second time is a no-op.
	if err := collectorstore.Upgrade(ctx, alembicCfg, alembicDB, 0); err != nil {
		t.Fatalf("Idempotent second Upgrade failed: %v", err)
	}
	// Confirm results_seen_at column now exists.
	var colCount int
	if err := alembicDB.QueryRowContext(
		ctx,
		"SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = ? AND TABLE_NAME = 'checkpoints' AND COLUMN_NAME = 'results_seen_at'",
		alembicName,
	).Scan(&colCount); err != nil || colCount != 1 {
		t.Fatalf("expected results_seen_at column, count=%d err=%v", colCount, err)
	}
}

func TestCollectorStoreSightingsCaseSensitivityAndConcurrency(t *testing.T) {
	adminCfg, adminDB := mysqlAdmin(t)
	_, db := createTestDB(t, adminCfg, adminDB, "collector")
	ctx := context.Background()

	discovered := makeEvent(t, "ABC", offerevents.EventDiscovered, offerevents.SourceBusinessFrance)
	lower := makeEvent(t, "abc", offerevents.EventDiscovered, offerevents.SourceBusinessFrance)

	if err := collectorstore.RecordPage(ctx, db, []offerevents.OfferEvent{discovered}, []string{"ABC"}, "scan", 1); err != nil {
		t.Fatalf("RecordPage 1: %v", err)
	}
	if err := collectorstore.RecordPage(ctx, db, []offerevents.OfferEvent{discovered, lower}, []string{"ABC", "abc"}, "scan", 2); err != nil {
		t.Fatalf("RecordPage 2: %v", err)
	}

	seenUpper, err := collectorstore.Seen(ctx, db, "ABC")
	if err != nil || !seenUpper {
		t.Fatalf("Seen(ABC) = %v, %v", seenUpper, err)
	}
	seenLower, err := collectorstore.Seen(ctx, db, "abc")
	if err != nil || !seenLower {
		t.Fatalf("Seen(abc) = %v, %v", seenLower, err)
	}

	var count int
	if err := db.QueryRowContext(ctx, "SELECT COUNT(*) FROM offers").Scan(&count); err != nil || count != 2 {
		t.Fatalf("offers count = %d, err = %v", count, err)
	}

	var eventID, contentHash string
	var observedAt, firstSighting time.Time
	if err := db.QueryRowContext(
		ctx,
		"SELECT event_id, content_hash, observed_at, last_seen_at FROM offers WHERE source_offer_id = 'ABC'",
	).Scan(&eventID, &contentHash, &observedAt, &firstSighting); err != nil {
		t.Fatal(err)
	}
	wantHash, _ := discovered.Offer.ContentHash()
	if eventID != discovered.EventID || contentHash != wantHash || !observedAt.Equal(discovered.ObservedAt) {
		t.Fatalf("row mismatch: eventID=%s hash=%s obs=%v", eventID, contentHash, observedAt)
	}

	time.Sleep(5 * time.Millisecond)
	if err := collectorstore.RecordPage(ctx, db, nil, []string{"ABC", "unrecorded"}, "scan", 3); err != nil {
		t.Fatalf("RecordPage 3: %v", err)
	}
	var secondSighting time.Time
	if err := db.QueryRowContext(ctx, "SELECT last_seen_at FROM offers WHERE source_offer_id = 'ABC'").Scan(&secondSighting); err != nil {
		t.Fatal(err)
	}
	if !secondSighting.After(firstSighting) {
		t.Fatalf("last_seen_at did not advance: %v vs %v", secondSighting, firstSighting)
	}
	if seenUnrec, _ := collectorstore.Seen(ctx, db, "unrecorded"); seenUnrec {
		t.Fatal("unrecorded offer should not be inserted by observed refresh")
	}

	// Concurrent RecordPage keeps one offer.
	_, concDB := createTestDB(t, adminCfg, adminDB, "collector")
	var wg sync.WaitGroup
	errs := make(chan error, 4)
	for range 4 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			errs <- collectorstore.RecordPage(ctx, concDB, []offerevents.OfferEvent{discovered}, []string{"ABC"}, "scan", 1)
		}()
	}
	wg.Wait()
	close(errs)
	for err := range errs {
		if err != nil {
			t.Fatalf("concurrent RecordPage: %v", err)
		}
	}
	if err := concDB.QueryRowContext(ctx, "SELECT COUNT(*) FROM offers").Scan(&count); err != nil || count != 1 {
		t.Fatalf("concurrent offers count = %d, err = %v", count, err)
	}
}

func TestDomainCredentialsCannotAccessOtherDomains(t *testing.T) {
	adminCfg, adminDB := mysqlAdmin(t)
	ctx := context.Background()

	type domainInfo struct {
		cfg   *mysqlcommon.Config
		table string
	}
	cfg0, _ := createTestDB(t, adminCfg, adminDB, "collector")
	cfg1, _ := createTestDB(t, adminCfg, adminDB, "collector")
	cfg2, _ := createTestDB(t, adminCfg, adminDB, "discord")
	domains := []domainInfo{
		{cfg0, "offers"},
		{cfg1, "offers"},
		{cfg2, "inbox"},
	}

	for owner, own := range domains {
		user := "bovie_test_" + strings.ReplaceAll(uuid.NewString(), "-", "")[:20]
		password := strings.ReplaceAll(uuid.NewString(), "-", "")
		if _, err := adminDB.ExecContext(ctx, fmt.Sprintf("CREATE USER '%s'@'%%' IDENTIFIED BY '%s'", user, password)); err != nil {
			t.Fatalf("create user: %v", err)
		}
		t.Cleanup(func() {
			_, _ = adminDB.ExecContext(context.Background(), fmt.Sprintf("DROP USER IF EXISTS '%s'@'%%'", user))
		})
		if _, err := adminDB.ExecContext(ctx, fmt.Sprintf("GRANT ALL ON %s.* TO '%s'@'%%'", mysqlcommon.QuoteIdentifier(own.cfg.Database()), user)); err != nil {
			t.Fatalf("grant: %v", err)
		}

		restricted, err := mysqlcommon.OpenDB(own.cfg.WithCredentials(user, password))
		if err != nil {
			t.Fatal(err)
		}
		defer func() { _ = restricted.Close() }()

		var cnt int
		if err := restricted.QueryRowContext(ctx, "SELECT COUNT(*) FROM "+own.table).Scan(&cnt); err != nil {
			t.Fatalf("owner %d own table select failed: %v", owner, err)
		}
		for idx, other := range domains {
			if idx == owner {
				continue
			}
			var dummy int
			err := restricted.QueryRowContext(
				ctx,
				fmt.Sprintf("SELECT COUNT(*) FROM %s.%s", mysqlcommon.QuoteIdentifier(other.cfg.Database()), other.table),
			).Scan(&dummy)
			if err == nil {
				t.Fatalf("owner %d unexpectedly read domain %d", owner, idx)
			}
		}
	}
}

func TestDiscordStoreInboxDedupAndQueueLeases(t *testing.T) {
	adminCfg, adminDB := mysqlAdmin(t)
	_, db := createTestDB(t, adminCfg, adminDB, "discord")
	ctx := context.Background()

	discovered := makeEvent(t, "ABC", offerevents.EventDiscovered, offerevents.SourceBusinessFrance)
	queued, err := discordstore.Accept(ctx, db, discovered)
	if err != nil || !queued {
		t.Fatalf("first Accept = (%v, %v)", queued, err)
	}
	queued, err = discordstore.Accept(ctx, db, discovered)
	if err != nil || queued {
		t.Fatalf("duplicate Accept = (%v, %v)", queued, err)
	}

	// Republished with later observed_at is accepted once.
	repub := discovered
	repub.ObservedAt = time.Now().UTC().Add(2 * time.Hour).Truncate(time.Microsecond)
	queued, err = discordstore.Accept(ctx, db, repub)
	if err != nil || queued {
		t.Fatalf("republished Accept = (%v, %v)", queued, err)
	}

	// Reused event ID for a different offer is rejected.
	collision := discovered
	collision.SourceOfferID = "other"
	if _, err := discordstore.Accept(ctx, db, collision); err == nil || !strings.Contains(err.Error(), "different offer") {
		t.Fatalf("expected collision error, got %v", err)
	}

	// Only discoveries create deliveries.
	if q, err := discordstore.Accept(ctx, db, makeEvent(t, "ABC", offerevents.EventUpdated, offerevents.SourceBusinessFrance)); err != nil || q {
		t.Fatalf("updated Accept = (%v, %v)", q, err)
	}
	if q, err := discordstore.Accept(ctx, db, makeEvent(t, "ABC", offerevents.EventClosed, offerevents.SourceBusinessFrance)); err != nil || q {
		t.Fatalf("closed Accept = (%v, %v)", q, err)
	}

	var inboxCount, delivCount int
	_ = db.QueryRowContext(ctx, "SELECT COUNT(*) FROM inbox").Scan(&inboxCount)
	_ = db.QueryRowContext(ctx, "SELECT COUNT(*) FROM deliveries").Scan(&delivCount)
	if inboxCount != 3 || delivCount != 1 {
		t.Fatalf("inbox=%d deliveries=%d, want 3 and 1", inboxCount, delivCount)
	}

	// Lease expiry and stale completion.
	now := time.Now().UTC().Add(time.Second).Truncate(time.Microsecond)
	first, err := discordstore.ClaimDelivery(ctx, db, &now, 10)
	if err != nil || first == nil {
		t.Fatalf("first claim = (%v, %v)", first, err)
	}
	if again, err := discordstore.ClaimDelivery(ctx, db, &now, 10); err != nil || again != nil {
		t.Fatalf("expected nil while leased, got (%v, %v)", again, err)
	}
	later := now.Add(11 * time.Second)
	second, err := discordstore.ClaimDelivery(ctx, db, &later, 120)
	if err != nil || second == nil || second.Token == first.Token {
		t.Fatalf("second claim = (%+v, %v)", second, err)
	}
	if ok, err := discordstore.FinishDelivery(ctx, db, *first, &later); err != nil || ok {
		t.Fatalf("stale finish should fail, got (%v, %v)", ok, err)
	}
	if ok, err := discordstore.FinishDelivery(ctx, db, *second, &later); err != nil || !ok {
		t.Fatalf("valid finish failed: (%v, %v)", ok, err)
	}
	if none, err := discordstore.ClaimDelivery(ctx, db, &later, 120); err != nil || none != nil {
		t.Fatalf("expected empty queue after finish, got (%v, %v)", none, err)
	}

	// Failed delivery retry backoff.
	_, retryDB := createTestDB(t, adminCfg, adminDB, "discord")
	if _, err := discordstore.Accept(ctx, retryDB, discovered); err != nil {
		t.Fatal(err)
	}
	c1, err := discordstore.ClaimDelivery(ctx, retryDB, &now, 120)
	if err != nil || c1 == nil {
		t.Fatal(err)
	}
	if ok, err := discordstore.RetryDeliveryLater(ctx, retryDB, *c1, &now, nil); err != nil || !ok {
		t.Fatalf("RetryDeliveryLater: (%v, %v)", ok, err)
	}
	if none, _ := discordstore.ClaimDelivery(ctx, retryDB, &now, 120); none != nil {
		t.Fatal("should not be claimable immediately after retry")
	}
	afterBackoff := now.Add(61 * time.Second)
	c2, err := discordstore.ClaimDelivery(ctx, retryDB, &afterBackoff, 120)
	if err != nil || c2 == nil || c2.Attempts != 2 {
		t.Fatalf("expected attempt 2 after backoff, got (%+v, %v)", c2, err)
	}
}

func deleteStreamIfExists(t *testing.T, url string) {
	t.Helper()
	nc, err := nats.Connect(url)
	if err != nil {
		return
	}
	defer nc.Close()
	js, err := jetstream.New(nc)
	if err != nil {
		return
	}
	_ = js.DeleteStream(context.Background(), natsclient.Stream)
}

func TestJetStreamEndToEndAndStreamPreservation(t *testing.T) {
	natsURL := os.Getenv("NATS_TEST_URL")
	if natsURL == "" {
		t.Skip("Set NATS_TEST_URL to a disposable JetStream server")
	}
	adminCfg, adminDB := mysqlAdmin(t)
	_, discordDB := createTestDB(t, adminCfg, adminDB, "discord")

	t.Setenv("NATS_URL", natsURL)
	t.Setenv("NATS_USER", "")
	t.Setenv("NATS_PASSWORD", "")

	deleteStreamIfExists(t, natsURL)
	t.Cleanup(func() { deleteStreamIfExists(t, natsURL) })

	ctx := context.Background()
	pub, err := natsclient.NewPublisher(ctx, 10*time.Second)
	if err != nil {
		t.Fatalf("NewPublisher: %v", err)
	}
	defer pub.Close()

	evBF := makeEvent(t, "bf-1", offerevents.EventDiscovered, offerevents.SourceBusinessFrance)
	evWTTJ := makeEvent(t, "wttj-1", offerevents.EventDiscovered, offerevents.SourceWTTJ)
	if err := pub.Publish(ctx, evBF); err != nil {
		t.Fatalf("publish BF: %v", err)
	}
	if err := pub.Publish(ctx, evWTTJ); err != nil {
		t.Fatalf("publish WTTJ: %v", err)
	}
	// Republish duplicate with same event_id (deduped by Nats-Msg-Id window).
	if err := pub.Publish(ctx, evBF); err != nil {
		t.Fatalf("republish BF: %v", err)
	}

	nc, err := natsclient.Connect()
	if err != nil {
		t.Fatal(err)
	}
	defer nc.Close()
	js, err := jetstream.New(nc)
	if err != nil {
		t.Fatal(err)
	}
	consumer, err := js.CreateConsumer(ctx, natsclient.Stream, jetstream.ConsumerConfig{
		Name:          natsclient.Consumer,
		Durable:       natsclient.Consumer,
		AckPolicy:     jetstream.AckExplicitPolicy,
		AckWait:       500 * time.Millisecond,
		MaxAckPending: 1000,
	})
	if err != nil {
		t.Fatalf("create consumer: %v", err)
	}

	// Fetch max wait must be shorter than AckWait so unacked messages don't redeliver inside the same batch.
	batch, err := consumer.Fetch(3, jetstream.FetchMaxWait(250*time.Millisecond))
	if err != nil {
		t.Fatalf("fetch: %v", err)
	}
	var msgs []jetstream.Msg
	for msg := range batch.Messages() {
		msgs = append(msgs, msg)
	}
	if len(msgs) != 2 {
		t.Fatalf("expected 2 unique messages, got %d", len(msgs))
	}

	// Commit first message to DB but simulate lost ack; ack second normally.
	firstEv, err := offerevents.ParseOfferEvent(msgs[0].Data())
	if err != nil {
		t.Fatal(err)
	}
	if _, err := discordstore.Accept(ctx, discordDB, firstEv); err != nil {
		t.Fatal(err)
	}
	secondEv, err := offerevents.ParseOfferEvent(msgs[1].Data())
	if err != nil {
		t.Fatal(err)
	}
	if _, err := discordstore.Accept(ctx, discordDB, secondEv); err != nil {
		t.Fatal(err)
	}
	if err := msgs[1].DoubleAck(ctx); err != nil {
		t.Fatal(err)
	}

	// First message redelivers after AckWait; inbox dedups it safely.
	replayBatch, err := consumer.Fetch(1, jetstream.FetchMaxWait(2*time.Second))
	if err != nil {
		t.Fatalf("fetch replay: %v", err)
	}
	var replayed []jetstream.Msg
	for m := range replayBatch.Messages() {
		replayed = append(replayed, m)
	}
	if len(replayed) != 1 || string(replayed[0].Data()) != string(msgs[0].Data()) {
		t.Fatalf("expected redelivery of first message")
	}
	if queued, err := discordstore.Accept(ctx, discordDB, firstEv); err != nil || queued {
		t.Fatalf("redelivered message should dedup, got (%v, %v)", queued, err)
	}
	if err := replayed[0].DoubleAck(ctx); err != nil {
		t.Fatal(err)
	}

	// Acknowledged messages stay in OFFERS stream (LimitsPolicy).
	stream, err := js.Stream(ctx, natsclient.Stream)
	if err != nil {
		t.Fatal(err)
	}
	info, err := stream.Info(ctx)
	if err != nil {
		t.Fatal(err)
	}
	if info.State.Msgs != 2 {
		t.Fatalf("stream msgs = %d, want 2", info.State.Msgs)
	}

	var delivCount int
	if err := discordDB.QueryRowContext(ctx, "SELECT COUNT(*) FROM deliveries").Scan(&delivCount); err != nil || delivCount != 2 {
		t.Fatalf("deliveries = %d, err = %v", delivCount, err)
	}

	// Existing stream preserves operator-modified limits.
	deleteStreamIfExists(t, natsURL)
	custom := natsclient.StreamConfig()
	custom.MaxBytes = 1024
	if _, err := js.CreateStream(ctx, custom); err != nil {
		t.Fatal(err)
	}
	if err := natsclient.EnsureStream(ctx, js); err != nil {
		t.Fatalf("EnsureStream on existing custom stream: %v", err)
	}
	stream2, err := js.Stream(ctx, natsclient.Stream)
	if err != nil {
		t.Fatal(err)
	}
	info2, err := stream2.Info(ctx)
	if err != nil {
		t.Fatal(err)
	}
	if info2.Config.MaxBytes != 1024 {
		t.Fatalf("EnsureStream overwrote max_bytes: got %d, want 1024", info2.Config.MaxBytes)
	}
}

func TestDeploymentNATSPermissions(t *testing.T) {
	authURL := os.Getenv("NATS_AUTH_TEST_URL")
	if authURL == "" {
		t.Skip("Set NATS_AUTH_TEST_URL to a disposable broker using deploy/nats.conf")
	}

	passwords := map[string]string{
		"nats-setup":                "local-nats-setup",
		"collector-business-france": "local-nats-collector-business-france",
		"collector-wttj":            "local-nats-collector-wttj",
		"collector-workday":         "local-nats-collector-workday",
		"discord-intake":            "local-nats-discord-intake",
	}

	connectAs := func(user string) *nats.Conn {
		t.Setenv("NATS_URL", authURL)
		t.Setenv("NATS_USER", user)
		t.Setenv("NATS_PASSWORD", passwords[user])
		nc, err := natsclient.Connect()
		if err != nil {
			t.Fatalf("connect as %s: %v", user, err)
		}
		t.Cleanup(nc.Close)
		return nc
	}

	t.Cleanup(func() {
		t.Setenv("NATS_URL", authURL)
		t.Setenv("NATS_USER", "nats-setup")
		t.Setenv("NATS_PASSWORD", passwords["nats-setup"])
		nc, err := natsclient.Connect()
		if err != nil {
			return
		}
		defer nc.Close()
		if js, err := jetstream.New(nc); err == nil {
			_ = js.DeleteStream(context.Background(), natsclient.Stream)
		}
	})

	ctx := context.Background()
	collectors := []struct {
		source offerevents.Source
		user   string
	}{
		{offerevents.SourceBusinessFrance, "collector-business-france"},
		{offerevents.SourceWTTJ, "collector-wttj"},
		{offerevents.SourceWorkday, "collector-workday"},
	}

	for _, c := range collectors {
		nc := connectAs(c.user)
		js, err := jetstream.New(nc)
		if err != nil {
			t.Fatalf("%s jetstream: %v", c.user, err)
		}
		if err := natsclient.EnsureStream(ctx, js); err != nil {
			t.Fatalf("%s EnsureStream: %v", c.user, err)
		}
		ev := makeEvent(t, "perm-"+string(c.source), offerevents.EventDiscovered, c.source)
		raw, _ := ev.MarshalBytes()
		if _, err := js.Publish(ctx, natsclient.Subject(c.source), raw); err != nil {
			t.Fatalf("%s publish: %v", c.user, err)
		}
	}

	intakeNC := connectAs("discord-intake")
	intakeJS, err := jetstream.New(intakeNC)
	if err != nil {
		t.Fatal(err)
	}
	consumer, err := intakeJS.CreateConsumer(ctx, natsclient.Stream, jetstream.ConsumerConfig{
		Name:          natsclient.Consumer,
		Durable:       natsclient.Consumer,
		AckPolicy:     jetstream.AckExplicitPolicy,
		AckWait:       120 * time.Second,
		MaxAckPending: 1000,
	})
	if err != nil {
		t.Fatalf("discord-intake CreateConsumer: %v", err)
	}
	batch, err := consumer.Fetch(3, jetstream.FetchMaxWait(2*time.Second))
	if err != nil {
		t.Fatalf("discord-intake Fetch: %v", err)
	}
	acked := 0
	for msg := range batch.Messages() {
		if err := msg.DoubleAck(ctx); err != nil {
			t.Fatalf("DoubleAck: %v", err)
		}
		acked++
	}
	if acked != 3 {
		t.Fatalf("expected 3 acked messages, got %d", acked)
	}

	// Verify permission violations for unauthorized subjects.
	denied := map[string][]string{
		"collector-business-france": {
			"offers.wttj.v1",
			"_INBOX.discord-intake.>",
			"$JS.API.STREAM.UPDATE.OFFERS",
			"$JS.API.STREAM.DELETE.OFFERS",
			"$JS.API.STREAM.CREATE.OTHER",
		},
		"discord-intake": {
			"$JS.API.CONSUMER.CREATE.OFFERS.other",
			"$JS.API.CONSUMER.DELETE.OFFERS.discord-intake",
		},
	}

	for user, subjects := range denied {
		errCh := make(chan string, len(subjects)*2)
		nc, err := nats.Connect(
			authURL,
			nats.UserInfo(user, passwords[user]),
			nats.ErrorHandler(func(_ *nats.Conn, _ *nats.Subscription, err error) {
				errCh <- strings.ToLower(err.Error())
			}),
		)
		if err != nil {
			t.Fatalf("connect denied test %s: %v", user, err)
		}
		defer nc.Close()

		for _, subj := range subjects {
			if strings.HasPrefix(subj, "_INBOX.") {
				_, _ = nc.Subscribe(subj, func(_ *nats.Msg) {})
			} else {
				_ = nc.Publish(subj, []byte("not permitted"))
			}
		}
		_ = nc.Flush()

		var violations []string
		deadline := time.After(3 * time.Second)
		for len(violations) < len(subjects) {
			select {
			case msg := <-errCh:
				violations = append(violations, msg)
			case <-deadline:
				t.Fatalf("user %s timed out waiting for %d violations, got %v", user, len(subjects), violations)
			}
		}
		for _, subj := range subjects {
			needle := fmt.Sprintf("%q", strings.ToLower(subj))
			found := false
			for _, v := range violations {
				if strings.Contains(v, needle) {
					found = true
					break
				}
			}
			if !found {
				t.Fatalf("user %s missing violation for %s in %v", user, subj, violations)
			}
		}
	}
}

func TestOfferEventJSONRoundTripErrorCheck(t *testing.T) {
	ev := makeEvent(t, "1", offerevents.EventDiscovered, offerevents.SourceWTTJ)
	raw, err := ev.MarshalBytes()
	if err != nil {
		t.Fatal(err)
	}
	var m map[string]any
	if err := json.Unmarshal(raw, &m); err != nil {
		t.Fatal(err)
	}
	if _, err := offerevents.ParseOfferEvent(raw); err != nil {
		t.Fatalf("round-trip failed: %v", err)
	}
	if errors.Is(err, collectorstore.ErrSourceSilent) {
		t.Fatal("unexpected ErrSourceSilent")
	}
}
