-- CURO v2 plans, credits, usage and costs (PLAN_V2.md §4.6). The server enforces every limit;
-- the credit ledger is append-only (no update, no delete for anyone but the owner's cascade).

create table public.plans (
  key                  text primary key,            -- 'free' | 'pro'
  label                text not null,
  price_usd            numeric(8, 2) not null,
  projects_per_month   integer not null,
  simulations_per_month integer not null,
  chat_per_month       integer not null
);
insert into public.plans values
  ('free', 'Free', 0, 2, 2, 10),
  ('pro', 'Pro', 30, 10, 10, 100);

create table public.subscriptions (
  creator_id    uuid primary key references public.creators (id) on delete cascade,
  plan          text not null references public.plans (key),
  status        text not null default 'active' check (status in ('active', 'cancelled', 'past_due')),
  provider      text not null default 'mock',
  provider_ref  text,
  period_start  timestamptz not null,
  period_end    timestamptz not null,
  created_at    timestamptz not null default now()
);

create table public.credit_ledger (
  id          bigint generated always as identity primary key,
  creator_id  uuid not null references public.creators (id) on delete cascade,
  kind        text not null check (kind in ('grant', 'spend', 'topup', 'refund')),
  resource    text not null check (resource in ('project', 'simulation', 'chat')),
  amount      integer not null check (amount > 0),
  reason      text not null,
  ref_id      text,
  period_end  timestamptz,       -- a grant expires at its period's end; top-ups never do
  created_at  timestamptz not null default now()
);
create index credit_ledger_creator_idx on public.credit_ledger (creator_id, resource, created_at);
-- A spend for the same thing is recorded once (retries never double-charge).
create unique index credit_ledger_spend_once on public.credit_ledger (creator_id, kind, resource, ref_id)
  where ref_id is not null;

create or replace function curo.ledger_append_only() returns trigger
  language plpgsql as $$
begin
  raise exception 'credit_ledger is append-only';
end $$;
create trigger credit_ledger_no_update before update on public.credit_ledger
  for each row execute function curo.ledger_append_only();

create table public.usage_ledger (
  id             bigint generated always as identity primary key,
  creator_id     uuid references public.creators (id) on delete set null,
  provider       text not null,      -- anthropic | gemini | apify | brightdata | ...
  model          text,
  task           text,               -- T1…T22, collection, embedding
  tokens_in      integer,
  tokens_out     integer,
  results        integer,            -- Apify results
  cost_usd       numeric(10, 5) not null default 0,
  ref_id         text,
  created_at     timestamptz not null default now()
);
create index usage_ledger_creator_idx on public.usage_ledger (creator_id, created_at);

alter table public.creators add column is_admin boolean not null default false;

alter table public.plans enable row level security;
alter table public.subscriptions enable row level security;
alter table public.credit_ledger enable row level security;
alter table public.usage_ledger enable row level security;
grant select on public.plans, public.subscriptions, public.credit_ledger to authenticated;
create policy plans_read on public.plans for select to authenticated using (true);
create policy subscriptions_own on public.subscriptions for select to authenticated
  using (creator_id = curo.current_creator_id());
create policy credit_ledger_own on public.credit_ledger for select to authenticated
  using (creator_id = curo.current_creator_id());
-- usage_ledger: no policy for authenticated; only the service role (admin costs page) reads it.

-- Revisions per project (PLAN_V2 §4.6): a project credit includes up to PROJECT_REVISIONS.
alter table public.projects add column revisions integer not null default 0;
