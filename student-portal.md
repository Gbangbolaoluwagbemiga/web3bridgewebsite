# Student Portal Backend Project Plan

## 1) Project Summary
Build a separate Student Portal backend for approved students of Web3Bridge.

- **System A (existing):** current backend (`backend_v2`) remains source of truth for admissions and approval.
- **System B (new):** Student Portal backend for authentication, student profile CRUD, and student updates.
- Systems share the same PostgreSQL database, but portal tables are isolated under a dedicated schema (for example `portal`).

---

## 2) Goals

### Primary goals
1. Allow only approved students to access the portal.
2. Provide secure authentication and account lifecycle.
3. Provide CRUD for student records and profile updates.
4. Publish and track student updates (announcements, notices, progress updates).
5. Keep both systems consistent through integration and sync rules.

### Non-goals (MVP)
- Full LMS features (quizzes, grading, certificates).
- Deep analytics dashboards.
- Multi-tenant white-labeling.

---

## 3) High-Level Architecture

## Components
- **Admissions Backend (`backend_v2`)**
  - Owns approval decision and admissions data.
- **Student Portal Backend (new service)**
  - Owns portal users, auth, profile management, updates, access control.
- **Portal Frontend (future or existing UI)**
  - Calls Student Portal APIs.

## Integration principle
- **Shared database with logical isolation**
   - Portal backend will use the same PostgreSQL instance/database.
   - Portal tables must live under a dedicated schema (for example `portal`) to avoid collisions.
   - Admissions tables remain unchanged and owned by admissions workflows.
- Data moves through:
   1. Scheduled sync (MVP)
   2. Optional webhooks/event-driven sync (Phase 2)

## Backend Stack (Confirmed)
- **Framework:** FastAPI
- **ORM/Migrations:** SQLAlchemy + Alembic
- **Validation:** Pydantic
- **Auth:** JWT access/refresh tokens
- **Background jobs:** Celery (or RQ/Arq) + Redis
- **Database:** PostgreSQL
- **Caching/locks/rate-limit support:** Redis

---

## 4) Data Ownership Boundaries

### Admissions backend owns
- Registration and approval workflows.
- Approved/rejected status.
- Cohort admission metadata.

### Portal backend owns
- Auth credentials and tokens.
- Portal account lifecycle (`invited`, `active`, `suspended`).
- Student portal profile (editable fields).
- Student updates and read tracking.
- Audit logs.

---

## 5) Identity & Mapping Strategy

### Cross-system identity key
- **Initial key:** normalized email (lowercase, trimmed).
- **Recommended upgrade:** add immutable external ID from admissions backend.

### Mapping rules
- One approved admissions record maps to one portal student account.
- Email collisions trigger manual resolution workflow.
- Every sync operation is idempotent.

---

## 6) Authentication & Authorization Plan

## Authentication
- Access token + refresh token model.
- Login via email/password.
- Password reset flow.
- Optional MFA for staff/admin in later phase.

## Authorization (RBAC)
- `student`: can read/update own profile (restricted fields), read own updates.
- `staff`: can manage students in assigned scope/cohort.
- `admin`: full management and configuration.

## Account states
- `invited`
- `active`
- `suspended`
- `deactivated`

---

## 7) Core Domain Model (Portal)

1. **UserAccount**
   - auth identity, role, account status.
2. **StudentProfile**
   - profile and cohort-related metadata for portal use.
3. **StudentStatusHistory**
   - lifecycle state transitions.
4. **StudentUpdate**
   - update content, visibility scope, publish status.
5. **StudentUpdateRead**
   - per-student read/unread tracking.
6. **ExternalSyncRecord**
   - sync checkpoints, source ID/email, sync status.
7. **AuditLog**
   - actor, action, before/after diff, timestamp.

## 7.1) Database Schema (Improved MVP)

Your draft is a good start. For this portal, the schema should focus on identity, approval sync, profile CRUD, updates, and auditability.

