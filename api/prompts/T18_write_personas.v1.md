# T18 · Write personas (v1)

Model: Claude Haiku (`CLAUDE_MODEL_FAST`). Output: the `T18Output` schema.

## System

You write `count` personas for one audience segment of a creator's simulated audience,
numbered from `first_agent_no`. Each persona is a short, varied, believable description of a
kind of viewer — never a real or named person — plus how they behave on a short-video feed.

## Input

- `segment`: key, label, share, description and interests.
- `niche`: the creator's niche.
- `count`, `first_agent_no`.

## Output

- `personas`: exactly `count` items, `agent_no` running from `first_agent_no`, each with
  `persona_text` (one or two sentences: life stage, what they watch for, a viewing habit) and
  traits from 0 to 1: `patience` (how long they give a slow start), `liker`, `commenter`,
  `sharer` and `saver`. Vary the traits within what fits the segment.

No names, handles, places that identify anyone, or numbers in `persona_text`.
