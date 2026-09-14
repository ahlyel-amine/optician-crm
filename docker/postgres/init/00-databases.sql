-- Local development bootstrap. Runs once, on first initialisation of the data volume.
-- Idempotent, so re-running it by hand against an existing cluster is safe — and a
-- cluster initialised before a given revision of this file MUST have it re-run by hand,
-- because Docker only executes /docker-entrypoint-initdb.d on an empty volume:
--   docker compose exec -T db psql -v ON_ERROR_STOP=1 -U postgres -d postgres \
--       -f /docker-entrypoint-initdb.d/00-databases.sql
--
-- This creates ONLY the control-plane database and the application role. Client
-- databases are never created here — they are created by the provisioning state machine
-- (plan 02-04), directly against PostgreSQL, with the ICU locale provider.

-- The application role. CREATEDB is required for two distinct reasons:
--   1. pytest-django creates and drops test_optique_* databases as this role.
--   2. the provisioning path creates client databases as this role.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'optique_app') THEN
        -- Development-only credential. Production roles are created by provisioning
        -- with a generated password, stored Fernet-encrypted in the control plane.
        CREATE ROLE optique_app WITH LOGIN CREATEDB PASSWORD 'optique_dev_only';
    ELSE
        ALTER ROLE optique_app WITH LOGIN CREATEDB PASSWORD 'optique_dev_only';
    END IF;
END
$$;

-- The control-plane database: identity, Client rows, business membership and permission
-- grants. It holds no business data — no ordonnances, no factures, no caisse.
-- CREATE DATABASE cannot run inside a transaction block, and a DO $$ ... $$ block is a
-- transaction, so this uses \gexec rather than a conditional block.
SELECT 'CREATE DATABASE optique_control OWNER optique_app'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'optique_control')
\gexec

-- --------------------------------------------------------------------------------------
-- Keep every other role out of the control-plane database (CLAUDE.md #12).
-- --------------------------------------------------------------------------------------
-- PostgreSQL grants CONNECT on every new database to PUBLIC, so without this REVOKE any
-- role that can reach this cluster — every `optique_u######` client role — can open the
-- control plane with psql. From Phase 3 on, this database holds the password hashes and
-- every permission grant of the WHOLE FLEET, so that is a fleet-wide compromise reachable
-- from a single client's credential.
--
-- This is the fourth instance of the same default in this project: client databases
-- (SqlProvisioner._restrict_connect), the `postgres` maintenance database and the
-- SECURITY DEFINER verifier function (01-pgbouncer-auth.sql) were the first three. All
-- four were invisible to code review, because the guarantee each one broke is written in
-- Python, one layer above.
--
-- Order matters: revoke from PUBLIC first, then grant back to the single role that needs
-- it. `postgres` and any other superuser bypass privilege checks and are unaffected.
REVOKE CONNECT ON DATABASE optique_control FROM PUBLIC;
GRANT  CONNECT ON DATABASE optique_control TO optique_app;

-- Let the app role connect to the maintenance database. Django's test runner and the
-- provisioning code both connect to `postgres` in order to issue CREATE DATABASE.
GRANT CONNECT ON DATABASE postgres TO optique_app;
