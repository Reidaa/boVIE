# 2. An offers catalog with exact-match duplicate groups and a private API

## Status

Accepted

## Context

ADR 0001 adds an offers catalog: a new `OFFERS` subscriber that owns one database of offers from
all sources, removes duplicates and serves a job-browsing webapp. It leaves four questions open:
who uses the webapp, when two offers are the same offer, what a closed offer shows, and how the
webapp and the catalog are deployed.

Facts that limit the answers:

- `OfferEvent` v1 has no structured contract type or posting date. `country` is a name from
  Business France (`CANADA`) and a code from WTTJ (`FR`).
- Collectors publish only `discovered` today. They store `last_seen_at` for each offer.
- Job boards merge copies of one job into one listing with several "Apply on" links (Google for
  Jobs). They keep the page of a closed job and remove it from search results (LinkedIn, Indeed).

[The design doc](../offers-catalog.md) has the pages, filters, data model and build layers.

## Decision

We will build the catalog as two processes that share the `catalog` database: `catalog-intake`
reads `OFFERS`, and `catalog-api` serves HTTP. This is the pattern of `discord-intake` and
`discord-sender`. The webapp is a separate service with server-rendered Astro pages.

We will follow these rules:

- **No user accounts.** The webapp is anonymous and read-only. Discord already sends alerts.
  With no user data, the catalog stays separate from a future Discord bot. Saved searches or
  alerts in the webapp need a new ADR, because ADR 0001 then joins the webapp and the bot into
  one service.
- **Duplicates by exact match only.** Two offers from different sources are one duplicate group
  when their normalized company, title, country code and city are equal. The webapp shows one
  listing per group, with one "Apply on" link per source. Offers from the same source are never
  merged. A wrong merge hides a real offer. A missed merge only shows a duplicate.
- **Group at read time.** The catalog keeps one row per `(source, source_offer_id)` and never
  deletes it. Each row stores its `group_key`. A change to the rule recomputes `group_key`. It
  does not need a replay of the stream.
- **Closed offers keep their page.** A `closed` event hides the offer from the list. Its detail
  page still answers, shows "No longer accepting applications" and is not indexed. A group is
  closed when all its sources are closed. The catalog ignores an event that is older than the
  stored `observed_at`.
- **A private API.** Only the webapp is public. `catalog-api` listens on the private network,
  so it needs no authentication, CORS or rate limits.

Alternatives considered:

| Option | Why not |
| --- | --- |
| Fuzzy duplicate matching (similar titles, nearby cities) | Wrong merges are silent and hide offers. Revisit with real duplicate data. |
| Merge duplicates on write into one row | A wrong merge loses the source row. A rule change needs a full replay. |
| A public API and a client-side webapp | Needs authentication or rate limits, CORS, and JavaScript to show any page. |
| Pages rendered by `catalog-api` | Joins the user interface and the data into one deploy. ADR 0001 keeps the webapp a caller of the catalog. |

## Consequences

Good:

- The catalog ships without a change to the collectors or the Discord services.
- A wrong duplicate group is fixed by a new rule and a recompute, with no data loss.
- Every search is a URL, so it can be shared and works without JavaScript.

Bad:

- Three new deployables on Railway (`catalog-intake`, `catalog-api` and the webapp) and one
  new database (`mysql-catalog`).
- The repository gets its first Node service. CI must build and test it.
- Few offers close until collectors publish `closed`. The list defaults to offers first seen in
  the last 30 days.
- A contract filter waits for a structured field in `OfferEvent`.

## Compliance

- `tests/test_architecture.py` covers the catalog packages like the other services.
- `tests/test_nats_permissions.py` limits the `catalog-intake` NATS user to its own consumer.
- Catalog tests check the duplicate rule: equal offers from two sources form one group, and equal
  offers from one source do not.
- Railway gives `catalog-api` no public domain. A manual review checks this for each new service.

## Notes

Author: Thomas KEMKEMIAN
Approved: Thomas KEMKEMIAN, 2026-10-28
Last Updated: 2026-10-28
