-- Simulator v0 (Phase 7). One run gives a score for each audience (the toggle switches between
-- stored results rather than re-running), and each suggested edit is re-scored for each.

alter table public.simulations
  add column caption text,      -- the caption the creator plans to post, when given
  add column scores  jsonb,     -- {"followers": 64, "new": 58, "both": 61}
  add column job_id  uuid references public.jobs (id) on delete set null,
  add column error   text;
create index simulations_parent_idx on public.simulations (parent_simulation_id);

alter table public.simulation_edits
  add column gains          jsonb,   -- audience → score change with the edit
  add column frame_label    text,    -- "Frame 1 · Hook", or the moment when there's no storyboard
  add column applied_job_id uuid references public.jobs (id) on delete set null;
create index simulation_edits_simulation_idx on public.simulation_edits (simulation_id);
