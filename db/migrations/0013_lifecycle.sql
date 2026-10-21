-- Phase 9: account deletion, matching a posted reel to its simulation, the accuracy record.

-- A deletion request (DELETE /v1/me). The cleanup job carries it out straight away, and the
-- daily run picks up any that didn't finish.
alter table public.creators
  add column deletion_requested_at timestamptz;

-- match_posted_reel (MVP doc §9): a new reel of the creator's that looks like one they
-- simulated or drafted. The creator confirms it before Home compares the reel with its
-- simulation and the accuracy record counts it (logic doc §15 step 2).
create table public.reel_matches (
  id            uuid primary key default gen_random_uuid(),
  creator_id    uuid not null references public.creators (id) on delete cascade,
  reel_id       uuid not null references public.reels (id) on delete cascade,
  simulation_id uuid references public.simulations (id) on delete cascade,
  project_id    uuid references public.projects (id) on delete cascade,
  score         numeric(4, 3) not null,
  reasons       jsonb not null default '[]',
  status        text not null default 'pending'
                check (status in ('pending', 'confirmed', 'rejected')),
  created_at    timestamptz not null default now(),
  decided_at    timestamptz,
  unique (reel_id)
);
create index reel_matches_creator_idx on public.reel_matches (creator_id, status);

alter table public.reel_matches enable row level security;
grant select, update on public.reel_matches to authenticated;
create policy reel_matches_own on public.reel_matches for all to authenticated
  using (creator_id = curo.current_creator_id())
  with check (creator_id = curo.current_creator_id());
