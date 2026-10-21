-- Phase 5: peer suggestions and opportunity presentation.

-- Why a peer was suggested (logic doc §3: content similarity, similar size, …), shown to the
-- creator when they confirm or replace suggestions.
alter table public.peers
  add column suggestion_score double precision,
  add column reasons jsonb not null default '[]';

-- Opportunity texts that are assembled, not written freely (logic doc §8 step 4).
alter table public.opportunities
  add column card text,
  add column signals text[] not null default '{}';

create index opportunities_creator_rank_idx on public.opportunities (creator_id, status, rank);

-- CURO's own posting index (MVP doc §5 "Trend data"): reels per day seen on each hashtag
-- page, accumulated across daily collections ({"2027-08-22": 251, …}). A page only lists its
-- most recent reels, so a busy tag's history is built one day at a time.
alter table public.hashtag_pages add column daily_counts jsonb not null default '{}';
