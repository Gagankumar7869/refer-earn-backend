# Refer & Earn — Backend API Service

A production-grade RESTful backend for a referral reward system built with **Python 3.12**, **FastAPI**, **SQLAlchemy 2.0**, **Alembic**, and **MySQL 8.0 (InnoDB)**.

Designed with strict transactional boundaries, pessimistic row-level locking (`SELECT ... FOR UPDATE`), an append-only point ledger, idempotent reward operations, milestone progression (`Pioneer`, `Trailblazer`, `Visionary`, `Icon`), compensating reversals, and SQL-aggregated reconciliation.

---

## 1. Complete Assignment Requirements Coverage

Every required endpoint, optional supporting endpoint, and business rule from the specification is fully implemented and verified by automated tests:

### A. Member APIs (Section 1 of Specification)
| Method & Endpoint | Specification Requirement | Status |
| :--- | :--- | :--- |
| `POST /api/v1/referrals` | Create a referral for a newly registered user using a referral code, with validation against self-referral and duplicate attribution. | Implemented & Tested |
| `GET /api/v1/referrals/me` | Return the authenticated user's referral code/link, reward balance, referral counts, milestone progress, and referral activity. | Implemented & Tested |
| `GET /api/v1/referrals/milestones` | Return milestone thresholds, descriptions/perks, and the user's achievement/progress status. | Implemented & Tested |
| `GET /api/v1/referrals/transactions` | Return the authenticated user's paginated reward ledger history. | Implemented & Tested |

### B. Admin APIs (Section 2 of Specification)
| Method & Endpoint | Specification Requirement | Status |
| :--- | :--- | :--- |
| `GET /api/v1/referrals/admin/list` | List referrals with pagination and optional filters (`status`, `from_date`, `to_date`, `referrer_id`). | Implemented & Tested |
| `POST /api/v1/referrals/admin/approve/{referred_user_id}` | Approve an eligible referral, grant the referral reward exactly once, update referral progress, and evaluate milestone achievements. | Implemented & Tested |
| `POST /api/v1/referrals/admin/reject/{referred_user_id}` | Reject a pending referral without granting rewards. | Implemented & Tested |
| `POST /api/v1/referrals/admin/reverse/{referred_user_id}` | Reverse a previously approved referral, record the corresponding reward adjustment, and update referral progress according to policy. | Implemented & Tested |
| `POST /api/v1/referrals/admin/reconcile` | Compare stored reward balances and successful-referral counts against their underlying records; return any discrepancies. | Implemented & Tested |

### C. Optional & Supporting APIs Implemented (Section 3 of Specification + Auth)
To deliver a complete, auditable, and immediately testable system, we also implemented:
1. **`GET /api/v1/referrals/admin/{referral_id}` *(Section 3 Optional Spec)*:** Returns the full referral details, referrer/referred user metadata, and the chronological lifecycle history (`PENDING` -> `SUCCESSFUL` / `REJECTED` / `REVERSED`) read directly from the transactional `audit_logs` table. **Why included:** Fulfils the requirement that sensitive admin actions are auditable and inspectable.
2. **`GET /api/v1/referrals/admin/reconciliation-report/{audit_id}` *(Section 3 Optional Spec)*:** Retrieves a previously generated reconciliation report snapshot persisted in the `reconciliation_reports` table. **Why included:** Allows admins and compliance reviewers to inspect historical drift reports by `audit_id` without re-running reconciliation.
3. **`POST /api/v1/auth/login` & `GET /api/v1/auth/me` *(Supporting Auth APIs)*:** Issues signed JWT Bearer tokens for seeded Member and Admin accounts so all protected endpoints (`401`/`403`) can be tested directly in Swagger UI or via `curl`.

---

## 2. Tech Stack & Layered Architecture

* **Language & Runtime:** Python 3.11+ (tested on Python 3.12.10)
* **Web Framework:** FastAPI `0.115.0` & Uvicorn
* **Database & ORM:** MySQL 8.0 (InnoDB, `utf8mb4`), SQLAlchemy `2.0.35` (synchronous), PyMySQL `1.1.1`
* **Migrations:** Alembic `1.13.2`
* **Validation & Settings:** Pydantic v2 (`2.9.2`), `pydantic-settings`
* **Authentication & Security:** JWT (`PyJWT` HS256), Argon2 password hashing (`pwdlib[argon2]`)
* **Testing:** `pytest` `8.3.3` & `httpx` running against a dedicated MySQL test database (`refer_earn_test`)

