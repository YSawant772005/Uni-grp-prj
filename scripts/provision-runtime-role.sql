-- Manual one-time procedure for the existing local database.
-- Do not run until the owner has approved modifying the uni_shortlist database roles.
\set ON_ERROR_STOP on
\getenv app_password APP_DB_PASSWORD
DO $$
BEGIN
    IF current_database() <> 'uni_shortlist' OR current_user <> 'uni_shortlist' THEN
        RAISE EXCEPTION 'Refusing runtime-role setup: connect as uni_shortlist to uni_shortlist';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'uni_shortlist_app') THEN
        RAISE EXCEPTION 'Role uni_shortlist_app already exists; inspect it before changing credentials or grants';
    END IF;
END
$$;

-- Pass a generated secret through the psql process environment. Never put it in
-- this tracked file or a command-line argument.
SELECT CASE
    WHEN length(:'app_password') < 32 THEN
        'DO $guard$ BEGIN RAISE EXCEPTION ''APP_DB_PASSWORD must contain at least 32 characters''; END $guard$'
    ELSE format(
        'CREATE ROLE uni_shortlist_app LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS',
        :'app_password'
    )
END
\gexec

GRANT CONNECT ON DATABASE uni_shortlist TO uni_shortlist_app;
GRANT USAGE ON SCHEMA public TO uni_shortlist_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO uni_shortlist_app;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO uni_shortlist_app;
ALTER DEFAULT PRIVILEGES FOR ROLE uni_shortlist IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO uni_shortlist_app;
ALTER DEFAULT PRIVILEGES FOR ROLE uni_shortlist IN SCHEMA public
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO uni_shortlist_app;
