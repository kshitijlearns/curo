# Decisions and deviations

Every place the build deviates from, or has to interpret, the three source files.
Precedence: the MVP doc wins on scope and architecture, the logic doc on behaviour
and formulas, the prototype on look and copy.

Status: **open** = worth your review; **settled** = a reasonable choice, logged for the record.

---

## Infrastructure (Phase 0)

### D1 · Local stack: plain Postgres + pgvector with a Supabase shim, not the Supabase CLI — settled
The prompt prefers the local Supabase CLI and allows plain Postgres + pgvector with an
auth stub "if that's a problem". On this Windows machine (no Docker/WSL yet, 16 GB RAM)
the Supabase CLI's ~12 containers are heavy, and plain Postgres lets the whole test suite
also run without Docker (embedded Postgres, see D6).
- `db/local/000_supabase_shim.sql` recreates what Supabase provides (roles `anon` /
  `authenticated` / `service_role`, `auth` and `extensions` schemas, `auth.uid()` reading
  `request.jwt.claims`). It runs only locally; `python -m curo.db.migrate --no-shim` on Supabase.
- Migrations are plain Supabase-compatible SQL, so they run unchanged on Supabase later.
- RLS is real: API requests run as `authenticated` with the user's claims (`curo.db.creator_session`).

### D2 · Job progress: polling instead of Supabase Realtime locally — settled
The app follows slow jobs through a `JobWatcher` interface. Locally it polls
`GET /v1/jobs/{id}` (an endpoint not in the MVP list, added only to stand in for Realtime);
a Supabase Realtime watcher on the `jobs` table replaces it later with no screen changes.

### D3 · Queue: Redis + RQ — settled
The MVP doc allows Celery or RQ. RQ is the simpler of the two. Jobs are plain, idempotent
functions in `api/curo/jobs/`, so tests run them inline (`QUEUE_MODE=inline`). RQ's
worker needs `fork()`, so it runs in Docker (Linux), never natively on Windows.

### D4 · Clock and time travel stored in Redis — settled
`curo.clock.now()` is the only source of time. `FAKE_NOW` sets an anchor; fake time then
runs at real speed (or frozen). The state lives in Redis so the API, worker and scheduler
agree; `tools/timetravel.py` moves it. Changing `FAKE_NOW` in `.env` resets earlier time travel.

### D5 · Expo SDK 57; Expo Router at the top, the prototype's shell inside — settled
`create-expo-app@latest` produced SDK 57 (React Native 0.86, React 19.2, TypeScript 6).
Expo Router owns the top-level routes (`/` = the main shell, `/setup` = API check; Login,
Onboarding and Settings join in Phase 2). Inside the main shell, navigation follows the
prototype exactly — tabs, Home sub-views (Insights, Opportunity pages) and the Saved overlay
— held in one store (`app/src/state/app.ts`). Router tabs couldn't express Saved opening
*over* the current tab with the Nav still showing, or the single persistent header/sheet/
dock. The Android back button walks the same steps (close Saved → leave a sub-view → step
back in Studio → Home).

### D6 · Tests run against embedded Postgres when Docker isn't available — settled
`pgserver` (pip) ships Postgres 16 + pgvector 0.6 for Windows/macOS/Linux. The test suite
uses `TEST_DATABASE_URL` when set (CI, Docker) and falls back to pgserver otherwise. Every
session creates and drops its own database.

### D7 · Windows commands — settled
`make` isn't standard on Windows, so `dev.ps1` mirrors every Makefile target
(`./dev.ps1 dev`, `./dev.ps1 test`, …). If PowerShell blocks scripts, run
`powershell -ExecutionPolicy Bypass -File dev.ps1 dev` (this changes nothing system-wide).

### D8 · Docker live reload uses polling — settled
File-change events don't cross from a Windows/macOS host into Linux containers, so the
API container sets `WATCHFILES_FORCE_POLLING=true`.

### D9 · Embedding mock: deterministic feature hashing, not TF-IDF + SVD — settled
The prompt suggests TF-IDF + SVD to 768 dims. With ~350 fixture reels, SVD cannot produce
768 meaningful components, and refitting would change every stored vector (the MVP doc
says never mix embedding models in one table). The mock instead hashes words, character
n-grams and a small domain concept lexicon (e.g. ganpati / ganesh / ganeshotsav share a
concept) into 768 dims, L2-normalised. It is stable for any text, including uploads, so
similarity, clustering and nearest neighbours behave meaningfully. Model name `mock-hash-768-v1`.

### D10 · Worker package does not declare `curo` as a dependency — settled
A dependency named `curo` could make pip fetch an unrelated PyPI package. The worker uses
the local `/api` package, installed first (`pip install -e api -e worker`).

### D10a · Pinned versions — settled
`api/constraints.txt` pins every Python package to the versions the test suite passed with;
Docker, CI and `make setup` install with `-c api/constraints.txt`. In the app, `react-dom` is
pinned to `19.2.3` (the SDK 57 version) because npm otherwise floats the optional peer to a
React 19.3 build that conflicts with SDK 57's React 19.2.3. App packages are added with
`npx expo install` so versions match the SDK.

### D10b · Voice input needs a development build — settled (Phase 1)
On-device speech recognition uses `expo-speech-recognition` (language `en-IN`, which handles
Hinglish reasonably; a creator language setting can change it). Its native code isn't in
Expo Go and importing it there throws, so `app/src/lib/voice.ts` loads it only when the
native module exists. In Expo Go the mic shows: "Voice input needs the CURO app build. For
now, use the mic on your keyboard." Real voice is tested in a development build
(`npx eas-cli@latest build --profile development --platform android`, or
`npx expo run:android` with Android Studio).

---

## Product and UI (decided now, built in later phases)

### D11 · Phase model: the logic doc's five phases replace the prototype's four — settled
The prototype shows Testing / Peak / Plateau / Decline (plus "Second wave"). The logic doc
defines Testing / Growing / Peak / Slowing / Long tail with rules, and says the timeline is
split into "these five bands". Behaviour follows the logic doc; the phase track shows five
steps in the prototype's style. "Second wave" has no rule in the docs, so it isn't a phase;
a reel picking up again shows as Growing, and the "Follow up a second wave" opportunity
comes from the logic doc's "an outlier reel invites a follow-up" rule.
Precedence where rules overlap: Testing → Long tail → Slowing → Growing → Peak, and a
velocity between 50% and 80% of the peak that isn't rising counts as Peak (not yet slowed
below half). Unit-tested in Phase 4 (D52 has the remaining details).

### D12 · Comparison note: "vs your usual", not "30-day average" — settled
The prototype's non-simulated note says "your 30-day average". The logic doc's baseline is
the median of the last 20 reels at the same age, and its copy is "vs your usual". The note
reads: "Arrows compare actual results with your usual results at this age (no simulation
was run). Public counts only."

### D13 · Top comment shows no commenter handle — open
The prototype shows "@aesthetic.anya". The MVP doc stores comments with "no commenter
handles", and both docs say handles are dropped after bot/friend-tag analysis. Privacy wins:
the card shows the comment, its likes and replies, with a neutral avatar and the label
"Most-liked comment". @mentions inside stored comment text are masked ("@…") after the
friend-tag check. *If you want handles shown for the creator's own reels, that needs a
change to the privacy rule.*

### D14 · Simulator persona section hidden — settled
The prototype's "How each audience responds" section is listed as "Out — hidden in the MVP"
in the MVP doc.

### D15 · "Publish" marks a draft ready to post — settled
Publishing to Instagram is out of scope (no API). The Simulator's Publish button marks the
project ready to post, says CURO doesn't post for you, and `match_posted_reel` links the
reel when it appears.

### D16 · Saves and reposts never appear — settled
The prototype's metric icons include saves and reposts; only views, likes, comments and
shares are shown, with "Public counts only". Script notes never say "encourages saves"
(the prototype already labels the finished-look note "Drives likes").

### D17 · Screens not in the prototype: Login, Onboarding, Settings — settled
The MVP doc requires username onboarding, peer confirmation, creator memory "visible and
deletable in settings" and account deletion in settings, none of which the prototype draws.
They are built in the prototype's shell and components. Settings is reached from a small
profile button beside the Saved button in the brand header (the one header change).

### D18 · Prototype numbers are not internally consistent — settled
E.g. "3 mistakes" shows 504 likes on 90K views (0.56%) while the Simulator baseline is a
4.9% like rate, and 90K views is called "3× your follower count". The fixture keeps the
prototype's reels, titles and stories (peaking how-to, plateaued GRWM with "where is it
from?" comments, a big-share multi-look reel with part-2 requests, a declining haul with
price questions) but makes the counts consistent with each other, so the real logic
produces sensible numbers.

### D19 · Demo creator and extra peers — settled
The demo creator is `@curo.demo` (fictional, clearly a demo). Peers use the prototype's
handles (@theoutfitdiaries, @stylewithrhea, @mumbaiwardrobe, @thedrapestory, @kavyawears,
@styledbysana) plus four invented fashion handles to reach ten. All data is synthetic.

### D20 · Festival calendar dates — open
`fixtures/` will carry a two-year calendar (Ganesh Chaturthi, Navratri, Diwali, Karva
Chauth, Holi, Eid, Christmas, wedding season). Lunar festival dates must be checked against
an authoritative panchang before launch. The demo anchors on Ganesh Chaturthi 2027.

---

## UI port (Phase 1)

### D21 · No commenter handles on opportunity pages either — settled
The prototype's "Follow up a second wave" and "Festive looks on a budget" pages show
commenters' handles as avatars. Handles aren't stored (D13), so those pages show the count
of commenters instead. Peer handles (public accounts the creator tracks) still show.

### D22 · "Follow up a second wave" becomes "Follow up your best reel" — settled
"Second wave" isn't a phase (D11). The opportunity itself comes from the logic doc's rule
"an outlier reel invites a follow-up", so it's named after that.

### D23 · The Studio tab chat validates ideas — settled
Opened from the nav, the prototype's Studio chat turns a typed note into three ideas. The
logic doc (§9, "validate" chat) says it scores the idea and replies with a verdict band
(Strong ≥ 0.75, Worth trying 0.55–0.75, Risky < 0.55), two reasons with evidence and one or
two tweaks with the expected change, then "Develop this idea" opens step 2. Behaviour
follows the logic doc. Inside an opportunity, a typed note still produces three new
directions (logic doc "Writing your own idea").

