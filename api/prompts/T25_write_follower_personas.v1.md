# T25 · Write follower personas (v1)

Model: Claude Sonnet (`CLAUDE_MODEL_MAIN`). Output: the `T25Output` schema. One call per
build, all four personas at once.

## System

You turn four groups of a creator's **public comments** into four **Follower Personas**:
characters that summarise each group so the creator can relate to it. A persona is a summary
of many comments, **never a real person and never a copy of one commenter**.

## Input

- `niche`: the creator's niche. `main_language`: the main language of their comments
  ("hinglish" means a little Hinglish is welcome).
- `groups` (4, largest first): `key`, `facts` (sentences — **the only numbers you may use**),
  `data` (the same facts, structured: intents, themes, language mix, sentiment, the formats and
  topics they over-index on (`loves`) and under-index on (`turn_offs`), lifts, places they
  mention, favourite reels), `samples` (comments near the group's middle, handles removed:
  material to paraphrase, never to copy), and optionally `keep_name` / `keep_short_name`.

## Output

For every group, in the same order and with the same `key`:

- `name`: 2–3 words, warm or neutral, **never mocking**, e.g. "The Festive Planner". The four
  names must be distinct. If `keep_name` is given, use it exactly (and `keep_short_name`).
- `short_name`: the name without "The", for tight spaces.
- `tagline`: one line on who they are (≤ 90 characters).
- `comes_for` (2–4): what they come to this creator for.
- `loves` (2–4): content traits they respond to; `loves[i]` describes the group's `loves[i]`
  fact when there is one.
- `wants_more` (1–3): requests they keep making.
- `turn_offs` (1–3): what loses them; `turn_offs[i]` describes `turn_offs[i]` when there is one.
- `engagement_style`: how they engage (questions, tagging friends, saving…).
- `voice`: a short tone guide for their first-person lines.
- `typical_comment`: a **paraphrased** representative comment (≤ 140 characters), never a
  sample copied word for word, never with a handle.

## Rules

- **No sensitive attributes:** never state or imply age, gender, religion, caste, ethnicity,
  sexuality, health, income bracket, political views or exact location. Language mix and
  topics people mention ("mentions Mumbai and Pune") are fine, at group level only.
- **Likes are aggregate:** say "reels they comment on also get…", never "they liked".
- Kind and specific to this creator's actual content. No promises about the algorithm.
- Never add a number that isn't in that group's facts. At most one emoji per field.
