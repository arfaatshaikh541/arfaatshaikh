# Platform integration assessment

For each platform: authentication flow, official API, technical feasibility, terms, and the
resulting decision. The build environment's network egress was blocked for every job
site, so the terms and flows below come from the platforms' published documentation and
terms as known at build time. **Re-check them before relying on them.** A platform's status
in the dashboard comes from real checks, never from this document.

## Supported: ATS-hosted employer job boards

Most employers do not publish jobs "on" these companies. They run their careers pages on
an applicant-tracking system (ATS), and the ATS publishes an official, unauthenticated
read API for exactly this purpose. Applicants apply through the employer's public hosted
form. No account or password is involved.

### Greenhouse
* **Discovery:** Job Board API, `GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true`.
  Public, documented, no auth.
* **Apply:** public hosted form `https://job-boards.greenhouse.io/{board_token}/jobs/{id}`.
  The API's own `POST` application endpoint needs the *employer's* API key, so it is not
  usable by an applicant and is not used.
* **Security checks:** many boards use (invisible) reCAPTCHA; some send an email security
  code. A visible challenge or a code prompt → `VERIFICATION_REQUIRED`.
* **Board token:** the path segment in `job-boards.greenhouse.io/<token>` or `boards.greenhouse.io/<token>`.

### Lever
* **Discovery:** Postings API, `GET https://api.lever.co/v0/postings/{company}?mode=json`
  (EU: `api.eu.lever.co`). Public, documented. It has **no company-name field**, so set
  "Company name" on the source or it stays UNKNOWN.
* **Apply:** public form at `https://jobs.lever.co/{company}/{id}/apply`. The API's `POST`
  apply endpoint needs the employer's key and is not used.
* **Security checks:** Lever commonly shows hCaptcha → expect a share of `VERIFICATION_REQUIRED`.

### Ashby
* **Discovery:** Posting API, `GET https://api.ashbyhq.com/posting-api/job-board/{org}?includeCompensation=true`.
* **Apply:** public form at `https://jobs.ashbyhq.com/{org}/{id}/application`.

**Live validation status for all three: PENDING.** The form engine is generic: it reads
labels, types, required flags and options from the live DOM. Real forms vary per employer
(custom questions, React comboboxes), so expect some applications to land in
`NEEDS_REVIEW` until you have added the facts those questions need. That is the intended,
safe behaviour.

## Login test only: employer career portal

You configure the login URL, CSS selectors and a success indicator. The worker performs
a real login with your stored credential. The result is `CONNECTED` (success indicator
seen), `LOGIN_FAILED` (with the site's visible error text) or `VERIFICATION_REQUIRED`
(MFA/CAPTCHA). The session cookies are stored encrypted. **Applying on arbitrary portals
such as Workday or Taleo is NOT SUPPORTED.** Each tenant's multi-page flow differs and could
not be built or tested here without faking it.

## NOT AUTOMATABLE (no connector exists)

| Platform | Reason |
|---|---|
| **LinkedIn** | User Agreement prohibits bots, scrapers and automated access. No job-application API for members. Anti-automation defences must not be evaded. |
| **Indeed** | Terms prohibit automated access/scraping. Its APIs are for employers and ATS partners, not job seekers. |
| **Bayt.com** | No public job-seeker API; terms prohibit automated use. |
| **GulfTalent** | No public job-seeker API; terms prohibit automated use. |
| **Naukrigulf** | No public job-seeker API; terms prohibit automated use; OTP/anti-bot verification. |

These platforms appear in the dashboard as `NOT_AUTOMATABLE`, and the server refuses to
store credentials for them. Many employers that advertise on these sites also host the same
job on a Greenhouse, Lever or Ashby board. Add those boards as sources: cross-platform
deduplication links the listings.

## Adding a platform later

A new connector must implement `DiscoveryConnector.fetch()` against a documented, permitted
interface and register an apply method in `jobs/matching.py::SUPPORTED_APPLY_METHODS` only
after live validation. Do not add a connector that relies on evading a platform's controls.
