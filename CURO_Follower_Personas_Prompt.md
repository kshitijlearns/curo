# CURO v2.2: Follower Personas (prompt for Claude Code)

This prompt builds on two earlier prompts:
- `CURO_WebApp_ClaudeCode_Prompt.md` (v2: the Vercel web app)
- `CURO_Onboarding_Recap_Home_Prompt.md` (v2.1: onboarding, Creator Recap, new Home)

Apply this after them, as new phases. **Where this prompt disagrees with them, this prompt wins.** Log every change in `docs/DECISIONS.md`.

Read first: `README.md`, `PLAN.md`, `PLAN_V2.md` (including the v2.1 section), `docs/DECISIONS.md`, `docs/INTEGRATION.md`, and both earlier prompts.

All earlier rules still hold:
- public data only, no Instagram login
- missing means unknown, never zero
- every number comes from code, and the no-new-numbers check runs on every AI text a creator reads
- `MOCK_MODE` for every outside service
- the six-colour CURO design system (`#5B73F2`, `#C3BFF2`, `#F2D4E2`, `#FFFFFF`, `#E4E4EC`, `#242424`), Figtree, no gradients

---

## 0. What this adds, in one paragraph

Every creator gets **4 Follower Personas**: four characters that stand for the main groups in their real audience, built from the public comments people leave and the reels those people respond to. Each persona has a name, a share of the audience, a voice, things they love and things they'd skip, and a distinctive **dot-cluster avatar**. The personas appear in four places:
- **Creator Recap:** introduced after the creator-type reveal.
- **Home:** a new top section, **"What your followers think of you"**, gives each persona a card. It replaces "What your followers will love", which is removed.
- **Idea Studio:** the personas sit above the chat box and react to every idea. The overall score stays, and tapping a persona shows **that persona's own opinion**.
- **Simulator:** the 1,000 AI followers are now drawn from these same four personas.

---

## 1. What a Follower Persona is (and isn't)

### 1.1 Definition
A Follower Persona is a **summary of a group of real comments**, written as a character so it's easy to relate to. It is **never a real person** and never a copy of one.

Each creator has **exactly 4** personas, ordered by share (largest first). A persona has:

| Field | Meaning | Example |
|---|---|---|
| `name` | 2–3 words, warm or neutral, never mocking | "The Festive Planner" |
| `short_name` | for tight spaces | "Festive Planner" |
| `share` | share of the creator's **engaged comments** in this group (code) | 31% |
| `tagline` | one line on who they are | "Plans every festival look weeks ahead." |
| `comes_for` | 2–4 things they come to the creator for | festive outfits, budget swaps |
| `loves` | 2–4 content traits they respond to, with evidence | quick transformations, "3 ways" formats |
| `wants_more` | 1–3 requests they keep making | budget versions, where-to-buy links |
| `turn_offs` | 1–3 things that lose them, with evidence | long intros, no prices |
| `engagement_style` | how they engage | mostly comment questions; tag friends often |
| `language` | language mix of their comments | Hinglish 70%, English 30% |
| `voice` | tone guide for their first-person lines | excited, practical, uses "yaar" sometimes |
| `typical_comment` | a **paraphrased** representative comment, never verbatim, never with a handle | "Love this! Can you do a under-₹1,000 version?" |
| `confidence` | low / medium / high, from how much data backs it | high |
| `avatar` | seed + colour + mood (section 2) | — |

### 1.2 Hard rules
- **No real individuals.** Personas come from clusters of comments, never from one commenter. Commenter handles are never stored, shown or used (v2 rule). Every quote a persona "says" is generated or paraphrased, never a real comment copied with attribution.
- **No sensitive attributes.** Never infer or state age, gender, religion, caste, ethnicity, sexuality, health, income bracket, political views or exact location. Language mix and **topics people mention** (e.g. "mentions Mumbai and Pune") are allowed, at group level only.
- **Likes are aggregate.** Public data shows *how many* liked a reel, not *who*. So a persona's like behaviour is inferred from the like and share rates of the reels its comments cluster on. Copy must say "reels they comment on also get…", never "they liked".
- **Always labelled.** Wherever personas appear: "Built from your public comments. Personas are summaries, not real people."
- **Honest confidence.** If data is thin, the persona is marked as an early guess (§3.5).

