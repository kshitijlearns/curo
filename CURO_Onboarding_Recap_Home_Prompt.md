# CURO v2.1: onboarding, the monthly Creator Recap and the new Home (prompt for Claude Code)

This prompt builds on `CURO_WebApp_ClaudeCode_Prompt.md` (CURO v2: the Vercel web app). If v2 isn't finished, finish it first, then apply this as new phases. Where this prompt and v2 disagree, **this prompt wins**. Log every change in `docs/DECISIONS.md`.

Read first:
- `README.md`, `PLAN.md`, `PLAN_V2.md`
- `docs/DECISIONS.md`, `docs/INTEGRATION.md`
- the v2 prompt

All v2 rules still hold:
- public data only, no Instagram login
- missing means unknown, never zero
- numbers are relative to the creator's own baseline
- the no-new-numbers check on every AI text a creator reads
- `MOCK_MODE` for every outside service
- the six-colour CURO design system, with no gradients

## What this adds, in one paragraph

A new creator opens CURO and types their Instagram username. While three short onboarding screens explain what CURO does (Home, Idea Studio, Simulator), the backend reads their public profile and reels and builds their first **Creator Recap**: a fun, full-screen story of their data, like an annual music recap but about their content. It ends by revealing **what type of creator they are**. The recap then lives at the top of Home. Below it are three swipeable sections: **Opportunity areas**, **Trending for you** and **What your followers will love**. A new recap arrives at the start of every month, and it's the first thing a creator sees when they open the app that month.

---

## 1. Naming and brand rules

- Call the feature **"Creator Recap"** (or "Your Month on CURO"). **Never use the word "Wrapped"** or any other company's product name, logo, fonts or signature visual style.
- Build the energy with CURO's own design system:
  - big bold numbers, full-bleed colour slides in the six CURO colours, motion and playful copy
  - no gradients
  - Figtree typography
- All Instagram-related copy must be accurate to **public data**. Never imply CURO sees private analytics.

---

## 2. The new first-run flow

```
Open app → 1. Username → 2. Onboarding (3 screens) ─┐
                     │                                ├→ 4. Creator Recap (story) → 5. Save your account → 6. Home
                     └→ background: read profile + build recap ┘
                                 (3. Waiting screen, only if the recap isn't ready yet)
```

### Step 1: Username (the very first screen)
- One input: "What's your Instagram username?", with an `@` prefix and a big Continue button.
- Validate as they type (allowed characters, no spaces). On Continue, call `POST /api/v1/onboarding/username`.
- **Create the session immediately, without asking for an email.** Use Supabase **anonymous sign-in** (check the current Supabase docs). If it isn't available, use a server-issued temporary session tied to a device token. Either way, the session is converted to a real account in step 5.
- **Errors:**
  - "We couldn't find that account. Check the spelling?"
  - **Private account:** "CURO can only read public profiles. Make your account public or try another one." Never ask for a password or Instagram login.
- If the account already belongs to a CURO user, offer **"Sign in instead"** (email OTP).

### Step 2: Onboarding (3 screens, explaining CURO)
- Swipeable cards with page dots, Next, and Skip (top right).
- Each card has a large illustration built from the existing `Sketch` component style, a title and two short lines. Use this copy, polished but keeping the meaning:

| # | Title | Body |
|---|---|---|
| 1 | **Your Home: know what's working** | Every month you get a Creator Recap, a story of your content and your audience. Below it: opportunity areas, what's trending in your niche, and ideas your followers will love. |
| 2 | **Idea Studio: create with CURO** | Pick an opportunity or bring your own idea. CURO helps you shape it into a script, a shot-by-shot storyboard and a caption with hashtags, in your own style. |
| 3 | **Simulator: test before you post** | Record your reel and upload it. 1,000 AI followers built from your real audience watch it, react, comment and skip. Then you can ask any of them why. |

- **Live progress strip.** At the bottom of every onboarding card, show what the backend is doing right now, from the real `jobs` progress via Supabase Realtime, with polling as fallback:
  - "Reading your profile…"
  - "Found 48 reels"
  - "Reading what your audience says…"
  - "Building your recap…" ✓
