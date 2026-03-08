# Alerts

Proactive notification system for transit operations — configurable alert rules with automatic background evaluation for maintenance, registration expiry, and transit delay conditions.

## Key Flows

### Create Alert Rule (Admin)

1. Validate rule configuration (name, type, severity, threshold_config)
2. Persist to `alert_rules` table
3. Background evaluator picks up enabled rules on next cycle

### Background Evaluation (Automatic)

1. Evaluator runs on configurable interval (default 60s)
2. Queries enabled rules from database
3. Per rule type:
   - `maintenance_due`: queries vehicles with `next_maintenance_date` within threshold
   - `registration_expiry`: queries vehicles with `registration_expiry` within threshold
   - `delay_threshold`: scans Redis for real-time vehicle delays exceeding threshold
4. Deduplicates via `find_active_duplicate` (partial unique index)
5. Creates new `AlertInstance` for each unmatched condition

### Acknowledge / Resolve Alert

1. Dispatcher or admin acknowledges alert (sets `acknowledged_at`, `acknowledged_by_id`)
2. Later resolves alert (sets `resolved_at`, status → `resolved`)
3. Partial unique index allows new alerts for same condition after resolution

## Database Schema

Table: `alert_rules`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK | Primary key |
| `name` | String(200) | NOT NULL | Rule display name |
| `description` | Text | nullable | Rule description |
| `rule_type` | String(30) | NOT NULL, CHECK | `delay_threshold`, `maintenance_due`, `registration_expiry`, `manual` |
| `severity` | String(20) | NOT NULL, default='medium' | `critical`, `high`, `medium`, `low`, `info` |
| `threshold_config` | JSONB | NOT NULL, default='{}' | Rule-specific thresholds (e.g., `{"days_before": 7}`) |
| `enabled` | Boolean | NOT NULL, default=True | Whether evaluator checks this rule |
| `created_at` | DateTime(tz) | NOT NULL | Auto-set |
| `updated_at` | DateTime(tz) | NOT NULL | Auto-set |

Table: `alert_instances`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK | Primary key |
| `title` | String(300) | NOT NULL | Alert display title |
| `severity` | String(20) | NOT NULL, default='medium' | Inherited from rule or set manually |
| `status` | String(20) | NOT NULL, default='active', indexed | `active`, `acknowledged`, `resolved` |
| `alert_type` | String(30) | NOT NULL | Rule type that generated this alert |
| `rule_id` | Integer | FK → alert_rules, nullable | Source rule (null for manual alerts) |
| `source_entity_type` | String(20) | nullable | `vehicle`, `route`, `driver` |
| `source_entity_id` | String(100) | nullable, indexed | Entity identifier |
| `details` | JSONB | nullable | Additional context |
| `acknowledged_at` | DateTime(tz) | nullable | When acknowledged |
| `acknowledged_by_id` | Integer | FK → users, nullable | Who acknowledged |
| `resolved_at` | DateTime(tz) | nullable | When resolved |
| `created_at` | DateTime(tz) | NOT NULL | Auto-set |
| `updated_at` | DateTime(tz) | NOT NULL | Auto-set |

Index: `ix_alert_dedup` — partial unique on `(rule_id, source_entity_type, source_entity_id)` WHERE `status = 'active'`

## Business Rules

1. Alert rules are admin-only (CRUD requires admin role)
2. Alert instances are accessible to admin and dispatcher roles
3. Summary endpoint (badge counts) is available to all authenticated users
4. Deduplication: only one active alert per rule+entity combination (enforced by partial unique index)
5. Acknowledged alerts can still be resolved; resolved alerts free the dedup slot for new alerts
6. Background evaluator respects `alerts_enabled` config flag and `alerts_check_interval_seconds`

## Integration Points

- **Vehicles**: Evaluator queries `Vehicle` model for maintenance dates and registration expiry
- **Transit (Redis)**: Evaluator reads `vehicle:*` Redis keys for real-time delay data
- **Auth**: `acknowledged_by_id` FK to users table; RBAC on all endpoints
- **App Lifespan**: Evaluator starts/stops alongside transit poller in `main.py`

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `alerts_enabled` | `True` | Enable/disable background evaluator |
| `alerts_check_interval_seconds` | `60` | Evaluation cycle interval |

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/alerts/rules` | admin | List alert rules (pagination, enabled filter) |
| GET | `/api/v1/alerts/rules/{rule_id}` | admin | Get single rule |
| POST | `/api/v1/alerts/rules` | admin | Create rule |
| PATCH | `/api/v1/alerts/rules/{rule_id}` | admin | Update rule |
| DELETE | `/api/v1/alerts/rules/{rule_id}` | admin | Delete rule |
| GET | `/api/v1/alerts/` | admin, dispatcher | List alerts (filters: status, severity, type, entity) |
| GET | `/api/v1/alerts/summary` | all authenticated | Dashboard badge counts by severity |
| GET | `/api/v1/alerts/{alert_id}` | admin, dispatcher | Get single alert |
| POST | `/api/v1/alerts/` | admin, dispatcher | Create manual alert |
| POST | `/api/v1/alerts/{alert_id}/acknowledge` | admin, dispatcher | Acknowledge alert |
| POST | `/api/v1/alerts/{alert_id}/resolve` | admin, dispatcher | Resolve alert |