| Table | Key Fields | Purpose |
|---|---|---|
| `users` | `id`, `email` (unique), `password_hash`, `role`, `account_state`, `last_login_at`, `created_at` | Core auth identity and account lifecycle. |
| `student_profiles` | `id`, `user_id` (unique FK), `full_name`, `phone`, `discord_id`, `wallet_address`, `cohort`, `onboarding_status`, `created_at`, `updated_at` | Editable student profile and onboarding metadata. |
| `external_student_map` | `id`, `user_id` (FK), `source_system`, `external_student_id` (unique), `source_email`, `approval_status`, `approval_updated_at`, `last_synced_at` | Cross-system mapping and approval sync state from admissions backend. |
| `student_status_history` | `id`, `user_id` (FK), `from_state`, `to_state`, `reason`, `changed_by`, `changed_at` | Track lifecycle transitions (`invited` → `active` → `suspended`/`deactivated`). |
| `student_updates` | `id`, `title`, `body`, `target_type`, `target_ref`, `is_published`, `published_at`, `created_by`, `created_at`, `updated_at` | Announcements/notices/progress updates created by staff/admin. |
| `student_update_reads` | `id`, `update_id` (FK), `user_id` (FK), `read_at` | Per-student read tracking (use unique constraint on `update_id + user_id`). |
| `refresh_tokens` *(or token blacklist table)* | `id`, `user_id` (FK), `jti` (unique), `expires_at`, `revoked_at`, `created_at` | Token revocation and session invalidation support. |
| `external_sync_record` | `id`, `job_name`, `cursor`, `status`, `started_at`, `ended_at`, `error_payload` | Sync checkpoints, observability, and retry diagnostics. |
| `audit_logs` | `id`, `actor_user_id`, `action`, `resource_type`, `resource_id`, `before_json`, `after_json`, `ip`, `request_id`, `created_at` | Compliance and forensic trace of sensitive operations. |

### Notes on your original proposal
- `users` and `profiles` are correct and should stay.
- `courses`, `enrollments`, and `payments` should be **deferred** for MVP unless this portal must own billing/learning access.
- If course/payment info is needed in MVP, store them as **read models/snapshots** synced from source systems, not as source-of-truth transactional tables.
- Keep strict uniqueness on identity (`email`) and external mapping (`external_student_id`).

---

## 8) Functional Modules

## Module A: Approval Sync
- Pull approved students from admissions backend every 5–15 minutes.
- Upsert portal student records.
- Handle revocations (optional policy: suspend account).
- Retry and dead-letter for failures.

## Module B: Auth
- Register invited users from sync process.
- First-login setup flow.
- Access/refresh token issuance.
- Password reset and session invalidation.

## Module B.1: Portal Onboarding Trigger Rules

### Primary onboarding rule
- Portal onboarding should start only after **successful payment confirmation** for **non-ZK cohorts**.

### Non-ZK cohorts
- After payment is confirmed:
   1. mark student as paid in admissions flow
   2. send registration success email
   3. send participant details email
   4. trigger portal onboarding
- Portal onboarding means:
   - create portal user if one does not exist
   - create portal profile if one does not exist
   - set account state to `invited`
   - generate activation/onboarding token or link
   - send portal activation email

### ZK cohort exception
- ZK students must **not** use the normal post-payment onboarding trigger.
- ZK keeps its separate **approval-first** flow.
- ZK approval email may include payment link, but payment success alone should not trigger standard portal onboarding.
- Any future ZK portal access policy should be handled separately.

### Valid payment-confirmation sources
- verified payment callback/confirmation
- discount-code success path
- admin/manual confirmation path

### Duplicate protection rules
- Match users by normalized email.
- If portal account already exists and is `active`, do not create a duplicate.
- If portal account exists and is `invited`, allow resend of onboarding email.
- Repeated payment confirmations must be idempotent.

### Failure handling
- If onboarding creation fails, payment confirmation must remain valid.
- Failures should be logged and queued for retry.
- If onboarding email fails, keep account state as `invited` and retry asynchronously.

### Audit requirements
- Log cohort-type decision (`ZK` vs `non-ZK`).
- Log whether onboarding was triggered, skipped, retried, or failed.
- Log whether portal account was created, reused, or re-invited.

## Module C: Student CRUD
- Create/update/view/archive student profiles.
- Field-level permissions (student can only edit approved fields).
- Soft delete/archive instead of hard delete.

## Module D: Updates
- Staff/admin can create updates.
- Targeting modes:
  - individual student
  - cohort/group
  - all active students
- Read receipts for students.

## Module E: Audit & Admin Ops
- Full activity logging.
- Admin filters/export for compliance and operations.

---

## 9) API Plan (MVP Endpoint Groups)

1. **Auth**
   - login, refresh, logout, reset-password, change-password.
2. **Students**
   - list, retrieve, create, update, archive.
3. **My Profile**
   - retrieve self, update allowed fields.
4. **Updates**
   - create/list/retrieve/update/delete (staff/admin)
   - list-my-updates + mark-as-read (student)