- The last onboarding card's button reads **"See my recap"**. It's enabled when the recap is ready; until then it reads "Almost there…".

### Step 3: Waiting screen (only if needed)
If the creator finishes onboarding before the recap is ready:
- Show a fun waiting screen: a looping animation in CURO colours, the live progress strip, and rotating one-line teasers built from data already collected ("You've posted 48 reels so far 👀").
- **Timeouts:**
  - After **90 seconds**, offer "We'll notify you when it's ready" and let them into Home with a placeholder recap card that fills in live.
  - After **5 minutes**, log it as an error and show a friendly fallback.

### Step 4: The first Creator Recap
The first recap is **"Your story so far"**, covering the creator's recent history (section 3.3). It plays full screen, and its last slide is the creator-type reveal plus a share card.

### Step 5: Save your account
- After the recap: "Save your recap and get a new one every month". Ask for an email and sign in with an email one-time code.
- Convert the anonymous session to that account, keeping all data.
- **"Maybe later"** is allowed: let them into Home, and remind them on the next app open. Anonymous accounts that never convert are deleted after 30 days, including all their data.

### Step 6: Home
Home opens (section 5).

### Backend for the first run
- `POST /api/v1/onboarding/username` starts `onboard_public` (from v2, with its cost limits). When enough data exists, it enqueues **`build_recap` with kind `first`**.
- **Speed budget: the first recap must be ready in about 60–90 seconds.** So the first recap uses only fast data:
  - profile
  - metadata and counts for the latest 50 reels
  - captions and hashtags
  - comment text for the newest 10 reels
- Slides that need video analysis (DNA) are **left out of the first recap** if DNA isn't ready. The full pipeline keeps running in the background for Studio and the Simulator.
- Expose progress steps on the job (`profile`, `reels`, `comments`, `recap`) for the progress strip.

---

## 3. The Creator Recap

### 3.1 Principles
1. **Every number comes from code, never from the AI.** `services/recap.py` computes all facts deterministically from stored data and is unit-tested. Claude only writes the playful copy around those facts, through a new task **T16 "write recap copy"**. The no-new-numbers validator checks every line, regenerates once on failure, then falls back to a template line.
2. **Public data only, honestly labelled.**
   - CURO cannot see saves, reach, watch time, demographics or a follower/non-follower split.
   - Where a slide talks about "people who don't follow you yet", it uses the public proxy **views ÷ follower count** and says so in small text ("based on public views vs. your follower count").
3. **Skip, don't fake.** Each slide has a minimum-data rule. If the data isn't there, the slide is dropped, never filled with zeros or guesses. A recap has at least 5 and at most 12 slides.
4. **Make the creator feel good, honestly.**
   - Lead with wins and growth. Compare the creator with their own past, never with other creators.
   - A tough month is framed kindly and constructively ("A quieter month, and here's what still worked"). Never invent a win.
5. **No individual commenters.** Show comment text only, never handles or profile pictures. Skip comments that look like spam or contain personal data (phone numbers, emails).

### 3.2 The story player
- **Layout:** full-screen vertical story. On desktop Chrome, keep the phone-width column.
- **Controls:**
  - segmented progress bars at the top
  - tap right = next, tap left = back, press and hold = pause
  - keyboard ← → and space
  - swipe down or ✕ to close
- **Timing:** each slide auto-advances after 6 seconds (8 for slides with more text). Respect `prefers-reduced-motion`: no auto-advance and no count-up animation.
- **Motion:**
  - numbers count up
  - charts draw in
  - each slide gets a full-bleed background from the six CURO colours, rotating, with high-contrast text (check WCAG AA)
  - small confetti or shape bursts in palette colours only on milestone slides
- **Audio:** none by default. Add a later TODO for optional sound.
- Each slide has a small "ⓘ How we got this" link that opens a sheet with the exact facts and formula behind it, for trust.
- **Replay:** the latest recap card on Home replays the story. Past recaps live in "All recaps".

