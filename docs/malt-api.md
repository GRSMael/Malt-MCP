# Malt internal REST API — reverse-engineered map

Captured from an authenticated freelancer session by driving the SPA and
recording XHR/fetch calls, then fetching each GET endpoint from the browser
context. **Field names only — no personal values.** Read surface for the
lightweight (in-browser `fetch`) architecture; no GraphQL, plain REST.

## Meaningful GET endpoints (path -> top-level JSON keys)

- `GET /dashboard/freelancer/api/company`
  - companyId, name, type, registrationNumber
- `GET /dashboard/freelancer/api/mission/summary`
  - caTTC, caHT, nbMissions, nbReviews, rating, currency
- `GET /dashboard/freelancer/api/profile/visibility`
  - profileId, alerts, status, profileCompleted, availabilityLabel, availabilityType, availabilityFrequency, nextAvailabilityDate, lastVerifiedAvailabilityInDays
- `GET /dashboard/freelancer/api/sales-revenue`
  - allTimeTotal, lastYearTotal, currentMissionsTotalHT, numberOfMissionsEndedLastYear, allTimeNumberOfMissionsEnded, last12MonthsHistory, currency
- `GET /dashboard/freelancer/api/scoring`
  - profile, points, pointsSinceLastVisit, bonusPoints, recoPoints, profileCompleted, profileCompletedPoints, hasDoneAtLeastOneMission, atLeastOneRatingOrThreeCompletedMissionLots, top, hasResponsibleLitigation, stepInfo, rating
- `GET /dashboard/freelancer/api/scoring/levels`
  - <array 3>
- `GET /dashboard/freelancer/api/sharing`
  - profileUrl, title
- `GET /dashboard/freelancer/api/stats`
  - nbProfileViews, nbSearchHits, nbWishlist, searchResultsAveragePosition, searchResultsTerm
- `GET /dashboard/freelancer/api/summary`
  - profileId, accountId, completionPercentage, firstName, lastName, jobTitle, availabilityInfos, photoId, photo, searchVisibilityChoice, profileIsStrategyVertical, emailVerified
- `GET /dashboard/freelancer/api/user/current-session`
  - visitorId, locale, currency, loggedInUser, pathWhereToRedirectUser
- `GET /dashboard/freelancer/api/user/me`
  - id, username, email, roles, identities, platformAdmin, impersonated, connectedThroughSso, organizationMemberDetails, selectedIdentity, photo, impersonatedBy, extraInformation
- `GET /dashboard/freelancer/api/visibility`
  - nbFavorites, nbAppearancesWeekly, nbAppearancesVariationRateWeekly, nbAppearancesMonthly, nbAppearancesVariationRateMonthly, nbViewsWeekly, nbViewsVariationRateWeekly, nbViewsMonthly, nbViewsVariationRateMonthly
- `GET /dashboard/freelancer/api/visibility/history`
  - searchHitsPerDate, profileViewsPerDate
- `GET /messenger/api/conversation/current-user`
  - identityType, firstName, lastName, hasActiveClientProjectOffers, hasFreelancerIdentity, hasClientIdentity, webPreferences, phoneNumber, photo, accountId
- `GET /messenger/api/user/current-session`
  - visitorId, locale, currency, loggedInUser
- `GET /messenger/api/user/me`
  - id, username, email, roles, identities, platformAdmin, impersonated, connectedThroughSso, selectedIdentity, photo, extraInformation
- `GET /navbar/api/context`
  - isEnforcedIdentity, state
- `GET /navbar/api/profile-availability`
  - value, partial, frequency, nextAvailabilityDate
- `GET /navbar/api/profile-preferences`
  - searchVisibilityChoice
- `GET /navbar/api/supported-host/l10n/hosts`
  - <array 8>
- `GET /navbar/api/user`
  - selectedIdentityId, identities, options, featureFlags, currentCountry, currentLanguage, insightsBaseUrl, punchoutSessionActive
- `GET /profile/api/user/current-session`
  - visitorId, locale, currency, loggedInUser, pathWhereToRedirectUser
- `GET /profile/api/visibility/<profileId>`
  - alerts, status, profileCompleted

## Talent search — find freelancers (validated live)

The public/client freelancer search is a separate Nuxt app (`search-front`,
served under `/s`) backed by its own REST app `/search/api/...`. Results are
server-rendered on first load, so no XHR fires on navigation; the endpoint and
its parameters were recovered from the generated API client in the JS bundles,
then verified live by in-browser `fetch` from the authenticated session.

- **`GET /search/api/profiles`** — the search results endpoint.
  - **Auth**: session cookie is enough. No CSRF/XSRF token needed for this GET.
  - **`q` is required** — the generated client throws "Required parameter q"
    when absent; live, `GET /search/api/profiles` with no `q` returns **400**
    (this is why earlier param-name guesses all failed: the keyword param is
    literally `q`, and the page param is `p`).
  - **Query params** (all optional except `q`):
    - `q` — free-text query (required, e.g. `python`)
    - `p` — page number (1-based)
    - `minPrice`, `maxPrice` — daily-rate bounds
    - `exp` — experience level ; `speciality` ; `category` ; `businessSector`
    - `badge` — quality badge filter ; `lang` — language
    - `remoteAllowed`, `remoteEuropa` — remote-work filters
    - Location: `lat`, `lon`, `city`, `location`, `countryCode`,
      `administrativeAreaLevel1Code` … `administrativeAreaLevel4Code`
    - `excludedProfiles`, `fallback`, `searchid`, `searchOrigin`, `adminFilter`
  - **Response envelope**: `{searchId, searchType, profiles[], pagination, query}`
    - `pagination`: `{current, total, totalElements, firstItem, lastItem}`
      (24 profiles per page; e.g. `total:25, totalElements:600`).
    - `profiles[]` item: `{id, firstName, lastNameNormalized, headline, photo,
      location{locationType,city,country,countryCode}, price{visibility,
      value{amount,currency,formatted}}, availability{status,workAvailability,
      nextAvailabilityDate,frequency}, stats{rating,missionsCount,
      recommendationsCount,appraisalsWithRatesCount,invalidatedCharter},
      badges[], skills[{label,certified,level}], portfolio[{title,index,type,
      picture{...}}], url, strongMatch, refinementCriteria[], consultingOffer}`
    - `query` is an opaque debug string exposing the backend (Elasticsearch
      `_search`); not needed to consume the API.
  - Verified live: `?q=python` → 200 with 24 profiles; `?q=python&p=2` →
    `pagination.current:2`. Read-only, no personal data written.
