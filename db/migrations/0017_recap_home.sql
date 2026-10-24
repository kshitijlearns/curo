-- CURO v2.1 (PLAN_V2.md v2.1): the monthly Creator Recap, "What your followers will love",
-- and anonymous first-run sessions.

-- ------------------------------------------------------------------ Creator Recap
create table public.recaps (
  id                   uuid primary key default gen_random_uuid(),
  creator_id           uuid not null references public.creators (id) on delete cascade,
  kind                 text not null check (kind in ('first', 'monthly')),
  period_start         date not null,
  period_end           date not null,
  status               text not null default 'building'
                       check (status in ('building', 'ready', 'failed')),
  facts                jsonb not null default '{}',
  slides               jsonb not null default '[]',   -- ordered {slide_id, facts, copy, visual}
  creator_level        text,
  level_modifier       text,
  archetype            text,
  archetype_runner_up  text,
  archetype_evidence   jsonb not null default '{}',
  share_image_path     text,
  viewed_at            timestamptz,
  version              text not null default 'recap-v1',
  error                text,
  created_at           timestamptz not null default now(),
  unique (creator_id, kind, period_start)
);
create index recaps_creator_idx on public.recaps (creator_id, created_at desc);

alter table public.recaps enable row level security;
grant select, update on public.recaps to authenticated;
create policy recaps_own on public.recaps for all to authenticated
  using (creator_id = curo.current_creator_id())
  with check (creator_id = curo.current_creator_id());

-- ------------------------------------------------------------------ What your followers will love
create table public.follower_ideas (
  id          uuid primary key default gen_random_uuid(),
  creator_id  uuid not null references public.creators (id) on delete cascade,
  key         text not null,               -- stable across rebuilds (source + topic)
  title       text not null,
  why         text not null,
  evidence    jsonb not null default '{}',
  segment     text,
  score       numeric(5, 3) not null,
  parts       jsonb not null default '{}',  -- demand, proven, novelty (0–1)
  status      text not null default 'active' check (status in ('active', 'used', 'dismissed')),
  created_at  timestamptz not null default now(),
  unique (creator_id, key)
);
create index follower_ideas_creator_idx on public.follower_ideas (creator_id, score desc);

alter table public.follower_ideas enable row level security;
grant select on public.follower_ideas to authenticated;
create policy follower_ideas_read on public.follower_ideas for select to authenticated
  using (creator_id = curo.current_creator_id());