### 3.3 Periods
- **First recap ("Your story so far"):** the creator's last 90 days of public reels, or their whole history if shorter.
  - Follower growth isn't available yet: CURO has no earlier snapshot. So it shows the current follower count and the next milestone instead.
- **Monthly recap:** the previous calendar month in the creator's time zone (default Asia/Kolkata), generated on the **1st of each month**.
  - A Vercel cron enqueues `build_recap` (kind `monthly`) for every active creator. Inactive creators (paused per v2) get theirs on next login.
- **"New recap" moment:** the first time a creator opens the app after a new recap is ready, it opens full screen before Home. After it's viewed, it sits at the top of Home with a "New" badge until the next one.
- **Month-specific data:**
  - **Follower gain** comes from `account_snapshots` (follower count on the first vs last snapshot of the month).
  - **Views in the month:** for reels posted in the month, use their latest counts. For older reels, add the views gained between the month's first and last snapshots, where snapshots exist.
  - Label this "views on your reels this month (public counts)".

### 3.4 Slide catalogue
Build these slide types. Each has an ID, its facts (computed), a minimum-data rule and copy guidance. The recap builder picks the slides whose rule passes, orders them for a good story arc (a hook, then wins, then audience, then style, then the reveal), and caps the total at 12.

| # | Slide ID | What it shows | Facts (code) | Minimum data | Example copy (T16 writes the real lines) |
|---|---|---|---|---|---|
| 1 | `intro` | Opening title card with the month (or "your story so far") and the creator's handle | period, handle | always | "October on @riya.styles. Let's unpack it." |
| 2 | `posting` | How much they posted, plus their most-used posting day and time | reels in period, posting day/hour mode, weeks with ≥1 post | ≥1 reel | "You posted **14 reels**. Sunday evenings were your thing." |
| 3 | `streak` | Consistency: longest run of weeks (or days) with a post | longest weekly streak | ≥3 reels | "**5 weeks** in a row without missing a beat." |
| 4 | `views_total` | Total views in the period, counting up, with a fun scale comparison | total views; comparison from a fixed list (§3.6) | ≥1 reel with views | "Your reels were watched **2,48,300 times**. That's a full cricket stadium, eight times over." |
| 5 | `beyond_followers` | Reach past their follower count (public proxy) | median and best views ÷ followers | followers > 0 | "Your best reel reached **6× your follower count**. Lots of new people found you." Small print: "Based on public views vs. followers." |
| 6 | `top_reel` | Their biggest hit: thumbnail, title, views and how it compared with their usual | top reel by views; lift vs their median | ≥3 reels | "**One kurta, five dupattas** did **3.4× your usual views**." |
| 7 | `most_talked` | The reel that got people talking most, by comments per view | top comment-rate reel; its comment count | ≥3 reels with comments | "This one got your audience talking: **184 comments**." |
| 8 | `most_shared` | The reel people sent to friends most | top share count (where public) | ≥2 reels with public shares | "People couldn't stop sending this one: **1,240 shares**." |
| 9 | `audience_voice` | What their audience said: top comment by likes, the top 3 comment themes, most-used emoji | from labelled comments and themes | ≥30 comments | "Your audience's favourite words: *'where is it from'*, *'part 2'*, *'so relatable'* 💖" |
| 10 | `language_mix` | The languages in their comments | language shares | ≥30 comments, ≥2 languages | "Your comment section speaks **Hinglish** (62%) and English (31%)." |
| 11 | `best_time` | When their reels do best (their own history) | best day × hour by views lift | ≥8 reels | "Your golden hour: **Sunday, 7–9 pm**." |
| 12 | `superpower` | Their strongest content pattern (needs DNA) | top pattern card by effect, n ≥ 5 | pattern card with n ≥ 5 | "Your superpower: **reels that start with a question** get **1.8× your usual views**." |
| 13 | `top_topic` | The topic they owned (sub-cluster with best lift) | sub-cluster label + lift | ≥2 sub-clusters | "You're the go-to for **festive styling**." |
| 14 | `growth` | Followers gained this month (monthly only), or the next milestone (first recap) | follower delta, or the next milestone and the gap to it | monthly: 2 follower snapshots; first: follower count | "**+1,320 new followers** this month!" / "**2,140** followers to go until 10K." |
| 15 | `vs_last_month` | Month-over-month change in views and posts (monthly, from the second recap on) | deltas vs the previous recap | previous recap exists | "Up **38%** in views from September. Keep going." |
| 16 | `creator_type` | **The reveal:** creator level + creator archetype (§3.5), with a short line about each | level, archetype, the archetype's evidence | always | "You're a **Rising Voice** · **The Storyteller**" |
| 17 | `share_card` | A shareable summary card (§3.7) with **Share** and **Download** | top 4 stats + creator type | always | — |
| 18 | `next_up` | Closing slide that leads into the product | count of opportunities ready | always | "Your next month starts here. **5 opportunities** are waiting." Button: **Let's go** → Home |

