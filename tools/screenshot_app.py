"""Screenshot the app (Expo web build) through the same journey as the prototype,
then write reference/compare.html with prototype and app screens side by side.

    make up && make seed                        # the API and the demo creator (dev-code sign-in)
    cd app && npx expo start --port 8081        # in another terminal
    python tools/screenshot_app.py [--url http://localhost:8081] [--email you@example.com]

The journey saves the first opportunity, so run `make seed` again before repeating it.

File names match tools/screenshot_prototype.py where the screens correspond, so the
comparison page can pair them. Uses the system's Microsoft Edge through Playwright.
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reference" / "app-screens"
PROTO = REPO / "reference" / "screens"
COMPARE = REPO / "reference" / "compare.html"
WIDTH, HEIGHT = 390, 844

# The main vertical scroller currently on screen: the tallest scrollable element that
# starts at the left edge and spans the phone width (pager pages sit off-screen).
FIND_SCROLLER = """() => [...document.querySelectorAll('div')].filter(el => {
  const s = getComputedStyle(el), r = el.getBoundingClientRect();
  return (s.overflowY === 'auto' || s.overflowY === 'scroll') && r.width > 300
    && Math.abs(r.left) < 5 && el.scrollHeight > el.clientHeight + 2;
}).sort((a, b) => b.scrollHeight - a.scrollHeight)[0]"""


class Shooter:
    def __init__(self, page: Page):
        self.page = page
        self.taken: list[str] = []

    def settle(self, ms: int = 700) -> None:
        self.page.wait_for_timeout(ms)

    def shot(self, name: str) -> None:
        self.page.screenshot(path=str(OUT / f"{name}.png"))
        self.taken.append(f"{name}.png")

    def _scroll(self, y: int) -> None:
        self.page.evaluate(
            f"(y) => {{ const s = ({FIND_SCROLLER})(); if (s) s.scrollTop = y; }}", y
        )

    def long_shot(self, name: str, step: int = 620) -> None:
        total, visible = self.page.evaluate(
            f"() => {{ const s = ({FIND_SCROLLER})(); "
            "return s ? [s.scrollHeight, s.clientHeight] : [0, 0]; }"
        )
        offsets = [0]
        while total and offsets[-1] + visible < total:
            offsets.append(min(offsets[-1] + step, total - visible))
        for i, y in enumerate(offsets):
            self._scroll(y)
            self.settle(350)
            self.shot(name + ("" if len(offsets) == 1 else "_" + "abcdefghijklmnop"[i]))
        self._scroll(0)
        self.settle(200)

    def click(
        self,
        *,
        role: str = "button",
        name: str | None = None,
        text: str | None = None,
        exact: bool = True,
        nth: int = 0,
        wait: int = 700,
    ) -> None:
        if text is not None:
            target = self.page.get_by_text(text, exact=exact).nth(nth)
        else:
            target = self.page.get_by_role(role, name=name, exact=exact).nth(nth)
        target.scroll_into_view_if_needed()
        target.click()
        self.settle(wait)

    def wait_text(self, text: str | re.Pattern, timeout: int = 60_000) -> None:
        """Wait for something the API sent to appear (Studio steps run as jobs)."""
        self.page.get_by_text(text).first.wait_for(timeout=timeout)
        self.settle(600)

    def click_test(self, test_id: str, wait: int = 700) -> None:
        target = self.page.get_by_test_id(test_id)
        target.scroll_into_view_if_needed()
        target.click()
        self.settle(wait)

    def type_and_send(self, message: str, wait: int = 1600) -> None:
        box = self.page.get_by_label("Message Curo")
        box.fill(message)
        box.press("Enter")
        self.settle(wait)


def sign_in(s: Shooter, email: str, handle: str) -> None:
    """Sign in with the development code, and onboard the handle if this email is new."""
    page = s.page
    page.get_by_label("Email").wait_for(timeout=180_000)
    s.settle(800)
    s.shot("00_login")
    page.get_by_label("Email").fill(email)
    s.click(name="Send code", wait=900)
    s.shot("00_login_code")
    s.click(name="Sign in", wait=300)
    username = page.get_by_label("Instagram username")
    username.or_(page.get_by_text("Previous content")).first.wait_for(timeout=60_000)
    if username.count():
        s.settle(500)
        s.shot("00_onboarding")
        username.fill(handle)
        s.click(name="Continue", wait=350)
        s.shot("00_onboarding_progress")
        # Last step: confirm the suggested creators to track (logic doc §3 step 5).
        track = page.get_by_role("button", name=re.compile(r"^Track \d+ creators?$"))
        track.wait_for(timeout=180_000)
        s.settle(800)
        s.long_shot("00_onboarding_peers")
        track.click()
    page.get_by_text("Previous content").wait_for(timeout=120_000)
    s.settle(1500)


def run(page: Page, email: str, handle: str) -> list[str]:
    """One straight journey, like tools/screenshot_prototype.py."""
    s = Shooter(page)
    sign_in(s, email, handle)

    # --- Home -----------------------------------------------------------------
    s.long_shot("01_home")
    for i in range(2, 6):
        s.click(name=f"Show reel {i}")
        s.shot(f"01_home_reel{i}")
    s.click(name="Show reel 1")

    # --- Settings (profile button) ------------------------------------------------
    s.click(name="Account and settings", wait=900)
    s.shot("15_settings")
    s.click(name="Back", wait=900)

    # --- Insights ---------------------------------------------------------------
    s.click(name="View insights")
    s.long_shot("02_insights_reel1")
    for i in range(2, 5):
        s.click(name=f"Show reel {i}")
        s.long_shot(f"02_insights_reel{i}")
    s.click(name="Back")

    # --- Opportunity pages --------------------------------------------------------
    s.click(name="Explore more")
    s.long_shot("03_opportunity_1")
    for i in range(2, 6):
        s.click(name=f"Opportunity {i}", wait=900)
        s.long_shot(f"03_opportunity_{i}")
    s.click(name="Opportunity 1", wait=900)
    s.click(name="Save for later", wait=500)
    s.shot("03_opportunity_saved_toast")

    # --- Saved -------------------------------------------------------------------
    s.click(name="Back", wait=3200)
    s.click(name="Saved opportunities and drafts")
    s.long_shot("04_saved")
    s.click(name="Back")

    # --- Studio: validate chat ------------------------------------------------------
    s.click(role="tab", name="Studio")
    s.shot("05_studio_empty")
    s.type_and_send("A festive outfit reel I can shoot at home this weekend", wait=300)
    s.wait_text(re.compile("Tweaks that would raise it|Idea score"))
    s.long_shot("05_studio_validate")

    # --- Studio: from an opportunity (each step runs on the API) -----------------------
    s.click(role="tab", name="Home")
    s.click(name="Explore more")
    s.click(name="Open in Studio", nth=0, wait=300)
    s.wait_text("Curo suggests")
    s.long_shot("06_studio_1_ideas")
    s.click_test("idea-0-0")
    s.click(text="Why this idea?", nth=0)
    s.long_shot("06_studio_1_idea_picked")
    s.type_and_send("Something quick I can shoot at home with what I already own", wait=300)
    s.wait_text("Three new directions from your note")
    s.long_shot("06_studio_1_ideas_own_note")
    s.click_test("idea-0-0")
    s.click(name="Develop this idea", wait=300)
    s.wait_text("Generate Script")
    s.shot("07_studio_2_before_script")
    s.click(name="Generate Script", wait=150)
    s.shot("07_studio_2_script_loading")
    s.wait_text(re.compile("Highlighted notes show"))
    s.long_shot("07_studio_2_script")
    if s.page.get_by_text("Why?", exact=True).count():
        s.click(text="Why?", nth=0)
        s.shot("07_studio_2_script_why_open")
    s.type_and_send("Can you make the hook punchier", wait=300)
    s.wait_text("Rewrote the hook. The rest of the script is unchanged.")
    s.long_shot("07_studio_2_script_revised")
    # Ask Curo: a question is answered from the draft, with its source (logic doc §14).
    s.type_and_send("Why is the first line there?", wait=300)
    s.wait_text(re.compile(r"^Line 1 of"))
    s.long_shot("07_studio_2_ask_curo")

    s.click(name="Proceed to visuals", wait=150)
    s.shot("08_studio_3_storyboard_loading")
    s.wait_text("How to record")
    s.long_shot("08_studio_3_storyboard")
    s.click(name="Go to frame 3")
    s.shot("08_studio_3_storyboard_frame3")
    s.type_and_send("Make this shot easier to record on my own", wait=300)
    s.wait_text(re.compile("Made it easier to record|as simple as it gets"))
    s.long_shot("08_studio_3_storyboard_easier")

    s.click(name="Proceed to caption & hashtags", wait=300)
    s.wait_text(re.compile(r"\d of 5 picked"))
    s.long_shot("09_studio_4_caption")
    unpicked = s.page.locator('[aria-label^="#"][aria-selected="false"]').first
    unpicked.scroll_into_view_if_needed()
    unpicked.click()
    s.settle(500)
    s.shot("09_studio_4_sixth_hashtag_blocked")
    s.settle(2600)

    s.click(name="Continue to final draft")
    s.long_shot("10_studio_5_final")
    s.click(name="Save draft", wait=300)
    s.wait_text("Draft saved. Find it under Saved at the top.")
    s.shot("10_studio_5_draft_saved_toast")
    s.settle(2600)
    s.click(name="Saved opportunities and drafts")
    s.long_shot("04_saved_with_draft")
    s.click(name="Back")

    # --- Simulator -----------------------------------------------------------------
    # The demo's sample takes stand in for a recording (the mock video provider offers them);
    # the first is linked to the Studio draft above.
    s.click(role="tab", name="Simulator")
    s.long_shot("11_sim_1_intro")
    s.click(name="Use the sample: First take", wait=300)
    s.shot("11_sim_1_uploading")
    s.wait_text(re.compile(r"· ready$"))
    s.long_shot("11_sim_1_uploaded")
    s.click(name="Run simulation", wait=500)
    s.shot("12_sim_2_running")
    s.wait_text("Predicted report", timeout=180_000)
    s.long_shot("13_sim_3_result")
    s.click(name="See evidence", nth=0)
    s.shot("13_sim_3_evidence_open")
    for label in ("Production", "Trend"):
        s.click(role="tab", name=label)
    s.long_shot("13_sim_3_dna_trend")
    edits = s.page.get_by_role("checkbox")
    picked = 0
    for i in range(edits.count()):
        edits.nth(i).scroll_into_view_if_needed()
        edits.nth(i).click()
        picked += 1
        s.settle(300)
    s.long_shot("13_sim_3_edits_selected")
    s.click(name=f"Edit & re-run ({picked})", wait=300)
    s.wait_text("Re-record with the edits, then re-run", timeout=120_000)
    s.long_shot("13_sim_3_edits_applied")
    s.click(name="Use the sample: Re-recorded with the edits", wait=500)
    s.wait_text(re.compile(r"since last run$"), timeout=180_000)
    s.long_shot("14_sim_4_rerun_result")
    s.type_and_send("Will people share it?", wait=300)
    s.wait_text(re.compile(r"^Shares per view"))
    s.type_and_send("What if I cut faster?", wait=300)
    s.wait_text(re.compile(r"moves from|stays at"))
    s.type_and_send("Never suggest dance trends", wait=300)
    s.wait_text(re.compile(r"I’ll remember"))
    s.long_shot("14_sim_4_ask_curo")
    for name in ("Followers", "New audiences"):
        s.click(role="radio", name=name)
        s.shot(f"14_sim_4_audience_{name.lower().replace(' ', '_')}")
    # The draft now carries the edits: the storyboard's opening frame was redrawn.
    s.click(role="tab", name="Studio")
    s.long_shot("14_sim_4_studio_after_edits")
    # Creator memory, visible and deletable in Settings.
    s.click(name="Account and settings", wait=900)
    s.wait_text("Never suggest dance trends")
    s.long_shot("15_settings_memory")
    return s.taken


def write_compare(taken: list[str]) -> None:
    rows = []
    for name in taken:
        proto = PROTO / name
        left = (
            f'<img src="screens/{html.escape(name)}">'
            if proto.exists()
            else '<div class="none">new in the app (no prototype screen)</div>'
        )
        rows.append(
            f'<section><h2>{html.escape(name[:-4])}</h2><div class="pair">'
            f"<figure>{left}<figcaption>Prototype</figcaption></figure>"
            f'<figure><img src="app-screens/{html.escape(name)}">'
            "<figcaption>App</figcaption></figure>"
            "</div></section>"
        )
    COMPARE.write_text(
        "<!doctype html><meta charset=utf-8><title>CURO · prototype vs app</title>"
        "<style>body{font:14px system-ui;margin:24px;background:#f5f4ef;color:#242424}"
        "h1{font-size:20px}h2{font-size:13px;color:#555;margin:28px 0 8px}"
        ".pair{display:flex;gap:16px}figure{margin:0}img{width:300px;border-radius:12px;"
        "box-shadow:0 1px 4px rgba(0,0,0,.15)}figcaption{font-size:12px;color:#777;margin-top:4px}"
        ".none{width:300px;height:120px;display:grid;place-items:center;border:1px dashed #bbb;"
        "border-radius:12px;color:#777}</style>"
        "<h1>CURO — prototype vs app</h1>" + "".join(rows),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8081")
    parser.add_argument("--browser", default="msedge")
    parser.add_argument(
        "--email",
        default="demo@curo.local",
        help="signs in with the dev code; the default is the seeded demo (opportunities need its "
        "tracked creators and a nightly build, so a new email shows none yet)",
    )
    parser.add_argument("--handle", default="curo.demo", help="onboarded if the email is new")
    args = parser.parse_args()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    with sync_playwright() as pw:
        channel = None if args.browser == "chromium" else args.browser
        browser = pw.chromium.launch(channel=channel)
        context = browser.new_context(
            viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=2
        )
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.goto(args.url, timeout=180_000)
        taken = run(page, args.email, args.handle)
        browser.close()

    write_compare(taken)
    print(f"{len(taken)} screenshots in {OUT}\ncomparison: {COMPARE}")
    if errors:
        print("page errors:", *errors[:20], sep="\n  ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
