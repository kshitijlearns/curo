-- Learned data (MVP doc §8): DNA, embeddings, baselines, sub-clusters, themes,
-- pattern cards, and the shared public hashtag pages and festival calendar.

create table public.reel_dna (
  reel_id       uuid primary key references public.reels (id) on delete cascade,
  content       jsonb not null,
  production    jsonb not null,
  transcript    jsonb,            -- the T1 video-understanding output
  confidence    jsonb not null,
  model_version text not null,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

-- One embedding model per table: never mix models (MVP doc §5).
create table public.reel_embeddings (
  reel_id    uuid primary key references public.reels (id) on delete cascade,
  embedding  extensions.vector(768) not null,
  model      text not null,
  created_at timestamptz not null default now()
);
create index reel_embeddings_hnsw_idx
  on public.reel_embeddings using hnsw (embedding extensions.vector_cosine_ops);

create table public.baselines (
  id          bigint generated always as identity primary key,
  account_id  uuid not null references public.accounts (id) on delete cascade,
  metric      text not null,
  age_bucket  text not null check (age_bucket in ('6h', '1d', '3d', '7d', '30d')),
  median      double precision,
  p25         double precision,
  p75         double precision,
  n           integer not null default 0,
  computed_at timestamptz not null,
  unique (account_id, metric, age_bucket)
);

create table public.subclusters (
  id          uuid primary key default gen_random_uuid(),
  account_id  uuid not null references public.accounts (id) on delete cascade,
  label       text not null,
  centroid    extensions.vector(768),
  reel_ids    uuid[] not null,
  lifts       jsonb not null default '{}',
  computed_at timestamptz not null
);

create table public.comment_themes (
  id                 uuid primary key default gen_random_uuid(),
  account_id         uuid not null references public.accounts (id) on delete cascade,
  label              text not null,
  kind               text not null check (kind in ('request', 'question')),
  share              double precision not null,
  n                  integer not null,
  sample_comment_ids uuid[] not null default '{}',
  computed_at        timestamptz not null
);

alter table public.comments
  add constraint comments_theme_fk
  foreign key (theme_id) references public.comment_themes (id) on delete set null;

-- account_id NULL = a prior learned across similar creators.
create table public.pattern_cards (
  id             uuid primary key default gen_random_uuid(),
  account_id     uuid references public.accounts (id) on delete cascade,
  feature        text not null,
  value          text not null,
  metric         text not null,
  effect         double precision not null,   -- after shrinkage toward the prior
  creator_effect double precision,
  prior_effect   double precision,
  n              integer not null,
  confidence     text not null check (confidence in ('low', 'medium', 'high')),
  scope          text not null check (scope in ('yours', 'similar_creators')),
  computed_at    timestamptz not null
);
create index pattern_cards_account_idx on public.pattern_cards (account_id);

-- Public hashtag pages, cached and refreshed at most daily; shared across creators.
create table public.hashtag_pages (
  tag             text primary key check (tag = lower(tag)),
  fetched_at      timestamptz not null,
  post_count      bigint,
  top_reel_ids    text[] not null default '{}',
  recent_reel_ids text[] not null default '{}',
  reel_count_7d   integer,
  reels           jsonb not null default '[]'   -- summaries of the public reels on the page
);

create table public.festival_calendar (
  id        text primary key,
  name      text not null,
  starts_on date not null,
  ends_on   date not null,
  regions   text[] not null default '{}',
  niches    text[] not null default '{}',
  keywords  text[] not null default '{}',
  verified  boolean not null default false,
  check (ends_on >= starts_on)
);