The number formats follow the creator's locale: Indian grouping (2,48,300) for `en-IN`, and short forms like 2.4L or 248K where the number is a headline.

### 3.5 What type of creator are you
Two parts, shown together on the reveal slide and the share card.

**A. Creator level, from follower count (with post count as a modifier):**

| Followers | Level | One-liner |
|---|---|---|
| 0–100 | **The Spark** | Curious and brave: you took the first step and started creating. |
| 101–1,000 | **The Explorer** | You're finding your voice and your people. |
| 1,001–10,000 | **The Community Builder** | A real community is forming around your content. |
| 10,001–50,000 | **The Rising Voice** | People are paying attention, and your reach is growing. |
| 50,001–100,000 | **The Trendsetter** | What you post starts conversations in your niche. |
| 100,001–500,000 | **The Influencer** | You shape what your audience watches and buys. |
| 500,001–1,000,000 | **The Star** | A big, loyal audience shows up for you. |
| 1,000,000+ | **The Icon** | You're a household name in your space. |

**Post-count modifiers** (shown as a small tag):
- fewer than 10 posts in total: "Just getting started"
- 4 or more reels in each of the last 4 weeks: "Consistency champ"
- 100 or more posts in total: "Seasoned creator"

Keep the thresholds and copy in one config file so they're easy to change.

**B. Creator archetype, from how they create** (deterministic scoring, highest score wins, with a runner-up shown as "with a dash of…"):

| Archetype | Signal (from reels in the period) |
|---|---|
| **The Storyteller** | Narrative shape is story arc, day-in-life or before/after in most reels |
| **The Teacher** | Most reels have the intent "educate": tips, how-tos, lists |
| **The Entertainer** | Most reels have the intent "entertain" or a comedy/skit format |
| **The Trend Rider** | A high share of reels use trending audio, or hashtags from the trend feed |
| **The Conversation Starter** | Comment rate is their strongest metric relative to their baseline |
| **The Aesthetic Curator** | One consistent visual style, and like rate above their baseline |
| **The Consistent One** | Posting rhythm: a reel in nearly every week |
| **The Night Owl** | Most reels posted after 9 pm |

When DNA isn't ready (first recap), score the archetypes from captions, hashtags, posting times and counts. A cheap Claude Haiku classification of captions into intent and format is allowed, with output restricted to the fixed lists. Store the score and its evidence so "ⓘ How we got this" can explain it.

### 3.6 Fun comparisons ("that's like…")
- Use a **small fixed list** in config. Each entry has a label, a size and a source note, e.g. "a 30,000-seat cricket stadium" or "a 40-seat classroom". Keep generic, verifiable sizes. Don't make up facts about real venues; if you name a real place, cite its published capacity in the config.
- Pick the comparison that gives a number between 2 and 50. The multiplication happens in code; T16 only gets the result.

### 3.7 Share card
- **Format:** a 1080×1920 image in CURO colours. It shows the handle, the period, 3–4 headline stats, the creator level and archetype, and a small CURO logo and URL.
- **Render** it client-side to a canvas → PNG, or server-side with an image route. Choose one and log it.
- **Buttons:**
  - **Share** uses the Web Share API with files where Chrome supports it (Android).
  - **Download** saves the PNG on desktop.