### Layered Separation of Concerns
```text
HTTP Request
   │
   ▼
[ API Layer: app/api/v1/ ]              -> FastAPI Routers: HTTP parsing, Pydantic validation, JWT/RBAC dependencies
   │
   ▼
[ Service Layer: app/services/ ]        -> Business rules, lifecycle state machine, transaction boundaries (commit/rollback)
   │
   ▼
[ Repository Layer: app/repositories/ ] -> Pure SQLAlchemy queries and row locking (never commits transactions)
   │
   ▼
[ Database Layer: MySQL 8.0 InnoDB ]    -> Final authority via UNIQUE constraints, FKs, CHECK constraints, and row locks
```

### Project Directory Structure
```text
refer-earn-backend/
├── alembic/                  # Alembic migration environment and versioned schema scripts
├── app/
│   ├── api/v1/               # Route handlers (auth.py, referrals.py, admin_referrals.py)
│   ├── core/                 # Config, JWT/Argon2 security, RBAC dependencies, global error handlers
│   ├── models/               # SQLAlchemy 2.0 declarative models (entities.py)
│   ├── repositories/         # Data access layer (referral_repository.py)
│   ├── schemas/              # Pydantic v2 request/response DTOs (auth.py, referral.py)
│   ├── services/             # Business logic & transaction owners (referral, admin, reconciliation)
│   ├── database.py           # Engine and SessionLocal configuration
│   └── main.py               # FastAPI application entrypoint
├── scripts/
│   ├── setup_db.sql          # Creates refer_earn, refer_earn_test, and dedicated MySQL user
│   └── seed.py               # Seeds milestone tiers, 1 Admin user, and 3 Member users
├── tests/
│   └── test_referrals.py     # Automated pytest suite (lifecycle, concurrency, milestones, reconciliation)
├── .env.example              # Environment variable template
├── alembic.ini               # Alembic configuration
├── requirements.txt          # Pinned Python dependencies
└── README.md                 # Project documentation
```

---

## 3. Quickstart: Local Setup & Verification

### Prerequisites
* **Python 3.11 or 3.12** installed locally
* **MySQL 8.0** running locally on port `3306`

