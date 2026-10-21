-- Row Level Security: a creator can only ever read their own rows (MVP doc §8).
--
-- * Product and system rows belong to one creator.
-- * Public records (accounts, reels, snapshots, comments, DNA…) are visible when the
--   account is the creator's own or one they track as a peer.
-- * Hashtag pages and the festival calendar are shared public reference data.
--
-- The API runs each request as `authenticated` with the user's JWT claims; the worker and
-- collection jobs connect as the table owner, which RLS does not restrict.

-- ------------------------------------------------------------------ helpers

create or replace function curo.current_creator_id() returns uuid
  language sql stable security definer set search_path = public
as $$
  select id from public.creators where user_id = auth.uid()
$$;

create or replace function curo.visible_account_ids() returns setof uuid
  language sql stable security definer set search_path = public
as $$
  select c.account_id from public.creators c
   where c.user_id = auth.uid() and c.account_id is not null
  union
  select p.account_id from public.peers p
    join public.creators c on c.id = p.creator_id
   where c.user_id = auth.uid()
$$;

create or replace function curo.visible_reel_ids() returns setof uuid
  language sql stable security definer set search_path = public
as $$
  select r.id from public.reels r where r.account_id in (select curo.visible_account_ids())
$$;

create or replace function curo.my_project_ids() returns setof uuid
  language sql stable security definer set search_path = public
as $$
  select id from public.projects where creator_id = curo.current_creator_id()
$$;

revoke all on function curo.current_creator_id() from public;
revoke all on function curo.visible_account_ids() from public;
revoke all on function curo.visible_reel_ids() from public;
revoke all on function curo.my_project_ids() from public;
grant execute on function curo.current_creator_id() to authenticated, service_role;
grant execute on function curo.visible_account_ids() to authenticated, service_role;
grant execute on function curo.visible_reel_ids() to authenticated, service_role;
grant execute on function curo.my_project_ids() to authenticated, service_role;

-- ------------------------------------------------------------------ enable RLS everywhere

do $$
declare t text;
begin
  foreach t in array array[
    'accounts', 'creators', 'account_snapshots', 'peers', 'reels', 'metric_snapshots', 'comments',
    'reel_dna', 'reel_embeddings', 'baselines', 'subclusters', 'comment_themes', 'pattern_cards',
    'hashtag_pages', 'festival_calendar',
    'opportunities', 'projects', 'ideas', 'script_versions', 'storyboard_versions', 'captions',
    'simulations', 'simulation_edits',
    'chat_messages', 'creator_memory', 'jobs', 'events'
  ] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('revoke all on public.%I from anon', t);
  end loop;
end $$;

-- ------------------------------------------------------------------ public records (read-only)

grant select on public.accounts, public.account_snapshots, public.reels, public.metric_snapshots,
  public.comments, public.reel_dna, public.reel_embeddings, public.baselines, public.subclusters,
  public.comment_themes, public.pattern_cards, public.hashtag_pages, public.festival_calendar
  to authenticated;

create policy accounts_read on public.accounts for select to authenticated
  using (id in (select curo.visible_account_ids()));
create policy account_snapshots_read on public.account_snapshots for select to authenticated
  using (account_id in (select curo.visible_account_ids()));
create policy reels_read on public.reels for select to authenticated
  using (account_id in (select curo.visible_account_ids()));
create policy metric_snapshots_read on public.metric_snapshots for select to authenticated
  using (reel_id in (select curo.visible_reel_ids()));
create policy comments_read on public.comments for select to authenticated
  using (reel_id in (select curo.visible_reel_ids()));
create policy reel_dna_read on public.reel_dna for select to authenticated
  using (reel_id in (select curo.visible_reel_ids()));
create policy reel_embeddings_read on public.reel_embeddings for select to authenticated
  using (reel_id in (select curo.visible_reel_ids()));
create policy baselines_read on public.baselines for select to authenticated
  using (account_id in (select curo.visible_account_ids()));
create policy subclusters_read on public.subclusters for select to authenticated
  using (account_id in (select curo.visible_account_ids()));
create policy comment_themes_read on public.comment_themes for select to authenticated
  using (account_id in (select curo.visible_account_ids()));
create policy pattern_cards_read on public.pattern_cards for select to authenticated
  using (account_id is null or account_id in (select curo.visible_account_ids()));
create policy hashtag_pages_read on public.hashtag_pages for select to authenticated using (true);
create policy festival_calendar_read on public.festival_calendar for select to authenticated using (true);

-- ------------------------------------------------------------------ the creator's own rows

grant select, insert, update on public.creators to authenticated;
create policy creators_own on public.creators for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

grant select, insert, update, delete on public.peers to authenticated;
create policy peers_own on public.peers for all to authenticated
  using (creator_id = curo.current_creator_id())
  with check (creator_id = curo.current_creator_id());

grant select, update on public.opportunities to authenticated;
create policy opportunities_own on public.opportunities for all to authenticated
  using (creator_id = curo.current_creator_id())
  with check (creator_id = curo.current_creator_id());

grant select, insert, update, delete on public.projects to authenticated;
create policy projects_own on public.projects for all to authenticated
  using (creator_id = curo.current_creator_id())
  with check (creator_id = curo.current_creator_id());

do $$
declare t text;
begin
  foreach t in array array['ideas', 'script_versions', 'storyboard_versions', 'captions'] loop
    execute format('grant select, insert, update, delete on public.%I to authenticated', t);
    execute format(
      'create policy %I on public.%I for all to authenticated '
      'using (project_id in (select curo.my_project_ids())) '
      'with check (project_id in (select curo.my_project_ids()))',
      t || '_own', t);
  end loop;
end $$;

grant select, insert, update on public.simulations to authenticated;
create policy simulations_own on public.simulations for all to authenticated
  using (creator_id = curo.current_creator_id())
  with check (creator_id = curo.current_creator_id());

grant select, update on public.simulation_edits to authenticated;
create policy simulation_edits_own on public.simulation_edits for all to authenticated
  using (simulation_id in (select id from public.simulations where creator_id = curo.current_creator_id()));

grant select, insert on public.chat_messages to authenticated;
create policy chat_messages_own on public.chat_messages for all to authenticated
  using (creator_id = curo.current_creator_id())
  with check (creator_id = curo.current_creator_id());

grant select, insert, delete on public.creator_memory to authenticated;
create policy creator_memory_own on public.creator_memory for all to authenticated
  using (creator_id = curo.current_creator_id())
  with check (creator_id = curo.current_creator_id());

grant select on public.jobs to authenticated;
create policy jobs_own on public.jobs for select to authenticated
  using (creator_id = curo.current_creator_id());

grant insert on public.events to authenticated;
create policy events_own on public.events for insert to authenticated
  with check (creator_id = curo.current_creator_id());

-- Identity columns need their sequences for inserts made as `authenticated`.
grant usage on all sequences in schema public to authenticated;