- Never include another person's comment or handle on the share card.

### 3.8 Data model and jobs
- **New table `recaps`:**
  - columns: `id`, `creator_id`, `kind` (`first`|`monthly`), `period_start`, `period_end`, `status` (`building`|`ready`|`failed`), `facts` jsonb, `slides` jsonb (ordered: `{slide_id, facts, copy, visual}`), `creator_level`, `level_modifier`, `archetype`, `archetype_runner_up`, `archetype_evidence` jsonb, `share_image_path`, `viewed_at`, `version`, `created_at`
  - unique on (`creator_id`, `kind`, `period_start`)
  - RLS: own rows only
- **New job `build_recap(creator_id, kind, period)`:** resumable steps — compute facts → choose slides → T16 copy (one call for all slides, structured JSON) → validate → store → (optional) render the share image.
- **New task T16 "write recap copy":**
  - Input: slide facts plus tone rules.
  - Output: per slide, a `headline` (≤ 60 characters) and a `subline` (≤ 90 characters).
  - Model: `CLAUDE_MODEL_MAIN`.
  - Tone: warm, playful, proud, second person, Indian-English-friendly, at most one emoji per slide, no slang that could read as mocking.
  - It gets the numbers to quote and may not introduce others.
  - The mock returns template lines from the facts.
- **Endpoints:**
  - `GET /api/v1/recaps/latest`
  - `GET /api/v1/recaps`
  - `GET /api/v1/recaps/{id}`
  - `POST /api/v1/recaps/{id}/viewed`
  - `GET /api/v1/recaps/{id}/share-image`
- **Cost:** about one Claude call per recap (≈ $0.02) plus data already collected. Record it in `usage_ledger` under feature `recap`. Recaps don't use credits and are free on every plan.

---

## 4. Relation to v2

- v2 removed the old Insights screen (reel phases, audience cards, carousel with arrows). **It stays removed.** The Creator Recap replaces it as the Insights section, reusing the existing services where useful: baselines, comment labelling and themes, top-comment ranking, pattern cards, sub-clusters.
- Peer tracking stays removed. Nothing in the recap compares the creator with named other creators.
- The v2 collection limits stay, with one addition: `account_snapshots` must record the follower count at least **daily** for active creators, so monthly follower growth works. The discovery run every 12 h already fetches the profile; store its follower count.

---

## 5. The new Home

Home is one vertical scroll with **four sections**. Each section is a **horizontal swipeable carousel**:
- cards snap into place
- the next card peeks at the edge
- page dots appear under the section
- keyboard and trackpad scrolling work on desktop

Order:

### 5.1 Insights: your Creator Recap
- **Large card:** the cover of the latest recap (month, creator level and archetype, one headline stat). A "New" badge until viewed. Tap → plays the story.
- **Then:** smaller cards for 3–4 highlight stats from the latest recap (tap → jumps to that slide).
- **Last:** an "All recaps" card.
- **Empty state** (recap still building): a skeleton card with the live progress strip.

### 5.2 Opportunity areas
- The v2 opportunity cards (top 5): name, score ring, tag, and one line on why it fits.
- Swipe to see all 5. Tap → opportunity detail. "Open in Studio" stays.

### 5.3 Trending for you
- The v2 trend cards ranked for this creator: name, why it's rising, how crowded it is, its timing window, and 1–2 example angles.
- Tap → trend detail with "Make this my way" → Studio, carrying the trend as context.

### 5.4 What your followers will love (new)
Content ideas driven by **this creator's own audience and best work**, not by trends. Build candidates from:
1. **Audience requests and questions:** comment themes like "part 2", "where is it from", "budget version", "tutorial please". Use the share of comments and an example comment.
2. **Proven formats:** the creator's top sub-clusters and pattern cards that lift likes, comments or shares, as "more of what worked".
3. **Persona interests:** the audience segments built for the Simulator (v2 §3.5): what each segment engages with most.

