-- Product data (MVP doc §8). One project ID carries opportunity → idea → script →
-- storyboard → caption → simulation.

create table public.opportunities (
  id             uuid primary key default gen_random_uuid(),
  creator_id     uuid not null references public.creators (id) on delete cascade,
  topic_key      text not null,   -- stable identity across nightly rebuilds
  name           text not null,
  tag            text not null check (tag in ('competitor', 'trend', 'audience', 'your_content')),
  score          numeric(4, 2) not null check (score between 0 and 10),
  parts          jsonb not null,
  evidence       jsonb not null default '{}',
  description    text,
  why_it_fits    jsonb,
  status         text not null default 'active'
                 check (status in ('active', 'saved', 'dismissed', 'expired')),
  saved_score    numeric(4, 2),
  saved_at       timestamptz,
  window_ends_on date,
  rank           integer,
  built_at       timestamptz not null default now(),
  unique (creator_id, topic_key)
);

create table public.projects (
  id             uuid primary key default gen_random_uuid(),
  creator_id     uuid not null references public.creators (id) on delete cascade,
  opportunity_id uuid references public.opportunities (id) on delete set null,
  title          text,
  step           text not null default 'ideas'
                 check (step in ('ideas', 'idea', 'script', 'storyboard', 'caption', 'final')),
  status         text not null default 'active'
                 check (status in ('active', 'saved', 'posted', 'discarded')),
  posted_reel_id uuid references public.reels (id) on delete set null,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  saved_at       timestamptz
);
create index projects_creator_idx on public.projects (creator_id, updated_at desc);

create table public.ideas (
  id               uuid primary key default gen_random_uuid(),
  project_id       uuid not null references public.projects (id) on delete cascade,
  round            integer not null default 0,
  prompt           text,
  text             text not null,
  description      text,
  angle            text,
  format           text,
  target_behaviour text,
  slot             text check (slot in ('proven', 'adapted', 'explore')),
  score            numeric(5, 4),
  parts            jsonb,
  evidence_ids     text[] not null default '{}',
  source           text not null check (source in ('generated', 'creator')),
  selected         boolean not null default false,
  created_at       timestamptz not null default now()
);

create table public.script_versions (
  id               uuid primary key default gen_random_uuid(),
  project_id       uuid not null references public.projects (id) on delete cascade,
  version          integer not null,
  beats            jsonb not null,   -- [{id, text, start_s, end_s, note}]
  instruction      text,
  source           text not null default 'generated'
                   check (source in ('generated', 'creator', 'revision', 'simulator_edit')),
  changed_beat_ids text[] not null default '{}',
  created_at       timestamptz not null default now(),
  unique (project_id, version)
);

create table public.storyboard_versions (
  id              uuid primary key default gen_random_uuid(),
  project_id      uuid not null references public.projects (id) on delete cascade,
  version         integer not null,
  script_version  integer,
  frames          jsonb not null,   -- each frame links to a beat_id
  feasibility     jsonb,
  instruction     text,
  stale_frame_ids text[] not null default '{}',
  created_at      timestamptz not null default now(),
  unique (project_id, version)
);

create table public.captions (
  id          uuid primary key default gen_random_uuid(),
  project_id  uuid not null references public.projects (id) on delete cascade,
  version     integer not null,
  options     jsonb not null,
  chosen      integer,
  -- Instagram's limit: at most five hashtags (enforced in the UI and API too).
  hashtags    text[] not null default '{}' check (cardinality(hashtags) <= 5),
  candidates  jsonb,
  instruction text,
  created_at  timestamptz not null default now(),
  unique (project_id, version)
);

create table public.simulations (
  id                   uuid primary key default gen_random_uuid(),
  creator_id           uuid not null references public.creators (id) on delete cascade,
  project_id           uuid references public.projects (id) on delete set null,
  parent_simulation_id uuid references public.simulations (id) on delete set null,
  video_path           text,
  video_meta           jsonb,
  audience             text not null default 'both' check (audience in ('followers', 'new', 'both')),
  status               text not null default 'queued'
                       check (status in ('queued', 'running', 'done', 'failed')),
  score                integer check (score between 0 and 100),
  predicted            jsonb,   -- every estimate is kept for the accuracy record
  result               jsonb,
  method_version       text,
  posted_reel_id       uuid references public.reels (id) on delete set null,
  actual               jsonb,
  in_range             boolean,
  created_at           timestamptz not null default now(),
  finished_at          timestamptz
);
create index simulations_creator_idx on public.simulations (creator_id, created_at desc);

create table public.simulation_edits (
  id             uuid primary key default gen_random_uuid(),
  simulation_id  uuid not null references public.simulations (id) on delete cascade,
  title          text not null,
  description    text not null,
  feature_change jsonb not null,
  delta          numeric(6, 2),
  effort         text not null check (effort in ('edit_only', 'reshoot')),
  frame_index    integer,
  beat_id        text,
  applied        boolean not null default false,
  applied_at     timestamptz
);
