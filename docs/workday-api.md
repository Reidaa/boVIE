# Workday career site contract

Verified on 2026-10-28 against these public boards:
`sanofi.wd3/SanofiCareers`, `thales.wd3/Careers`, `nvidia.wd5/NVIDIAExternalCareerSite`
and `salesforce.wd12/External_Career_Site`. Workday career sites call this JSON API
themselves. It is undocumented and has no official support. No login, cookie or key
is required.

A board's public URL is `https://<tenant>.<wdN>.myworkdayjobs.com/<site>`. Some URLs
put a locale before the site (`/en-US/<site>`). The API lives under
`https://<tenant>.<wdN>.myworkdayjobs.com/wday/cxs/<tenant>/<site>`. Not every
company uses its brand name as the tenant: `airbus/Airbus`, `loreal/LOREAL_Careers`
and `totalenergies/TotalEnergies_careers` returned 422. Copy the URL from the career
site instead of guessing.

## Job list

`POST .../jobs` with a JSON body and `Accept: application/json`:

```json
{"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}
```

- `limit` is at most 20. `21` and `50` returned 400.
- `searchText` and `appliedFacets` are optional. Omitting them returns every job.
- `appliedFacets` maps a `facetParameter` to a list of value `id`s, for example
  `{"locationCountry": ["54c5b6971ffb4bf0b116fe7651ec789a"]}` (Sanofi, France).
  An unknown id returned 400.
- The response has `total`, `jobPostings` and `facets`. Each posting has `title`,
  `externalPath` (`/job/<location>/<jobPostingId>`), `locationsText` and `postedOn`.
  `bulletFields` and `timeType` vary by board.
- `total` is set only when `offset` is 0. Later pages return `total: 0`.
- `total` is capped at 2000 (NVIDIA, Thales).
- An `offset` at or past the end returns the first page again, with `total` set.
  Sanofi (`total` 1019) returned 9 postings at offset 1010, then page 1 at offset 1019.
- The newest postings come first ("Posted Today").
- `facets` lists each filter with its `facetParameter` and values (`descriptor`, `id`,
  `count`). Some facets nest another level, such as `locationMainGroup` →
  `locationCountry`. Read the ids for `appliedFacets` here.

The collector reads `total` from the first page. It stops at a short or empty page,
at `total`, or at its per-run limit. It never trusts a later page to end the list.

## Job detail

`GET .../job/<location>/<jobPostingId>` (the posting's `externalPath`) returns
`jobPostingInfo`, `hiringOrganization` and `similarJobs`. Workday finds the job by its
last path segment (`Job_Posting_Anchor_ID`). The location segment is ignored. An unknown
id returns 404 with `errorCode` `S21`.

`jobPostingInfo` has `id`, `title`, `jobDescription` (HTML), `location`, `postedOn`,
`startDate`, `timeType`, `jobReqId`, `jobPostingId`, `jobPostingSiteId`, `posted`,
`canApply`, `externalUrl` and `jobRequisitionLocation`
(`descriptor`, `country.alpha2Code`). `endDate` and `additionalLocations` appear on
some postings. `hiringOrganization.name` is an internal entity name, such as
`(1675) Sanofi Pasteur de Mexico`, so the collector takes the company name from its
board configuration.

## Identity

`source_offer_id` is `<tenant>/<site>/<jobPostingId>`. `jobPostingId` is the last
segment of `externalPath`, so the collector can skip known offers before it reads a
detail. The detail's `jobPostingId` must match it. The id keeps its first title slug when
the title changes later (a Sanofi posting titled "spectrométrie" has the slug
"chromatographie"). A reposted requisition gets a new suffix (`_R0340738-2` at Thales),
so it is a new offer.

`tests/test_workday.py` uses synthetic responses with this shape. The tests make no
live requests.