Each card shows:
- an idea title
- **why your followers will love it**, with evidence: "**38 comments** asked for a budget version", or "Your 'one item, many looks' reels get **1.7× your usual shares**"
- the audience segment it's for ("Festive planners")
- **Open in Studio**

**Scoring:** `0.45 × audience demand + 0.35 × proven performance + 0.20 × novelty` (not repeating their last 10 reels). Show the top 5.

**Dedupe:** never show the same idea in Opportunity areas and here; merge near-duplicates by embedding similarity and keep the higher-scoring section.

**Data:** add a `follower_ideas` table (`creator_id`, `title`, `why`, `evidence` jsonb, `segment`, `score`, `parts`, `status`, `created_at`). Rebuild it weekly and after each recap.

**New task T17 "name and explain a follower idea":** Claude Sonnet, evidence in, title and why out, with the no-new-numbers check. Write a mock.

### 5.5 Other Home details
- The header stays: lavender "Curo" with Saved.
- Every section has a one-line title and a "See all" link opening a full list.
- Loading: skeleton cards. Error: a friendly retry card per section, so one failure doesn't block Home.
- Pull to refresh (mobile web) or a refresh button re-fetches sections only, without triggering new scrapes.

---

## 6. Copy and tone guide (for T16, T17 and UI text)

- Second person, warm, proud, playful. Short sentences.
- Celebrate effort as well as results ("You showed up 14 times this month").
- Use Indian number grouping and ₹ where money appears. Hinglish is fine when it fits the creator's own comment language mix.
- Never: comparisons with other creators, words like "fail" or "flop", guilt about posting less, promises about the algorithm or guaranteed results.
- Saves, reach, watch time and demographics are never claimed. The beyond-followers slide always carries its proxy note.

---

## 7. Tests (required)

- **Unit tests for `services/recap.py`:**
  - every fact
  - every slide's minimum-data rule
  - slide selection and ordering
  - level thresholds at every boundary (100, 101, 1,000, 1,001, …)
  - every modifier
  - archetype scoring with ties
  - comparison selection
  - Indian number formatting
- **Recap tests on three fixture creators:**
  - a beginner: 60 followers, 6 reels, few comments
  - a mid creator: the demo creator, about 48K
  - a large creator: 1.2M
  - Check slide counts (5–12), that no slide shows a missing number as 0, and that every T16 line passes the validator.
- **First-run flow end to end on mocks:** username → onboarding → recap ready within the mock time budget → save account → Home with four sections.
- **Accessibility:** story player keyboard controls, `prefers-reduced-motion`, colour contrast.

---

## 8. Build order: stop after each phase and report

After each phase, give me a short report and the exact steps to check it in Chrome.

1. **Plan.** Update `PLAN_V2.md` with a v2.1 section covering the flows, tables, jobs, T16/T17 schemas, the slide catalogue and the Home layout. *Check:* I approve.
2. **First-run flow.** Username screen, anonymous session, the 3 onboarding cards with the live progress strip, the waiting screen, save-account and conversion. *Check:* entering the demo handle in Chrome runs the whole flow on mocks.
3. **Recap engine.** `services/recap.py`, the slide catalogue, level and archetype, comparisons, the `recaps` table, the `build_recap` job, T16 with mock and validator, and the monthly cron. *Check:* the three fixture creators each get a sensible recap; the facts sheet matches hand calculations (include them in the report).
4. **Story player and share card.** *Check:* tap, keyboard and swipe all work, reduced motion works, and the share image downloads correctly.
5. **New Home.** All four swipeable sections, "What your followers will love" with T17 and dedupe, and empty, loading and error states. *Check:* the Home order matches section 5 and every card opens the right place.
6. **Hardening.** Tests, accessibility, docs (`docs/DECISIONS.md`, `docs/INTEGRATION.md`), then commit and push to the same branch and pull request as v2 (or a new branch `v2.1-recap` with its own pull request if v2 is already merged). Run the secret scan from v2 §5 before pushing. *Check:* the pull request contains no secrets and all checks pass.

Start with phase 1.
