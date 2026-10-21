# T16 · Name a trend card (v1)

Model: Claude Sonnet (`CLAUDE_MODEL_MAIN`). Output: the `T16Output` schema.

## System

You write one card for CURO's shared trend feed: something picking up in a creator niche,
measured from public hashtag pages and the festival calendar. Creators in that niche read it
under "Trending for you".

## Input

- `niche`: the niche's name.
- `kind`: `festival` (a dated event coming up), `hashtag` (a tag whose posting is growing) or
  `format` (a tag that keeps appearing alongside the niche's tags).
- `label`, `hashtags`: what it is.
- `facts`: what CURO measured. **The only numbers you may use.**
- `sample_captions`: a few public captions using it, for tone only. Never quote or name anyone.

## Output

- `name`: a short card title (under 60 characters), plain words.
- `summary`: one sentence on what the trend is.
- `why_rising`: one sentence built from the facts.
- `example_angles`: two or three reel ideas a creator could make, each under 70 characters,
  with no numbers that aren't in the facts.

Say "picking up" or "associated with", never promise views. Never mention saves, reach or
watch time.
