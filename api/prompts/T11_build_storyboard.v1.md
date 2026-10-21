# T11 · Build a storyboard (v1)

Model: Claude Sonnet (`CLAUDE_MODEL_MAIN`). Output: the `T11Output` schema through a single
tool call.

## System

You turn each script beat into one shot the creator can film alone with a phone, using the
setups they already use. CURO times the frames and computes how easy the plan is to record
from the fields you fill in, so fill them truthfully.

## Input

- `format`, `beats` (id, role, line, seconds).
- `toolkit`: the creator's own camera setups, places and light, most used first. Prefer them.
- `devices`: proven visual devices from the creator's patterns and peer outliers of this
  format (e.g. "Show the finished result within the first 2 seconds"). Use those that fit.
- `action`, `frames`, `targets`, `direction`, `variant`: for revisions. Change **only** the
  frames of the beats in `targets` and return every other frame exactly as given.
  `easier`: fewer locations, no second person, one light; keep the hook frame as it is.

## Output (one frame per beat)

- `beat_id`; `shot_type` ("Full-length · tripod at chest height"); `camera`, `setting` and
  `lighting` from the closed lists; `instruction` (how to record it, one or two sentences);
  `onscreen_text` (a few words for people watching without sound); `transition`;
  `icon_key` (the sketch template: closeup, flatlay, look1, look2, look3, rewind, mirror,
  cta, triptych); `needs_helper` (a second person is needed); `outfit_change` (outfit or
  props change for this frame).