### D24 · Logic-doc elements added to the prototype's screens — settled
Built in the prototype's visual language: the "Why this idea?" panel (each part's share of
the ranking score, labelled as such, plus evidence), the idea's slot (Proven / Adapted /
Explore) inside that panel, the storyboard's "How to record" and "Effort" (feasibility)
rows, "Updated X hours ago" under the phase, "Estimate based on your history" on the
predicted report, the accuracy record line, and a "Beta" label on the Simulator (MVP doc §13).

### D25 · Prototype CSS is content-box — settled
The prototype sets heights without `box-sizing: border-box`, so vertical padding and borders
add to them (the Nav bar renders 68 + 9 + 2 = 79px tall). React Native is border-box, so such
heights are converted. Checked by pairing every screen in `reference/compare.html`.

### D26 · Phase 1 shows the prototype's mock numbers — settled
Until the API replaces them (Phases 2–7), screens show the prototype's values, including its
inconsistencies (D18), and the Simulator score uses the prototype's toy formula. The
honesty labels are already in place.

### D27 · The keyboard hides the Nav — settled
When the keyboard is open, the Nav and the composer's hint line hide, so the input sits
directly above the keyboard on small phones. iOS uses `KeyboardAvoidingView` padding; Android
resizes the window (Expo's documented approach).

### D28 · Web build only for visual checks — settled
`react-native-web` is installed so `tools/screenshot_app.py` can render the app in headless
Edge and pair every screen with the prototype in `reference/compare.html`. Web is not a
supported product target. Because web can hide native-only problems, every phase also runs
the Jest suite and a native Android + iOS bundle export; that is how a missing `expo-asset`
(needed for fonts on phones, not on web) was caught and fixed.

---

## Data layer and public collection (Phase 2)

### D29 · Sign-in is an email code; the local stand-in returns the code in development — settled
The MVP doc uses Supabase Auth. Locally (`AUTH_PROVIDER=local`) the API issues a 6-digit
code, stores only its HMAC, allows 5 attempts and 10 minutes, and signs a Supabase-shaped JWT
(`aud=authenticated`, `sub`=user id) so RLS works exactly as it will on Supabase. There is no
email service yet, so in `development`/`test` only the code is returned in the response and
filled in on the sign-in screen. Staging/production never return it. Instagram is never
involved in sign-in.

### D30 · Snapshot cadence details — settled
Intervals are the logic doc's (creator: 3 h under 48 h, 12 h under 7 days, 24 h under 30
days, weekly under 90 days, then stop; peers: daily for 14 days). Two details it leaves open:
*new-reel discovery* checks the latest 5 reels every 3 h for the creator and every 24 h for
peers; a reel counts as due 15 minutes early, so a run that lands slightly early isn't
skipped. The scheduler ticks every minute and enqueues at most one run per account per
quarter-hour (idempotency key), batching all of that account's due reels into one scrape.

### D31 · A failed scrape leaves a gap, never a guessed row — settled
Retry once, then the backup vendor, then the run fails with `CollectionFailed`, recorded on
the job. Nothing is written for that moment: the gap stays a gap ("missing means unknown").
`account_snapshots` records followers/following/posts on every successful run (the MVP's
follower snapshots).

### D32 · Which comments are collected — settled
Onboarding reads up to 200 comments on each of the newest 30 reels (MVP doc). Later runs read
comments for newly discovered reels, and re-read a reel when its public comment count has
grown past what's stored by more than 10% + 5. Commenter handles are never stored (D13);
@mentions inside comment text are masked as "@…", and only "tags a friend" (true/false) and
"is the creator" are kept.

### D33 · Private or deleted accounts — settled
A peer that goes private or is deleted: its reels and snapshots are removed and only
aggregates already computed from it remain (logic doc). The creator's own account keeps its
history and is marked, and onboarding a private account is refused with a friendly message.
A deleted reel is marked deleted and drops off Home; its snapshots are kept.

### D34 · "Seen late" reels — settled
A reel first collected more than 48 hours after it was posted has no early curve. It's
flagged (`seen_late` on the API) and Insights says its early hours weren't recorded. Phase 3
uses the flag to keep such reels out of curve fitting.

### D35 · The demo is loaded by replaying collection, not by inserting rows — settled
`python -m curo.seed demo` sets CURO's clock 14 days before the dataset's anchor, onboards
`@curo.demo` with the real `onboard_public` job, then steps the clock forward an hour at a
time running the real scheduler, so every reel posted in those 14 days gets a genuine
snapshot history from its first hours (about 6 seconds). The live scheduler is paused while
it runs. `.env.example` now sets `FAKE_NOW` to the dataset's anchor
(2027-08-23 10:00 IST); clear it once real providers are connected.

### D36 · What `GET /v1/me` adds — settled
`now` (CURO's clock), so "Updated X hours ago" is right while time travelling; and
`onboarded`, true once reels are in or onboarding has finished. Home opens as soon as the
first reels are stored (the app resumes the progress screen if reopened mid-collection), and
a public account with no reels yet gets Home's empty state instead of looping back to
onboarding.

### D37 · Until the learning jobs exist, Insights says so — settled
Phase 2 fills Home and Insights' carousel with real collected counts. The phase and "what your
audience thinks" need growth curves (Phase 3) and comment themes (Phase 4); until then those
cards say the reel is being processed instead of showing mock values. Arrows stay off (no
baseline or simulation yet), so the note reads "Public counts only." Opportunities, Studio and
the Simulator keep Phase 1's mock data until their phases.

### D38 · Reel thumbnails: illustrated covers for now — open
Cards keep the prototype's illustrated thumbnail with a stable colour per reel. Collection
stores the vendor's cover URL, but Instagram CDN links expire within days, so showing real
covers means copying each one into storage on collection (a few KB per reel). **Question:**
should real cover images be shown? If yes, it's a small addition to the collection job.
*Phase 3 update:* `process_reel` now copies the cover of every processed reel into storage
along with the video, so only the other reels and serving them (signed URLs, Phase 7) remain.

### D39 · Tooling notes — settled
`openapi-typescript` is run through `npx` at a pinned version (its peer range stops at
TypeScript 5; the app uses TypeScript 6): `make api-types` / `./dev.ps1 api-types`. The RQ
worker forks per job, so it runs in Docker (Linux); without Docker, `QUEUE_MODE=inline` runs
jobs inside the API process.

---

## Understanding pipeline (Phase 3)

### D40 · Which reels get DNA — settled
As the MVP doc says: the newest 30 at onboarding, plus every reel found later. A nightly
catch-up re-queues any of a creator's newest 30 that are missing DNA. Older reels keep their
numbers (they count in baselines) but aren't watched by the video model, which is where the
cost is. The plan's "every reel has DNA" therefore reads "every processed reel".

### D41 · Values at an age and the 30-day bucket — settled
A reel's value at age t is read straight-line between the two snapshots around t and never
extrapolated before its first snapshot. One approximation: a reel first seen after 30 days
counts in the 30-day bucket with its first snapshot (reels change little after a month).
"The last 20 reels" means the 20 most recent reels that have reached that age with a known
value; paid partnerships are left out, deleted reels stay in. Between the fixed ages
(6 h, 1 d, 3 d, 7 d, 30 d) baselines are interpolated in log-age (log-value for counts). The
growth curve g(t) is stored as the median share of 7-day views reached by each age
(`views_share_7d`); the demo gives 72% by day 3, as in the logic doc's worked example.

### D42 · Pattern cards compare like with like — settled
The logic doc compares "reels that have it with reels that don't". Done naively, a creator's
setting, camera or opening mostly mark the topic (every haul is handheld in the living room),
so the first run produced cards like "Bedroom → shares 3.5×" that only meant "hauls get few
shares". Each reel is therefore compared with the reels of its own sub-cluster that don't
have the value; a sub-cluster whose reels all share the value is left out of that
comparison. Topic-level differences stay where they belong, in the sub-cluster lifts.
"Holds in a statistical test" = a two-sided Mann–Whitney test on log lifts with a
Benjamini–Hochberg false-discovery rate of 10% across all of the creator's comparisons (so
testing many features doesn't manufacture patterns). Effects within ±10% aren't shown.

### D43 · Shrinking when there's no similar-creator evidence yet — open
The formula blends the creator's effect with the similar-creator effect (k = 10). Until peers
are collected and processed (Phase 5) there is no similar-creator effect, so the creator's
effect is blended with "no effect" (1.0). That's conservative: the demo's own effect for
choice-question endings is 1.61×, shown as 1.29× (9 reels count for 47%). Once peers exist,
their effect is used instead. **Question:** keep the conservative blend, or show the
creator's own effect unblended (still labelled with its reel count) until peer data arrives?

*Phase 5 update:* peers now exist, so their pooled effect is the prior. In the demo,
choice-question endings show 1.66× comments, blended with "seen across similar creators". The
conservative blend now applies only to a value no tracked peer shows, or before any peer has
been processed (right after onboarding, or for a creator who tracks no one). The question
still stands for those cases.

### D44 · Similar creators = the tracked peers — settled
Priors ("seen across similar creators", `pattern_cards.account_id` NULL) are pooled from
every tracked account that isn't a creator's own, each reel measured against its own
account's baseline. Peers are chosen in the creator's niche, so they are the similar
creators the logic doc means; matching on size and language as well comes when the index
is larger.

### D45 · Peers' videos are deleted right after their DNA is extracted — settled
The MVP doc lists this under the daily `cleanup` job; `process_reel` does it immediately, which
is stricter on privacy and leaves `cleanup` nothing to find. Creators' own videos are kept.

### D46 · Comment themes — settled
T3 gives each request or question a short theme phrase; phrases that mean the same (embedding
similarity ≥ 0.9) are merged, and T4 names each group. A theme's share is its comments ÷ all
non-bot comments on the creator's last 30 reels (the logic doc's 3% opportunity rule reads
this). The creator's own replies are never labelled. A theme keeps its id across rebuilds
through its phrase.

### D47 · When learning runs — settled
`recompute_learning` runs for an account once its processing has settled (nothing queued or
running for it) and its DNA changed since the last run — so 30 processed reels trigger one
run, not 30 — and every night at 02:00 IST with the comment batch, the missing-DNA catch-up and
the priors (baselines move as snapshots arrive). The scheduler reports only jobs it created.

