# T20 · Thread round (v1)

Model: `CLAUDE_MODEL_AGENTS` (Claude Haiku). Output: the `T20Output` schema.

## System

Some viewers who engaged with the reel now read its top comments. As their personas, they
may like a comment or reply to it, or do nothing. Most do nothing.

## Input

- `timeline`: the video (as in T19).
- `comments`: the top comments, each with the `agent_no` who wrote it.
- `agents`: the engaged viewers who read them.

## Output

- `actions`: for agents who act, `agent_no`, `reply_to` (the comment's `agent_no`), `liked`
  and an optional `reply_text` (one short line; no handles, no numbers). An agent never
  replies to its own comment.
