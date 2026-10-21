-- Phase 3: what the understanding pipeline needs beyond 0003.

-- T3's theme phrase for a request or question, normalised; comments sharing one are grouped.
alter table public.comments add column theme_key text;

-- A theme keeps its id across rebuilds through its key (the group's most common phrase).
alter table public.comment_themes add column key text not null default '';
alter table public.comment_themes
  add constraint comment_themes_account_key unique (account_id, key);

-- Evidence behind each pattern card (shown on tap) and a stable identity per
-- (account, feature, value, metric); account_id NULL = a similar-creator prior.
alter table public.pattern_cards
  add column n_without integer,
  add column p_value double precision,
  add column evidence jsonb not null default '{}';
alter table public.pattern_cards
  add constraint pattern_cards_key unique nulls not distinct (account_id, feature, value, metric);

-- The scheduler asks "is anything still processing for this account?" every minute.
create index jobs_open_by_account_idx on public.jobs ((payload->>'account_id'), type)
  where status in ('queued', 'running');
