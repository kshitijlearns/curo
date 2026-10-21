-- Accounts and collected public data (MVP doc §8, "Accounts and data").
-- Public records (accounts, reels, snapshots, comments) are shared: a peer's reel is stored
-- once even if several creators track it. Creators see them through Row Level Security.
-- Missing public counts are NULL (unknown), never zero.

create table public.accounts (
  id                uuid primary key default gen_random_uuid(),
  username          text not null unique check (username = lower(username)),
  full_name         text,
  bio               text,
  followers         integer,
  following         integer,
  posts             integer,
  category          text,
  is_private        boolean not null default false,
  -- active | private | deleted | not_found | opted_out (deleted their CURO account; never re-collect)
  status            text not null default 'active'
                    check (status in ('active', 'private', 'deleted', 'not_found', 'opted_out')),
  last_collected_at timestamptz,
  created_at        timestamptz not null default now()
);

create table public.creators (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null unique references auth.users (id) on delete cascade,
  ig_username   text not null check (ig_username = lower(ig_username)),
  account_id    uuid references public.accounts (id) on delete set null,
  niche         text,
  goal          text check (goal in ('reach', 'community', 'sales')),
  formats       text[] not null default '{}',
  languages     text[] not null default '{}',
  voice_profile jsonb,
  accuracy      jsonb,
  timezone      text not null default 'Asia/Kolkata',
  created_at    timestamptz not null default now()
);

create table public.account_snapshots (
  id         bigint generated always as identity primary key,
  account_id uuid not null references public.accounts (id) on delete cascade,
  taken_at   timestamptz not null,
  followers  integer,
  following  integer,
  posts      integer,
  unique (account_id, taken_at)
);

create table public.peers (
  creator_id uuid not null references public.creators (id) on delete cascade,
  account_id uuid not null references public.accounts (id) on delete cascade,
  source     text not null check (source in ('suggested', 'creator')),
  confirmed  boolean not null default false,
  created_at timestamptz not null default now(),
  primary key (creator_id, account_id)
);

create table public.reels (
  id                  uuid primary key default gen_random_uuid(),
  account_id          uuid not null references public.accounts (id) on delete cascade,
  ig_media_id         text not null unique,
  shortcode           text not null unique,
  permalink           text not null,
  posted_at           timestamptz not null,
  duration_s          numeric(6, 2),
  caption             text not null default '',
  hashtags            text[] not null default '{}',
  mentions            text[] not null default '{}',
  audio_name          text,
  is_paid_partnership boolean not null default false,
  -- The vendor's media links expire; process_reel copies the files into storage.
  video_url           text,
  thumb_url           text,
  video_path          text,
  thumb_path          text,
  -- When CURO first saw the reel: tells an early-tracked reel from one seen late.
  first_seen_at       timestamptz not null,
  is_deleted          boolean not null default false,
  deleted_at          timestamptz,
  likes_hidden        boolean not null default false,
  comments_disabled   boolean not null default false,
  created_at          timestamptz not null default now()
);
create index reels_account_posted_idx on public.reels (account_id, posted_at desc);

create table public.metric_snapshots (
  id          bigint generated always as identity primary key,
  reel_id     uuid not null references public.reels (id) on delete cascade,
  taken_at    timestamptz not null,
  age_hours   numeric(10, 2) not null,
  views       bigint,
  likes       bigint,   -- NULL when likes are hidden
  comments    bigint,   -- NULL when comments are turned off
  shares      bigint,   -- NULL when the share count isn't shown
  flagged     boolean not null default false,
  flag_reason text,
  source      text not null default 'schedule'
              check (source in ('onboarding', 'schedule', 'refresh', 'discovery')),
  unique (reel_id, taken_at)
);
create index metric_snapshots_reel_taken_idx on public.metric_snapshots (reel_id, taken_at);

-- No commenter handles are stored: they're used for bot filtering and friend tags, then
-- dropped, and @mentions inside the text are masked.
create table public.comments (
  id            uuid primary key default gen_random_uuid(),
  reel_id       uuid not null references public.reels (id) on delete cascade,
  ig_comment_id text not null unique,
  text          text not null,
  posted_at     timestamptz,
  like_count    integer not null default 0,
  reply_count   integer not null default 0,
  is_creator    boolean not null default false,
  language      text,
  sentiment     text check (sentiment in ('positive', 'neutral', 'negative')),
  intent        text,
  theme_id      uuid,   -- foreign key added with comment_themes (0003)
  is_bot        boolean,
  tags_friend   boolean not null default false,
  labelled_at   timestamptz,
  label_version text,
  created_at    timestamptz not null default now()
);
create index comments_reel_idx on public.comments (reel_id);
