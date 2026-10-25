-- CURO v2.2 (PLAN_V2.md v2.2): Follower Personas. Four characters per creator built from
-- clusters of public comments; they react to Studio drafts, chat in character and seed the
-- Simulator's AI audience. "What your followers will love" (v2.1) is removed.

-- ------------------------------------------------------------------ comment embeddings (cache)
-- One vector per comment ("text · theme · intent · language"); the model is recorded and a
-- vector from another model is never compared (the build re-embeds those).
create table public.comment_embeddings (
  comment_id  uuid primary key references public.comments (id) on delete cascade,
  embedding   extensions.vector(768) not null,
  model       text not null,
  created_at  timestamptz not null default now()
);

-- ------------------------------------------------------------------ builds
create table public.persona_builds (
  id            uuid primary key default gen_random_uuid(),
  creator_id    uuid not null references public.creators (id) on delete cascade,
  version       integer not null,
  reason        text not null,                 -- onboarding | refine | monthly | midmonth | manual
  fast          boolean not null default false,
  is_starter    boolean not null default false,
  n_comments    integer not null default 0,    -- usable comments the build saw
  n_reels       integer not null default 0,
  n_labelled    integer not null default 0,    -- of n_comments, how many had labels
  comments_seen integer not null default 0,    -- all collected comments (the mid-month trigger)
  stability     numeric(5, 4),                 -- mean adjusted Rand index of the kept clustering
  created_at    timestamptz not null default now(),
  unique (creator_id, version)
);

-- ------------------------------------------------------------------ the personas
-- Updated in place: a persona keeps its id (and name, colour, seed) for life while its group
-- keeps matching (centroid cosine >= 0.8); a replaced persona is retired, never deleted, so
-- opinions, chats, history and AI agents stay linked.
create table public.follower_personas (
  id            uuid primary key default gen_random_uuid(),
  creator_id    uuid not null references public.creators (id) on delete cascade,
  slot          smallint not null check (slot between 1 and 4),   -- share order, 1 = largest
  name          text not null,
  short_name    text not null,
  tagline       text not null,
  share         numeric(5, 4) not null check (share > 0 and share <= 1),
  color         text not null check (color in ('blue', 'lavender', 'pink', 'ink')),
  avatar_seed   integer not null,
  confidence    text not null check (confidence in ('low', 'medium', 'high')),
  profile       jsonb not null default '{}',   -- written fields + "evidence" (code facts)
  thought       jsonb not null default '{}',   -- T26: thought, mood, loves, wants_more
  centroid      extensions.vector(768),        -- the group's comments (identity matching)
  topic_vector  extensions.vector(768),        -- its favourite reels + what it comes for
  version       integer not null,
  period_start  date not null,
  period_end    date not null,
  is_starter    boolean not null default false,
  n_comments    integer not null default 0,
  n_reels       integer not null default 0,
  retired_at    timestamptz,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  unique (creator_id, slot, version)
);
create index follower_personas_active_idx
  on public.follower_personas (creator_id, slot) where retired_at is null;

create table public.persona_history (
  persona_id  uuid not null references public.follower_personas (id) on delete cascade,
  creator_id  uuid not null references public.creators (id) on delete cascade,
  period      date not null,                    -- the first day of the month
  share       numeric(5, 4) not null,
  mood        text not null,
  sentiment   numeric(6, 4),                    -- positive share − negative share
  n_comments  integer not null default 0,
  version     integer not null,
  primary key (persona_id, period)
);

-- ------------------------------------------------------------------ opinions (Studio, Simulator)
create table public.persona_opinions (
  id              uuid primary key default gen_random_uuid(),
  creator_id      uuid not null references public.creators (id) on delete cascade,
  persona_id      uuid not null references public.follower_personas (id) on delete cascade,
  project_id      uuid references public.projects (id) on delete cascade,
  target_type     text not null
                  check (target_type in ('idea', 'script', 'storyboard', 'caption', 'simulation')),
  target_id       uuid not null,
  target_version  integer not null default 1,
  reaction        text not null check (reaction in ('watch_all', 'watch', 'scroll_past', 'skip')),
  score_model     numeric(5, 2),                -- T27's 0–100 (null: the model gave none)
  score_code      numeric(5, 2) not null,       -- the code-side fit, 0–100
  score           numeric(5, 2) not null,       -- the blend shown
  would           jsonb not null default '{}',  -- like, comment, share, save
  opinion         text not null,
  win_them_over   text,
  evidence_ids    text[] not null default '{}',
  model_version   text not null,
  created_at      timestamptz not null default now(),
  unique (persona_id, target_type, target_id, target_version)
);
create index persona_opinions_target_idx
  on public.persona_opinions (creator_id, target_type, target_id, target_version);

-- ------------------------------------------------------------------ persona chat (T28)
create table public.persona_messages (
  id            uuid primary key default gen_random_uuid(),
  seq           bigint generated always as identity,  -- order within a second (and a frozen clock)
  creator_id    uuid not null references public.creators (id) on delete cascade,
  persona_id    uuid not null references public.follower_personas (id) on delete cascade,
  context_type  text not null check (context_type in ('home', 'studio', 'simulator')),
  context_id    uuid,
  role          text not null check (role in ('user', 'persona')),
  content       text not null,
  created_at    timestamptz not null default now()
);
create index persona_messages_thread_idx
  on public.persona_messages (persona_id, context_type, context_id, seq);

-- ------------------------------------------------------------------ the Simulator
alter table public.audience_personas
  add column persona_id uuid references public.follower_personas (id) on delete set null;
-- Per-persona calibration factors ('' = the overall factor, the fallback).
alter table public.persona_calibrations add column segment text not null default '';
alter table public.persona_calibrations drop constraint persona_calibrations_pkey;
alter table public.persona_calibrations add primary key (creator_id, version, segment, metric);

-- ------------------------------------------------------------------ costs by feature
alter table public.usage_ledger add column feature text;  -- personas, studio_personas, …

-- ------------------------------------------------------------------ removed (v2.1)
drop table public.follower_ideas;

-- ------------------------------------------------------------------ Row Level Security
alter table public.comment_embeddings enable row level security;  -- service role only
alter table public.persona_builds enable row level security;
alter table public.follower_personas enable row level security;
alter table public.persona_history enable row level security;
alter table public.persona_opinions enable row level security;
alter table public.persona_messages enable row level security;
grant select on public.persona_builds, public.follower_personas, public.persona_history,
  public.persona_opinions, public.persona_messages to authenticated;
create policy persona_builds_own on public.persona_builds for select to authenticated
  using (creator_id = curo.current_creator_id());
create policy follower_personas_own on public.follower_personas for select to authenticated
  using (creator_id = curo.current_creator_id());
create policy persona_history_own on public.persona_history for select to authenticated
  using (creator_id = curo.current_creator_id());
create policy persona_opinions_own on public.persona_opinions for select to authenticated
  using (creator_id = curo.current_creator_id());
create policy persona_messages_own on public.persona_messages for select to authenticated
  using (creator_id = curo.current_creator_id());
