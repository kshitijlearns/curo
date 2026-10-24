-- Local stand-in for what Supabase already provides. Idempotent.
-- NEVER run this against a Supabase project (python -m curo.db.migrate --no-shim).
--
-- Mirrors Supabase: roles anon / authenticated / service_role, the `auth` and
-- `extensions` schemas, auth.users, and auth.jwt() / auth.uid() / auth.role(),
-- which read the JWT claims the API sets per request (request.jwt.claims).

create schema if not exists extensions;
create schema if not exists auth;

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    create role anon nologin noinherit;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then
    create role authenticated nologin noinherit;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'service_role') then
    create role service_role nologin noinherit bypassrls;
  end if;
end $$;

-- The API connects as the database owner and switches role per request
-- (SET LOCAL ROLE authenticated), as Supabase's own clients do.
grant anon, authenticated, service_role to current_user;

grant usage on schema extensions to anon, authenticated, service_role;
grant usage on schema auth to anon, authenticated, service_role;

create table if not exists auth.users (
  id              uuid primary key default gen_random_uuid(),
  email           text unique,
  created_at      timestamptz not null default now(),
  last_sign_in_at timestamptz
);

-- Anonymous first-run sessions (v2.1), as Supabase Auth's own column.
alter table auth.users add column if not exists is_anonymous boolean not null default false;

-- One-time codes for the local email-OTP auth stub (Supabase Auth replaces this).
create table if not exists auth.local_otp_codes (
  email      text primary key,
  code_hash  text not null,
  expires_at timestamptz not null,
  attempts   int not null default 0
);

create or replace function auth.jwt() returns jsonb
  language sql stable
as $$
  select coalesce(nullif(current_setting('request.jwt.claims', true), ''), '{}')::jsonb
$$;

create or replace function auth.uid() returns uuid
  language sql stable
as $$
  select nullif(auth.jwt() ->> 'sub', '')::uuid
$$;

create or replace function auth.role() returns text
  language sql stable
as $$
  select nullif(auth.jwt() ->> 'role', '')
$$;

grant execute on function auth.jwt(), auth.uid(), auth.role() to anon, authenticated, service_role;
