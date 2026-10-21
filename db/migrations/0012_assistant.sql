-- Ask Curo and memory (Phase 8).

-- What a simulation was run on, so Ask Curo can re-score "what if" changes and line the video
-- up with the draft again: the DNA features, the video's embedding, its transcript and timing.
alter table public.simulations
  add column inputs jsonb;

-- Each assistant reply: the intent it was routed by, the records it cites, and how its
-- numbers were checked ("model", "model_retry" or "template").
alter table public.chat_messages
  add column intent  text,
  add column sources jsonb,
  add column checked text;
create index chat_messages_context_idx
  on public.chat_messages (creator_id, (context->>'project_id'), (context->>'simulation_id'), created_at);

-- A learned preference the creator deleted in Settings isn't learned again.
alter table public.creators
  add column memory_dismissed text[] not null default '{}';

grant update on public.creator_memory to authenticated;
