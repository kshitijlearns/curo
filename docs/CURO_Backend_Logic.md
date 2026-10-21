# CURO — Backend Logic for Every Feature

Oct 11, 2026 · @Kshitij

## 1. Summary

CURO can be built on one idea: every reel becomes a single linked record of what was made, how it was made, how it performed and how people reacted. Every feature in the app reads from, or writes to, that record.

CURO works entirely from public data. A creator types their username, and CURO collects their public reels in the background: view counts, likes, comments, share counts where Instagram shows them, captions, audio and comment text. First insights appear within minutes. CURO does not use the Instagram API and never asks creators to log in with Instagram, so numbers only the owner can see, such as saves, reach and watch time, are never shown or guessed.

From those records CURO learns three things for each creator:

- **Their baseline:** what a normal reel looks like for them, so every number is judged against their own past, not against other creators.
- **Their patterns:** which topics, hooks, formats and endings tend to lift which behaviour (comments, likes, shares, views).
- **Their context:** what peers are doing, what the audience keeps asking for, and what is becoming timely.

Every recommendation is then made the same way: gather evidence, generate options with an AI model, score the options with a transparent formula or a trained model, and show the creator *why*.

**How to read this doc.** Sections 2–5 explain the shared engine. Sections 6–14 take each screen of the prototype and explain its logic: inputs, steps, formulas, a worked Ganpati example and what is shown. Sections 15–17 cover learning, competitors, stack and guardrails.

**Two honesty rules apply throughout.** First, weights and percentages in this doc are starting values chosen by design; the system recalibrates them from real outcomes. Second, CURO never claims to know Instagram's algorithm; it reports patterns in the creator's own data and labels every prediction as an estimate.

## 2. The big picture

CURO is five layers stacked on one shared record: data is collected, stored, understood by AI, turned into learned patterns and scores, and finally shown in the app.

&#91;embedded content: CURO system architecture · 5 layers\]

Data flows down through the layers; the creator's choices and their reels' real results flow back up and retrain the Learn layer. Home, Insights and Opportunities mostly read from the engine, while Studio and the Simulator also write new records into it.

## 3. Where the data comes from

Every number in CURO comes from what anyone can see on a public Instagram profile, collected logged-out by a data vendor, plus outside trend sources and CURO's own app data. There is no Instagram login and no Meta API.

| Source | What CURO gets | How | Used for |
| --- | --- | --- | --- |
| Creator's public profile | Bio, follower count, following count, post count, account category | Public scrape by username | Baseline, reach proxy, follower growth |
| Creator's public reels | Caption, hashtags, audio name, duration, post time, view count, like count (unless hidden), comment count, share count where shown, video file, thumbnail | Public scrape by username | Reel Records, DNA, metrics |
| Public comments on those reels | Comment text, time, like count, reply count | Public scrape by reel URL | Audience cards, top comment, opportunity demand |
| Peers' public reels and comments | The same fields for each tracked peer | Public scrape by username | Competitor evidence, Outlier Index |
| Public hashtag and audio pages | Top and recent reels for a hashtag or sound | Public scrape | Trend momentum, hashtag candidates |
| Outside trend sources | Festival and cultural calendar; search interest when available | Calendar file; trend API later | Timeliness of opportunities |
| CURO's own app data | Ideas picked or skipped, scripts, edits, drafts, simulations, chat, results after posting | Use of the app | Learning what works for this creator |

### What public data cannot show, and what CURO does instead

| Not public | What CURO does |
| --- | --- |
| Saves | Never shown or estimated. Save prompts in scripts are allowed but not scored |
| Reach and impressions | Uses view count instead |
| Average watch time, skip rate, retention | Not measured. The Simulator uses visible proxies, such as how fast the payoff appears, and says they are proxies |
| Follower vs non-follower split | Uses views divided by follower count |
| Follows and profile visits from one reel | Uses the change in follower count between snapshots while one reel dominates new views |
| Audience age, gender and location | Uses the language mix and places mentioned across comments, as a group-level hint only |
| When followers are online | Uses the creator's past results by posting day and hour |

