-- Phase 5: a suggested peer is not yet a creator you track (DECISIONS D66).
--
-- Suggestions are written for a creator before they choose anyone. They may see who was
-- suggested (handle, follower count) to decide, but an account's reels, comments and learned
-- records only become visible once it is tracked (confirmed) — as 0006 intended.

create or replace function curo.visible_account_ids() returns setof uuid
  language sql stable security definer set search_path = public
as $$
  select c.account_id from public.creators c
   where c.user_id = auth.uid() and c.account_id is not null
  union
  select p.account_id from public.peers p
    join public.creators c on c.id = p.creator_id
   where c.user_id = auth.uid() and p.confirmed
$$;

create or replace function curo.suggested_account_ids() returns setof uuid
  language sql stable security definer set search_path = public
as $$
  select p.account_id from public.peers p
    join public.creators c on c.id = p.creator_id
   where c.user_id = auth.uid() and not p.confirmed
$$;

revoke all on function curo.suggested_account_ids() from public;
grant execute on function curo.suggested_account_ids() to authenticated, service_role;

drop policy accounts_read on public.accounts;
create policy accounts_read on public.accounts for select to authenticated
  using (id in (select curo.visible_account_ids()) or id in (select curo.suggested_account_ids()));