---

## 2. The persona avatar: dot-cluster characters

Each persona has a living avatar made of dots: a soft circular cluster of small dots that breathes and reacts. Design it **from scratch** as CURO's own visual. Don't copy another product's avatars, illustrations or assets.

### 2.1 Spec
- **Component:** `PersonaAvatar` (SVG, React), props `{seed, color, mood, size, animated, state}`.
- **Shape:** 18–40 dots of 2–3 sizes inside a circle, placed by a **deterministic** pattern from `seed` (Poisson-disc or a seeded spiral). The same persona looks the same everywhere and across months.
- **Colour:** each of the 4 personas gets one fixed CURO colour, in order of share: **blue `#5B73F2`**, **lavender `#C3BFF2`**, **pink `#F2D4E2`**, **ink `#242424`**. Use dot opacity (40–100%) for depth.
  - Light dots on white need a hairline ring in `#E4E4EC` so they stay visible.
  - Check contrast in the light and dark backgrounds the app uses.
- **Moods** (shape the cluster; no faces, eyes or mouths):

| Mood | How the dots arrange |
|---|---|
| `neutral` | calm round cluster |
| `love` | dots lift into an upward arc and pulse once |
| `like` | slight upward drift |
| `unsure` | dots spread out a little, slow sway |
| `skip` | cluster drifts sideways and dims slightly |
| `thinking` | dots orbit slowly |
| `listening` | gentle breathing, used while the creator types |

- **Motion:** spring easing that matches the app's nav animation. Respect `prefers-reduced-motion`: static mood shapes, no orbiting.
- **Sizes:** 24 px (inline), 40 px (Studio row), 64 px (cards), 120 px (recap and detail).
- **Accessibility:** `role="img"` and `aria-label="The Festive Planner, 31% of your comments, mood: love"`.

### 2.2 Persona identity across months
Personas are rebuilt monthly. Keep them **stable**: match each new cluster to last month's persona by centroid similarity, and keep the same name, colour and avatar seed when they match (cosine ≥ 0.8). Only a genuinely new group gets a new persona. When one replaces another, show "A new group is showing up: …" in the next recap.

---

## 3. Building the personas

### 3.1 Inputs (all already collected by v2)
- labelled comments (T3): text, intent, sentiment, theme, language, bot flag
- which reel each comment is on, and that reel's DNA, rates and lifts vs the creator's baseline
- comment themes and pattern cards
- for creators with very few comments: niche priors from all CURO creators (cross-creator pattern cards and theme distributions)

### 3.2 Pipeline: job `build_personas(creator_id)`
Resumable steps (v2 job rules):

1. **Collect** non-bot, non-spam comments from the creator's analysed reels. Use all comments CURO holds, weighted toward the last 90 days.
2. **Embed** each comment (comment text + its theme + intent + language). Use the embedding provider, cached per comment.
3. **Cluster into exactly 4 groups**, on embeddings plus behaviour features (intent mix, language, which content sub-clusters they comment on):
   - Use k-means with k = 4, several seeds; keep the most stable result.
   - Every group must have ≥ 8% of comments. If a group is smaller, merge it into its nearest group and split the largest to get back to 4.
4. **Profile each group in code:**
   - share of comments
   - top themes and intents
   - language mix
   - sentiment
   - top content sub-clusters and formats they comment on
   - the like/share/comment lift of those reels vs baseline
   - the reels they respond to least compared with how often they appear (for turn-offs)
   - places and topics mentioned (group level)
   - a confidence score
5. **Write the persona** with new task **T18 "write follower persona"** (Claude Sonnet):
   - Input: the group profile facts.
   - Output: name, short_name, tagline, comes_for, loves, wants_more, turn_offs, engagement_style text, voice, typical_comment (paraphrased).
   - The no-new-numbers check applies. Forbid sensitive attributes in the prompt, and add a post-check that rejects outputs naming them (keyword list + a second cheap classifier pass).
   - Names must be distinct, kind, and never mock the group.