Three limits shape the design. Public counts are totals at the moment of collection, so growth curves exist only from the time CURO starts tracking a reel; older reels have one final number. Creators can hide like counts, and share counts are not visible on every reel. Saves are visible only to the owner ([Meta, April 2026](https://developers.facebook.com/blog/post/2026/04/22/instagram-api-updates-for-partnerships-metrics-collaboration-and-engagement/)), which is why CURO never shows them.

### Onboarding from a username

1. The creator types their handle. CURO checks that the account exists and is public.
2. CURO fetches the profile and metadata for the latest 50 reels. The first numbers appear within seconds.
3. In the background it downloads the latest 30 reel videos and up to 200 comments per reel.
4. The AI pipeline (section 5) processes reels newest first. Home fills in progressively, so the creator never waits on a blank screen.
5. CURO suggests 10 likely peers and asks the creator to confirm or replace them.
6. CURO starts its snapshot schedule. It explains once that growth curves for older reels are estimated, and that every new reel will be tracked from its first hours.

**A copy change the backend forces.** The prototype says "You follow a few creators who recently posted…". Instagram does not expose a creator's following list through its API. CURO should instead say "creators you track", built from the peers confirmed in step 5 and from accounts the creator adds later.

### How peers are found

CURO suggests peers by ranking accounts in its index on four signals: content similarity to the creator's reels, similar follower size (0.3× to 3× the creator's), the same language and region, and audience overlap seen in shared commenters. The creator always has the final say.

### Legal guardrails

In *Meta v. Bright Data* (2024), a US court found that Meta's terms do not bar logged-out scraping of public data, though it did not declare all such scraping lawful ([Zyte summary](https://www.zyte.com/blog/california-court-meta-ruling)). Meta later dropped the case ([MediaPost](https://www.mediapost.com/publications/article/393996/meta-abandons-lawsuit-against-bright-data-over-scr.html)).

India's DPDP Act does not apply to personal data that the person made public themselves. Its Rules were notified on 13 November 2025 with a 12–18 month phased rollout ([Hogan Lovells](https://www.hoganlovells.com/en/publications/indias-digital-personal-data-protection-act-2023-brought-into-force-)).

CURO's rules therefore are:

- Collect only public data, only while logged out, and never from private accounts.
- Never ask creators for Instagram passwords or logins.
- Keep commenters' handles out of long-term storage and keep only analysed text and counts.
- Let the vendor handle request pacing, and keep collection to what each feature needs.
- Honour takedown and deletion requests.
- Get a legal review before launch. This section is a design summary, not legal advice.

## 4. The Reel Record

Each reel is stored as one record with four linked parts, so CURO can ask "which choices went with which results?" instead of reading four separate reports. The table uses the prototype's reel "3 mistakes ruining your aesthetic reel" as the example.

| Part | Fields | Example values |
| --- | --- | --- |
| Content DNA (what it is about) | Cluster, sub-cluster, context or occasion, characters, core tension, key entities | Fashion and aesthetics → "Reel-making tips" → everyday → creator solo → "you're doing it wrong" → lighting, framing |
| Production DNA (how it was made) | Format, hook type and text, time to first payoff, opening style, narrative shape, ending, call to action, point of view, camera setup, cuts per 10 seconds, audio type, on-screen text, visual style, setting, duration | Listicle → "mistake" hook → payoff at 1.8 s → face to camera → 3-step list → recap → "save this" CTA → first person → tripod → 4.2 cuts per 10 s → voiceover → captions on → warm light → bedroom → 32 s |
| Performance (what happened) | Snapshots over time of views, likes, comments and shares (where shown), plus the account's follower count | 90K views, 504 likes, 281 shares, 98 comments at day 3 |
| Audience response (how people reacted) | Comment themes, sentiment, intent counts, top comment, bot share | 41% "that's me" comments, 18% questions, top comment from @aesthetic.anya |

### Numbers CURO derives from the record

**Rates.** Raw counts grow with views, so CURO divides by views: likes per view, shares per view and comments per view are the core rates. Instagram's head has named watch time, sends per reach and likes per reach as its most important ranking signals ([eClincher summary](https://www.eclincher.com/articles/how-the-instagram-algorithm-works-in-2026)). Watch time isn't public, so CURO leans on the two it can see: shares per view as the stand-in for sends, and likes per view.

**Lift.** Lift compares a reel with the creator's own normal at the same age, because a reel at day 1 cannot be compared with one at day 30.

```latex
\text{lift}_m = \frac{m_{\text{reel}}(t)}{\operatorname{median}\big(m_{\text{last 20 reels}}(t)\big)}
```

Here m is any metric or rate and t is the reel's age (6 hours, 1 day, 3 days, 7 days or 30 days). A lift of 1.6 on shares means 60% more shares than this creator normally gets by that age. The **Outlier Index** is the lift on views, borrowed from how YouTube tools like ViewStats score videos against a channel's recent uploads ([OutlierKit comparison](https://outlierkit.com/resources/spotter-studio-vs-viewstats/)).

**Sub-clusters.** CURO turns each reel's transcript, caption and visual description into an embedding (a list of numbers that captures meaning). It then groups similar reels with a clustering algorithm such as HDBSCAN and asks an AI model to name each group, for example "Festive styling" or "Reel-making tips". As the spec requires, a sub-cluster is a group of reels, never a single reel.

**Taxonomy.** Production DNA uses a fixed list of values (for example 14 hook types and 9 narrative shapes) so that reels can be compared and counted. Free-text descriptions are kept beside the fixed values for the AI to read.

## 5. Processing pipeline

Every reel, whether the creator's own, a peer's or an uploaded draft, goes through the same eight steps. That keeps the Simulator's view of a draft identical to Home's view of a posted reel.

1. **Store the raw material.** Save the video, thumbnail, caption, hashtags, audio name and comments.
2. **Understand the video.** A multimodal AI model watches the reel. It produces a transcript with word timings, shot changes, on-screen text and a short description of each second. Google's Gemini, for example, samples video at 1 frame per second and uses about 300 tokens per second at default settings ([Gemini docs](https://hex.pm/packages/ex_llm/0.7.1/files/docs/gemini/GEMINI-DOCS-18-VIDEO-UNDERSTANDING.md)), so a 30-second reel costs roughly 9,000 tokens.
3. **Extract the DNA.** A language model reads step 2's output and fills every Content DNA and Production DNA field from the fixed lists. Each field carries a confidence score; below 0.6 the field is stored as "unknown" rather than guessed.
4. **Read the comments.** CURO removes likely bot and spam comments, then labels each comment for sentiment (positive, neutral, negative) and intent. Intents include question, request, "that's me", tags a friend, plans to save, disagreement and praise. Requests and questions are grouped into themes such as "wants budget versions". The model must handle Hindi, English and Hinglish.
5. **Embed and cluster.** Turn transcript, caption and visuals into embeddings, then update the creator's sub-clusters.
6. **Take public snapshots.** For the creator's reels: every 3 hours for the first 48 hours, every 12 hours until day 7, daily until day 30, then weekly. Peers' reels follow a lighter schedule, daily for 14 days, because every snapshot is a scrape. The follower count is captured with each snapshot.
7. **Update baselines.** Recompute the rolling median of each metric at each age over the last 20 reels. Reels marked as paid partnerships are flagged and left out, because they may have been boosted.
8. **Mine patterns.** For each Production and Content DNA value, compare the lift of reels that have it with reels that don't. The result is a **pattern card**, for example: "Choice-question endings → comments 1.6× (14 reels, confidence high)".

### Why patterns are shrunk toward a prior

A creator with 8 reels can show a big effect by luck. CURO blends the creator's own effect with the average effect seen across similar creators, giving the creator more weight as their reel count grows.

```latex
\text{effect} = \frac{n \cdot \text{creator effect} + k \cdot \text{similar-creator effect}}{n + k}, \quad k = 10
```

With 10 reels showing the pattern, the creator's own data counts for half. With 40 reels it counts for 80%. A pattern is shown to the creator as "yours" only when n is at least 8 and the effect holds in a statistical test. Otherwise it is labelled "seen across similar creators".

Every later feature — annotations, "What's working", idea scoring — reads these pattern cards instead of asking the AI to guess.

## 6. Home: previous content

The carousel shows the creator's latest 10 reels, newest first. Each card pairs the thumbnail with four public numbers and an arrow, and the arrow always answers one question: "is this reel doing better or worse than expected *at this age*?"

**Where each number comes from**

| Metric | Source | If it's missing |
| --- | --- | --- |
| Views | Public view count on the reel | Always present |
| Likes | Public like count | Hidden by the creator: show a dash and leave likes out of rates |
| Shares | Public share count | Not visible on this reel: show a dash |
| Comments | Public comment count | Comments turned off: show a dash |

Saves, reposts and reach were in an earlier design and are removed, because they aren't reliably public. The note under the carousel says "Public counts only".

**How the arrow is calculated**

The prototype's note reads "Arrows compare actual results with Curo's pre-publish simulation". That is only possible when the reel went through the Simulator. CURO therefore picks the expected value in this order:

1. If the reel was simulated, use the simulated 7-day prediction, scaled to the reel's current age with the creator's own growth curve.
2. If not, use the creator's baseline (median of the last 20 reels at the same age).

```latex
\text{expected}(t) = \text{prediction}_{7d} \times g(t), \qquad \text{change} = \frac{\text{actual}(t) - \text{expected}(t)}{\text{expected}(t)}
```

Here g(t) is the share of a 7-day total that this creator's reels usually reach by age t. Changes between −5% and +5% show as a flat dash, so small noise doesn't look like news. The note under the carousel switches between "vs your simulation" and "vs your usual" so the comparison is never hidden.

**Worked example.** "3 mistakes ruining your aesthetic reel" is 3 days old with 90K views. The Simulator had predicted 95K views by day 7. This creator's reels usually reach 72% of their 7-day views by day 3, so the expected value is 95K × 0.72 = 68.4K. The change is (90K − 68.4K) ÷ 68.4K = +32%, which is the ↗32% shown in the prototype.

**Refresh.** Home reads the latest stored snapshot. Pulling down to refresh requests a new one if the last is older than 3 hours. Tapping the thumbnail opens the reel on Instagram through its permalink.

## 7. Insights: phase, audience and top comment

Insights turns one reel's numbers into three plain answers: where the reel is in its life, what the audience's behaviour says, and what people are actually writing.

### Phase of reel

CURO reads the phase from **velocity**, the views gained per hour between two snapshots, compared with the highest velocity the reel has reached so far.

| Phase | Rule | Text shown |
| --- | --- | --- |
| Testing | Under 24 hours old, and views are still below the follower count | Mostly being shown to your followers so far |
| Growing | Velocity rose in the last two snapshots | Views are picking up speed |
| Peak | Velocity is within 80% of its highest and has stopped rising | Views are climbing fast; when views pass 2× the follower count, it adds that the reel is reaching people beyond your followers |
| Slowing | Velocity is below 50% of its highest | Views are slowing down |
| Long tail | Velocity below 10% of its highest for 48 hours, but still above zero | New views have slowed to a trickle |

The range next to the phase ("1 – 3 days" in the prototype) is how long this phase usually lasts for this creator, taken from the middle half (25th to 75th percentile) of their past reels. The phase timeline under it is the velocity curve split into these five bands.

**Beyond your followers.** Public data has no follower vs non-follower split. CURO uses views divided by follower count as the signal: a reel with 3× as many views as the account has followers must be reaching people who don't follow it. The text never claims an exact share.

**Freshness.** Public counts are close to real time, but CURO only knows what its last snapshot saw. Insights shows "updated X hours ago" under the phase, and older reels collected at onboarding show "phase estimated from one snapshot".

### What your audience thinks

These cards explain behaviour, not just numbers. CURO builds them in four steps.

1. Compute the lift of each public rate: likes, comments and shares per view, plus the views lift itself.
2. Convert each lift into a z-score against the creator's own history, which says how unusual it is for them.
3. Pick up to three cards with a z-score of at least 0.75 in either direction, always including the strongest positive one. If any rate is clearly low (z of −1 or below), one card must be about it. Comment-based cards (below) can fill a slot when no rate is unusual.
4. Attach the reason from comments and DNA, then have the AI write one plain sentence from that evidence. The AI may not add numbers that aren't in the evidence.

| Card | Condition | Evidence used for the reason |
| --- | --- | --- |
| Comments are driving engagement | Comment rate z ≥ 0.75 | Share of "that's me", question and disagreement comments; whether the reel ends on a question |
| Shares are lower than usual | Share rate z ≤ −0.75 | Few "tags a friend" comments; no share prompt; low usefulness for someone else |
| Likes per view are high or low | Like rate z ≥ 0.75 or ≤ −0.75 | How early the payoff appears; how long the intro runs |
| People are tagging friends | 10% or more of comments tag another account | Tags are the visible sign that people pass a reel on |
| Your follower count jumped | Follower count rose faster than usual while this reel brought most new views | Series or "part 2" requests; clear niche signal |

For the example reel, 41% of comments are "that's me" reactions and its comment rate is 1.4× the creator's median. That produces "This topic is sparking conversations. People find it relatable and are sharing their thoughts in the comments."

### Top comment

CURO ranks comments by their own like count, then by reply count. It skips the creator's own comments, likely bots and emoji-only comments. If the most-liked comment is negative it is still shown, with a small label, because hiding criticism would make the insight less honest.

## 8. Opportunity areas

An opportunity area is a topic with evidence behind it, found from four sources and scored out of 10. CURO refreshes the list every night and shows the top 5, which is the "5 for you" pill on Home.

### Step 1: find candidates

| Source (tag shown) | What triggers a candidate |
| --- | --- |
| Competitor | Two or more tracked peers posted on a similar topic in the last 14 days, with an Outlier Index of 2 or more (twice their usual views) |
| Trend | A festival or cultural date relevant to the creator's region and niche falls in the next 7–30 days, or search interest grew 1.5× or more over the last 7 days vs the previous 28, or the topic is growing across CURO's index of reels in the niche |
| Audience | A request or question theme appears in 3% or more of comments across the creator's last 30 reels |
| Your content | One of the creator's sub-clusters had a lift of 1.3 or more but hasn't been posted in 30 days, or an outlier reel invites a follow-up |

### Step 2: merge, name and filter

Candidates that mean the same thing are merged when their embeddings are very similar. An AI model then names the topic in plain words, for example "Ganpati dress ideas". CURO drops topics the creator has blocked, topics they posted in the last 14 days and topics that fail brand-safety checks.

### Step 3: score

```latex
\text{Score} = 10 \times (0.30\,F + 0.20\,D + 0.20\,P + 0.20\,T + 0.10\,O)
```

Each part is a number from 0 to 1:

- **F – Creator fit (30%).** How close the topic is to the creator's best sub-clusters (weighted by their lift), plus whether the creator has already made the formats it needs.
- **D – Audience demand (20%).** How often the audience asks for it, how they engaged with related reels before, and whether the languages and places mentioned in comments match the topic.
- **P – Peer evidence (20%).** How many tracked peers posted on it and how far above their own normal those reels did.
- **T – Timeliness (20%).** Search and posting momentum, and for dated events, closeness to the best window. The window peaks 7–14 days before the event and drops quickly after it.
- **O – Openness (10%).** The opposite of saturation: how much room is left before the creator's niche is flooded with the same topic.

Creator fit weighs most because the spec says the creator's own history should matter heavily. These are starting weights. After launch, CURO relearns them from outcomes: which opportunities creators open, save and take to Studio, and how the resulting reels perform.

### Worked example: Ganpati dress ideas

| Part | Evidence | Value | Weighted |
| --- | --- | --- | --- |
| Creator fit | "Festive styling" sub-cluster has a views lift of 1.5; the creator often makes outfit-styling reels | 0.85 | 0.255 |
| Audience demand | 2.8% of recent comments ask about festive outfits; comments are mostly in Hinglish and Marathi and often mention Mumbai and Pune | 0.70 | 0.140 |
| Peer evidence | 4 of 10 tracked peers posted Ganpati outfit reels; median Outlier Index 2.7 | 0.90 | 0.180 |
| Timeliness | 12 days before Ganesh Chaturthi; search interest up 2.1× | 0.95 | 0.190 |
| Openness | Many peers already posting; some room left | 0.55 | 0.055 |
| **Total** |  |  | **0.82 → 8/10** |

The tag shows where the candidate was first found, so this card says "Competitor" even though creator fit contributes the most.

### Step 4: explain

The detail page is assembled from the score's parts, not written freely:

- The **description** comes from the two biggest contributors.
- **What your competitors are doing** shows up to 3 peer reels with their Outlier Index.
- **Why it fits you** names the creator's matching sub-cluster and its lift.
- The **score ring** shows the total out of 10.

Swiping moves to the next of the 5 opportunities in score order. The bookmark adds the opportunity to Saved. "Open in Studio" creates a new project that carries the opportunity and its evidence forward.

## 9. Studio, step 1: the three ideas

The three ideas are the winners of a contest, not the AI's first three thoughts. An AI model writes about 15 candidate ideas from a fixed evidence pack, a scoring formula ranks them, and a diversity rule picks three that do different jobs.

### What the AI is given (the evidence pack)

| Evidence | What goes in |
| --- | --- |
| Opportunity | Its name, score parts and the evidence from its detail page |
| Creator history | Top 5 sub-clusters with their lifts, the 10 strongest pattern cards, usual reel length per format, voice profile from past transcripts |
| Audience | Top 5 request and question themes with sample comments, and the language mix of comments |
| Peers | The 5 strongest peer reels on this topic, each with its Outlier Index and DNA summary |
| Trend | Event date, rising sub-angles, how saturated the topic already is |

Each candidate the AI writes must state its angle, its format, the behaviour it aims for (comments, likes, shares or views) and the IDs of the evidence it relies on. Candidates that cite no evidence are thrown away, which is how CURO avoids generic "AI content ideas".

### How candidates are scored

```latex
\text{Idea score} = 0.35\,H + 0.25\,A + 0.20\,P + 0.15\,T + 0.05\,N
```

- **H – Your history (35%).** The lift the Simulator's model expects for this creator from the idea's topic, format and hook type, before anything is recorded.
- **A – Audience (25%).** How well it answers what the audience asks for and engages with.
- **P – Peers (20%).** How far above their normal similar peer reels performed.
- **T – Trend (15%).** Whether it rides the rising angle inside the topic, and fits the timing window.
- **N – Novelty (5%).** How different it is from the creator's last 10 reels, so CURO doesn't keep suggesting the same reel.

### How the final three are picked

If CURO simply took the top three scores, it would often show three versions of the same idea. It uses a diversity rule instead: take the best idea, then repeatedly take the one with the highest 0.7 × score − 0.3 × similarity to the ideas already chosen. It also fills three slots, so the creator always sees a real choice:

1. **Proven:** a format that already works for this creator.
2. **Adapted:** an angle with strong peer or trend evidence, made in the creator's style.
3. **Explore:** something the audience is asking for, or a fresh angle.

### Worked example: Ganpati dress ideas

| Idea | Slot | H | A | P | T | N | Score | Main evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Styling the same outfit 3 different ways for Ganpati | Proven | 0.90 | 0.70 | 0.85 | 0.80 | 0.40 | 0.80 | The creator's "one item, many looks" reels have a shares lift of 1.7 across 9 reels; 2 of the 4 peer outliers use a multi-look format |
| What I wore for Ganpati last year vs this year | Adapted | 0.80 | 0.75 | 0.40 | 0.80 | 0.80 | 0.71 | Last year's Ganpati reel drew 1.5× the usual comments; comparison reels drive comments for this creator; few peers have done it |
| Quick prasad recipes you can make in under 10 minutes | Explore | 0.30 | 0.80 | 0.60 | 0.85 | 0.90 | 0.60 | Festive-reel comments often mention family prep and food; food searches rise before the festival; outside the creator's usual niche |

A candidate called "5 Ganpati outfits under ₹1,000" scored 0.74, higher than the prasad idea. It was too similar to idea 1 (similarity 0.82), so the diversity rule gave it 0.7 × 0.74 − 0.3 × 0.82 = 0.27. The prasad idea got 0.7 × 0.60 − 0.3 × 0.25 = 0.34, so it took the third slot.

### "What percentage of each data did it use?"

The AI model that writes ideas does not mix data in fixed percentages. The percentages CURO can honestly show are each part's share of the ranking score: the weight times the part's value, divided by the total. The "Why this idea" panel shows these shares, plus the evidence chips behind each part.

```latex
\text{share}_i = \frac{w_i \, s_i}{\sum_j w_j \, s_j}
```

&#91;embedded content: example values from this doc · Ganpati opportunity, 3 ideas\]

The same opportunity produces three different mixes: the proven idea leans on the creator's history, while the explore idea leans on what the audience asks for.

### Writing your own idea

When the creator types or speaks their own idea, CURO extracts its topic, format, tone and limits and treats them as fixed rules. It then runs the same generate, score and pick steps, so the three returned ideas all keep the creator's core thought and differ in angle or format. The opportunity stays attached to the conversation.

### The Studio tab's "validate" chat

Opening Studio from the nav shows the plain chat: "Type any idea or thoughts you have here to validate them with Curo". CURO scores the idea with the same formula and replies with three things:

- A verdict band: **Strong** (0.75 or more), **Worth trying** (0.55–0.75) or **Risky** (below 0.55).
- Two reasons, each with its evidence.
- One or two tweaks that would raise the score, with the expected change.

"Develop this idea" then opens step 2 with the idea as the project's anchor.

## 10. Studio, step 2: the script and its notes

The script is written to the creator's own length, structure and voice, and every highlighted note is backed by a pattern card. If no pattern supports a note, the note is not shown.

### How a script is generated

1. **Pick the length.** CURO uses the duration band in which this creator's reels of this format get the most views per follower, for example 25–35 seconds for multi-look reels.
2. **Pick the structure.** CURO takes the beat order from the creator's three strongest reels of the same format, checked against peer outliers. For the Ganpati idea: hook, quick setup, look 1, look 2, look 3, question to the audience.
3. **Set the word budget.** The voice profile measured from past transcripts gives the creator's speaking speed, for example 2.6 words per second. A 32-second reel therefore gets about 80 spoken words.
4. **Write in the creator's voice.** The AI follows the voice profile: sentence length, mix of Hindi and English, recurring phrases and energy level. The selected idea and opportunity stay in the prompt as the anchor.
5. **Add the notes.** A second AI pass labels each line, then CURO keeps only the labels that a pattern card supports.

### The notes and what backs them

| Note | When a line gets it | Evidence shown on tap |
| --- | --- | --- |
| Strong hook | The first line lands within 3 seconds and makes a promise, contrast or open question | Your reels that open with a question or promise got 1.8× the views of your other openings |
| Drives comments | A direct question with choices, an opinion prompt or a "comment your pick" line | Your reels ending on a choice question got 1.6× the usual comments across 14 reels |
| Drives likes | The finished result lands as a clear, satisfying payoff | Your reels that end on the finished look get 1.7× your median likes |
| Encourages shares | A line people will relate to or want to send to a friend | Peer reels with "send this to…" lines got higher share rates (seen across similar creators) |

Save prompts can still appear in a script, but CURO never labels a line "encourages saves", because saves aren't public and can't be checked.

Every note is worded as an association, never a promise: "CURO links this kind of line with more comments for you", not "this will get comments".

### Iterating

Chat and voice requests are first sorted into an action, such as rewrite the hook, change the tone, shorten to N seconds, expand, change the ending or call to action, or edit one line. CURO then rewrites only the beats that action touches and leaves the rest word for word, so the creator can see exactly what changed. After each change it re-runs the notes. If a storyboard already exists, the frames tied to changed lines are marked for update.

"Regenerate" writes a new version with a different structure and a different hook. "Dump your script idea here" takes the creator's own text, splits it into beats and adds notes, but doesn't rewrite it unless asked. "Skip to final draft" is always available.

## 11. Studio, step 3: the storyboard

Each storyboard frame is one script beat turned into a shot the creator can actually film with the setups they already use. Frames are linked to beats by ID, so the script and the storyboard never drift apart.

### How frames are built

1. **Time each beat.** CURO converts each beat's word count into seconds using the creator's speaking speed, which gives the timestamps such as "0:00 – 0:04".
2. **Choose the shot from the creator's own toolkit.** CURO lists the camera setups found in the creator's Production DNA, such as mirror selfie, tripod mid-shot, close-up of hands or balcony daylight. It prefers these, so the plan is realistic for one person with a phone.
3. **Borrow proven visual devices.** From peer outliers of the same format CURO takes devices such as a snap cut between looks. It applies the creator's own pattern cards too, for example showing the final look within the first 2 seconds.
4. **Write the frame.** Each frame gets the recording instruction, the exact script line, shot type, short on-screen text for people watching without sound, and the transition.
5. **Draw the sketch.** An image model draws the frame in one fixed line-art style from the structured shot description. Common shots come from a pre-drawn template library to keep it fast and cheap.

### Feasibility

Every storyboard gets a feasibility score from four costs: number of locations, need for a second person, props and outfit changes, and lighting changes. "Make this easier to record" lowers that score. It merges locations, swaps shots that need a helper for tripod shots, and reuses one lighting setup, while keeping the hook frame intact.

### Iterating

Requests are mapped to frame-level actions: change this shot, another opening, easier to record, change the transition, change the pacing, change the visual treatment. Pacing changes adjust frame durations but keep the total inside the creator's best length band. If a script line changes, only its linked frame is regenerated.

"Proceed to Caption/Hashtag" moves on, "Continue iterating on visuals" keeps the chat open, and "Skip to final draft" jumps ahead.

## 12. Studio, step 4: caption, hashtags and final draft

CURO offers three captions that each do a different job, and five hashtags chosen for relevance rather than size. The five-hashtag limit matches Instagram's own: it now caps posts and reels at five hashtags, and its head says hashtags help search but don't increase reach ([Social Media Today](https://www.socialmediatoday.com/news/instagram-implements-new-limits-on-hashtag-use/808309/)).

### Captions

| Caption | Job | Built from |
| --- | --- | --- |
| Hook echo + question | Comments | The script's hook, then the same choice question as the ending |
| Quick summary of the looks | Likes | The three looks as a short list people can come back to |
| Relatable story line | Shares | The "that's me" angle the audience responds to |

All three follow the same rules:

- The first line restates the hook, because it is what shows before the caption is cut off.
- The caption includes one or two phrases people actually search, such as "Ganpati outfit ideas".
- The call to action matches the script's intended behaviour and isn't repeated twice.
- Length, emoji use and language mix follow the creator's own caption pattern cards.

### Hashtags

1. **Collect candidates** from four places: the creator's past hashtags with their results, hashtags on peer outliers for this topic, public hashtag pages, and topic tags an AI model suggests. CURO caches each hashtag page and refreshes it at most once a day, shared across creators.
2. **Score each candidate:** 50% relevance to this reel's transcript and caption, 30% past results for the creator and peers, 20% specificity. Generic tags such as #reels score low.
3. **Suggest a mix of five:** one broad topic tag (#ganpati), two niche tags (#ganpatioutfit, #festivestyling), one community or region tag (#mumbaifashion) and one series or signature tag if the creator has one.

The UI stops a sixth tag from being selected. "Dump your caption idea" takes the creator's own caption and only polishes it if asked.

### Final draft

The final draft bundles the idea, script, storyboard, caption and hashtags under one project ID. "Save draft" puts it on the Saved page. There is no "Simulate" button here, because CURO only simulates a recorded video. The project ID lets the Simulator compare the recording against this draft later.

## 13. Simulator

The Simulator treats an uploaded video exactly like a posted reel: it builds its Reel Record, feeds it to a trained model, and reports the expected result against the creator's own baseline. Every "why" comes from the model's own reasoning on that video, checked against the creator's similar past reels.

&#91;embedded content: Simulator flow · 4 steps, 4 outputs\]

All four outputs come from the same model run on the same features, so the score, its reasons and the suggested edits can never contradict each other.

### Inputs

- The uploaded video, run through pipeline steps 2–5 (understanding, DNA, embeddings).
- Optionally, the Studio draft it came from (the compare switch).
- The target audience toggle: followers, new audiences, or both.
- The creator's baselines, pattern cards and personas.
- Trend context at the planned posting time: topic momentum, saturation, days to the event.

### The model

**What it predicts.** For each public metric (views, likes, comments and shares) the model predicts the lift at day 7, not the raw count. Predicting lift removes the effect of follower count, so one model can learn from creators of every size.

**What it learns from.** Every public reel in CURO's index, creators' and peers' alike, gives views, likes, comments and, where shown, shares, with growth timing from CURO's own snapshots. Because all reels are measured the same public way, the model can learn from peers as freely as from the creator.

**How it is built.** A gradient-boosted tree model (for example LightGBM) reads the DNA fields, the video embedding, opening-seconds features such as time to payoff, plus duration, audio type, creator features and trend features. Separate quantile versions give a low, middle and high estimate (10th, 50th and 90th percentile), which becomes the range shown.

**How it becomes personal.** CURO adds a correction from the creator's own past prediction errors in similar sub-clusters, with more weight as their reel count grows.

```latex
\text{log-lift}_{\text{final}} = \text{log-lift}_{\text{global}} + \frac{n}{n+20} \times \text{creator's average error}
```

With 20 reels, the creator's own correction counts for half; with 80 reels, 80%.

### The estimated score

The score from 0 to 100 is a percentile against the creator's own last 50 reels. A score of 72 means "likely to do better than 72% of your recent reels". The model scores a weighted mix of predicted lifts, and the mix follows the audience toggle and the signals Instagram's head has named most important, with views lift standing in for watch time, which isn't public:

| Audience toggle | Views lift | Shares per view | Likes per view | Comments per view |
| --- | --- | --- | --- | --- |
| Followers | 15% | 20% | 40% | 25% |
| New audiences | 45% | 35% | 10% | 10% |
| Both | 30% | 25% | 25% | 20% |

**Predicted report.** Each metric is shown as the creator's 7-day baseline multiplied by the predicted lift, as a range and as a percentage against baseline. Saves, reach and watch time are never shown, because they aren't public.

**Best time to post.** CURO compares the views lift of the creator's past reels by posting day and hour, and for reels it has tracked from the start, how fast they grew in their first 6 hours. It avoids hours when tracked peers usually post, and suggests the best slot in the next 48 hours.

### What's working and what's holding it back

For this specific video, CURO measures how much each feature pushed the prediction up or down, using SHAP values (a standard way to explain a tree model's prediction). The top three positive features become "What's working" and the top three negative ones "What's holding it back".

Each item is then backed by evidence. CURO finds the creator's past reels most similar to this one that differ on that feature, and shows their results. For example: "The final look appears at 3.8 s. Your 5 strongest reels show the result within 1.5 s." The item links to the storyboard frame at that timestamp.

### Specific edits and "Edit & re-run"

CURO tests changes before suggesting them:

1. Make a variant of the video's features for each editable change, such as moving the payoff from 3.8 s to 1.5 s, cutting from 41 s to 32 s, ending on a choice question, or adding on-screen text to the hook.
2. Re-run the model on each variant and record the score change.
3. Label each change by effort: "edit only" or "needs a reshoot".
4. Show the three with the best score gain for their effort, for example "Show the final look first: +6".

"Edit & re-run" writes accepted script and storyboard changes back to the Studio project. Once the creator uploads the edited video, the Simulator runs again and shows the new score next to the old one.

### Audience persona fit

Personas are groups of the creator's engaged audience, never individual people. CURO groups commenters by the topics and language of their comments only; no demographic data is used. Examples: "Festive planners", "Working women styling on a budget", "Reel-making learners". For every past reel CURO knows roughly how much response came from each persona. Persona fit is the predicted response from that persona compared with its usual level, shown from 0 to 100. Commenter-level data is deleted once the grouping is done.

### Content, Production and Trend DNA

These panels show the uploaded video's extracted DNA. Trend DNA adds topic momentum, saturation, how similar peer reels performed, audience and creator fit with the trend, and **originality**. Originality is 1 minus the highest similarity to any recent peer reel, so near-copies are flagged; the spec asks to adapt trends, not copy them.

### Comparing with the Studio draft

When the switch is on, CURO lines up the video's transcript with the draft's script beat by beat. It flags skipped beats, a changed hook, a missing call to action, a length difference, and any script notes whose lines were dropped.

### Staying honest

CURO stores every estimate and compares it with the actual result after posting. The Simulator shows a running record, such as "Curo's range contained the result for 8 of your last 10 reels". If accuracy drops, the ranges are widened automatically. Every screen says "estimate based on your history" and never "Instagram will…".

## 14. Ask Curo, memory and Saved

Every chat box in CURO talks to the same assistant, which works by calling tools on the creator's records rather than answering from general knowledge. It may only state numbers that a tool returned.

### Tools the assistant can call

| Tool | What it does |
| --- | --- |
| Search my reels | Finds past reels by topic, format or result |
| Get reel record | Returns one reel's DNA, metrics and comment themes |
| Get pattern cards | Returns what tends to work for this creator, with evidence |
| Get opportunity | Returns an opportunity's score parts and evidence |
| Score ideas | Runs the idea formula from section 9 |
| Rewrite script beats | Changes only the beats a request targets |
| Update storyboard frame | Regenerates one frame |
| Run simulation | Re-scores a video or a changed feature set |
| Compare to draft | Lines up a recording against its Studio draft |

A small classifier first decides what the creator wants, for example "explain", "change the script" or "what if". It then picks the tool. If the request is unclear, the assistant asks one short question. Voice input goes through speech-to-text that handles Hindi, English and Hinglish, then follows the same path.

### Memory

- **Project memory.** Everything in one piece of content shares a project ID: opportunity, chosen idea, every script and storyboard version, captions and simulations. That is how the Ganpati context stays attached from Home to Simulator, as the spec requires.
- **Creator memory.** CURO keeps stable preferences, either stated ("never suggest dance trends") or learned from repeated behaviour (always shortens scripts, so drafts start shorter). The creator can see and delete these in settings.

The fixed hint line above each chat box comes from the screen's state. In the Simulator, for example, the hint points at the biggest item under "What's holding it back".

### Saved

The Saved page has two lists. **Opportunities** keep the score from when they were saved and show today's score beside it; they are marked "window passed" once a dated event is over. **Drafts** are Studio projects, and opening one restores the exact step and versions the creator left.

## 15. Learning loop and cold start

CURO gets more accurate for each creator with every reel they post, because every estimate is later checked against what actually happened.

### The loop

1. **Estimate.** The Simulator stores its prediction with the project.
2. **Match.** When a new reel appears, CURO links it to the project using its audio fingerprint, caption similarity and timing, and asks the creator to confirm the match.
3. **Track.** Snapshots begin, and Home's arrows compare the reel with its simulation.
4. **Correct.** The difference updates the creator's personal correction and their pattern cards right away. The global model is retrained every week.
5. **Re-weight.** Every month CURO refits the weights in the opportunity and idea formulas from outcomes, such as whether chosen ideas beat the baseline. To keep the app stable, no weight moves by more than 0.05 in a month.
6. **Listen to choices.** Ideas picked or skipped, opportunities saved or dismissed, and edits accepted or ignored all feed the ranking.

The Explore slot in section 9 is kept on purpose. Advice built only from past data tends to push every creator toward the same formats, so CURO always leaves room for something new.

### Cold start

| Reels available | What CURO does |
| --- | --- |
| 0–4 | No personal baseline yet. CURO uses creators similar in niche, size and language as the baseline, labels everything "based on creators like you", and asks four onboarding questions: niche, main goal (reach, community or sales), formats they're comfortable with, and languages |
| 5–19 | Personal baseline with wide ranges. Most pattern cards still come from similar creators |
| 20–49 | Solid personal baseline. Patterns become personal once at least 8 reels show them |
| 50 or more | Full personalisation; the creator's own correction carries most of the weight |

Because CURO sees only public numbers, its ranges stay wider than an owner-data tool could give, and saves, reach and watch time are never shown. CURO says this plainly on screen rather than hiding it.

## 16. What competitors do and what CURO borrows

The closest competitor is now Instagram itself, so CURO has to win on the full workflow, outside evidence and transparent reasoning rather than on access to data.

| Product | What it does | What CURO borrows | Where CURO differs |
| --- | --- | --- | --- |
| [Instagram Edits Assistant](https://yourstory.com/ai-story/instagram-ai-reel-performance-edits-app) (Meta, rolling out from 1 October 2026) | A chat in the Edits app that explains why reels worked from follows, views, retention, shares, likes, comments and trends; also suggests ideas, hooks, captions and scripts; usage limits apply outside paid plans | Plain-language "why did this work?" answers grounded in the creator's numbers | Works on any public account, including peers, and adds competitor evidence, scored ideas, storyboards and a pre-post Simulator. Edits sees private retention data that CURO cannot |
| [Spotter Studio](https://spotterstudio.com/features) (YouTube) | Finds outlier videos across YouTube and brainstorms ideas tuned to a connected channel's style and performance | Brainstorming from outliers; ideas personalised to channel history | Instagram reels, script-to-storyboard flow, prediction after recording |
| [ViewStats](https://outlierkit.com/resources/spotter-studio-vs-viewstats/) (YouTube) | Outlier Score: how a video did against the channel's recent uploads | The Outlier Index and baseline-relative thinking | Applied to every metric, not just views |
| [HypeAuditor](https://hypeauditor.com/blog/uncovering-the-ai-capabilities-of-hypeauditor) | AI audience-quality scoring from public data, including fake-follower and comment-quality checks | Bot and spam filtering before comments are analysed | Used to coach creators, not to vet them for brands |
| [VYRL](https://www.g2.com/sellers/vyrl) | Pre-publish performance predictions for reels, trained on over 60,000 videos | Predicting before posting | Predictions relative to the creator's own baseline, with tested edits and a public accuracy record |
| [Apify Instagram scrapers](https://apify.com/scrapesmith/instagram-reels-scraper) | Public reel data from a username, priced from about $0.45 to $2.50 per 1,000 results | Possible data vendor for public mode | — |

The lesson across all of them is the same: tools that measure stay separate from tools that create. CURO's bet is to connect measuring, creating and testing on one shared Reel Record.

## 17. Tech stack, cost, privacy and honesty rules

CURO can be built from standard parts; the hard work is the data model and the evaluation, not exotic infrastructure.

### Suggested stack

| Layer | Choice | Why |
| --- | --- | --- |
| Mobile app | React Native | The prototype is already React |
| Backend API | Python (FastAPI) | Same language as the ML work |
| Background jobs | A workflow queue such as Temporal or Celery | Snapshots and video processing need schedules and retries |
| Records | PostgreSQL | Reel Records, projects, drafts |
| Embeddings | pgvector inside PostgreSQL | Similarity search without a second database |
| Metric snapshots | TimescaleDB | Fast time-series queries for phases and growth curves |
| Files | Object storage such as S3 | Videos and thumbnails |
| Video understanding | A multimodal model such as Gemini | Transcript, shots, on-screen text and visual descriptions |
| Writing and reasoning | A frontier language model such as Claude | Ideas, scripts, explanations and the Ask Curo assistant |
| Prediction | LightGBM with SHAP, HDBSCAN for clusters | Accurate on mixed data and explainable per video |
| Public data | A vendor such as Apify or Bright Data | Logged-out public collection without running scrapers in-house |

**No Meta API.** CURO uses no Instagram API, needs no Meta app review and asks creators for no Instagram login. All Instagram data comes from a public-data vendor.

**Cost shape.** Onboarding one creator processes about 30 reels. At roughly 300 tokens per second of video, 30 reels of 30 seconds come to about 270,000 tokens for video understanding, plus DNA extraction and comment reading. Public data for 50 reels costs a few cents at the vendor prices above. Model prices change often, so budget in tokens and re-price quarterly.

### Privacy

- Never ask for or store Instagram passwords or logins.
- Delete a creator's data on request, and offer that in settings.
- Delete peers' raw videos after DNA extraction and keep only DNA fields and embeddings.
- Drop commenters' handles after analysis and keep only text themes and counts.
- Use collected data only to serve the creator who asked, never to build profiles of commenters or other individuals.
- Plan for DPDP duties as its phases come into force, including notice, consent and a minimum one-year log retention ([Lakshmisri](https://lakshmisri.com/insights/articles/digital-personal-data-protection-rules-2025-incremental-tweaks-and-the-way-ahead)).

### Honesty rules inside the product

1. Every predicted number is a range labelled "estimate based on your history".
2. Every recommendation shows its evidence on tap: reels, comments, peers or trend data.
3. Script notes say "associated with", never "will".
4. Percentages shown to the creator are shares of a scoring formula, and the screen says so.
5. When data is thin (fewer than 20 reels, or a reel first seen late in its life), CURO says so and widens ranges. CURO never shows or implies numbers that aren't public, such as saves or watch time.
6. All weights in this doc are starting values, refitted monthly from real outcomes.

## 18. Sources

- [Instagram API updates, April 2026](https://developers.facebook.com/blog/post/2026/04/22/instagram-api-updates-for-partnerships-metrics-collaboration-and-engagement/) — Meta for Developers (saves are owner-only)
- [Instagram limits hashtags to five](https://www.socialmediatoday.com/news/instagram-implements-new-limits-on-hashtag-use/808309/) — Social Media Today
- [How the Instagram algorithm works in 2026](https://www.eclincher.com/articles/how-the-instagram-algorithm-works-in-2026) — eClincher
- [Instagram's new AI explains why your Reel worked or flopped](https://yourstory.com/ai-story/instagram-ai-reel-performance-edits-app) — YourStory, 1 October 2026
- [Court rules Meta's terms do not prohibit scraping of public data](https://www.zyte.com/blog/california-court-meta-ruling) — Zyte
- [Meta abandons lawsuit against Bright Data](https://www.mediapost.com/publications/article/393996/meta-abandons-lawsuit-against-bright-data-over-scr.html) — MediaPost
- [India's DPDP Act brought into force](https://www.hoganlovells.com/en/publications/indias-digital-personal-data-protection-act-2023-brought-into-force-) — Hogan Lovells
- [DPDP Rules 2025: incremental tweaks](https://lakshmisri.com/insights/articles/digital-personal-data-protection-rules-2025-incremental-tweaks-and-the-way-ahead) — Lakshmikumaran & Sridharan
- [Gemini video understanding notes](https://hex.pm/packages/ex_llm/0.7.1/files/docs/gemini/GEMINI-DOCS-18-VIDEO-UNDERSTANDING.md) — mirror of Google's Gemini docs
- [Spotter Studio features](https://spotterstudio.com/features) — Spotter
- [Spotter Studio vs ViewStats](https://outlierkit.com/resources/spotter-studio-vs-viewstats/) — OutlierKit
- [HypeAuditor's AI capabilities](https://hypeauditor.com/blog/uncovering-the-ai-capabilities-of-hypeauditor) — HypeAuditor
- [VYRL](https://www.g2.com/sellers/vyrl) — G2
- [Instagram Reels Scraper](https://apify.com/scrapesmith/instagram-reels-scraper), [Ultimate Instagram Scraper](https://apify.com/apigeek/ultimate-instagram-scraper) and [Instagram Reel Scraper Pro](https://apify.com/brilliant_gum/instagram-reel-scraper-pro.md) (share counts) — Apify Store
