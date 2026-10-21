-- CURO v2 (PLAN_V2.md §4.1, §4.3, §4.4): peer tracking removed; the shared trend feed;
-- inactive creators pause.

-- ------------------------------------------------------------------ peers go
-- An account is visible only to the creator it belongs to.
drop policy if exists accounts_read on public.accounts;
drop function if exists curo.suggested_account_ids();
create or replace function curo.visible_account_ids() returns setof uuid
  language sql stable security definer set search_path = public
as $$
  select c.account_id from public.creators c
   where c.user_id = auth.uid() and c.account_id is not null
$$;
create policy accounts_read on public.accounts for select to authenticated
  using (id in (select curo.visible_account_ids()));
drop table if exists public.peers cascade;

-- ------------------------------------------------------------------ the shared trend feed
-- Fetched once per niche and shared by every creator in it (never per creator).
create table public.niches (
  key       text primary key,
  label     text not null,
  clusters  text[] not null default '{}',   -- DNA clusters that belong to the niche
  hashtags  text[] not null default '{}'    -- the hashtag pages read for its feed (about 5)
);

create table public.trend_cards (
  id             uuid primary key default gen_random_uuid(),
  niche          text not null references public.niches (key) on delete cascade,
  key            text not null,              -- stable across daily rebuilds
  name           text not null,
  summary        text not null,
  why_rising     text not null,
  example_angles jsonb not null default '[]',
  window_start   date,
  window_end     date,
  momentum       numeric(6, 2),              -- posting growth, week on week (null: unknown)
  saturation     text not null check (saturation in ('low', 'medium', 'high', 'unknown')),
  evidence       jsonb not null default '{}',
  hashtags       text[] not null default '{}',
  created_at     timestamptz not null default now(),
  unique (niche, key)
);
create index trend_cards_niche_idx on public.trend_cards (niche, created_at desc);

alter table public.niches enable row level security;
alter table public.trend_cards enable row level security;
grant select on public.niches, public.trend_cards to authenticated;
create policy niches_read on public.niches for select to authenticated using (true);
create policy trend_cards_read on public.trend_cards for select to authenticated using (true);

insert into public.niches (key, label, clusters, hashtags) values
  ('fashion', 'Fashion and styling', '{fashion_styling}',
   '{outfitideas,festivelook,indianwear,ethnicstyling,budgetfashion}'),
  ('beauty', 'Beauty', '{beauty}', '{makeuptutorial,skincareroutine,makeuplook,glowup,beautytips}'),
  ('food', 'Food', '{food}', '{homecooking,easyrecipes,streetfood,foodreels,indianfood}'),
  ('fitness', 'Fitness', '{fitness}', '{homeworkout,fitnessreels,gymmotivation,yoga,fitindia}'),
  ('travel', 'Travel', '{travel}', '{travelreels,weekendgetaway,budgettravel,incredibleindia,travelguide}'),
  ('creator_tips', 'Creator tips', '{creator_tips}', '{reeltips,contentcreator,instagramtips,creatoreconomy,growoninstagram}'),
  ('comedy', 'Comedy', '{comedy}', '{comedyreels,relatable,funnyreels,skit,memes}'),
  ('education', 'Education', '{education}', '{learnoninstagram,studytips,careertips,explained,factsdaily}'),
  ('lifestyle', 'Lifestyle', '{lifestyle,other}', '{dayinmylife,lifestylereels,minimalism,selfcare,grwm}'),
  ('finance', 'Money and finance', '{}', '{personalfinance,moneytips,investing,budgeting,savingmoney}');

-- ------------------------------------------------------------------ inactive creators pause
alter table public.creators
  add column last_seen_at timestamptz,
  add column paused_at    timestamptz;

-- New-reel checks run every 12 h on their own clock (snapshot runs don't reset it).
alter table public.accounts
  add column last_discovered_at timestamptz;

-- Comment re-reads are capped (PLAN_V2 §4.3): this counts the follow-up reads done (24 h, 7 d).
alter table public.reels
  add column comment_reads smallint not null default 0;