6. **Match to last month** (§2.2). Assign colour and seed.
7. **Write "what they think of you"** (§5.2) with task **T19**.
8. **Store** in `follower_personas` and a `persona_history` snapshot.

### 3.3 When it runs
- **Onboarding:** as part of the first recap (v2.1). Must fit the first-recap speed budget; if not, the recap shows the persona slides from a fast version built on the comments read so far, and refines them in the background.
- **Monthly:** before `build_recap` on the 1st.
- **Mid-month:** if 150+ new comments arrived since the last build, refresh, but keep identities.

### 3.4 Cost
About one embedding batch plus 2 Claude Sonnet calls per build (T18 for all 4 in one call, T19 for all 4 in one call): roughly $0.03–0.05 per creator per month. Record it in `usage_ledger` under feature `personas`. Personas are free on every plan.

### 3.5 Thin data
- **< 40 usable comments or < 5 reels with comments:** build **starter personas** from the creator's niche priors + their content + their comment language, and label them **"Early guess: gets sharper as people comment"**, with `confidence = low`.
- **40–150 comments:** `confidence = medium`.
- **> 150:** `high`.
- Show confidence as a small 3-dot meter on cards and detail views.

---

## 4. Creator Recap changes (onboarding and monthly)

Add a **"Meet your followers"** sequence **right after the `creator_type` reveal** (v2.1 §3.4) and before `share_card`:

| Slide ID | Content |
|---|---|
| `followers_intro` | "Now meet the people who watch you." The 4 avatars float in one by one (`neutral` → `love`). |
| `persona_1` … `persona_4` | One slide per persona, in share order: big avatar (mood `love`), name, share ("**31%** of your comments"), tagline, what they come for, and their first-person line about the creator from T19. Colour background = the persona's colour (ink persona uses a white background with ink dots). |
| `followers_summary` | All 4 personas in a 2×2 grid with names and shares. Tap any → its detail sheet (§5.3) after the recap closes. |

Other recap changes:
- **Slide cap:** raise the maximum from 12 to **18** when the persona slides are included. The persona sequence is never dropped if personas exist. If they're starter personas, add the "early guess" label on each slide.
- **Monthly recaps:** add `followers_shift` when a persona's share changed by ≥ 5 points or a new persona appeared ("**Festive Planners** grew from 22% to 31% of your comments this month").
- **Share card:** add a row of the 4 avatars with short names under the creator type. Names only; no quotes on the share card.
- **T16 (recap copy)** gets the persona facts; persona lines come from T19 and pass the same validator.

---

## 5. Home changes

### 5.1 New section order
1. **What your followers think of you** (new, at the top)
2. **Insights: your Creator Recap** (v2.1 §5.1)
3. **Opportunity areas** (v2.1 §5.2)
4. **Trending for you** (v2.1 §5.3)

**Remove "What your followers will love" completely:** UI, `follower_ideas` table (new migration to drop it), T17, its job and tests. Fold its useful evidence into the persona cards: each persona card's "wants more" can link to Studio.

When a **new recap** is ready, it still opens full screen first on app open (v2.1 §3.3). Home's order applies after it's closed.

### 5.2 "What your followers think of you": persona cards
A horizontal swipeable carousel of **4 cards**, one per persona, in share order, with snap, peek, dots and keyboard support (v2.1 rules). Above it, a one-line summary from code: "**3 of 4** of your follower groups are loving your recent reels."

**Each card** (design it fresh in the CURO system):
- **Top row:** `PersonaAvatar` (64 px, mood from their current sentiment), name, share chip ("31% of comments"), confidence dots.
- **The thought:** a speech-bubble-style block with their **first-person line about the creator**, e.g. "Your festive looks are my go-to for planning outfits. Just get to the final look faster!" Written by T19 from the group's facts.
- **Mood meter:** a 5-step scale from "Not feeling it" to "Big fan", from the group's sentiment and engagement lift (code). Label it in words, not just colour.
- **Loves:** 2 chips. **Wants more of:** 1–2 chips, each with a "Make this" link that opens Studio with the request as the idea seed and this persona preselected.
- **Evidence line:** "From 214 comments across 18 reels · updated 3 Oct."
- **Footer label:** "Built from your public comments. Personas are summaries, not real people."

