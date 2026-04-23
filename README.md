# TON — Talent Observable Network
### Backend API Reference & Developer Guide
**Django + PostgreSQL + Railway | MVP Edition | March 2026**

---

## Table of Contents

1. [What This Is](#1-what-this-is)
2. [Project Structure](#2-project-structure)
3. [Local Development Setup](#3-local-development-setup)
4. [Environment Variables](#4-environment-variables)
5. [Database](#5-database)
6. [API Reference](#6-api-reference)
7. [NikoScore Engine](#7-nikoscore-engine)
8. [Authentication Flow](#8-authentication-flow)
9. [Privacy Rules](#9-privacy-rules)
10. [Running Tests](#10-running-tests)
11. [Deployment to Railway](#11-deployment-to-railway)
12. [Daily Cron Jobs](#12-daily-cron-jobs)
13. [Build Order](#13-build-order)
14. [Critical Rules — Never Violate](#14-critical-rules--never-violate)

---

## 1. What This Is

TON connects Tanzanian university students (DIT) with verified companies through real task-based performance. Students attempt tasks publicly, companies score submissions privately, and the platform computes a **NikoScore (0–100)** from behavioural signals — consistency, quality, and reliability. Internship invitations follow observation, not lottery applications.

**Core loop:** Company posts task → Students attempt → Platform scores behaviour → Company sends invitation

---

## 2. Project Structure

```
ton_backend/
├── config/
│   ├── settings/
│   │   ├── base.py          # Shared: JWT, throttles, NikoScore constants
│   │   ├── development.py   # Local: AT sandbox, console email, local PG
│   │   └── production.py    # Railway: dj-database-url, Redis, Sentry, HSTS
│   ├── urls.py              # Root URL routing
│   └── wsgi.py
│
├── apps/
│   ├── authentication/      # User model, OTP, JWT, permissions, throttles
│   ├── students/            # StudentProfile, DIT verification, signals
│   ├── companies/           # Company, Watchlist, 3-stage onboarding
│   ├── tasks/               # Task, Submission, atomic counter, privacy split
│   ├── nikoscore/           # Engine (4 components), audit log, decay cron
│   ├── invitations/         # Lifecycle, contact_released gate, expiry cron
│   ├── notifications/       # Africa's Talking SMS + Resend email
│   └── admin_panel/         # Verification queues, suspend, analytics
│
└── tests/
    ├── test_auth.py
    ├── test_nikoscore.py    # Most critical — run these first
    ├── test_tasks.py
    └── test_invitations.py
```

---

## 3. Local Development Setup

### Prerequisites
- Python 3.11+
- PostgreSQL 14+
- Node.js (not required — backend only)

### Steps

```bash
# 1. Clone and enter
git clone <repo>
cd ton_backend

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env — set SECRET_KEY, DB credentials, AT_API_KEY, RESEND_API_KEY

# 5. Create local PostgreSQL database
psql -U postgres -c "CREATE DATABASE ton_db;"
psql -U postgres -c "CREATE USER ton_user WITH PASSWORD 'ton_pass';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE ton_db TO ton_user;"

# 6. Run migrations
python manage.py migrate --settings=config.settings.development

# 7. Create admin user
python manage.py createsuperuser --settings=config.settings.development

# 8. Seed development data (50 students, 5 companies, 30 tasks)
python manage.py seed_dev_data --settings=config.settings.development

# 9. Run development server
python manage.py runserver --settings=config.settings.development
```

**API base URL:** `http://localhost:8000/api/`

---

## 4. Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Django secret key — generate with `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DATABASE_URL` | Production | Railway PostgreSQL URL (injected automatically) |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` | Development | Local PostgreSQL credentials |
| `CLOUDINARY_CLOUD_NAME` | Yes | Cloudinary cloud name |
| `CLOUDINARY_API_KEY` | Yes | Cloudinary API key |
| `CLOUDINARY_API_SECRET` | Yes | Cloudinary API secret |
| `AT_USERNAME` | Yes | Africa's Talking username (`sandbox` for development) |
| `AT_API_KEY` | Yes | Africa's Talking API key |
| `RESEND_API_KEY` | Yes | Resend transactional email API key |
| `RESEND_FROM_EMAIL` | Yes | Sender email (e.g. `noreply@ton.co.tz`) |
| `FRONTEND_URL` | Yes | Vercel frontend URL — used in email links and CORS |
| `REDIS_URL` | Production | Railway Redis URL |
| `SENTRY_DSN` | Production | Sentry error monitoring DSN |

---

## 5. Database

### Tables and FK cascade rules

| Table | Cascade Rule | Reason |
|---|---|---|
| `users → student_profiles` | CASCADE | Profile is meaningless without user |
| `users → companies` | CASCADE | Same |
| `companies → tasks` | **PROTECT** | Never silently delete tasks with submissions |
| `tasks → submissions` | **PROTECT** | Submissions contain student work |
| `student_profiles → submissions` | **PROTECT** | History survives soft-delete |
| `student_profiles → nikoscores` | CASCADE | Score tied to profile — safe |
| `student_profiles → nikoscore_events` | **PROTECT** | Audit log must survive all state changes |
| `companies → invitations` | **PROTECT** | History needed for dispute resolution |
| `companies/students → watchlist` | CASCADE | Watchlist is ephemeral |

### Required indexes (all defined in migrations)

| Table | Index | Reason |
|---|---|---|
| `users` | `email` | Every login hits this |
| `tasks` | `(sector, status)` | Task feed composite filter |
| `tasks` | `deadline` | Feed sorted by deadline |
| `submissions` | `(task, student)` unique | One submission per student per task |
| `submissions` | `(task, status)` | Company submission review panel |
| `submissions` | `(student, submitted_at)` | Student history sorted by date |
| `nikoscore_events` | `(student, created_at)` | Score timeline |
| `invitations` | `(student, status)` | Student inbox |
| `invitations` | `(company, status)` | Company sent list |

---

## 6. API Reference

### Authentication
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/register/student/` | None | Register student, send OTP |
| POST | `/api/auth/register/company/` | None | Register company, send OTP |
| POST | `/api/auth/verify-otp/` | None | Verify OTP → receive JWT tokens |
| POST | `/api/auth/resend-otp/` | None | Regenerate OTP |
| POST | `/api/auth/login/` | None | Login (verified users only) |
| POST | `/api/auth/logout/` | JWT | Blacklist refresh token |
| POST | `/api/auth/token/refresh/` | Refresh token | Rotate access token |

### Students
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/students/profile/` | Student | Own full private profile |
| PATCH | `/api/students/profile/` | Student | Update bio, photo, sectors |
| POST | `/api/students/verify-dit/` | Student | Upload DIT ID document URL |
| GET | `/api/students/public-profile/<id>/` | **None** | Shareable public profile |
| GET | `/api/students/dashboard/` | Student | Aggregated dashboard data |

### Companies
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/companies/profile/` | Company (any) | Company profile |
| PATCH | `/api/companies/profile/` | Company (verified) | Update profile |
| GET | `/api/companies/dashboard/` | Company (verified) | Stats overview |
| GET | `/api/companies/watchlist/` | Company (verified) | Saved students |
| POST | `/api/companies/watchlist/add/` | Company (verified) | Save student |
| DELETE | `/api/companies/watchlist/remove/<id>/` | Company (verified) | Remove student |

### Tasks
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/tasks/feed/` | Student | Personalised task feed by sector |
| GET | `/api/tasks/<id>/` | Student | Task detail |
| POST | `/api/tasks/create/` | Company (verified) | Post a new task |
| PATCH | `/api/tasks/<id>/close/` | Company (verified, owner) | Close task |
| POST | `/api/tasks/<id>/submit/` | Student | Submit work |
| GET | `/api/tasks/<id>/submissions/` | Company (verified, owner) | Review panel |
| PATCH | `/api/tasks/submissions/<id>/review/` | Company (verified, owner) | Score 1–5 |
| PATCH | `/api/tasks/submissions/<id>/abandon/` | Student (own only) | Withdraw submission |

### NikoScore
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/nikoscore/my-score/` | Student | Own full breakdown + history |
| GET | `/api/nikoscore/student/<id>/` | Company (verified) | Total score only |

### Invitations
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/invitations/send/` | Company (verified) | Send invitation |
| GET | `/api/invitations/received/` | Student | Inbox |
| GET | `/api/invitations/sent/` | Company (verified) | Sent list |
| PATCH | `/api/invitations/<id>/respond/` | Student | Accept or decline |

### Admin
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/admin/companies/pending/` | Admin | Pending verification queue |
| PATCH | `/api/admin/companies/<id>/verify/` | Admin | Approve or reject company |
| GET | `/api/admin/students/pending-dit/` | Admin | Pending DIT queue |
| PATCH | `/api/admin/students/<id>/verify-dit/` | Admin | Approve or reject DIT |
| PATCH | `/api/admin/users/<id>/suspend/` | Admin | Soft-ban user |
| GET | `/api/admin/analytics/` | Admin | Platform metrics |

---

## 7. NikoScore Engine

**Location:** `apps/nikoscore/engine.py` — the ONLY place scoring logic lives.

**Never call the engine directly from a view.** It is triggered exclusively by Django signals.

### Score structure (max 100)

| Component | Max | Trigger |
|---|---|---|
| Profile | 25 | DIT verified (+10), photo (+3), bio 50+ words (+3), course+year (+3), 2+ sectors (+3), first submission (+3) |
| Activity | 25 | Submissions × 2 (cap 15) + active weeks × 2 (cap 10). Decay: −1/week after 30 days inactive |
| Quality | 25 | Average company rating (1–5) → 5–25 pts. Requires 3+ reviews. Outliers weighted 0.3× |
| Reliability | 25 | On-time submissions +3/each (cap 15), profile updated in 90 days +5, responded to invite +5, abandoned −2/each (cap −10) |

### Signal trigger map

| Signal | Trigger | Engine action |
|---|---|---|
| `StudentProfile.post_save` | Any field change | Recalculate profile component |
| `Submission.post_save` (created) | New submission | Recalculate activity + reliability |
| `Submission.post_save` (score set) | Company review | Recalculate quality component |
| `Submission.post_save` (abandoned) | Status change | Reliability penalty |
| `Invitation.post_save` (responded) | Accept or decline | Recalculate reliability |
| Daily cron (`apply_decay`) | 30+ days inactive | Apply activity decay |

---

## 8. Authentication Flow

```
1. POST /register/student/  →  Creates User + StudentProfile
                               Sends OTP via Africa's Talking SMS
                               Returns { user_id, email }  ← NO TOKEN

2. POST /verify-otp/        →  Validates OTP (max 5 attempts, 10 min expiry)
                               Clears OTP immediately on success
                               Returns { access_token, refresh_token, role }  ← ONLY HERE

3. POST /login/             →  For returning verified users
                               Returns { access_token, refresh_token, role }

4. POST /token/refresh/     →  Rotates refresh token (old one blacklisted)
                               Returns { access_token }
```

**JWT config:** Access token = 15 min | Refresh token = 30 days | Role embedded in payload

---

## 9. Privacy Rules

These are enforced in serializers — the last line of defence before data reaches the client.

| Field | Student (own) | Student (other) | Company | Admin |
|---|---|---|---|---|
| `email` | ✅ | ❌ | ❌ (until invitation accepted) | ✅ |
| `dit_student_id` | ✅ | ❌ | ❌ | ✅ |
| `dit_id_document_url` | ❌ | ❌ | ❌ | ✅ |
| `nikoscore` components | ✅ (full) | ❌ | ❌ (total only) | ✅ |
| `company_feedback` | ❌ | ❌ | ✅ (own tasks) | ✅ |
| `company_score` | ❌ | ❌ | ✅ (own tasks) | ✅ |
| `contact_released` | N/A | N/A | ✅ (only after student accepts) | ✅ |

**The most important test:** `company_feedback` must be absent from all student-facing responses. There is a dedicated test assertion in `tests/test_tasks.py::CompanyFeedbackPrivacyTest`.

---

## 10. Running Tests

```bash
# All tests
python manage.py test tests --settings=config.settings.development

# NikoScore engine only (run first — most critical)
python manage.py test tests.test_nikoscore --settings=config.settings.development

# Privacy tests
python manage.py test tests.test_tasks.CompanyFeedbackPrivacyTest --settings=config.settings.development

# Invitation contact gate
python manage.py test tests.test_invitations.ContactReleasedPrivacyTest --settings=config.settings.development

# With verbosity
python manage.py test tests -v 2 --settings=config.settings.development
```

### Pre-launch checklist (run before every release)

- [ ] `CompanyFeedbackPrivacyTest` passes — `company_feedback` not in student responses
- [ ] `test_unverified_company_cannot_post_task` passes — 403 on write operations
- [ ] `test_duplicate_submission_blocked` passes — one submission per student per task
- [ ] `test_locked_after_five_failed_attempts` passes — OTP lockout works
- [ ] `test_total_score_never_exceeds_100` passes — score boundary respected
- [ ] `test_contact_null_when_not_released` passes — privacy gate works
- [ ] `test_company_cannot_see_other_company_submissions` passes — ownership enforced

---

## 11. Deployment to Railway

### First deployment

```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login and link project
railway login
railway link

# 3. Set environment variables (do this in Railway dashboard or CLI)
railway variables set SECRET_KEY="your-secret-key"
railway variables set CLOUDINARY_CLOUD_NAME="..."
railway variables set AT_USERNAME="ton_production"
railway variables set AT_API_KEY="..."
railway variables set RESEND_API_KEY="..."
railway variables set RESEND_FROM_EMAIL="noreply@ton.co.tz"
railway variables set FRONTEND_URL="https://ton.vercel.app"
railway variables set DJANGO_SETTINGS_MODULE="config.settings.production"

# 4. Deploy
railway up
```

The `Procfile` handles everything:
```
web: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2
release: python manage.py migrate --no-input
```

`release` runs `migrate` automatically on every deploy — no manual migrations needed.

### PostgreSQL on Railway
Railway injects `DATABASE_URL` automatically when you add a PostgreSQL plugin. The production settings read it via `dj-database-url`.

---

## 12. Daily Cron Jobs

Configure these in Railway's cron scheduler. Both run at midnight EAT (21:00 UTC).

```
# Apply NikoScore activity decay
0 21 * * *  python manage.py apply_decay

# Expire stale invitations (14+ days old)
0 21 * * *  python manage.py expire_invitations
```

**`apply_decay`** — finds students inactive for 30+ days and reduces their activity component by 1 point per run. Floor is 0, never negative.

**`expire_invitations`** — marks any invitation in `sent` or `viewed` status that has passed its `expires_at` timestamp as `expired`. Students cannot respond to expired invitations.

---

## 13. Build Order

Follow this sequence. Each milestone has a gate test before proceeding.

| Step | Build | Gate Test |
|---|---|---|
| 1 | Auth app — register, OTP, JWT | Postman: register → OTP SMS → verify → receive token |
| 2 | StudentProfile + CompanyProfile + signals | Django admin: create student user, confirm profile auto-created |
| 3 | Admin verification queue (DIT + BRELA) | Admin: approve a company, verify a student DIT |
| 4 | NikoScore model + engine (profile component only) | Unit test: verified student has `component_profile > 0` |
| 5 | Task model + create/list/detail views | Postman: verified company posts task, student lists tasks |
| 6 | Submission model + submit/review views | Postman: student submits, company reviews, NikoScore updates |
| 7 | Full NikoScore engine (all 4 components) | Unit test suite: all component calculations with known inputs |
| 8 | Invitation + watchlist models and views | Postman: company watchlists student, sends invitation, student accepts |
| 9 | Notification service (email + SMS) | End-to-end: register a new account, receive OTP SMS in real life |
| 10 | Public profile endpoint | Browser: open `/api/students/public-profile/<id>/` unauthenticated — verify no private data leaks |

---

## 14. Critical Rules — Never Violate

These rules are non-negotiable. Violating any of them creates technical debt that is expensive to fix.

**UUID primary keys everywhere.** Never use auto-incrementing integers. Sequential IDs reveal your user count to competitors and enable enumeration attacks.

**Soft delete on critical tables.** Users, students, companies, tasks, and invitations are never hard-deleted. Use `soft_delete()`. Hard-deleting a student with submissions breaks NikoScore history and orphans foreign keys.

**NikoScore is always computed, never manually set.** The `nikoscores` table is a cache only. Always call the engine. Never write `student.nikoscore.total_score = 80` directly in a view.

**Tokens are issued ONLY after OTP verification.** Registration returns `user_id` only. No token at registration — ever.

**Company verification is enforced at the permission class level.** `IsCompany` checks both `role == 'company'` AND `verification_status == 'verified'`. An unverified company must receive 403 on all write operations.

**`company_feedback` is never exposed to students.** This field is private. Every student-facing serializer explicitly omits it. There is a test that asserts this. Run it before every release.

**`contact_released` is the privacy gate for student contact.** Company sees `null` for student contact until `contact_released=True`. This is enforced in the serializer `get_student_contact()` method with two conditions that must both pass.

**Always use `update_fields` when saving inside a `post_save` signal.** Saving the full object inside a post_save signal re-triggers the signal — infinite loop.

**Audit log records are immutable.** `NikoScoreEvent` records are never updated or deleted. The model raises `ValueError` if you attempt to update an existing record.

**Files are never stored in PostgreSQL.** Only Cloudinary URLs are stored. No `BinaryField` for documents or images — ever.
