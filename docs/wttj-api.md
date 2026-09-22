# WTTJ public search contract

Verified against WTTJ's own public website and API on 2026-09-22. These are
observed website endpoints, not a promise of a stable supported third-party API.
No login, private cookies, or copied API keys are required by this implementation.

The public client on [WTTJ's jobs page](https://www.welcometothejungle.com/fr/jobs)
calls `GET https://api.welcometothejungle.com/api/v3/public/jobs` with
`job_title` and `page`. `page` starts at 1. The client also adds `query_id` for
tracking; direct verification succeeded without it.

The response contains `data` and `metadata`. Each search hit supplies
`reference`, `slug`, `contract_type`, and `organization.slug`. Metadata supplies
`page`, `page_count`, `per_page`, and `total`. Verified page 1 and page 2 return
matching page metadata. The collector follows `page_count` within its configured
limit. Requests using `contract_type` or `per_page` were rejected with 422, so
those parameters are not sent.

Details come from `GET /api/v3/organizations/{organization_slug}/jobs/{job_slug}`.
The response wraps the detail under `job`; `wttj_reference` matches the search
hit's `reference`. The detail has `offices`, not the legacy single `office` field.
The collector validates this identity before storing anything and checks both
search and detail contract type. Geography is filtered against all detail offices.

`src/wttf/core/search.py` contains minimal projections of the verified v3
responses. Existing v1 models in `types.py` and Yaak examples are preserved.
`tests/test_wttj.py` uses synthetic, credential-free responses with the observed
shape. No live requests are needed to run tests.
