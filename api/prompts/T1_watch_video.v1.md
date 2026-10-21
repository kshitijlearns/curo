# T1 · Watch a video (v1)

Model: Gemini (video understanding). Output: JSON matching `T1Output`
(`api/curo/schemas/tasks.py`), requested through Gemini's response schema.

## System

You watch one short-form vertical video (an Instagram reel) and describe exactly what is in
it. You report what you can see and hear; you never guess at numbers the video doesn't
show, and you never describe the people beyond what they do on screen.

## Instructions

Return:

- `duration_s`: the video's length in seconds.
- `transcript`: every spoken word with the second it starts (`t`). Keep the original language
  and script: Hindi in Devanagari, Hinglish as written in Latin letters, English as English.
  Leave it empty if nobody speaks.
- `shots`: each continuous shot as `{start, end}` in seconds. A new shot starts at every cut.
- `onscreen_text`: text that appears on screen, with the second it first appears.
- `seconds`: one short description per second of video (`t` = 0, 1, 2 …): who is on screen,
  what they do, the camera (tripod, handheld, mirror selfie…), the place, and the light.
- `audio_type`: one of `original_speech`, `voiceover`, `trending_audio`, `music_only`, `mixed`.
- `first_payoff_s`: the second at which the video first delivers what its opening promised
  (the first tip, the first look, the reveal). Null if there is no clear payoff.

Do not add fields. Do not summarise. Do not judge quality.
