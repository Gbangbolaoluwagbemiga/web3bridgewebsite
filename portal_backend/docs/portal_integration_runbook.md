# Portal Integration Runbook

## Scope
This document covers operational ownership and runtime behavior for onboarding data shared between `backend_v2` and `portal_backend`.

## Source Of Truth
- Source of truth is the DB-coupled cron in `portal_backend`:
  - Module: `app.cron.onboard_students`
  - Job name: `cron_onboard_students`
  - Reads from `cohort_participant` and `cohort_course` in shared database.
- API push from `backend_v2` (`apps/cohort/helpers/portal.py`) is legacy/backward-compatible and not authoritative.

## Ownership
- Product/behavior ownership:
  - Cohort acceptance/payment status lifecycle: `backend_v2` team.
  - Portal account creation and activation: `portal_backend` team.
- Operational ownership:
  - Cron execution health and cursor progression: `portal_backend` team.
  - Data quality in participant status/payment fields: `backend_v2` team.

## Data Contract
- Cron eligibility:
  - `cohort_participant.status = ACCEPTED`
  - `cohort_participant.payment_status = TRUE`
  - Course must be non-ZK.
- Canonical approval statuses stored in `portal.external_student_map.approval_status`:
  - `approved`, `pending`, `rejected`, `revoked`
- Cross-system alias normalization:
  - `accepted -> approved`
  - `declined -> rejected`
  - `suspended -> revoked`
  - unknown/empty values default to safe fallback per integration path.

## Observability Signals
- Cron summary fields (logged):
  - `processed`, `created`, `updated`, `skipped`
  - `cursor`, `duration_seconds`, `cursor_lag_seconds`
  - `integration_mode=db_coupled_cron`, `source_system=backend_v2`
- Warning threshold:
  - `ONBOARD_CURSOR_LAG_WARNING_SECONDS` (default: 3600 seconds)

## Standard Operations
1. Trigger immediate sync (admin/internal API):
   - `POST /api/v1/sync/jobs`
   - `POST /api/v1/sync/jobs/schedule`
2. Verify latest status:
   - `GET /api/v1/sync/jobs/cron_onboard_students/latest`
3. Inspect sync history:
   - `GET /api/v1/sync/jobs`

## Incident Response
1. If onboarding count drops unexpectedly:
   - Check latest sync record status and `error_payload`.
   - Check cron logs for cursor lag warnings.
2. If lag is increasing:
   - Compare `cursor_lag_seconds` against `ONBOARD_CURSOR_LAG_WARNING_SECONDS`.
   - Validate DB connectivity and query performance.
3. If individual students are missing:
   - Verify `status/payment_status/course` eligibility in `backend_v2` rows.
   - Confirm non-ZK rule did not exclude the student.
   - Check `portal.external_student_map` for prior mapping.

## Change Management
- Any change to `cohort_participant` fields used by cron (`status`, `payment_status`, `updated_at`, `course_id`, `email`) requires coordinated rollout and contract test updates in both codebases.