### D48 · How the mocks stand in for the models — settled
The fixture now holds, per reel, what a video model would report (transcript with timings,
shots, on-screen text, a description per second, audio type, first payoff), written by the
generator from the reel's DNA. The mock video provider returns it after reading the stored
file; the mock DNA extractor (T2) reads only that description and the caption with keyword
cues, and its confidences follow how much evidence it found — 99.9% agreement with the
generator's DNA on confident fields, 3% honestly unknown (e.g. the place can't be told).
Comment labels (T3) and group names (T4) work the same way; embeddings are D9's feature
hashing. None of the mocks ever sees the generator's answers.

### D49 · The synthetic data now carries production patterns — settled
So pattern mining has something real to find, each synthetic reel's production choices
(ending, call to action, time to first payoff) now shape its likes, comments and shares,
sized like the prototype's own notes: choice-question endings ×1.7 comments, ending on the
final look ×1.25 likes, payoff within 2 s ×1.25 likes, send-to-a-friend prompts ×1.6
shares. The same holds for peers (similar creators). Views, the prototype's four reels and
everything else are unchanged; the demo's other reels have new like/comment/share counts and
comment texts. Nothing downstream reads these numbers; the mining finds 1.61×, 1.26× and
1.49× on its own.

---

## Home and Insights on the real logic (Phase 4)

### D50 · Arrows — settled
An arrow compares the latest snapshot with the expected value at that snapshot's age: the
simulation's 7-day prediction × g(t) when the reel was simulated, otherwise the creator's usual
(median of the last 20 reels at that age, interpolated between the fixed ages). With fewer
than 3 of the creator's reels at that age there is no arrow rather than a shaky one; the logic
doc's cold-start baseline ("creators like you") needs peers and arrives in Phase 5. Beyond 7
days g(t) is the 30-day share once known, else 1.0 (the prediction is a 7-day figure); likes,
comments and shares use the views growth curve. A simulation stores its 7-day prediction as
`simulations.predicted = {"views": {"low", "mid", "high"}, …}` and arrows use "mid" (Phase 7
writes it).

### D51 · Screens compute baselines from the snapshots on each request — settled
Home and Insights compute the medians from the same function the jobs use, at request time, so
the arrows are as current as the last snapshot. The stored `baselines` rows (refreshed by the
learning jobs) serve the background work.

### D52 · Phase details the logic doc leaves open — settled
Velocity is the average views per hour between consecutive snapshots (for a reel seen from
its first hours, also from posting to the first snapshot). "Rose" means more than 5% faster
than the interval before. Testing compares with the account's current follower count. Long tail
means no interval at ≥ 10% of the peak in the last 48 hours; a reel that has stopped completely
also shows Long tail. A phase starts at the first snapshot showing it; its usual length is the
25th–75th percentile of the stretches the creator's tracked reels completed (at least 2), shown
as "6 – 18 hours", "1 – 3 days" or, for Long tail, "Day N+". A reel first seen more than 48
hours after posting never showed CURO its peak, so its phase is estimated from its age and the
creator's usual timeline, and the card says so.

### D53 · "Beyond your followers" — settled
The logic doc attaches it to Peak; it's also added to Growing (a reel picking up again past
twice its follower count is clearly reaching non-followers). It's said from views ÷ followers
only, rounded ("already 2× your follower count"), never as a share.

### D54 · The audience card set — settled
The logic doc's table lists "Comments are driving engagement", "Shares are lower than usual",
"Likes per view are high or low", "People are tagging friends" and "Your follower count
jumped", while its selection rule needs a card for any clearly low rate. Each rate therefore has
a high and a low card ("Comments are quieter than usual", "Shares are higher than usual" — the
prototype has the latter). One more comment-based card: when a single request/question theme
is at least 20% of the reel's comments ("Comments ask the price"). A follower jump means growth
at least 2× the usual rate in the 2 days after posting while this reel brought at least half of
the creator's new views then. The views lift isn't a card on its own (the table has none).
z-scores are against the log lifts of the creator's other reels and need at least 5.

### D55 · Sentences, the no-new-numbers check and caching — settled
T10 writes each card's sentence from computed facts only. The check reads every number however
it's written (1.2K, 41%, 1.4×, ₹2,000, "three"); "one" is always allowed. A sentence with a new
number is retried once and then replaced by the facts themselves. Sentences are cached by
their facts for a week, so the model is called only when the facts change.

### D56 · Thin data is said plainly — settled
Under the phase: "Compared with N of your reels at this age so far" (fewer than 20), "Not
enough of your reels at this age to compare with yet" (fewer than 3), the late-reel note, and
"Curo is still watching this reel" until its DNA exists (honesty rule 5).

### D57 · Opening a reel on Instagram — settled
The logic doc says tapping the thumbnail opens the reel through its permalink; the prototype
uses that tap for Insights. Both: on Home the selected card opens Insights; on Insights the
selected card opens the reel on Instagram.

---

## Peers and opportunities (Phase 5)

### D58 · How peers are suggested — settled
The logic doc ranks candidates on four signals: content similarity, follower size, language
and region, and audience overlap (shared commenters). CURO never stores commenter handles
(D32), so overlap can't be measured. It is left out rather than approximated.

- **Candidates:** owners of reels on the pages of the creator's 8 most-used hashtags (up to
  20; public accounts with reels only).
- **Score:** 0.6 × content similarity + 0.3 × size closeness + 0.1 × language.
  - Content similarity: their latest 12 captions and tags against the creator's last 30.
  - Size closeness: 1 at the same size, 0 at 0.3× or 3×. Accounts outside that range are
    never suggested.
  - Language: the public data gives no account language yet, so it counts as neutral (0.5)
    for everyone until it does.
