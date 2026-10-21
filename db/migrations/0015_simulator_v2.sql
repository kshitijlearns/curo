-- CURO v2 Simulator (PLAN_V2.md §4.5): an AI audience built from the creator's own comments.
-- Segments and personas are built once per creator a month; every simulation's agents, their
-- reactions and the "talk to an agent" chats are kept. Nothing here is a real person: no
-- handles, no avatars, every comment is labelled simulated in the app.

create table public.audience_segments (
  id           uuid primary key default gen_random_uuid(),
  creator_id   uuid not null references public.creators (id) on delete cascade,
  version      text not null,                -- 'YYYY-MM': rebuilt monthly
  key          text not null,
  label        text not null,                -- e.g. "Festive planner"
  share        numeric(5, 4) not null check (share > 0 and share <= 1),
  description  text not null,
  interests    text[] not null default '{}',
  created_at   timestamptz not null default now(),
  unique (creator_id, version, key)
);

create table public.audience_personas (
  creator_id    uuid not null references public.creators (id) on delete cascade,
  version       text not null,
  agent_no      integer not null check (agent_no >= 1),
  segment       text not null,
  persona_text  text not null,
  traits        jsonb not null default '{}',  -- patience, sharer, commenter, saver (0–1)
  primary key (creator_id, version, agent_no)
);

-- Calibration: agents' rates against the real rates on the creator's past reels, per metric.
create table public.persona_calibrations (
  creator_id   uuid not null references public.creators (id) on delete cascade,
  version      text not null,
  metric       text not null check (metric in ('views', 'likes', 'comments', 'shares')),
  factor       numeric(10, 5),                -- k_m (null: no past reel to calibrate on)
  low          numeric(10, 5),                -- p10 of the ratios
  high         numeric(10, 5),                -- p90 of the ratios
  n            integer not null default 0,    -- past reels used
  created_at   timestamptz not null default now(),
  primary key (creator_id, version, metric)
);

create table public.simulation_agents (
  simulation_id  uuid not null references public.simulations (id) on delete cascade,
  agent_no       integer not null,
  segment        text not null,
  reaction       jsonb not null,             -- {watch_until_s, skipped, liked, commented, ...}
  thread         jsonb not null default '[]', -- replies in the thread round
  primary key (simulation_id, agent_no)
);

create table public.agent_chats (
  id             bigint generated always as identity primary key,
  simulation_id  uuid not null references public.simulations (id) on delete cascade,
  agent_no       integer not null,
  role           text not null check (role in ('user', 'agent')),
  content        text not null,
  created_at     timestamptz not null default now()
);
create index agent_chats_sim_idx on public.agent_chats (simulation_id, agent_no, created_at);

alter table public.simulations
  add column timeline         jsonb,           -- T1's second-by-second timeline
  add column engagement_score integer check (engagement_score between 0 and 100),
  add column persona_version  text;

alter table public.audience_segments enable row level security;
alter table public.audience_personas enable row level security;
alter table public.persona_calibrations enable row level security;
alter table public.simulation_agents enable row level security;
alter table public.agent_chats enable row level security;
grant select on public.audience_segments, public.audience_personas, public.persona_calibrations,
  public.simulation_agents, public.agent_chats to authenticated;

create policy audience_segments_read on public.audience_segments for select to authenticated
  using (creator_id = curo.current_creator_id());
create policy audience_personas_read on public.audience_personas for select to authenticated
  using (creator_id = curo.current_creator_id());
create policy persona_calibrations_read on public.persona_calibrations for select to authenticated
  using (creator_id = curo.current_creator_id());
create policy simulation_agents_read on public.simulation_agents for select to authenticated
  using (simulation_id in (select id from public.simulations));
create policy agent_chats_read on public.agent_chats for select to authenticated
  using (simulation_id in (select id from public.simulations));
grant insert on public.agent_chats to authenticated;
create policy agent_chats_insert on public.agent_chats for insert to authenticated
  with check (simulation_id in (select id from public.simulations));
