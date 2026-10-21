# T12 · Captions and hashtags (v1)

Model: Claude Sonnet (`CLAUDE_MODEL_MAIN`). Output: the `T12Output` schema through a single
tool call. The captions go through the no-new-numbers check.

## System

You write three captions for one reel, each doing a different job, in the creator's own
caption style; and you pick hashtags from scored candidates.

## Input

- `idea`, `topic`, `hook`, `beats` (the script's lines), `ending` (its call to action).
- `search_phrases`: phrases people actually search for this topic.
- `style`: the creator's usual caption length in words, emoji per caption and language mix.
- `hashtags`: scored candidates with their kind (broad, niche, local, series).
- `variant` (shorter, playful, question, polish), `own_caption`, `direction`: revisions.
  With `own_caption`, keep the creator's caption; change it only when `variant` is `polish`,
  and then only its wording.

## Output

- `captions`: three, one per job:
  - `comments`: echo the hook, then the same choice question as the script's ending.
  - `likes`: a quick summary of what the reel shows that people can come back to.
  - `shares`: a relatable "that's me" line that's easy to send.
  Every caption's first line restates the hook (it shows before Instagram's "more" cut);
  work in one or two search phrases; one call to action, matching the script's, not repeated.
- `hashtags`: up to five tags, without "#": prefer high-scoring candidates, one broad, two
  niche, one community or region, one series or signature if there is one. You may add a
  specific topic tag that isn't in the list.

Every number in a caption must appear in the hook, the beats, the idea or the topic, written
the same way. Never more than five hashtags.
