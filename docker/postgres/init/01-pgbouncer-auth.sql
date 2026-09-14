-- PgBouncer credential lookup (`auth_query`). Runs once, on first initialisation of the
-- data volume, in the `postgres` database. Idempotent, so re-running it by hand against
-- an existing cluster is safe — and necessary, because Docker only runs
-- /docker-entrypoint-initdb.d on an empty volume:
--
--     docker compose exec -T db psql -U postgres -d postgres \
--         < docker/postgres/init/01-pgbouncer-auth.sql
--
-- WHY THIS EXISTS
--
-- Provisioning creates one login role per client business (`optique_u000047`), minutes
-- after PgBouncer started. Web and Celery traffic goes through PgBouncer
-- (`Client.connection_params(direct=False)`) and authenticates as that role. With a
-- static `auth_file` PgBouncer only knows the roles somebody last typed into it, so every
-- newly provisioned client is refused at the pooler — which would make a new client a
-- deployment (edit the file, reload the pooler) rather than a provisioning operation, and
-- TENANT-01 says it is a provisioning operation.
--
-- `auth_query` moves the credential lookup into PostgreSQL, where the provisioner has
-- already written it. Nothing has to be reloaded, ever.
--
-- WHY A FUNCTION RATHER THAN `SELECT ... FROM pg_shadow`
--
-- `pg_shadow` is readable by superusers only. Pointing `auth_query` straight at it forces
-- `auth_user` to be a superuser, i.e. the pooler's own stored credential becomes the keys
-- to the whole cluster. A `SECURITY DEFINER` function owned by `postgres` does the read
-- instead, and `EXECUTE` on it is granted to one unprivileged role and revoked from
-- PUBLIC.

-- --------------------------------------------------------------------------------------
-- The role PgBouncer runs the lookup as.
-- --------------------------------------------------------------------------------------
-- Deliberately the narrowest role in the cluster: it may log in, connect to `postgres`,
-- and call exactly one function. It owns nothing, creates nothing, inherits nothing.
-- Development-only credential, matching docker/pgbouncer/userlist.txt — PgBouncer cannot
-- look up the credential it needs in order to run the lookup, so `auth_user`'s own
-- password is the one thing that must still live in a file. In production that file holds
-- this single line and nothing else.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pgbouncer_auth') THEN
        CREATE ROLE pgbouncer_auth WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD 'pgbouncer_auth_dev_only';
    ELSE
        ALTER ROLE pgbouncer_auth WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD 'pgbouncer_auth_dev_only';
    END IF;
END
$$;

-- --------------------------------------------------------------------------------------
-- The lookup function.
-- --------------------------------------------------------------------------------------
-- Created in `postgres`, and only in `postgres`. PgBouncer runs `auth_query` inside the
-- database the client asked for unless `auth_dbname` says otherwise; ours does say
-- otherwise, and it has to. With one database per client there is no other workable
-- answer: a function installed per database would be missing from the next client's
-- database the moment it is created, which is the same "needs a deployment step" failure
-- `auth_query` is here to remove.
--
-- Output column names are `username`/`password`, **not** `usename`/`passwd`: in a
-- `RETURNS TABLE` function the output parameter names are in scope inside the body, so
-- reusing pg_shadow's own column names makes every reference to them ambiguous and the
-- function fails to create.
--
-- `SET search_path` is not decoration on a `SECURITY DEFINER` function. Without it, any
-- role able to create objects in a schema earlier on the caller's `search_path` can
-- shadow an unqualified name inside the body and have it executed as the owner — here,
-- as a superuser.
CREATE OR REPLACE FUNCTION public.pgbouncer_get_auth(p_usename text)
RETURNS TABLE (username text, password text)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT s.usename::text, s.passwd::text
    FROM pg_catalog.pg_shadow AS s
    WHERE s.usename = p_usename;
$$;

ALTER FUNCTION public.pgbouncer_get_auth(text) OWNER TO postgres;

-- PostgreSQL grants EXECUTE on a new function to PUBLIC by default, so this REVOKE is the
-- whole of the access control and its absence is silent. Without it, *any* role that can
-- reach this database — every client role, since `postgres` is the maintenance database —
-- could call a superuser-owned function and read every other client's SCRAM verifier.
-- That is the same shape as the `REVOKE CONNECT ... FROM PUBLIC` fix in
-- `SqlProvisioner._restrict_connect`: a default grant that quietly undoes the isolation.
REVOKE ALL ON FUNCTION public.pgbouncer_get_auth(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.pgbouncer_get_auth(text) TO pgbouncer_auth;

-- `auth_dbname` points at this database, so the lookup role must be able to open it.
GRANT CONNECT ON DATABASE postgres TO pgbouncer_auth;
