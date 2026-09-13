-- Local development bootstrap. Runs once, on first initialisation of the data volume.
-- Idempotent, so re-running it by hand against an existing cluster is safe.
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

-- Let the app role connect to the maintenance database. Django's test runner and the
-- provisioning code both connect to `postgres` in order to issue CREATE DATABASE.
GRANT CONNECT ON DATABASE postgres TO optique_app;
