# Offers catalog design

## Status

Accepted. This document answers the "Decisions needed" list of issue #11.
[ADR 0002](adr/0002-offers-catalog-with-a-private-api.md) records the decisions that are hard to reverse.

## Goal

One database of offers from every source, read by a job-browsing webapp. ADR 0001 sets the
frame: the catalog is a new `OFFERS` subscriber with its own durable consumer, database and NATS
user. It owns duplicate removal. The webapp calls it synchronously. Discord delivery does not.

## Facts from the current code

- `OfferEvent` v1 has `title`, `organization`, `country`, `city`, `url`, `observed_at` and free-text
  display `fields`. It has no structured contract type or posting date.
- `country` is not uniform. Business France sends a country name (`CANADA`). WTTJ sends a code (`FR`).
- Collectors publish only `discovered`. The contract already allows `updated` and `closed`.
- Collectors store `last_seen_at` per offer, so they can detect an offer that left the source.

## Decisions

| # | Question | Recommendation | Reason |
| --- | --- | --- | --- |
| 1 | Pages and filters | A list page and a detail page. Filters: text search (title, company), kind (VIE/VIA or job), country, first seen (7 days, 30 days, all). Newest first. No contract filter yet. | These filters use only v1 fields. A contract filter needs a structured field that v1 does not have. |
| 2 | Accounts, saved searches, alerts | None in the MVP. The webapp is anonymous and read-only. | Discord already gives alerts. With no user data, the catalog stays a separate service from a future bot. |
| 3 | Same offer on two sources | Merge only on an exact match of normalized company, title, country and city, across different sources. Show one listing with one "Apply on" link per source. Never merge fuzzy matches. | A wrong merge hides a real offer. A missed merge only shows a duplicate. |
| 4 | `updated` and `closed` | `updated` replaces the stored details. `closed` hides the offer from the list. Its detail page stays and shows "No longer accepting applications". Ignore events older than the stored `observed_at`. | LinkedIn and Indeed keep closed pages so shared links work. Google requires closed offers out of search results. |
| 5 | Stack, hosting, public API | Catalog: Python, FastAPI, MySQL, two processes (`catalog-intake`, `catalog-api`) like `discord-intake` and `discord-sender`. Webapp: server-rendered Astro on Node, a separate Railway service. Only the webapp is public. The API stays on the private network. | It reuses the existing libraries and patterns. A private API needs no auth, CORS or rate limits. Server-rendered pages work without JavaScript, and a filter is a shareable URL. |

## Webapp layout

The chosen layout is a classic job board. [The static mock](offers-catalog-mock.html) shows it
with sample data.

- **List page.** A search box at the top. A filter sidebar on the left: kind with an offer count
  for each kind, country, and first seen. Offers show as cards: title, company, place, kind and
  source tags, and time since first seen. Newest first, with a "Next page" link.
- **Detail page.** A full page with the title, company, place, first-seen time and the display
  fields. An "Apply on" box lists one button for each source in the duplicate group.

Every filter is a URL query parameter, so a search is a shareable link.

## Duplicate rule

Job boards merge copies of one job and point to one canonical page. Google asks for one canonical
URL per job and shows several "Apply on" sites for one listing. The catalog does the same, at read
time:

1. The catalog stores one row per `(source, source_offer_id)`. It never deletes a source row.
2. On write, it computes `group_key = sha256(normalize(organization), normalize(title), country_iso, normalize(city))`.
   `normalize` folds case, accents and spaces.
3. The list shows one card per open `group_key`. The detail page lists every open source in the group.
4. Two offers from the same source are two postings. The catalog does not merge them.

A later layer can add a manual "not a duplicate" override if a wrong merge happens. The MVP does not.

## Closed offers

1. The catalog sets `closed_at` on a `closed` event. A group is closed when all its sources are closed.
2. The list hides closed groups. The detail page returns 200 with a closed banner and `noindex`.
3. Collectors publish `closed` when an offer leaves its source (issue #62). They already have
   `last_seen_at`. Until then, few offers close, so the list defaults to "first seen in the last
   30 days".

## MVP layers

Each layer works end to end before the next starts.

1. `catalog-intake` consumes `OFFERS` from the start of the stream, upserts offers and acknowledges
   after the commit. `nats-setup` creates its consumer. `nats.conf` gets its user. Migrations live
   in a `catalog_store` library.
2. `catalog-api`: `GET /offers` (filters, keyset pagination, offer count for each kind) and
   `GET /offers/{source}/{source_offer_id}`.
3. Webapp list and detail pages on Railway.
4. Collectors publish `closed` and `updated` (issue #62).

## Data model

`offers`: `source`, `source_offer_id` (primary key), `title`, `organization`, `country_iso`,
`country_raw`, `city`, `url`, `fields` (JSON), `group_key` (indexed), `first_seen_at`,
`observed_at`, `closed_at`, `search_text` (full-text index).

Country names map to ISO 3166 codes with `pycountry`. An unknown name keeps `country_raw`, gets no
code and logs a warning.

## Sources

- [Google: Job posting structured data](https://developers.google.com/search/docs/appearance/structured-data/job-posting)
- [Joveo: Handling duplicate job postings across aggregators](https://www.joveo.com/blog/handling-duplicate-job-postings-across-aggregators/)
- [Search Engine Land: Manual actions on expired job listings](https://searchengineland.com/google-may-issue-manual-actions-over-job-schema-on-expired-job-listings-296376)
- [JobsPipe: Finding old job postings](https://jobspipe.dev/blog/find-expired-job-postings)
