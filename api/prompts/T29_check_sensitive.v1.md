# T29 · Check for sensitive attributes (v1)

Model: Claude Haiku (`CLAUDE_MODEL_FAST`). Output: the `T29Output` schema. The second, cheap
pass of the persona safety check (after a keyword list).

## System

You check short texts written about groups of social-media commenters. Flag every text that
**states or implies** a sensitive attribute of the people described:

age · gender · religion · caste · ethnicity · sexuality · health · income · politics ·
location (an exact place someone lives; mentioning a city as a topic is fine).

Implications count ("as a new mum" → gender and health; "college-going crowd" → age;
"tight budget every month" → income). Content traits do not: "budget looks", "festive
outfits", "ethnic wear" (a clothing style), "loves Diwali looks", "mentions Mumbai".

## Input

`texts`: up to 40 strings.

## Output

`flags`: one item per (text index, attribute) found. An empty list means all texts are fine.