### Step 1: Clone the Repository & Create Virtual Environment
```bash
git clone [https://github.com/Gagankumar7869/refer-earn-backend.git](https://github.com/Gagankumar7869/refer-earn-backend.git)
cd refer-earn-backend

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

### Step 2: Create the MySQL Databases & Dedicated User
Run the SQL setup script to create both the development database (`refer_earn`), the isolated test database (`refer_earn_test`), and the local application user (`refer_user`):
```bash
mysql -u root -p < scripts/setup_db.sql
```

### Step 3: Configure Environment Variables
Copy `.env.example` to `.env` (default credentials match `scripts/setup_db.sql`):
```bash
cp .env.example .env
```

### Step 4: Run Database Migrations & Seed Initial Data
Apply the Alembic schema migrations and seed the 4 milestone definitions (`Pioneer`, `Trailblazer`, `Visionary`, `Icon`) along with default test accounts:
```bash
alembic upgrade head
python -m scripts.seed
```

### Step 5: Run the Automated Test Suite
The test suite runs against the real MySQL test database (`refer_earn_test`) to verify row-level locking, constraint enforcement, and multi-threaded concurrency:
```bash
pytest -v
```

### Step 6: Start the API Server
```bash
uvicorn app.main:app --reload
```
* **Interactive Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **ReDoc Documentation:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 4. Seeded Credentials for Testing

Running `python -m scripts.seed` provisions the following accounts:

| Role | Name | Email | Password | Referral Code |
| :--- | :--- | :--- | :--- | :--- |
| **ADMIN** | System Admin | `admin@eduskills.com` | `AdminPassword123!` | `ADMIN001` |
| **MEMBER** | Alice Referrer | `alice@example.com` | `MemberPassword123!` | `ALICE100` |
| **MEMBER** | Bob Member | `bob@example.com` | `MemberPassword123!` | `BOB20000` |
| **MEMBER** | Charlie Member | `charlie@example.com` | `MemberPassword123!` | `CHARLIE3` |

---

## 5. Database Design, Constraints & Indexes

All tables use **InnoDB** and `utf8mb4`:

1. **`users`**: `id` (PK), `name`, `email` (`UNIQUE`), `password_hash`, `referral_code` (`UNIQUE`), `role` (`MEMBER` | `ADMIN`), `created_at`.
2. **`referrals`**:
   * `id` (PK), `referrer_id` (FK -> `users.id`), `referred_user_id` (FK -> `users.id`, **`UNIQUE`** — guarantees one referred user cannot be attributed more than once).
   * `status` (`PENDING` | `SUCCESSFUL` | `REJECTED` | `REVERSED`), timestamps (`created_at`, `approved_at`, `rejected_at`, `reversed_at`), `reviewed_by`, `rejection_reason`, `reversal_reason`.
   * **`CHECK (referrer_id <> referred_user_id)`** — database-level guard preventing self-referral.
   * Indexes on `(status, created_at)` and `referrer_id`.
3. **`reward_ledger` (Append-Only Source of Truth)**:
   * `id` (PK), `user_id` (FK), `referral_id` (FK), `entry_type` (`REFERRAL_CREDIT` | `REFERRAL_REVERSAL`), `points` (signed integer: `+100` for credit, `-100` for reversal), `balance_after` (running balance snapshot).
   * `idempotency_key` (**`UNIQUE`**): deterministic key (`referral:{id}:approval` or `referral:{id}:reversal`) blocking duplicate credits or reversals.
   * `reversal_of_entry_id` (nullable self-FK linking a reversal debit directly to its original credit entry).
4. **`reward_balances` (Cached Projection)**:
   * `user_id` (PK, FK -> `users.id`), `balance`, `successful_referral_count`, `updated_at`.
5. **`milestone_definitions`**:
   * Seeded with the 4 required tiers: **Pioneer** (`5`), **Trailblazer** (`10`), **Visionary** (`25`), and **Icon** (`50`).
6. **`user_milestones`**:
   * Tracks unlocked tiers with **`UNIQUE (user_id, milestone_id)`** so each tier is awarded at most once.
7. **`audit_logs`**:
   * Written in the **same transaction** as every admin action (`APPROVE`, `REJECT`, `REVERSE`, `RECONCILE`), powering the referral lifecycle history endpoint.
8. **`reconciliation_reports`**:
   * Persists every reconciliation run (`id`/`audit_id`, `run_by`, `started_at`, `completed_at`, `status`, `total_users_checked`, `discrepancy_count`, and JSON `details`).

---

## 6. Key Engineering Decisions & Policies

| Area | Policy / Decision | Rationale |
| :--- | :--- | :--- |
| **Reward per Approval** | Configurable via `REFERRAL_REWARD_POINTS` (default `100` points) | Avoids magic numbers in business logic. |
| **Lifecycle State Machine** | Only `PENDING` -> `SUCCESSFUL` or `REJECTED`. Only `SUCCESSFUL` -> `REVERSED`. Invalid transitions return `409 Conflict`. | Prevents double-credits, re-approving rejected referrals, or reversing twice. |
| **Self-Referral Handling** | Rejected with `409 Conflict` (`SELF_REFERRAL_NOT_ALLOWED`) | Enforced in both service logic and MySQL `CHECK` constraint. |
| **Reversal Ledger Mechanics** | Inserts a new `REFERRAL_REVERSAL` row (`-100`) linked via `reversal_of_entry_id`. Original credit row is never modified or deleted. | Guarantees a strictly immutable, auditable append-only ledger. |
| **Milestone Policy on Reversal** | `successful_referral_count` decrements on reversal; historical `user_milestones` records (`achieved_at`) are retained while `currently_meets_threshold` reflects live count. | Preserves honest historical audit logs of when a badge was unlocked while accurately reporting current active progress. |
| **Reconciliation Policy** | Read-only detection using SQL `SUM` / `COUNT` aggregation; persists an audit report without silently mutating balances. | Silent auto-repairs hide bugs. Detection and repair must be separate, explicitly audited operations. |

---

## 7. Concurrency & Idempotency Strategy

To guarantee that concurrent admin approval requests (`POST /api/v1/referrals/admin/approve/{referred_user_id}`) never grant duplicate rewards, the service applies 4 layers of protection inside a **single database transaction**:

1. **Pessimistic Row Locking (`SELECT ... FOR UPDATE`):** Locks the `referrals` row first and the referrer's `reward_balances` row second (consistent lock ordering prevents deadlocks).
2. **In-Lock State Verification:** Verifies `referral.status == PENDING` after acquiring the lock. Any concurrent request waiting on the lock sees `SUCCESSFUL` once the first transaction commits and immediately exits with `409 Conflict`.
3. **Deterministic Unique Idempotency Key:** The `reward_ledger` insert includes `idempotency_key = "referral:{id}:approval"` (`UNIQUE` constraint). Even if application checks were bypassed, MySQL rejects a second credit with `IntegrityError` (mapped to `409 Conflict`).
4. **Verified by Multi-Threaded Test:** `test_concurrent_approvals_grant_reward_exactly_once` runs 8 concurrent threads against the same pending referral on MySQL and asserts exactly `1` HTTP `200` response, `7` HTTP `409` responses, `1` ledger entry, and `+100` balance.

---

## 8. API Reference & Sample Requests / Responses

### Standard Error Response Envelope
All error responses (`401`, `403`, `404`, `409`, `422`, `500`) follow one consistent schema:
```json
{
  "error": {
    "code": "INVALID_LIFECYCLE_TRANSITION",
    "message": "Cannot approve referral in 'SUCCESSFUL' state. Only PENDING referrals can be approved.",
    "details": []
  }
}
```

### 8.1 Supporting Auth: Login (`POST /api/v1/auth/login`)
```bash
curl -X POST [http://127.0.0.1:8000/api/v1/auth/login](http://127.0.0.1:8000/api/v1/auth/login) \
  -H "Content-Type: application/json" \
  -d '{"email": "bob@example.com", "password": "MemberPassword123!"}'
```
**Response (`200 OK`):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": 3,
    "name": "Bob Member",
    "email": "bob@example.com",
    "role": "MEMBER",
    "referral_code": "BOB20000"
  }
}
```

### 8.2 Member API 1: Create Referral (`POST /api/v1/referrals`)
```bash
curl -X POST [http://127.0.0.1:8000/api/v1/referrals](http://127.0.0.1:8000/api/v1/referrals) \
  -H "Authorization: Bearer <BOB_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"referral_code": "ALICE100"}'
```
**Response (`201 Created`):**
```json
{
  "id": 1,
  "referrer_id": 2,
  "referred_user_id": 3,
  "referral_code_used": "ALICE100",
  "status": "PENDING",
  "created_at": "2026-10-23T06:16:29",
  "approved_at": null,
  "rejected_at": null,
  "reversed_at": null,
  "rejection_reason": null,
  "reversal_reason": null
}
```

### 8.3 Member API 2: My Referral Dashboard (`GET /api/v1/referrals/me`)
```bash
curl -X GET [http://127.0.0.1:8000/api/v1/referrals/me](http://127.0.0.1:8000/api/v1/referrals/me) \
  -H "Authorization: Bearer <ALICE_TOKEN>"
```
**Response (`200 OK`):**
```json
{
  "user_id": 2,
  "name": "Alice Referrer",
  "email": "alice@example.com",
  "referral_code": "ALICE100",
  "referral_link": "[https://app.eduskills.com/register?ref=ALICE100](https://app.eduskills.com/register?ref=ALICE100)",
  "reward_balance": 100,
  "referral_counts": {
    "total": 1,
    "pending": 0,
    "successful": 1,
    "rejected": 0,
    "reversed": 0
  },
  "milestone_progress": {
    "current_tier": null,
    "next_tier": "Pioneer",
    "next_threshold": 5,
    "successful_referrals": 1,
    "referrals_remaining_to_next": 4
  },
  "recent_activity": [
    {
      "referral_id": 1,
      "referred_user_id": 3,
      "referred_user_name": "Bob Member",
      "status": "SUCCESSFUL",
      "created_at": "2026-10-23T06:16:29",
      "approved_at": "2026-10-23T06:20:00"
    }
  ]
}
```

### 8.4 Member API 3: Milestones & Progress (`GET /api/v1/referrals/milestones`)
```bash
curl -X GET [http://127.0.0.1:8000/api/v1/referrals/milestones](http://127.0.0.1:8000/api/v1/referrals/milestones) \
  -H "Authorization: Bearer <ALICE_TOKEN>"
```
**Response (`200 OK`):**
```json
{
  "successful_referral_count": 1,
  "current_tier": null,
  "next_tier": "Pioneer",
  "referrals_remaining_to_next": 4,
  "milestones": [
    {
      "id": 1,
      "threshold": 5,
      "name": "Pioneer",
      "description": "Reach 5 successful referrals",
      "perk": "Priority community badge and early feature access",
      "status": "IN_PROGRESS",
      "achieved_at": null,
      "currently_meets_threshold": false
    },
    {
      "id": 2,
      "threshold": 10,
      "name": "Trailblazer",
      "description": "Reach 10 successful referrals",
      "perk": "Exclusive Trailblazer merchandise kit",
      "status": "LOCKED",
      "achieved_at": null,
      "currently_meets_threshold": false
    }
  ]
}
```

### 8.5 Member API 4: Paginated Ledger Transactions (`GET /api/v1/referrals/transactions`)
```bash
curl -X GET "[http://127.0.0.1:8000/api/v1/referrals/transactions?page=1&page_size=20](http://127.0.0.1:8000/api/v1/referrals/transactions?page=1&page_size=20)" \
  -H "Authorization: Bearer <ALICE_TOKEN>"
```
**Response (`200 OK`):**
```json
{
  "items": [
    {
      "id": 1,
      "referral_id": 1,
      "entry_type": "REFERRAL_CREDIT",
      "points": 100,
      "balance_after": 100,
      "reversal_of_entry_id": null,
      "created_at": "2026-10-23T06:20:00"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total_items": 1,
  "total_pages": 1
}
```

### 8.6 Admin API 1: List & Filter Referrals (`GET /api/v1/referrals/admin/list`)
```bash
curl -X GET "[http://127.0.0.1:8000/api/v1/referrals/admin/list?status=PENDING&page=1&page_size=20](http://127.0.0.1:8000/api/v1/referrals/admin/list?status=PENDING&page=1&page_size=20)" \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```

### 8.7 Admin API 2: Approve Referral (`POST /api/v1/referrals/admin/approve/{referred_user_id}`)
```bash
curl -X POST [http://127.0.0.1:8000/api/v1/referrals/admin/approve/3](http://127.0.0.1:8000/api/v1/referrals/admin/approve/3) \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```

### 8.8 Admin API 3: Reject Referral (`POST /api/v1/referrals/admin/reject/{referred_user_id}`)
```bash
curl -X POST [http://127.0.0.1:8000/api/v1/referrals/admin/reject/3](http://127.0.0.1:8000/api/v1/referrals/admin/reject/3) \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Duplicate account verification failed"}'
```

### 8.9 Admin API 4: Reverse Approved Referral (`POST /api/v1/referrals/admin/reverse/{referred_user_id}`)
```bash
curl -X POST [http://127.0.0.1:8000/api/v1/referrals/admin/reverse/3](http://127.0.0.1:8000/api/v1/referrals/admin/reverse/3) \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Order refunded / policy violation"}'
```

### 8.10 Admin API 5: Run Reconciliation (`POST /api/v1/referrals/admin/reconcile`)
```bash
curl -X POST [http://127.0.0.1:8000/api/v1/referrals/admin/reconcile](http://127.0.0.1:8000/api/v1/referrals/admin/reconcile) \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```
**Response (`200 OK`):**
```json
{
  "audit_id": 1,
  "run_by": 1,
  "started_at": "2026-10-23T06:30:00",
  "completed_at": "2026-10-23T06:30:00",
  "status": "CLEAN",
  "total_users_checked": 4,
  "discrepancy_count": 0,
  "discrepancies": [],
  "details": {
    "discrepancies": [],
    "summary": {
      "balance_drift_count": 0,
      "counter_drift_count": 0,
      "ledger_snapshot_drift_count": 0
    }
  }
}
```

### 8.11 Optional Admin API 6 (Section 3 Spec): Referral Details & Lifecycle History (`GET /api/v1/referrals/admin/{referral_id}`)
```bash
curl -X GET [http://127.0.0.1:8000/api/v1/referrals/admin/1](http://127.0.0.1:8000/api/v1/referrals/admin/1) \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```
**Response (`200 OK`):**
```json
{
  "referral": {
    "id": 1,
    "referrer_id": 2,
    "referred_user_id": 3,
    "referral_code_used": "ALICE100",
    "status": "REVERSED",
    "created_at": "2026-10-23T06:16:29",
    "approved_at": "2026-10-23T06:20:00",
    "rejected_at": null,
    "reversed_at": "2026-10-23T06:25:00",
    "rejection_reason": null,
    "reversal_reason": "Order refunded / policy violation"
  },
  "referrer_name": "Alice Referrer",
  "referrer_email": "alice@example.com",
  "referred_user_name": "Bob Member",
  "referred_user_email": "bob@example.com",
  "lifecycle_history": [
    {
      "id": 1,
      "actor_id": 1,
      "action": "APPROVE",
      "from_status": "PENDING",
      "to_status": "SUCCESSFUL",
      "reason": "Approved by admin",
      "created_at": "2026-10-23T06:20:00"
    },
    {
      "id": 2,
      "actor_id": 1,
      "action": "REVERSE",
      "from_status": "SUCCESSFUL",
      "to_status": "REVERSED",
      "reason": "Order refunded / policy violation",
      "created_at": "2026-10-23T06:25:00"
    }
  ]
}
```

### 8.12 Optional Admin API 7 (Section 3 Spec): Retrieve Persisted Reconciliation Report (`GET /api/v1/referrals/admin/reconciliation-report/{audit_id}`)
```bash
curl -X GET [http://127.0.0.1:8000/api/v1/referrals/admin/reconciliation-report/1](http://127.0.0.1:8000/api/v1/referrals/admin/reconciliation-report/1) \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```