**T19 "what this persona thinks of you":**
- Input: per persona, its profile facts, recent sentiment change, top-responded reels (titles), top requests, turn-offs with evidence.
- Output per persona: `thought` (first person, ≤ 140 characters, in the persona's voice), `mood` (one of the avatar moods), `loves[2]`, `wants_more[≤2]`.
- Must be specific to the creator's actual content, kind, and honest: a persona with low sentiment says so constructively, never rudely. No new numbers. Mock: template lines from the facts.

**Empty and thin states:**
- **Personas still building:** skeleton cards with breathing avatars.
- **Starter personas:** cards show "Early guess" and invite the creator to post and reply to comments to sharpen them.

### 5.3 Persona detail sheet
Tap a card to open a bottom sheet (or a side panel on desktop) with:
- a large avatar, name, tagline, share, confidence
- **What they come for**, **What they love** (each with evidence: "reels with a '3 ways' format get **1.7×** your usual shares in this group's favourite topics")
- **What makes them scroll past** (turn-offs with evidence)
- **How they engage** (comments questions, tags friends, shares…)
- **Their favourite reels:** up to 4 thumbnails of the reels this group responds to most
- **A typical comment** (paraphrased, labelled as such)
- **Language mix**
- **Over time:** share and mood for the last 6 months, once there's history
- **Chat with this persona** (§7)

---

## 6. Idea Studio: personas react to every idea

### 6.1 Layout
- Directly **above the Studio chat composer**, show the **persona row**: the creator's 4 `PersonaAvatar`s at 40 px, in share order, with short names under them (truncate on small screens; full name on hover or long-press).
- The row stays visible on every Studio step (idea, script, visuals, caption, final draft).
- **States:**
  - Creator typing → all avatars `listening`.
  - Scoring in progress → `thinking`.
  - After a score → each avatar shows **its own mood** plus a tiny reaction badge (icon + word: Love / Like / Unsure / Skip). Icons are CURO's own, not platform logos.

### 6.2 Overall verdict (unchanged in spirit)
When the creator submits an idea (the validate chat, or selecting or typing an idea in step 1), CURO shows the **overall** result as before: score, verdict band (Strong / Worth trying / Risky), two reasons, one or two tweaks.

Make the overall score and the personas agree by construction. In the idea score (v2 §3.1: `0.40 H + 0.30 A + 0.20 T + 0.10 N`), **A (audience) becomes the share-weighted average of the four persona scores**:

```
A = Σ (share_i × persona_score_i) / Σ share_i      (persona_score_i on 0–1)
```

Show a one-line summary under the verdict, from code: "**3 of 4** follower groups are in. The Budget Stylist isn't sure."

### 6.3 Persona opinion: tap an avatar
Tapping a persona opens a **popover** anchored to the avatar (a bottom sheet on mobile) with **that persona's personal take, not the overall one**:
- avatar (mood), name, share
- **Reaction:** Would watch it all / Would watch / Might scroll past / Would skip, plus their **persona score** (0–100)
- **Would they…** ✓/✗ chips: like, comment, share, save. Mark save as "simulated", as in v2.
- **In their words:** a 1–3 sentence first-person opinion grounded in their profile ("I'd stop for this, it's exactly what I plan Navratri around. But show me the price of each look or I'll scroll.")
- **One change that would win them over**, with an "Apply" button that sends it to the Studio chat as a revision request
- **Why we think so:** evidence chips from the persona's facts ("Your festive reels are this group's top topic")

### 6.4 How persona opinions are computed
- **New task T20 "persona reactions"**: one Claude Sonnet call per idea that returns all 4 reactions:
  - Input: the idea (and, on later steps, the current script, storyboard or caption), each persona's profile and voice, the idea's DNA guess, pattern cards relevant to each persona.
  - Output per persona: `reaction`, `score` (0–100), `would{like,comment,share,save}`, `opinion` (≤ 280 characters), `win_them_over` (≤ 120 characters), `evidence_ids`.
  - **Code checks the score:** blend the model's score with a code-side fit score (similarity of the idea to the persona's top content + their requests − their turn-offs). Default 50/50, configurable. Log both.
