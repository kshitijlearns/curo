# Recorded vendor and model responses

Contract tests (`../test_contracts.py`) replay every `*.json` file under this folder through
the real provider's parser (`curo/providers/contracts.py`) and check CURO's rules on the
result: the task's schema, missing counts as `None` (never 0), 768-long normalised vectors.

There are none yet: they are recorded once the keys arrive, with
`python tools/record_contracts.py …` (see `docs/INTEGRATION.md`). Layout:

```
public_data/apify/{profile,reels,comments,hashtag}/*.json
public_data/brightdata/{profile,reels,comments,hashtag}/*.json
video/gemini/*.json
embedding/gemini/*.json
llm/claude/T2 … T15/*.json
```

Record only your own test account. The recorder replaces every other handle with a
placeholder and masks @mentions before it writes a file; check a new file before committing
it anyway.