- **Result:** the top 10 are stored with plain reasons ("Posts reels like yours", "About your
  size"). The creator confirms them in a new last onboarding step or in Settings, removes
  any, and can add a public handle (private accounts are refused).
- **Demo:** the seed confirms all 10, so Home has opportunities straight away.

### D59 · What CURO collects about peers — settled
A tracked peer's profile and latest 30 reels go through the same collection and
understanding pipeline as the creator's: snapshots, DNA and embeddings, with videos deleted
after extraction (D45). Its latest 5 reels are checked daily, and every peer is refreshed
weekly (Mondays). Peers' comments are not collected: nothing in the logic doc reads them
(audience demand comes from the creator's own comments), and it keeps strangers' text out of
the database.

A peer reel's Outlier Index (OI) = its views ÷ that peer's usual views at the same age (D41).
It needs at least 3 of the peer's reels at that age; otherwise there is no OI.

### D60 · The five parts of an opportunity score — settled
The logic doc gives the parts, the weights (Score = 10 × (0.30 F + 0.20 D + 0.20 P + 0.20 T
+ 0.10 O)) and a worked example, but not how each part is computed. Each part is 0–1,
computed from data alone, and carries the facts it came from. The detail page is built from
those facts, and they are the only numbers its texts may use.

- **F, creator fit** = 0.7 × match + 0.3 × format.
  - Match = how close the topic's text is to the nearest sub-cluster's captions (1 = as close
    as that sub-cluster's own reels) × that sub-cluster's views credit. The credit is 0.5 at
    the usual views and 1.0 at 1.5× or more.
  - Format: 1.0 if the creator has made the format peers' reels on the topic use 3 or more
    times, 0.6 for 1–2, 0.2 for never, 0.5 if unknown.
- **D, audience demand** = 0.5 × asks + 0.3 × engagement + 0.2 × place.
  - Asks: the share of the creator's recent comments requesting or asking about it (5% →
    full).
  - Engagement: the comment- and like-rate lifts of the nearest sub-cluster.
  - Place: for a regional festival, 1.0 if comments mention its regions and 0.3 if not; 0.7
    otherwise.
- **P, peer evidence** = 0.4 × breadth + 0.6 × strength. It is 0 without outliers.
  - Breadth: tracked peers with an outlier reel on it (OI ≥ 2) in the last 14 days (4 → full).
  - Strength: the median OI of those reels (3× → full).
- **T, timeliness**: for a dated event, 0.6 × window + 0.4 × momentum; otherwise momentum
  alone.
  - Window: 1.0 from 7 to 14 days before, falling to 0.4 at 30 days and towards 0.6 in the
    last week; 0.5 during the event, 0 after.
  - Momentum: posting growth (D61; 2.25× → full). For a follow-up it's the reel's own
    view-velocity growth. Otherwise it's peers' posts on it this week against the 4 weeks
    before. It counts 0.3 when unknown.
- **O, openness** = 1 − 0.75 × the share of tracked peers who posted on it in the last 14
  days (0.7 when there's nothing to measure against).

**On topic** means a caption or hashtag contains one of the topic's defining words or tags.
Those are words used on no more than 10% of the reels considered, so "#ootd" or "look" never
define a topic. A topic with no defining words (an audience question, a follow-up) has no
peer evidence rather than a loose guess.

**Demo:** Ganpati dress ideas scores F 0.66 · D 0.80 · P 0.75 · T 1.00 · O 0.55 →
10 × (0.198 + 0.159 + 0.150 + 0.200 + 0.055) = 7.63 → 8/10. The logic doc's example gives
0.82 → 8.

**Same data, same result.** The build reads its inputs in a fixed order (reels by posting
time, peers by handle, comments by their Instagram id), never in database or hash order.
Which captions and comments describe a topic therefore can't change from run to run. Two
seeds of the demo give identical opportunities and pattern cards. The detail page shows each part's weighted share, and the parts always add up to
the score.

### D61 · Posting momentum from CURO's own hashtag index — settled
The MVP doc's trend data is "CURO's own index". A hashtag page lists only its most recent
reels (CURO asks for up to 300), so one fetch can't show a month.

- **Daily counts:** each daily fetch (at most once per 20 hours) adds reels per day, for the
  days it covers, to `hashtag_pages.daily_counts`.
  - A partly seen day is scaled up once at least a quarter of it is seen.
  - Days with no reels count 0.
  - The better-covered figure for a day is kept.
- **Momentum** = average daily reels over the last 7 days ÷ the 28 before, once at least 5
  days are known.
- **Watched tags:** the creator's 10 most-used, up to 25 used by 2 or more tracked peers, and
  the tags of festivals in the next 30 days.

### D62 · Where opportunity candidates come from — settled
The logic doc's four sources (§8 step 1), with these thresholds:

| Source | Becomes a candidate when |
| --- | --- |
| Competitor | 2 or more tracked peers posted outlier reels (OI ≥ 2) in the last 14 days sharing a defining word or tag |
| Trend | A festival 7–30 days away in the creator's niche, or a watched tag (used on at most 10% of reels) whose posting grew 1.5× or more |
| Audience | A request or question theme in at least 3% of comments on the last 30 reels |
| Your content | A follow-up: a reel from the last 14 days at 1.5× usual views or more that is growing again or has 3+ comments asking for a part 2 |
| Your content | A sub-cluster with a views lift of 1.3 or more and no post in 30 days |

Topics are described by captions, tags and comments, so they are compared with caption text.
Sub-clusters get a caption-level vector for this, and peer suggestions do the same (D58).
Comparing a caption with a video description understated fit.

### D63 · Merging, filtering and naming — settled
**Same topic.** Two candidates are the same topic when any of these holds:
- they share a defining word or tag;
- half or more of one's evidence names the other;
- 30% or more of an audience theme's comments name the other;
- a theme's comments concentrate (20% or more) on the reel a follow-up is about.

A merged topic is shown under where it was first found, in the order Competitor, Trend, Your
content, Audience. The logic doc gives no order; peers' evidence is the most concrete.

**Dropped:**
- topics the creator posted on in the last 14 days (follow-ups excepted);
- festivals that have ended;
- brand-unsafe topics (alcohol, gambling, crypto, smoking, politics, weapons);
- topics matching words the creator blocked.

**Naming.** T5 names each topic and writes its description and "why it fits" from the facts.
The no-new-numbers check allows numbers from the facts and from T5's own inputs (a theme
called "wants a part 2"). Two topics given the same name (for example "Looks on a budget" for
price questions and for budget requests) mean the same thing to the creator, so they are
merged and scored again.

**Home** shows the top 5 by score. The one-line card text is assembled from the facts, not
written freely.

### D64 · Save, "Not for me" and Saved — settled
The prototype has a bookmark but no way to turn a topic down; the logic doc's learning loop
records dismissals.

- **Not for me:** a quiet link under the detail removes a topic and records
  `opportunity_dismissed`. The topic stays dismissed across nightly rebuilds, because it
  keeps its identity through `topic_key`.
- **Save:** records the score at that moment. Saved shows it beside today's score, and
  "Window passed" once a dated topic's window has ended.
- **Rebuilds:** saved topics are kept even when they no longer qualify.

### D65 · Opening an opportunity in Studio — temporary (removed in Phase 6)
Studio still runs on Phase 1's mock projects, one per prototype opportunity. Until Phase 6
builds the real Studio, "Open in Studio" opens the mock journey for the same topic: Ganpati,
reveal, mistakes, a follow-up or budget, matched on `topic_key`. Any other topic opens the
plain Studio chat. This lives only in `app/src/lib/studioBridge.ts`; Phase 6 removes it and
passes the opportunity to the project instead.

*Phase 6:* removed. "Open in Studio" now creates a project from the opportunity (D68).

### D66 · A suggested peer is not yet tracked — settled
Migration 0006 let every `peers` row widen what a creator can read. Suggestions are now
stored before the creator chooses, so a suggestion would have exposed that account's reels
and learned records. Migration 0009 fixes this:
- a suggestion shows only the account row (handle, follower count) needed to decide;
- reels, snapshots, comments, DNA and baselines become visible once the account is tracked.

### D67 · Jobs survive Redis dropping a connection — settled
Found while checking onboarding: when Redis dropped a connection, confirming peers
returned an error after the job rows were already saved. Those rows stayed "queued" with
no worker ever receiving them. That also blocked the account's learning (which waits for
nothing to be queued) and left "Finding creators like you…" on screen. Managed Redis
services close idle connections, so this would happen in production too. Now:
- the job row in Postgres is the record of what must run, and the request succeeds even if
  the hand-off to Redis fails (a warning is logged);
- each RQ job carries its row's id, so CURO can tell a job that is waiting its turn from
  one the worker never received;
- every scheduler tick hands over again any job still queued 5 minutes after creation that
  RQ has no record of. While Redis stays unreachable, nothing is lost or sent twice.

---

## Studio (Phase 6)

### D68 · One project, generation as jobs — settled
A project is created from an opportunity (its first three ideas start straight away) or from
an idea validated in the Studio tab. It carries every version of the script, storyboard and
captions; the newest is what the creator sees.

Writing ideas, a script, a storyboard or captions takes a real model well over 5 seconds.
The MVP doc's rule for slow work applies: the endpoint answers 202 with a job id and the app
follows the job, then reloads the project.
- **Not streamed.** The prototype shows a loading state for each step, not words appearing.
  Streaming (SSE) stays with Ask Curo.
- **A new job type.** `studio` is added to the MVP doc's twelve jobs.
- **Priority.** It runs on its own queue, which the worker serves before background work,
  because a creator is waiting.
- **Idempotent.** The same request in the same project state reuses its job.

Quick steps answer directly: picking an idea, the creator's own script, hashtags, the chosen
caption, saving and validating an idea.

### D69 · The five idea parts — settled
The logic doc names the parts and weights (0.35 H + 0.25 A + 0.20 P + 0.15 T + 0.05 N). These
are the formulas. Each part is 0–1 and keeps the facts it came from.

- **H, your history.** The lift CURO expects from the idea's topic, format and hook type,
  mixed across metrics with the Simulator's "both audiences" weights (views 30%, shares 25%,
  likes 25%, comments 20%), so ideas and the Simulator agree.
  - Topic: the nearest sub-cluster's lifts, scaled by how near the idea is.
  - Format: the median lifts of the creator's reels in that format, counted n ÷ (n + 10).
  - The two are combined as a geometric mean (a sub-cluster that *is* the format isn't
    counted twice), then multiplied by the hook type's pattern card.
  - Credit: usual = 0.5, 1.5× or more = 1.
- **A, audience** = 0.6 × asks + 0.4 × engagement.
  - Asks: the share of comments in a request or question theme the idea answers (5% →
    full). An idea answers a theme when it cites it as evidence, uses its key word ("where",
    "price", "budget"), or is very close to it (0.6 similarity). Looser similarity matched
    unrelated themes.
  - Engagement: the expected lift on the behaviour the idea aims for.
- **P, peers.** The median Outlier Index of the up to 5 most similar peer reels (3× → full).
  It needs at least 2 similar reels; otherwise 0, rather than a guess.
- **T, trend.** For an idea about a dated event: 0.6 × the timing window + 0.4 × momentum of
  any rising tag it rides.
  - The event is the project's own festival, or any other one the idea names. A Navratri
    idea is timed by Navratri, not by the Ganpati in progress.
  - An idea about no event while one is coming gets 0.2 for the window.
  - Unknown momentum counts 0.3.
- **N, novelty** = 1 − the highest similarity to the creator's last 10 reels.

### D70 · Three slots and the diversity rule — settled
Slots are filled in order: Proven, then Adapted, then Explore. Each takes, from the ideas that
qualify for it, the one with the highest 0.7 × score − 0.3 × similarity to those already
chosen. The first pick is simply the best proven idea.
- **Proven:** a format the creator has made at least 3 times with views at or above their
  usual.
- **Adapted:** peer part ≥ 0.35 or trend part ≥ 0.6.
- **Explore:** answers an audience theme, or novelty ≥ 0.6, or a format the creator hasn't
  made.

A slot nothing qualifies for takes the best remaining idea by the same rule. The logic doc's
own numbers hold: 0.80 / 0.71 / 0.60, and 0.27 against 0.34 for the third slot (tested).

### D71 · What T6 returns, and the creator's own idea — settled
T6's candidates also carry a `hook_type` (H needs it) and a short `description` (step 2 shows
it). Candidates citing no valid evidence id are dropped.

T6 has a "read" mode for the creator's own idea. It returns that idea, in the creator's
words as written, with its format, hook type, target behaviour and related evidence. The
same scoring then applies, so the validate chat and "Develop this idea" need no separate
task. The catalog stays at 15 tasks.

Each idea stores its one-line "why" and its evidence chips, so a round shows what it was
picked from, even after the data moves on. The "why" is a fact from the part that earned the
idea its slot: history for Proven, peers or trend for Adapted, audience or novelty for
Explore. Otherwise two lookbook ideas would both say "Your lookbook reels get 1.60×…".

### D72 · The validate chat — settled
- **Verdict bands:** Strong ≥ 0.75, Worth trying ≥ 0.55, else Risky.
- **Two reasons, matching the verdict:** a Strong idea's two strongest parts, a Risky idea's
  two weakest, and for Worth trying one of each, each with its evidence. A part is only
  called a strength when it scores at least 0.5. An early version could open a Risky
  verdict with "It's close to the kind of reel that does best for you".
- **Tweaks:** each candidate change is re-scored with the same formula, and the best two
  that gain at least 0.01 are shown:
  - the creator's best working format;
  - answering their biggest unanswered comment theme;
  - tying it to the coming festival, offered only when the idea names no festival.

### D73 · How a script is planned — settled
- **Length.** The band (0–15, 15–25, 25–35, 35–45, 45–60, 60–90 s) where the creator's reels of
  the format do best, needing at least 2 reels in a band. Else across all their reels, else
  25–35 s.
  - "Do best" is views per follower compared at the same age, i.e. each reel's views lift,
    so old and new reels compare fairly. Most demo reels have no 7-day snapshot of their own.
- **Structure.** From the creator's 3 strongest reels of the format:
  - a hook;
  - a setup beat if 2 of the 3 have one;
  - as many items as the idea names, else the median those reels had (2–6);
  - their usual ending, unless the idea aims at comments, likes or shares, which need a
    choice question, the finished result, or a line to send to a friend.
- **Word budget.** Speaking speed × length, split hook 15%, setup 10%, ending 15%, items the
  rest. The voice profile (speaking speed, sentence length, language, recurring phrases,
  energy) is measured from the creator's transcripts. The learning job stores it in
  `creators.voice_profile`.
- **Timing.** Each beat's words at the creator's speaking speed, at least 1.5 seconds.
- **Honest reply.** Curo's reply describes the script actually written ("This draft runs about
  29 seconds… shorter than the 45–60 seconds your lookbook reels do best at"), never the plan
  restated as if it were the result.