- **Later Studio steps:** when the script, visuals or caption change, re-run T20 on the current draft, debounced, at most once per revision. Avatars update their mood; tapping shows the opinion of the **current draft**.
- **Cache** per (project, version, persona). Re-opening a popover never re-calls the model.
- **Cost and credits:** T20 is about $0.01–0.02 per run. It's included in the Studio project credit and counts toward that project's 10-revision limit only when the content changes, not when a popover is opened. Record it in `usage_ledger` as `studio_personas`.
- **Mock:** deterministic reactions from persona facts and idea keywords, so the UI can be built and tested fully on fixtures.

### 6.5 Studio details
- If personas aren't built yet, the row shows 4 breathing placeholder avatars with "Your follower personas are being built…" and the overall score works as before (A uses the old audience-demand calculation).
- Persona reactions and opinions are saved on the project, so the final draft shows "Who this is for: The Festive Planner ❤︎, The Budget Stylist 🙂…" (CURO icons).
- Don't show a persona row for creators with starter personas without the "Early guess" marker.

---

## 7. Chat with a persona

Available from the persona detail sheet (Home), the Studio popover ("Ask more") and the Simulator.

- One-to-one chat in the persona's voice, grounded in its profile, its evidence and, in Studio, the current draft. New task **T21 "persona chat"**, Claude Sonnet.
- It may answer "why", "what would make you share this", "what do you want next" and similar questions.
- It must stay in character but honest: when asked something the data can't support, it says so ("I'm a summary of your comments, so I can't tell you that").
- No new numbers beyond its facts. Never claims to be a real follower.
- **Fair use:** persona chat messages count toward Ask Curo's monthly cap (Free 10, Pro 100). In the Simulator, the existing 10 agent messages per simulation stay separate.
- Store conversations in `persona_messages` (creator_id, persona_id, context type and ID, role, content, created_at).

---

## 8. Simulator changes

- The **1,000 AI followers are drawn from the 4 Follower Personas**, in proportion to each persona's share. Each agent is a **variation** of its persona (different patience, mood and interests within the persona's range), generated once per persona build and stored in `audience_personas` (v2) with a `persona_id` foreign key.
- **Labels** become "Agent 12 · The Festive Planner" (agent number + persona short name), with the persona's colour as a small dot.
- **New result block "How each follower group reacted":** one row per persona with its avatar (mood from the results), watched-to-end %, like / comment / share / save rates (calibrated as in v2; saves marked simulated), and a one-line takeaway. Tap → the persona's own Simulator opinion, using T20 inputs from the simulation results.
- **Calibration** (v2 §3.5) now fits correction factors per persona where there's enough data, with an overall factor as fallback.
- **Studio–Simulator consistency:** if the upload is linked to a Studio project, show Studio's predicted persona reactions next to the Simulator's measured ones ("In Studio, the Budget Stylist was unsure; in the simulation, 61% of them watched to the end").

---

## 9. Data model

**New migration:**
- **`follower_personas`:** `id`, `creator_id`, `slot` (1–4), `name`, `short_name`, `tagline`, `share`, `color`, `avatar_seed`, `confidence`, `profile` jsonb (comes_for, loves, wants_more, turn_offs, engagement_style, language, voice, typical_comment, evidence), `thought` jsonb (T19 output), `centroid` vector(768), `version`, `period_start`, `period_end`, `is_starter` bool, `created_at`, `updated_at`. Unique (`creator_id`, `slot`, `version`). RLS: own rows.
- **`persona_history`:** `persona_id`, `period`, `share`, `mood`, `sentiment`, `n_comments`.
- **`persona_opinions`:** `id`, `creator_id`, `persona_id`, `target_type` (`idea`|`script`|`storyboard`|`caption`|`simulation`), `target_id`, `target_version`, `reaction`, `score_model`, `score_code`, `score`, `would` jsonb, `opinion`, `win_them_over`, `evidence_ids`, `model_version`, `created_at`.
- **`persona_messages`:** as in §7.
- **Changes:**
  - `audience_personas` gains `persona_id`
  - drop `follower_ideas` (v2.1)
  - recap slides gain the new slide IDs
