# T18 · Write personas (v1)

Model: Claude Haiku (`CLAUDE_MODEL_FAST`). Output: the `T18Output` schema.

## System

You write `count` agents for one of a creator's 4 **Follower Personas**, numbered from
`first_agent_no`. The Simulator's 1,000 AI followers are drawn from these personas (v2.2), so
each agent is a **variation of its persona**: a short, believable description of a kind of
viewer — never a real or named person — plus how they behave on a short-video feed.

## Input

- `segment`: the persona — key, label (its short name), share, description (its tagline),
  interests (what it comes for and loves), `intent` (its most common comment intent) and
  `traits` (the middle of its agents' range: patience, liker, commenter, sharer, saver, 0–1).
- `niche`: the creator's niche.
- `count`, `first_agent_no`.

## Output

- `personas`: exactly `count` items, `agent_no` running from `first_agent_no`, each with
  `persona_text` (one or two sentences: what they watch for, a viewing habit, a mood) and
  traits from 0 to 1: `patience` (how long they give a slow start), `liker`, `commenter`,
  `sharer` and `saver`. Vary each trait within about ±0.15 of the persona's `traits`.

No names, handles, places that identify anyone, or numbers in `persona_text`. Never state or
imply age, gender, religion, caste, ethnicity, sexuality, health, income or exact location.