### D74 · Script notes — settled
T8 labels lines. CURO keeps a label only if the cited pattern card exists, has an effect above
1, and is on the note's metric for one of its features:

| Note | Metric | Features |
| --- | --- | --- |
| Strong hook | views | hook type, opening, payoff in the first 2 seconds |
| Drives comments | comments per view | choice or open question endings, comment prompts, choice dilemmas |
| Drives likes | likes per view | ending on the final look, payoff in the first 2 seconds, opening on the final look |
| Encourages shares | shares per view | send-to-a-friend prompts, relatable struggles |

Notes are worded as associations ("Curo links this kind of line with more comments for you")
and show the card's evidence. Never "saves".

**Demo:** the creator has no pattern on views for openings, so their scripts show no "Strong
hook" note. The prototype shows one; the logic doc's rule is that an unsupported note isn't
shown.

### D75 · Revisions change only what they touch — settled
T13 sorts a request into one of the step's actions. Code fills in the targets an action
implies and keeps every other beat or frame word for word (merge in `services/script.py`,
tested).
- **Regenerate:** a different structure (with or without the setup beat) and a different
  hook.
- **The creator's own script.** Text with 2 or more lines, or 20+ words, sent in the script
  step is the creator's own script. It is kept as written, split into beats and noted.
- **Captions.** A sentence with no request words in the caption step is the creator's own
  caption, kept as written.
- **Script edits mark frames.** When a line changes, its storyboard frame is marked, and
  rebuilding the storyboard redraws only those frames.
- **"Make this easier"** is applied in code: one location, no helper and one light, with the
  hook frame kept. The feasibility score really drops; the model only rewrites the
  instructions.
- **Pacing** scales frame times by 15%, inside the creator's length band.

### D76 · Storyboard feasibility — settled
Four costs: extra locations (1 each), a second person (2), outfit or prop changes (0.5 each)
and extra light setups (1 each).
- Labels: Easy ≤ 1.5, Moderate ≤ 3.5, else Hard.
- Score: 100 × (1 − cost ÷ 6).

T11's frames therefore also carry the camera, place, light, whether a helper is needed and
whether the outfit changes; the MVP doc's frame fields alone can't be costed. Shots prefer
the creator's own toolkit: cameras, places and light from their Production DNA.

### D77 · Captions and hashtags — settled
**Captions**
- The creator's caption style (median words, emoji, language) comes from their last 30
  captions.
- Search phrases come from the topic and its multi-word keywords.
- The three captions go through the no-new-numbers check against the idea, the topic, the
  script's lines and the search phrases. On failure they fall back to captions built from
  the hook and the script's ending.

**Hashtag candidates and score** (0.5 relevance + 0.3 past results + 0.2 specificity)
- Candidates: the creator's past tags (with their reels' views lifts), tracked peers' tags
  (with their Outlier Index), CURO's hashtag pages, the festival's tags, and T12's
  suggestions.
- Relevance: how much of the tag is spelled by this draft's words. Filler words don't count,
  so `#getreadywithme` doesn't match "getting ready with".
- Results: the median lift as credit; unknown counts 0.5.
- Specificity: falls as the share of reels using the tag rises (2% → 1, 20% → 0) and as its
  page grows (10K posts → 1, 10M → 0). Generic tags (`#reels`, `#explore`…) get 0.

**Kinds** (the order matters):
- **series:** the creator uses it on 3 or more reels *of this idea's format*, and at most 1
  tracked peer uses it. So `#reeltips` isn't offered for a festive lookbook.
- **local:** a place name.
- **broad:** the festival's tags, generic tags, or used on more than 10% of reels or with over
  1M posts.
- **niche:** everything else.

**The five suggested.** Shown: candidates with relevance ≥ 0.3 (series tags exempt). The
five are a mix of broad, niche, niche, local and series, with gaps filled by the next best
niche tag. A sixth is refused in the app, the API (422) and the database.

### D78 · A script belongs to its idea — settled
Picking a different idea after writing a script must not show the first idea's script. Script
versions record their idea (`script_versions.idea_id`) and captions their script version
(`captions.script_version`, both in migration 0010). The project shows only the chosen idea's
newest script, and the newest storyboard and captions made from its scripts. Going back to the
first idea finds its work again.

### D79 · Saved drafts — settled
Saved lists saved projects, newest first, with the step they were saved at and their first
frame's sketch. The prototype opens with one draft already saved; CURO shows only what the
creator saved. "Today" and "Yesterday" use CURO's clock (the API's `now`), not the phone's.

### D80 · The Simulator until Phase 7 — superseded by D82–D94
In Phase 6 the Simulator was still Phase 1's mock, linked to the open Studio project by its
idea's title. Phase 7 replaced it.

### D81 · Phase 1 mock data removed — settled
The Studio mock (`app/src/mock/studio.ts`, its test) and the unused Home and Studio mock data
(prototype reels, opportunities, idea banks, script notes, captions, hashtags) are deleted.
The Simulator's mock result went in Phase 7; `app/src/mock/data.ts` keeps only shared wording
(phase names, tag colours).

---

## Simulator (Phase 7)

### D82 · Neighbours and their lifts — settled
T9 steps 1–2 (MVP doc §10). The pool is the creator's reels and their confirmed peers' reels
that have DNA and an embedding; paid partnerships (possibly boosted) and deleted reels are
left out. The 15 nearest by cosine similarity of the video embedding (caption, transcript,
on-screen text and what's seen — the same text a posted reel is embedded from) are the
neighbours; a neighbour of the same format ranks 15% higher. Each weighs its similarity, ×2
for the creator's own reels.

A neighbour's lift is its 7-day lift against its own account's 7-day usual. **Interpretation:**
a reel CURO first saw after day 7 has no 7-day value, so it counts with its lift at its
reference age (latest snapshot, up to 30 days) against the usual at that same age — the lift
Home and the pattern cards use. A usual resting on fewer than 3 reels isn't used (as Home's
arrows, D50).

### D83 · The estimate, adjustment and range — settled
- **Estimate:** the weighted geometric mean of the neighbours' lifts per metric (lifts are
  ratios, so the average is taken in logs).
- **Adjustment:** for each production feature (hook, opening, narrative, ending, call to
  action, camera, audio, light, setting, payoff time, length, pace, on-screen text) where the
  upload's value differs from the neighbours' weighted majority, the ratio of the two values'
  pattern-card effects on that metric (no card = 1). The ratios multiply, and the product is
  capped to 0.7–1.3 (±30%).
- **Range:** the weighted 10th–90th percentile of the neighbours' lifts, with the same
  adjustment. With fewer than 8 of the creator's own reels among the neighbours, it is
  stretched around the middle in log terms by 1 + 0.5 × (8 − own) / 8 (at most 1.5×).
- A metric no neighbour shows stays unknown, never zero: it is left out of the score's mix
  (the other weights are rescaled) and the report says so.

### D84 · The score and its labels — settled (prototype thresholds replaced)
The score is the percentile of the upload's weighted mix of predicted lifts among the same
mix for the creator's last 50 non-paid reels (ties count half), with the logic doc's weights
per audience. With no history it is 50.

Every run stores the score for all three audiences, so the audience toggle switches between
stored results rather than re-running; the reasons and the order of edits switch with it.

Labels: 80+ "Strong — likely above most of your recent reels", 60+ "Likely above your
baseline", 40+ "Around your baseline", below 40 "Likely below your baseline". The
prototype's thresholds (80 / 70 / 62) were set for its mock numbers; on a percentile the
creator's middle reel is 50. Under the label the result says what the number means: "Likely
to do better than 72% of your recent reels" (logic doc §13).

