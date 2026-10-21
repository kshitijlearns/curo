-- Baseline: extensions and CURO's helper schema.
-- Runs unchanged on local Postgres (with db/local shim) and on Supabase.

-- pgvector, in the `extensions` schema as Supabase installs it.
create extension if not exists vector with schema extensions;

-- Helper functions used by Row Level Security policies live here (added with the
-- full schema in Phase 2).
create schema if not exists curo;
grant usage on schema curo to authenticated, service_role;
