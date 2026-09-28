# Operating JOB AUTOPILOT

## First-time setup (onboarding)

The Overview page lists whatever is still missing. Work through it in this order.

1. **Upload your CV** (CV page). It is stored encrypted, byte-for-byte, with its SHA-256.
   Facts are extracted as `EXTRACTED`. They are *not* used until you confirm them.
2. **Review your facts** (Candidate profile). Correct each extracted fact and press
   *Save & verify*, delete wrong ones, and add what the parser cannot know:
   * `identity`: full_name, first_name, last_name, nationality (if you want to answer it)
   * `contact`: email, phone, city, country, address_line, linkedin_url
   * `work_authorization`: `authorized:united arab emirates` = yes/no,
     `requires_sponsorship:united arab emirates` = yes/no (one pair per country)
   * `availability`: notice_period, willing_to_relocate · `compensation`: expected_salary, current_salary
   * **employment entries**: for each job add title, employer, **employment_type**
     (full-time / part-time / contract / freelance / internship / academic / volunteer),
     start_date `YYYY-MM`, end_date `YYYY-MM` or `present`. Use group `new` for the first
     fact, then reuse the group key shown for the rest of that entry. Professional years are
     computed only from non-internship, non-academic entries with month-precision dates.
   * **skills**: value = `professional`, `academic` or `personal`. A skill that is only
     academic is never claimed as professional experience. Optional `skill_years` per skill.
   * education entries, certifications, languages
3. **Preferences and rules** (Candidate profile): target roles, locations, workplace
   types, employment types, salary floor, exclusions, minimum match threshold, and what to do
   when rules fail or a mandatory question has no verified answer (`REVIEW` or `SKIP`).
4. **Job sources**: add the Greenhouse, Lever or Ashby boards of employers you are interested in.
5. **AI (optional)**: on Settings choose a provider and model, store the API key on
   Credentials as `ai:anthropic` / `ai:openai`, tick the data-sharing consent, and press
   *TEST AI CONNECTION*. Without AI, narrative questions are UNKNOWN (optional ones are left
   blank; required ones go to review).
6. **Dry run first**: the mode is `DRY_RUN` by default. Press *START AUTOMATION*. Workers
   fill real forms but never click submit, and they save a pre-submit screenshot. Open a few
   `DRY_RUN_COMPLETE` applications and check every answer and its provenance.
7. **Go live**: Automation → Mode → LIVE (type `LIVE` to confirm). The banner turns red.

## Daily use

* **Overview** shows today's real counts and live system status.
* **Applications**, filtered by status:
  * `NEEDS_REVIEW`: a mandatory question had no verified answer, or rules sent the job to
    review. The reason names the questions. Add the missing facts, then press
    *Retry / approve*.
  * `VERIFICATION_REQUIRED`: the site showed a CAPTCHA, OTP or MFA challenge. It is not
    bypassed. Apply manually if you want that job, or retry later.
  * `UNKNOWN`: submit was clicked but no confirmation was seen, or a worker died
    mid-submission. **Check your email and the employer site first.** Then *Confirm submitted*
    (paste the confirmation you received) or *Mark NOT submitted*. It is never retried automatically.
  * `FAILED`: the site rejected the form, the posting closed, or retries ran out. The reason and
    screenshot are on the application page.
* **Reports**: generated at the configured time each day, or on demand with *GENERATE REPORT
  NOW*. Every figure is a database query. Dry-run figures are listed separately.

## Controls

| Control | Effect |
|---|---|
| START / RESUME | Scheduler searches sources on schedule and dispatches queued applications within limits |
| PAUSE | Nothing new is started; running tasks finish |
| STOP | Like pause, and pending search/apply tasks are cancelled |
| RUN JOB SEARCH NOW | Queues a discovery task for every enabled source |
| TEST LOGIN | Queues a real login attempt for a configured portal |
| Retry / approve | Re-queues a FAILED / VERIFICATION_REQUIRED / NEEDS_REVIEW / SKIPPED application |

All control actions are written to the Audit log.

## Data rights

* Profile → *Export all candidate data* downloads your facts, preferences and CV metadata as JSON.
* Profile → *Delete candidate data* erases facts and CV files. Application history (jobs,
  events, evidence) remains for auditability; delete the database volume to remove everything.