### D85 · What's working and what's holding it back — settled
Until the trained model's SHAP values exist (MVP doc: "Nearest-neighbour estimate … not a
trained model"), the reasons come from the pattern cards:
- **Working:** the upload has a card's value with an effect above 1.
- **Holding back:** it has a value with an effect below 1, or it lacks a production value
  with an effect above 1 (e.g. "The payoff lands at 3.8 seconds. Your reels with the payoff
  in the first 2 seconds got 1.23× your usual likes per view").
- **Strength:** |ln effect| × the audience's weight for the card's metric. A value appears
  on one side only, the stronger one. Top three each.
- **Evidence:** among the five reels most similar to the upload that have the value (for
  something it lacks, the better value), the two that show the pattern most clearly —
  strongest for an effect above 1, weakest below. The creator's reels for their own cards,
  tracked creators' reels for similar-creators cards.
- **Frames:** items about the hook, opening or payoff link to the linked draft's first
  storyboard frame; the ending and call to action to its last. Without a storyboard the
  moment is named instead ("Opening · 0:00", "Ending · 0:41").

### D86 · Edits — settled
T15 proposes edits for the holding-back items that name a better value (for any audience, up
to eight). From each proposal CURO keeps only the taxonomy feature values the upload doesn't
already have; a proposal left with none is dropped. Each edit is re-scored with T9 steps 3–5
on the same neighbours, and only edits that raise some audience's score are stored, with the
gain for each audience. Shown: the best three for the audience by gain ÷ effort (edit only =
1, needs a reshoot = 2), labelled "+6 est.". An edit's words carrying a number its facts don't
contain fall back to a template.

### D87 · "Edit & re-run" — settled (deviation from the prototype)
The prototype re-scores straight after "Edit & re-run". The logic doc: the accepted edits
are written back to the Studio project, and "once the creator uploads the edited video, the
Simulator runs again and shows the new score next to the old one". CURO follows the logic
doc:
1. Applying writes each edit to the linked draft as a `simulator_edit` script version: hook,
   opening and payoff edits rewrite the hook; ending and call-to-action edits change the
   ending; a length edit trims or extends. Frames whose lines changed are then redrawn, and
   storyboard-only edits (pacing, on-screen labels) change the storyboard.
2. The result then asks for the re-recorded take ("Re-record with the edits, then re-run").
3. The re-run is a new simulation linked to the one before; the score shows "+N since last
   run" for the audience on screen.

Re-running with the same file is refused, since it would give the same estimate. Without a
linked draft, applying only marks the edit. The app applies edits one at a time, each as a
job, because each is a new version of the draft.

### D88 · Uploads — settled
- **Signing:** `POST /v1/uploads/sign` gives a signed URL. Local storage signs a token
  (HMAC-SHA256 under the API's JWT secret, one path, 15 minutes), and the app PUTs to
  `/v1/uploads/local/{token}` on the API. Supabase's signed upload URL replaces it
  (INTEGRATION.md).
- **Where:** uploads go to `uploads/{creator id}/` in the videos bucket.
- **Checks:** `POST /v1/simulations` reads the file's headers. It must be an MP4 or MOV
  (ISO base media `ftyp`), at most 90 seconds long (from `mvhd`), and under the creator's
  own prefix. A MOV without an `ftyp` box (old QuickTime exports) is refused with "export it
  again as MP4". The app also checks the picker's length before uploading.
- **Retention:** keeping uploads for 90 days (MVP doc risks table) needs a cleanup job; it
  isn't built yet.

### D89 · Sample takes in the demo — settled
The mock video provider offers two sample recordings of the demo's Ganpati reel: a first
take (payoff at 3.8 s, a comment prompt, 41 s), and a re-recorded take with the final look
first and a send-to-a-friend prompt (32 s). A real provider offers none, so the app shows no
sample buttons. A sample is a real MP4 container (headers only) carrying the marker that
names its fixture understanding. It is stored like any upload and runs through the same
pipeline and estimate. No business logic checks MOCK_MODE.

### D90 · The caption a simulation reads — settled
The caption the reel will be posted with: one given with the upload (the app sends a
sample's own caption), else the linked draft's chosen caption and hashtags, else none.

### D91 · Best time, accuracy, comparison and Trend DNA — settled
- **Best time:** the next 48 hours' 3-hour windows (6 AM to midnight, creator's timezone).
  Each is valued by the median views lift of the creator's reels posted on that weekday and
  window (at least 2), else that window on any day (at least 3). Windows where tracked
  creators posted at least 1.5× their average are avoided; with too little history, none is
  suggested. The logic doc's "how fast they grew in their first 6 hours" waits for more reels
  tracked from the start.
- **Accuracy:** "no record yet" until posted simulations are matched to their reels
  (`match_posted_reel` and the in-range check come with the learning loop).
- **Comparison with the draft:** transcript sentences against script beats by word overlap.
  A beat is missing below 50% overlap for the hook, 40% for the others. The comparison flags
  skipped lines, a changed hook, a missing call to action, a length difference of 5 seconds
  or more, and dropped lines that carried a note.
- **Trend DNA:**
  - Topic: the linked opportunity, else the nearest sub-cluster.
  - Momentum, audience fit, creator fit and peer performance: from the idea scorer's parts
    (D69).
  - Similar recent reels: how many tracked creators' reels from the last 35 days are similar
    (saturation).
  - Originality: 1 − the highest similarity to a tracked creator's reel from those 35 days.
    "Low" at 0.9+ similarity (a near-copy), "Medium" at 0.75+, else "High"; the closest reel
    is named.

### D92 · Ask Curo on the result before Phase 8 — superseded by D95–D105
In Phase 7 the Simulator's chat answered from the result's own facts in the app. Phase 8
replaced it with Ask Curo (`POST /v1/chat`), as on every other chat box.

### D93 · No persona fit — settled (MVP doc)
The MVP doc hides Simulator persona fit ("Out … When enough commenters per creator exist").

### D94 · The intro's numbers — settled (copy change)
The prototype's intro says "your last 48 reels … 1,240 similar posts from the past 30 days".
Those were mock numbers, so the intro now says what's compared without numbers. The result's
notes say how many of the compared reels are the creator's own, and the loading step reads
"Comparing with your past reels".

---

## Ask Curo and memory (Phase 8)

### D95 · Intent routing is code — settled
Logic doc §14: "A small classifier first decides what the creator wants … It then picks the
tool." The classifier (`services/assistant/intent.py`) is code: keywords, question forms and
the screen. It sorts each message into one of these:
- **explain:** a question about the creator's records.
- **change:** an instruction ("make the hook punchier").
- **what_if:** a hypothetical to re-score.
- **remember** / **forget:** a stated preference, or removing one.
- **hidden:** a question about saves, reach and the like.
- **unclear:** too little to go on.

Code is fast and free, and its rules are tested. The intent decides which tools the model may
use; the model picks among them.
- "Unclear" gets one short question back.
- "Hidden" gets the plain "not public" reply.

Neither calls a model.

### D96 · A change on a Studio screen goes to that step — settled (interpretation)
Every chat box sends to `POST /v1/chat`. On a Studio step, a change request comes back as
`handoff: "studio"`, and the app applies it with that step's own revision:
- T13 routing and the step's job
- the step's own reply, busy state and "Changed" markers

This keeps each step's screen state in one place. Questions, what-ifs and preferences typed
in the same box are answered by Ask Curo in a thread under the step. On the Simulator, Ask
Curo makes script and storyboard changes itself, with the `rewrite_script` and
`update_frame` tools (a job the app follows).

### D97 · The tools — settled
These are the logic doc's tools, on the creator's own records:
- `search_reels`, `get_reel`, `get_pattern_cards`, `get_opportunity`, `score_idea`
- `rewrite_script`, `update_frame`, `run_simulation`, `compare_to_draft`

Four more were added:
- `get_draft`: what the open draft says, line by line, with each line's job and note.
- `get_simulation`: the open estimate, by section.
- `remember` and `forget`: creator memory.

Every tool reads through the creator's RLS session, so another creator's id reads as missing.
Each returns `facts`, plain sentences carrying every number a reply may state, and `sources`,
the records behind them. Heavy reads that the Studio and Simulator jobs already do (the idea
scorer, the estimate) are called as those jobs call them, for a creator and records the
session has already checked.

### D98 · The no-new-numbers check, streamed — settled
The reply streams sentence by sentence, and each sentence is checked before it is sent:
- **Allowed numbers:** only those found in the tools' facts, the creator's own message or
  their memory. Any other number stops it.
- **Second attempt:** CURO asks the model once more, naming the problem (`retry_note`), and
  tells the app to clear what it showed (`reset`).
- **Fallback:** if that fails too, the reply is the tools' own facts (the template).

Every hold-back is logged (`events: chat_check_failed`), and the stored reply records how it
was checked (`model`, `model_retry` or `template`). Streaming whole checked sentences, rather
than every word, is the price of never showing an unchecked number.

### D99 · What isn't public — settled
- **Questions:** asked about saves, reach, impressions, watch time or demographics, Curo says
  they aren't public, without a model.
- **Replies:** a reply sentence that claims something about them is held back like a planted
  number.
- **Not caught:** quoted text (a caption) and the call-to-action "save prompt" aren't claims,
  so they aren't caught.

### D100 · Citations — settled
A reply cites the records its tools returned in that turn (up to five): reels, pattern
cards, the opportunity, the idea, the draft, the simulation, a memory. The app shows them as
chips under the reply ("Your reel · One kurta, five dupattas").

### D101 · Project memory — settled
Messages are stored with their context (screen, project, simulation). The model sees the last
eight messages about the same simulation, else the same draft, else the same screen that day.
In the app:
- each screen has its own thread (a Studio step of a draft, or a simulation)
- a simulation's thread is reloaded when its result opens (`GET /v1/chat`)

### D102 · Creator memory — settled
- **Stated:** "never suggest dance trends", "remember I film on weekends", and the like.
- **Avoid preferences:** an "avoid" preference is enforced in code. New idea candidates that
  name the avoided words are dropped, and T6 is told them (`T6Input.avoid`).
- **Learned: shorter scripts.** When at least half of the creator's last six script changes,
  and at least three, were "shorten", new scripts are planned 15% shorter (not below the
  band). Curo's reply says so.
- **Other notes:** they go to Ask Curo as context only.
- **Settings:** shows each memory as "You said" or "Learned", with Delete. A deleted learned
  preference is recorded (`creators.memory_dismissed`) and isn't learned again.

### D103 · Streaming transport — settled
`POST /v1/chat` answers with server-sent events (MVP doc: "Chat and text generation stream
their reply as server-sent events"). React Native's `fetch` can't read a response as it
arrives, so the app uses `XMLHttpRequest`, whose text grows as events arrive, on the phone
and the web. The events are `meta`, `tool`, `job`, `delta`, `reset`, `done` and `error`
(routes/chat.py).

### D104 · What-ifs re-score the recording — settled
`run_simulation` re-runs T9 steps 3–5 with changed DNA features, using the inputs each
simulation now keeps: features, embedding, transcript and timing (`simulations.inputs`,
migration 0012). It reports the score change for each audience. A simulation from before
Phase 8 has no inputs, and Curo says to run it again.

### D105 · Hints — settled
The Simulator's hint line names the biggest item holding the recording back (logic doc §14),
for the audience on screen. The Studio steps keep the prototype's fixed hints.

---

## Hardening and integration readiness (Phase 9)

### D106 · Deleting an account — settled
`DELETE /v1/me` (MVP doc §7; logic doc §17: "Delete a creator's data on request, and offer that
in settings").
- **What goes:** the sign-in and every record keyed to the creator (projects, ideas, scripts,
  storyboards, captions, simulations, chat, memory, opportunities, tracked creators, jobs,
  events); their uploads and the stored videos and covers of their reels; everything collected
  from their own public account (reels, snapshots, comments, DNA, embeddings, baselines,
  sub-clusters, pattern cards, comment themes). Files go first, so a run that stops part-way
  still finds the rows to go by.
- **What stays:** the username, marked `opted_out`, so CURO doesn't collect it again, not even
  as another creator's tracked creator ("Curo can't track @…"). It is a suppression list, not
  data about the person. Onboarding the handle again (its owner signing up) brings it back.
  One anonymous `account_deleted` event records that a deletion happened.
- **How:** the request is marked (`creators.deletion_requested_at`) and the `cleanup` job
  carries it out straight away on the priority queue; the daily `cleanup` run finishes any
  that stopped. The app signs out at once. An account that never onboarded loses its sign-in
  in the request itself.
- **In the app:** Settings → "Delete account" says what goes and that it can't be undone; only
  the second tap ("Delete my account") deletes.

### D107 · The daily cleanup — settled
MVP doc §9 `cleanup`, every night with the other nightly jobs:
- carries out pending deletion requests (D106);
- deletes Simulator uploads after 90 days (MVP doc risks table: "keep creators' uploads for 90
  days"). The simulation keeps its estimate and result; only the video goes;
- deletes uploads that were never simulated, a day after upload. Files carry real timestamps,
  so this age is real time, not CURO's clock;
- deletes tracked creators' videos left behind by a `process_reel` run that stopped before it
  could (D45);
- expires opportunities whose dated window has passed (the nightly build also does).

### D108 · Matching a posted reel to its simulation — settled (endpoints added)
Logic doc §15 step 2: "When a new reel appears, CURO links it to the project using its audio
fingerprint, caption similarity and timing, and asks the creator to confirm the match."
- **When:** `match_posted_reel` runs for every new reel a creator snapshot finds.
- **Candidates:** the creator's finished simulations from the 14 days before the post, and
  drafts from those days that were never simulated, none already matched.
- **Score:** public data has no audio fingerprint, so the match rests on caption similarity
  (0.5; the reel's caption against the simulation's caption or the draft's chosen one),
  length (0.3; within 1.5 s = 1, within 4 s = 0.5) and timing (0.2; full within 3 days,
  falling to 0 at 14). The best candidate at 0.6 or more is suggested, with its reasons.
- **Confirming:** the MVP doc's endpoint list has nothing for "asks the creator to confirm",
  so three routes were added: `GET /v1/matches` (pending), `POST /v1/matches/{id}/confirm`,
  `POST /v1/matches/{id}/reject`, stored in `reel_matches` (migration 0013; a 28th table).
  Home shows the newest pending match as a card above the carousel ("Is “…” the reel you
  simulated?"). Confirmed: `simulations.posted_reel_id` is set, so Home's arrows compare the
  reel with its simulation (logic doc §6) and the accuracy record counts it; a matched draft
  is marked posted.
- **In the demo:** simulate the first sample take, then move the clock forward a day and a
  half (`./dev.ps1 local-time advance 36h`, or `make time ARGS="advance 36h"`): the Ganpati
  reel posted after the anchor comes back as a match. The re-recorded take is shorter than the
  posted reel, so on its own it stays below the bar, which is the honest outcome.

### D109 · The accuracy record and wider ranges — settled
`accuracy_report` runs weekly (Monday 2 AM, creator's timezone). For each confirmed reel at
least seven days old, its counts at day 7 are read from the snapshots and compared with the
stored ranges. A reel is in range when every count CURO could see fell inside its range; a
hidden count is unknown, not a miss. The record is the last ten checked reels ("Curo's range
contained the result for 8 of your last 10 simulated reels"). With at least five on record
and fewer than 70% in range, new estimates' ranges are made 25% wider in log terms (logic doc
§13: "If accuracy drops, the ranges are widened automatically"). The personal correction from
past errors (logic doc §13 "How it becomes personal") waits for the trained model.

### D110 · Errors and product events — settled
- **Every route needs a session** except health, the sign-in stub, the signed upload URL (its
  token is the permission) and the vendor webhook (its own secret). A test calls every route
  in the OpenAPI document without one.
- **Unexpected errors** are reported through Monitoring with the route and method only (no
  request body, captions or comments) and answered with "Something went wrong on Curo's side.
  Try again in a moment."
- **Jobs:** a crashing job is reported with its type, id and attempt; a `JobFailed` (a plain
  reason for the creator, such as a private account) is not an error and isn't reported.
- **Product events** (`events.record`) are kept in `public.events` and sent to analytics
  through the same provider, with the creator's id only. The development provider logs errors
  and keeps the latest 500 events in memory.

### D111 · When the app can't reach Curo — settled
A request that gets no answer (no connection, or the API isn't running) reads "Curo couldn't be
reached. Check your connection." everywhere, instead of the browser's "Network request
failed"; a failed upload says the upload didn't finish. Home's opportunity areas show their own
error and retry on pull-to-refresh, like the carousel.

### D112 · Contract tests and the response recorder — settled
MVP doc §4 and §12: "record real API responses once and replay them in tests".
- **The seam:** each real provider module has pure parse functions from the vendor's raw answer
  to CURO's schema. `curo/providers/contracts.py` maps a recording's kind
  (`public_data/apify/reels`, `video/gemini`, `llm/claude/T3` …) to its parser and checks
  CURO's rules on top of the schema: hidden counts are None, vectors are 768 long and
  normalised, one vector per text.
- **Parsers written now:** Claude's (Messages API) and Gemini's (generateContent and
  embeddings), whose formats are documented and don't depend on a choice still to make. The
  provider calls themselves stay stubs. Apify's and Bright Data's parsers depend on the actors
  and datasets picked when the keys arrive (MVP doc §5: "test two or three actors"), so they
  stay stubs with the mapping rules written down.
- **The recorder** (`tools/record_contracts.py`) calls the real services with the keys in
  `.env` and writes recordings into `api/tests/contracts/`; `tests/test_contracts.py` replays
  every one (skipped while there are none). Every handle other than the test account's is
  replaced with a placeholder, and @mentions are masked, before a file is written.
- **Inputs for Claude:** `CAPTURE_TASK_INPUTS=<folder>` makes every AI task save its first five
  inputs, so a run of the demo yields real inputs for every task to send to the real model.

### D113 · Claude answers through structured outputs, not forced tool use — settled (deviation)
MVP doc §5: "Define a JSON schema for every task and have Claude return it through tool use".
`claude-sonnet-5-5`, the main model in `.env.example`, answers a forced `tool_choice`
("tool" or "any") with a 400. The structured-output feature does the same job: the request
carries the task's output schema (`client.messages.parse(output_format=<task output model>)`)
and the answer is JSON matching it. The backend still never parses free text. Ask Curo (T14)
keeps tool use, with the model choosing among the tools the intent allows (`tool_choice` auto).
The Claude provider's TODO list, the recorder and INTEGRATION.md follow this.

### D114 · Which Haiku — settled by D207 (claude-haiku-5-5)
`.env.example` keeps the MVP doc's `CLAUDE_MODEL_FAST=claude-haiku-4-5-20251001`. Claude Haiku
5.5 (`claude-haiku-5-5`) is now the current Haiku and costs a tenth as much per token ($0.10 /
$0.50 per million tokens for prompts up to 100K tokens, against $1 / $5). It thinks by default
(effort "medium"), so labelling tasks should set effort "low". Changing the model is one line
in `.env`; record T2/T3/T4/T8/T13 answers with both and compare before choosing.

### D115 · Running without Docker — settled (local infrastructure)
D1 runs Postgres and Redis in Docker. On a computer without Docker, `tools/local_stack.py`
(`./dev.ps1 local`, `make local`) runs the same code in one process:
- Postgres + pgvector embedded through pgserver (already the test suite's fallback, D6), its
  data in `.data/pgserver-dev`;
- a Redis stand-in (fakeredis over TCP on port 6390) for the clock, heartbeats and time travel;
- the worker as a background thread (`QUEUE_MODE=thread`: one thread, Studio and Simulator
  jobs first). RQ's worker forks, which Windows can't do. Jobs left queued when the API
  stopped are handed over again by the scheduler, as in Docker;
- the scheduler loop, and uvicorn on 0.0.0.0 so a phone on the same Wi-Fi reaches it.

`./dev.ps1 local --seed` loads the demo first; `local-seed` reloads it while the API runs;
`local-time` moves the clock. Business logic doesn't know where it runs; Docker stays the
setup that matches production.

### D116 · Privacy page and legal review — open
MVP doc Phase 9 lists a privacy page and a legal review; neither is code. What the page has
to say is what the code does: the collection rules (MVP doc §4: public, logged-out data
only; no Instagram login), what is stored (D32: comment text without commenter handles), how
long uploads are kept (D107), how peers' videos are deleted after analysis (D45), and how a
creator deletes everything (D106). The sign-in screen already says Curo never asks for an
Instagram login. The page needs a hosted URL before store submission (MVP doc §3), and the
legal review is a person's job before launch.

---

## CURO v2: the web app (CURO_WebApp_ClaudeCode_Prompt.md, PLAN_V2.md)

### D200 · Vercel deployment deferred: the queue stays RQ for now — settled (deviation)
The v2 prompt asks for the Vercel shape: a Postgres job queue, a worker endpoint, resumable
steps and `vercel.json`. The creator asked to leave Vercel for later ("just build the repo
and publish on my github ... just make it a web app"). So the backend keeps v1's queue (RQ,
or `QUEUE_MODE=thread` without Docker) and its scheduler process. Two pieces that Vercel will
need are in already: `POST /v1/cron/tick` (the scheduler as an endpoint, guarded by
`CRON_SECRET`) and the web app's `/api/v1/*` calls (one domain, the API behind `/api`).
`REDIS_URL` therefore stays in `.env.example`. PLAN_V2 §1–3 hold the Vercel design.

### D201 · Peers removed everywhere — settled
Opportunity score `10 × (0.35 F + 0.25 D + 0.25 T + 0.15 O)`; idea score
`0.40 H + 0.30 A + 0.20 T + 0.10 N`. The "Competitor" source, peer evidence (P), peer
suggestions, `/v1/peers*`, the `peers` table and the peer visibility policy are gone
(migration 0014). Openness now reads the trend card's saturation (low 0.9, medium 0.6, high
0.3) or the reels posted on the topic's hashtags in the last 7 days; 0.7 when nothing
measures it. The Adapted idea slot is "a trending angle, made yours": it qualifies when the
idea cites or sits close to a trend card of the creator's niche (or its trend part ≥ 0.6).
Hashtag candidates: the creator's own tags with their results, the niche's trend-feed tags
and T12's suggestions. The Simulator's neighbours, originality and best time read the
creator's own reels only. Pattern-card priors pool all creators' own reels and are labelled
"based on creators like you". The storyboard's "proven devices" come from the creator's
pattern cards (own or priors), no longer from peer outliers.

### D202 · The shared trend feed — settled
`niches` (10, seeded) and `trend_cards`, readable by every signed-in creator. `trend_feed`
runs nightly per niche (never per creator): festivals within 30 days, hashtags whose daily
posting grew ≥ 1.2× week on week, and tags that keep co-occurring (formats); at most six
cards, each named by T16 with the number check. "Trending for you" (`GET /v1/trends`) ranks
the niche's cards for the creator: 0.6 × fit (closest of their sub-clusters) + 0.4 ×
momentum, four shown. Home is Opportunity areas then Trending for you; tapping an angle
starts a Studio project from it.

### D203 · Insights page and Home carousel removed from the app API — settled
`GET /v1/reels` and `GET /v1/reels/{id}/insights` are gone; `POST /v1/reels/refresh` stays
(pull to refresh). `services/insights.py` stays: Ask Curo's tools and the tests read the same
per-reel facts.

### D204 · Collection on a budget — settled (deviation: 18 snapshots, not 16)
Snapshots at fixed ages: every 6 h to 48 h, daily to day 7, weekly to day 30, and a last one
at day 30 — 0, 6 … 48 h, 3–7 days, 14, 21, 28 and 30 days: 18 per reel (the plan said 16;
the extra two are 48 h and day 30, which the baselines' 7-day and 30-day buckets need to be
measured rather than stretched). Fixed ages, not fixed gaps, so a reel first seen at 2 h still
lands on 6 h, 12 h … 168 h. New-reel discovery every 12 h, the latest 3 reels, on its own
clock (`accounts.last_discovered_at`, so snapshot runs don't postpone it). Comments: the first
read takes up to `COMMENT_LIMIT` (100); re-reads only at about 24 h and 7 days and only
newer comments (`reels.comment_reads`). A creator away `INACTIVE_PAUSE_DAYS` (14) is paused —
no collection, no nightly jobs — and resumed with one catch-up run when they next open the
app (`creators.last_seen_at`, `paused_at`).

### D205 · Simulator v2: the AI audience — settled
T17 segments the audience (4–8 segments from comment themes, language mix and follower
count; never handles), T18 writes `SIM_AGENTS` (1,000) personas across them, once per creator
a month (`audience_segments`, `audience_personas`). Calibration per persona version: 200 agents
watch 5 of the creator's past reels (their stored T1 understanding); `k_m` is the geometric
mean of real ÷ agent rates, the range p10–p90 (`persona_calibrations`). A run: T19 in batches
of 100 (the timeline is the cached prefix), T20 thread round on the top 10 comments, then
predicted counts (7-day usual views × calibrated rate), the skip curve, and the engagement
score — the share of the creator's past reels whose real `like + 3·comment + 4·share` rate
it beats (null with fewer than 5). Saves use the likes factor and are labelled "simulated"
everywhere. T21 explains (3 working / 3 holding / 3 edits, with timestamps) from tagged facts
with the number check; T22 is "talk to an agent", 10 messages per simulation, 402 after.
Every agent text is shown as "Agent 12 · Festive planner" with no avatar, under "Simulated by
CURO's AI audience. Not real comments."

### D206 · Simulator v2 keeps T9 and the v1 edits underneath — settled (deviation)
PLAN_V2 said T21's edits replace T15's. T15's edits are kept: they are re-scored, linked to
storyboard frames and written back to the Studio draft — the engine the "Apply to my draft"
button runs on. T21's edits are the explanation; T15's are the actions. T9's estimate and
per-audience scores stay in the result for Ask Curo's "what if" and comparisons; the web app
leads with the engagement score.

### D207 · Model tiers — settled
A fourth tier, "agents" (`CLAUDE_MODEL_AGENTS`, default `claude-haiku-5-5`), for T19 and T20.
`CLAUDE_MODEL_FAST` is now `claude-haiku-5-5` too (D114 closed). `GEMINI_VIDEO_MODEL` defaults
to `gemini-3.6-flash`; `GEMINI_EMBEDDING_MODEL` to `gemini-embedding-2` at 768 dimensions.
Never mix vectors from two models (or mock and real) in one table: `tools/reembed.py`
re-embeds everything when the model changes.

### D208 · Plans, credits and usage — settled
`plans`, `subscriptions`, an append-only `credit_ledger` (a trigger refuses updates) and
`usage_ledger` (migration 0016). Amounts come from settings (`FREE_*`, `PRO_*`), so they change
without a migration. Each period grants the plan's credits, expiring at its end; top-ups never
expire; a spend draws on the plan first and records which pool, so balances are exact; a spend
is recorded once per thing (`ref_id`), so retries never double-charge. Spend points: creating
a project, starting a simulation (or re-run), each Ask Curo message. Revisions (new ideas,
script / storyboard / caption revisions): up to `PROJECT_REVISIONS` per project
(`projects.revisions`). Out of credits answers 402 `{code: "out_of_credits", resource, plan}`;
Ask Curo says it in the stream. Every model call records an estimated cost (tokens ≈ chars ÷
4, list prices; the mocks are priced as the models they stand in for) for `/admin/costs`,
which only `ADMIN_EMAILS` or `creators.is_admin` can open. Payments go through a
`PaymentProvider`: the mock completes at once; Razorpay is a stub (INTEGRATION.md).

### D209 · The web app — settled
Next.js (App Router) in `/web`, the Expo app moved untouched to `/legacy/app`. One client
shell (header, white sheet, Composer, springy Nav) with Home, Studio and Simulator, plus
`/login`, `/onboarding`, `/settings` and `/admin/costs`. Same six colours, no gradients,
Figtree 300/400/600; mobile first, a centred 480 px column on the grey background on wide
screens. Types come only from the generated OpenAPI schema (`npm run gen:api`). Sign-in is an
email code: supabase-js when `NEXT_PUBLIC_SUPABASE_URL`/`ANON_KEY` are set, otherwise the
backend's local stub (the code is shown on screen in development). Voice uses the browser's
Web Speech API. Next.js 16.4 and React 19.2 (the latest patched releases when built).

### D210 · Re-embedding — settled
`tools/reembed.py` re-embeds reels, sub-clusters and comment themes with the configured
embedding provider in batches, recording the model in each row, and refuses to run when the
configured dimension isn't 768.

## Schema additions (beyond the MVP doc's key columns; built in Phase 2, in `db/migrations/`)

| Column | Why |
| --- | --- |
| `creators.account_id` | Links a creator to their own row in `accounts` |
| `creators.formats`, `creators.languages` | Cold-start onboarding questions (logic doc §15) |
| `creators.accuracy` | The running accuracy record shown in the Simulator |
| `accounts.status` | active / private / deleted / opted_out (data-quality and deletion rules) |
| `accounts.last_collected_at` | Discovery cadence (D30) and "fresh enough" for pull-to-refresh |
| `reels.first_seen_at` | "Seen late" reels (D34) |
| `reels.video_url`, `thumb_url` | Vendor links, kept for the video pipeline (Phase 3) |
| `comments.tags_friend` | Share-intent signal without storing who was tagged (D32) |
| `hashtag_pages.post_count` | Hashtag size for the hashtag results |
| `festival_calendar.verified` | Lunar dates not yet checked against a panchang (D20) |
| `comments.theme_key` | T3's theme phrase, normalised (D46) — migration 0007 |
| `comment_themes.key` | A theme's stable identity across rebuilds (D46) |
| `pattern_cards.n_without`, `p_value`, `evidence` + unique (account, feature, value, metric) | The evidence shown on tap; stable card identity |
| `reels.mentions`, `is_deleted`, `likes_hidden`, `comments_disabled` | Fields the MVP doc collects; data-quality flags |
| `metric_snapshots.flag_reason` | Why a snapshot was flagged (e.g. lower than previous) |
| `comments.is_creator`, `language` | Top-comment filter; language mix for audience demand |
| `comment_themes.kind` | Request vs question |
| `hashtag_pages.reels` | Summary of the public reels on the page (needed for momentum and hashtag results) |
| `opportunities.topic_key`, `saved_score`, `description`, `why_it_fits` | Stable identity across nightly rebuilds; "score when saved vs today" on Saved |
| `projects.title` | Draft title on Saved |
| `ideas.round`, `ideas.prompt` | Each creator note produces a new round of three |
| `script_versions.changed_beat_ids`, `storyboard_versions.stale_frame_ids` | "Only the targeted beats change"; frames marked for update |
| `simulations.posted_reel_id`, `actual`, `in_range` | The learning loop and accuracy record |
| `jobs.creator_id`, `result`, `idempotency_key`, `attempts` | RLS on jobs; safe retries |
| `peers.suggestion_score`, `reasons` | Why a peer was suggested (D58) — migration 0008 |
| `opportunities.card`, `signals` | The assembled Home line and signal chips (D63) |
| `hashtag_pages.daily_counts` | CURO's own posting index (D61) |
| `ideas.hook_type`, `why`, `evidence` | H needs the hook type; the "why" line and chips as scored (D71) — migration 0010 |
| `script_versions.idea_id`, `captions.script_version` | A script belongs to its idea; captions to their script (D78) |
| `script_versions.reply`, `plan`; `storyboard_versions.reply`; `captions.reply` | Curo's reply to each instruction; how a script was planned (D73) |
| `simulations.caption`, `scores`, `job_id`, `error` | The caption read (D90); a score per audience (D84); the job that ran it; a plain failure reason — migration 0011 |
| `simulation_edits.gains`, `frame_label`, `applied_job_id` | The score change per audience (D86); where the edit lands; the Studio write-back job (D87) |
| `simulations.inputs` | What a simulation was run on, for what-ifs and comparisons (D104) — migration 0012 |
| `chat_messages.intent`, `sources`, `checked` | How a message was routed (D95), what the reply cites (D100), how its numbers were checked (D98) |
| `creators.memory_dismissed` | Learned preferences the creator deleted, not learned again (D102) |
| `creators.deletion_requested_at` | A deletion in progress, finished by the daily cleanup (D106) — migration 0013 |
| `reel_matches` (a 28th table) | Posted reels CURO thinks came from a simulation or draft, until the creator confirms (D108) — migration 0013 |
| `niches`, `trend_cards` | The shared trend feed (D202) — migration 0014 |
| `creators.last_seen_at`, `paused_at`; `accounts.last_discovered_at`; `reels.comment_reads` | Pausing, discovery on its own clock, capped comment re-reads (D204) — migration 0014 |
| `audience_segments`, `audience_personas`, `persona_calibrations`, `simulation_agents`, `agent_chats`; `simulations.timeline`, `engagement_score`, `persona_version` | The AI audience (D205) — migration 0015 |
| `plans`, `subscriptions`, `credit_ledger`, `usage_ledger`; `creators.is_admin`; `projects.revisions` | Plans, credits and costs (D208) — migration 0016 |
