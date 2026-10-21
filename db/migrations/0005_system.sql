-- System tables (MVP doc §8).

create table public.chat_messages (
  id         uuid primary key default gen_random_uuid(),
  creator_id uuid not null references public.creators (id) on delete cascade,
  context    jsonb not null default '{}',   -- screen, project_id, simulation_id
  role       text not null check (role in ('user', 'assistant', 'tool')),
  content    text not null,
  tool_calls jsonb,
  created_at timestamptz not null default now()
);
create index chat_messages_creator_idx on public.chat_messages (creator_id, created_at);

-- Visible and deletable in settings.
create table public.creator_memory (
  id         uuid primary key default gen_random_uuid(),
  creator_id uuid not null references public.creators (id) on delete cascade,
  key        text not null,
  value      text not null,
  source     text not null check (source in ('stated', 'learned')),
  created_at timestamptz not null default now(),
  unique (creator_id, key)
);

-- Watched by the app for progress (Supabase Realtime later; polling locally).
create table public.jobs (
  id              uuid primary key default gen_random_uuid(),
  creator_id      uuid references public.creators (id) on delete cascade,
  type            text not null,
  status          text not null default 'queued'
                  check (status in ('queued', 'running', 'succeeded', 'failed')),
  progress        jsonb not null default '{}',
  payload         jsonb not null default '{}',
  result          jsonb,
  error           text,
  attempts        integer not null default 0,
  idempotency_key text unique,
  created_at      timestamptz not null default now(),
  started_at      timestamptz,
  finished_at     timestamptz,
  updated_at      timestamptz not null default now()
);
create index jobs_creator_idx on public.jobs (creator_id, created_at desc);
create index jobs_open_idx on public.jobs (type, status) where status in ('queued', 'running');

create table public.events (
  id         bigint generated always as identity primary key,
  creator_id uuid references public.creators (id) on delete cascade,
  name       text not null,
  props      jsonb not null default '{}',
  created_at timestamptz not null default now()
);