- **Endpoints:**
  - `GET /api/v1/personas`
  - `GET /api/v1/personas/{id}`
  - `GET /api/v1/personas/{id}/history`
  - `POST /api/v1/projects/{id}/persona-reactions` (runs or returns cached T20)
  - `GET /api/v1/projects/{id}/persona-reactions?version=`
  - `POST /api/v1/personas/{id}/chat` (SSE)
  - `GET /api/v1/home` returns the 4 sections in order, each independently loadable

New tasks **T18–T21** each get a schema, a versioned prompt file in `api/prompts/`, a mock, and validator coverage.

---

## 10. Copy and safety rules for persona text

- **First person, warm, specific, short.** At most one emoji. Indian-English friendly; Hinglish only if the persona's language mix is mostly Hinglish.
- **Honest but kind.** Negative reactions explain what would win them over. Never insult the creator or the audience.
- **No sensitive attributes** (§1.2). No claims of being a real person. No promises about the algorithm or guaranteed results.
- **Every persona surface carries the label:** "Built from your public comments. Personas are summaries, not real people."
- **Sensitive-attribute check:** a validation step after T18–T21 rejects and regenerates any output that states or implies sensitive attributes, with a template fallback.

---

## 11. Tests (required)

- **Clustering:**
  - always exactly 4 personas
  - minimum-share rule
  - stable identity across months on fixture data (same names, colours and seeds when the data barely changes)
  - starter personas below the data threshold
- **Persona facts:** shares sum to 100%; evidence numbers match hand calculations on the demo creator.
- **Idea score:** A = share-weighted persona score. Add a worked example and hand-check it.
- **Persona reactions:**
  - the cache hits on re-open
  - a re-run happens only on a content change
  - the revision counter increments only on content change
- **Safety:** the sensitive-attribute validator catches planted examples; the no-new-numbers check catches a planted number in T18–T21 outputs.
- **UI:**
  - `PersonaAvatar` renders all moods; reduced motion is static; accessible labels
  - Home order is correct
  - the Studio row updates its states correctly
  - popovers are keyboard-accessible and close with Esc
- **End-to-end on mocks:** onboarding → recap with the persona sequence → Home with persona cards first → Studio idea with 4 reactions → tap a persona → apply its change → Simulator shows per-persona results.

---

## 12. Build order: stop after each phase and report

After each phase, give me a short report and the exact steps to check it in Chrome. Wait for "continue".

1. **Plan.** Add a v2.2 section to `PLAN_V2.md` covering personas, the avatar design (include an SVG sketch of each mood), tables, tasks T18–T21, scoring changes, and the Home, Studio, Recap and Simulator changes. *Check:* I approve.
2. **Avatar component.** `PersonaAvatar` with all moods, sizes and motion, plus a `/dev/avatars` preview page. *Check:* I review the look in Chrome.
3. **Persona engine.** The `build_personas` job, clustering, profiles, T18, T19, stability matching, starter personas, tables, mocks and tests. *Check:* the demo creator and the three fixture creators each get 4 sensible personas; facts match hand calculations.
4. **Recap.** The persona slide sequence, `followers_shift`, the share-card row. *Check:* the onboarding recap shows "Meet your followers".
5. **Home.** Remove "What your followers will love"; add the persona cards at the top and the detail sheet. *Check:* the new order and all states.
6. **Studio.** Persona row, T20, popovers, Apply, the new A in the idea score, re-runs on later steps, caching and credits. *Check:* typing an idea gives an overall verdict plus 4 different persona opinions.
7. **Persona chat** (T21) and fair-use counting. *Check:* chatting from Home and from Studio both work and stay in character.
8. **Simulator.** Agents drawn from personas, the new labels, the per-persona results block, per-persona calibration, the Studio comparison. *Check:* a sample upload shows per-group reactions.
9. **Hardening and publish.** Tests, accessibility, docs (`DECISIONS.md`, `INTEGRATION.md`), the secret scan, then commit and push to a new branch `v2.2-personas` with a pull request. *Check:* the pull request has no secrets and checks pass.

Start with phase 1.
