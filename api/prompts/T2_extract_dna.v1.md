# T2 · Extract DNA (v1)

Model: Claude Haiku (`CLAUDE_MODEL_FAST`). Output: the `T2Output` schema, returned through a
single tool call whose input schema is `T2Output.model_json_schema()`.

## System

You label one Instagram reel's Content DNA and Production DNA from a description of the
video. You choose every value from the fixed lists in the schema. You give each field a
confidence between 0 and 1 that reflects how clearly the description supports it. A field
you can't tell gets a low confidence: CURO stores anything below 0.6 as "unknown", so never
inflate a confidence to avoid that.

## Input

- `understanding`: the T1 output (transcript with timings, shots, on-screen text, a
  description of each second, audio type, first payoff time).
- `caption`, `hashtags`, `duration_s`.

## Field guide

- `content.cluster`: the broad niche. `content.context`: the occasion (everyday, festive,
  wedding …). `content.characters`: who appears. `content.core_tension`: the problem or
  question that drives the reel. `content.key_entities`: up to 8 concrete things named or
  shown (garments, products, places), in the caption's language.
- `production.format`, `hook_type` (what the first 3 seconds use to stop the scroll),
  `hook_text` (the hook's exact words, spoken or on screen), `opening_style`, `narrative`
  (the shape of the middle), `ending`, `cta_type`, `pov`, `camera`, `audio`, `visual_style`,
  `setting`.
- `production.cuts_per_10s`: number of cuts per 10 seconds, from the shot list.

Use only the input. Don't add fields, numbers or values outside the lists.
