-- Additive patch for installations that already ran the ERP schema.
-- Adds account deactivation support without changing existing account states.
BEGIN;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

CREATE INDEX IF NOT EXISTS idx_users_active_role
    ON users(is_active, role);

COMMIT;
