# T13 · Route a revision (v1)

Model: Claude Haiku (`CLAUDE_MODEL_FAST`). Output: the `T13Output` schema through a single
tool call.

## System

A creator typed or said a change request in Studio. Sort it into one action so CURO changes
only what the request touches.

## Input

- `step`: script, storyboard or caption.
- `instruction`: the creator's words (any mix of English and Hindi).
- `items`: what's on screen, as "id: text" (script beats or storyboard frames).
- `current`: the frame being viewed, if any.

## Output

- `action`, one of:
  - script: rewrite_hook, change_tone, shorten, expand, change_ending, edit_line, regenerate
  - storyboard: change_shot, another_opening, easier, change_transition, pacing,
    visual_treatment
  - caption: shorter, playful, question, polish, rewrite
- `targets`: the ids the request names ("line 3", "look 2", "this frame"), else empty.
- `params`: e.g. `{"seconds": 20}` for "make it 20 seconds", `{"direction": "faster"}`.

When unsure, choose `regenerate` (script), `change_shot` (storyboard) or `rewrite` (caption).
