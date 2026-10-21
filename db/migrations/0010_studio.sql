-- Phase 6: Studio (logic doc §9–§12). The tables exist since 0004; these columns carry what
-- each step shows beside its content.

-- An idea's one-line reason and the evidence chips behind it, as computed when it was scored
-- (the facts move on; a round of ideas keeps showing what it was picked from).
alter table public.ideas
  add column hook_type text,
  add column why       text,
  add column evidence  jsonb not null default '[]';

-- Curo's reply to the instruction that produced a version ("Rewrote the hook. The rest of the
-- script is unchanged."), and how the version was planned (length band, word budget, beats).
-- A script belongs to the idea it was written for: picking another idea starts its own
-- script (and going back to the first idea finds its script again).
alter table public.script_versions
  add column idea_id uuid references public.ideas (id) on delete set null,
  add column reply   text,
  add column plan    jsonb;

alter table public.storyboard_versions
  add column reply text;

-- Captions are written from one script version.
alter table public.captions
  add column script_version integer,
  add column reply          text;

-- The latest version of each step is read on every Studio request.
create index ideas_project_idx on public.ideas (project_id, round);
create index script_versions_latest_idx on public.script_versions (project_id, version desc);
create index storyboard_versions_latest_idx on public.storyboard_versions (project_id, version desc);
create index captions_latest_idx on public.captions (project_id, version desc);
