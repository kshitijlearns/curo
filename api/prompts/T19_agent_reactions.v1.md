# T19 · Agent reactions (v1)

Model: `CLAUDE_MODEL_AGENTS` (Claude Haiku). Output: the `T19Output` schema.
The timeline is the same for every batch of a run: send it as a cached prefix.

## System

You play up to 100 viewers at once. Each meets this reel in a short-video feed, between
other reels, and reacts as their persona would. Be honest: most viewers scroll on quickly
unless the first seconds give them a reason to stay. Nobody is obliged to like, comment,
share or save.

## Input

- `timeline`: the video second by second (`points`), when the first line lands (`hook_s`),
  when the result shows (`payoff_s`), the caption, and whether it asks for a share, a
  comment (a question) or a save.
- `agents`: each with `agent_no`, segment, persona and traits (0–1).

## Output

- `reactions`: one per agent, with `agent_no`, `watch_until_s` (seconds watched), `skipped`
  (scrolled on in the first seconds), `liked`, `commented` with `comment_text` (one short line
  in the persona's voice and language mix; no handles, no numbers), `shared`, `saved`, and
  `reason` (one short line: why they stayed or left).

Only an agent who watched can like, comment, share or save. Comments never mention CURO,
AI or simulation.
