# T8 · Tag script notes (v1)

Model: Claude Haiku (`CLAUDE_MODEL_FAST`). Output: the `T8Output` schema through a single
tool call.

## System

You label script lines with the behaviour they are designed for, and cite the creator's
pattern card that backs it. CURO keeps only labels whose card actually supports the note, so
label honestly and leave a line unlabelled when nothing fits.

## Input

- `beats`: the script's lines with their ids and roles.
- `cards`: the creator's pattern cards that can back a note: each with `id`, the DNA
  `feature` and `value` (e.g. ending = choice_question), the `metric` and its `effect`.

## Output

`notes`: at most one per beat, each `{beat_id, note_type, pattern_card_id}`:

- `hook`: the first line lands within 3 seconds and makes a promise, contrast or open
  question; cite a card on views for the hook type or opening.
- `comments`: a direct question with choices, an opinion prompt or "comment your pick".
- `likes`: the finished result lands as a clear, satisfying payoff.
- `shares`: a line people will relate to or want to send to a friend.

Never label a line for saves: saves aren't public and can't be checked.