- Related endpoints in the same app (not yet exercised): `/search/api/profiles/filters`
  (available facets, same query params), `/search/api/profiles/features`
  (needs `q`,`p`), `/search/api/search/autocomplete?q=` (query suggestions),
  `/search/api/autocomplete/skill`, `/search/api/location/autocomplete`,
  `/search/api/skills/suggestions`.

## Full raw capture

See `malt-api-raw.json` for every endpoint (incl. infra/noise) and status codes.

## Missions / client offers & billing (mapped; empty on the test account)

Freelancers don't browse a project marketplace — Malt is invitation-based, so
"missions" surface as client project offers in the messenger. These endpoints
were mapped but returned empty on the reverse-engineering account (no offers,
no invoices), so item-level field names are not yet confirmed.

- `GET /messenger/api/conversation/conversations-or-client-project-offers?status=ACTIVE&type=&page=0&pageSize=N`
  - paginated envelope: content[], totalElements, first, last, numberOfElements, empty, pageNumber, pageSize, type
  - status ∈ {ACTIVE, ARCHIVED}
- `GET /messenger/api/conversation/current-user`
  - identityType, firstName, lastName, hasActiveClientProjectOffers, hasFreelancerIdentity, hasClientIdentity, phoneNumber, accountId
- `GET /invoicing/api/freelancers/invoices/years`
  - array of years (empty when no invoices); billing app lives at `/invoicing/freelancer`

## Writes (validated live)

Malt's write endpoints are the same REST API with a mutating verb (PUT/POST)
and require an anti-CSRF header. Validated end-to-end via in-browser fetch:

- **CSRF**: send header `X-XSRF-TOKEN` whose value is the `XSRF-TOKEN` cookie
  (URL-decoded). In-page fetch pattern:
  ```js
  const token = decodeURIComponent(document.cookie.match(/XSRF-TOKEN=([^;]+)/)[1]);
  await fetch(path, {method:'PUT', credentials:'include',
    headers:{'content-type':'application/json','x-xsrf-token':token,'accept':'application/json'},
    body: JSON.stringify(payload)});
  ```
- **Availability** — `PUT /navbar/api/profile-availability`
  - body: `{"value": "AVAILABLE"|"NOT_AVAILABLE", "frequency": "FULL_TIME"|...}`
  - GET returns `value` as `AVAILABLE_AND_VERIFIED` after a confirm (the
    "_AND_VERIFIED" suffix reflects a fresh confirmation).
  - Re-confirming the same value is a safe no-op write (verified live).

### Profile edition endpoints (captured live)

Captured by driving the edit drawers while recording the mutating XHR
(`profileId` is the profile object id, e.g. from `/profile/api/visibility/<id>`).
**All three send the full object, not a partial patch.**

- **Skills** — `PUT /profile/api/expertises/skills` *(used by the skills path)*
  - GET (read-back) → `{"topSkills": [...], "selectedSkills": [...]}` where an
    entry is `{id, label, type, origin, seoUrl}`.
  - PUT body → `{"selectedSkillsOrder": [{id,type,origin}, ...], "topSkills":
    [{id,type,origin}, ...]}` — reduced entries (drop `label`/`seoUrl`); the
    write key is `selectedSkillsOrder`, **not** the read-side `selectedSkills`.
  - `topSkills` is a **disjoint** highlighted list; leave it unchanged.
  - Free-text add resolution: `GET /profile/public-api/suggest/tags/autocomplete?query=<q>`
    → `[{label, occurrences, universe, tag}]`; match a label case-insensitively,
    then send `{id: <label>, type: "GLOBAL", origin: "MANUAL"}`.
  - Bounds: `GET /profile/public-api/rules?profileId=<id>` →
    `GLOBAL_SKILLS_LENGTH {min:1, max:100}`.
  - **This is the only profile field with a clean read-back**, so it is the only
    one implemented as a pure-API read-merge-write (`core/skills_api.py`).
    Verified live: add + exact restore (25→26→25).
- **Header (headline + daily rate)** — `PATCH /profile/api/profiles/<id>/header`
  - full body: `{dailyRate:{currencyCode,hidden,price}, experienceLevel,
    headline, location{...}, nameDisplayOption, topSkills:[...]}`.
- **Bio (about)** — `PATCH /profile/api/profiles/<id>/about`
  - full body: `{description, industryExpertises:[], languages:[{code,level}],
    workplacePreferences:{...}}`.
- ⚠️ **No GET read-back for header/about**: `GET .../header` and `.../about`
  return **405**; the editable object only lives in the Nuxt hydration payload
  (devalue-encoded, index-referenced). A pure-API full-object PATCH would risk
  clobbering `location`/`languages`/`topSkills`, so headline, bio and daily rate
  stay on the **DOM drawer path** (`scraping/update_profile.py`).