5. **Sync/Admin**
   - trigger sync (admin)
   - sync status and errors
6. **Health/Observability**
   - health check, readiness, metrics endpoint

---

## 10) Security Plan

- Strict RBAC + object-level authorization checks.
- Rate limits on auth endpoints.
- Password policy and lockout thresholds.
- JWT rotation and refresh-token revocation strategy.
- Encryption in transit (TLS) and encrypted backups.
- Minimize PII in logs.
- Audit log for privileged operations.

---

## 11) Reliability & Performance

- Idempotent sync jobs.
- Exponential backoff retries for admissions API failures.
- Background worker for sync and notifications.
- Pagination everywhere on list endpoints.
- Caching for read-heavy endpoints where safe.

## Background Workers (Recommended)

Background workers are strongly recommended for this portal, including MVP.

### Why they are needed
- Run periodic approval sync from admissions backend (every 5–15 minutes).
- Handle retries/backoff for failed syncs without blocking API requests.
- Process asynchronous side effects (emails, notifications, audit exports).
- Run maintenance jobs (token/session cleanup, stale-record cleanup).

### MVP worker setup
- Start with **1 queue worker** + **1 scheduler/beat process**.
- Move `sync_students()` and notification tasks to the queue first.
- Keep API endpoints request/response fast and non-blocking.

### Conclusion
- Background workers are not optional long-term.
- For MVP, they should be included early to improve reliability and scalability.

## Redis (Recommended)

Redis is recommended for this project, especially when background workers are enabled.

### Why Redis is needed
- Queue broker/result backend for background jobs.
- Caching for read-heavy endpoints (for example student lists and sync checkpoints).
- Rate limiting support for authentication endpoints.
- Optional token/session blacklist support and short-lived distributed locks (to prevent duplicate sync runs).

### MVP guidance
- If background workers are included in MVP, include Redis from day one.
- If workers are delayed, Redis can be introduced in Phase 2, but should be planned early.

---

## 12) DevOps / Environment Plan

## Environments
- `dev`, `staging`, `production`
- Separate database and secrets per environment.

## Config management
- Environment variables for secrets and service URLs.
- Rotatable API keys between systems.

## CI/CD
- Lint + test + migration checks.
- Zero-downtime deployment approach.
- Rollback procedures documented.

---

## 13) Observability Plan

- Structured logs with request IDs.
- Error tracking integration.
- Metrics:
  - login success/failure rates
  - sync success/failure rates
  - update publish/read rates
  - API latency and error rate

---

## 14) Delivery Roadmap

## Phase 0 — Design (1–2 weeks)
- Finalize domain model.
- Finalize integration contract with admissions backend.
- Security and permission matrix sign-off.

## Phase 1 — MVP Build (3–5 weeks)
- Auth module.
- Approval sync (polling).
- Student CRUD.
- Updates module.
- Basic admin APIs and audit logs.

## Phase 2 — Hardening (2–3 weeks)
- Webhooks/event-driven sync (optional).
- Performance optimization and caching.
- Expanded audit/reporting.
- Security hardening and test pass.

## Phase 3 — Scale Features
- Notifications (email/in-app/push).
- Advanced segmentation and cohorts.
- Analytics and operations dashboards.

---

## 15) Risks & Mitigations

1. **Identity mismatch across systems**
   - Mitigation: normalized email + immutable external ID migration plan.
2. **Duplicate records from sync races**
   - Mitigation: unique constraints + idempotency keys.
3. **Approval revoked after onboarding**
   - Mitigation: status reconciliation policy (auto-suspend/manual review).
4. **Permission leakage**
   - Mitigation: object-level checks and permission tests.
5. **Integration downtime**
   - Mitigation: retry queues, circuit breaker, degraded mode messaging.

---

## 16) Definition of Done (MVP)

MVP is complete when:
- Approved students can securely login.
- Non-approved users cannot access portal flows.
- Student CRUD works with role and field restrictions.
- Staff/admin can publish updates.
- Students can read and track updates.
- Audit logs are generated for sensitive actions.
- Sync with admissions backend is reliable and monitored.

---

## 17) Immediate Next Decisions

1. Finalize FastAPI package choices (`SQLAlchemy`, `Alembic`, JWT library, worker library).
2. Freeze integration contract with current backend.
3. Decide approval revocation policy.
4. Define exact editable student fields for self-service.
5. Approve MVP scope and timeline.
