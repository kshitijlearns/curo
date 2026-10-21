"""Screenshot every prototype screen into reference/screens/.

Opens the unpacked main screen (reference/prototype/pages/main-screen/bundle.html,
from tools/extract_prototype.py) at phone size and clicks through every screen
and state the prototype has. Long screens are captured in several scroll steps
(``…_a.png``, ``…_b.png``, …).

    python tools/screenshot_prototype.py [--browser msedge|chrome|chromium]

Uses Playwright with the system's Microsoft Edge by default (no browser download).
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

REPO = Path(__file__).resolve().parents[1]
PAGES = REPO / "reference" / "prototype" / "pages"
OUT = REPO / "reference" / "screens"
WIDTH, HEIGHT = 390, 844

# The white sheet that scrolls under the fixed header is the element with the -32px overlap.
FIND_SHEET = """() => [...document.querySelectorAll('div')].find(el =>
  getComputedStyle(el).marginTop === '-32px' && getComputedStyle(el).overflowY !== 'visible')"""


class Shooter:
    def __init__(self, page: Page):
        self.page = page
        self.taken: list[str] = []

    def settle(self, ms: int = 700) -> None:
        self.page.wait_for_timeout(ms)

    def shot(self, name: str) -> None:
        self.page.screenshot(path=str(OUT / f"{name}.png"))
        self.taken.append(f"{name}.png")

    def scroll_to(self, y: int) -> int:
        return self.page.evaluate(
            f"(y) => {{ const s = ({FIND_SHEET})(); if (!s) return 0;"
            " s.scrollTop = y; return s.scrollTop; }",
            y,
        )

    def long_shot(self, name: str, step: int = 620) -> None:
        """Capture the whole sheet, top to bottom, in overlapping steps."""
        heights = self.page.evaluate(
            f"() => {{ const s = ({FIND_SHEET})(); "
            "return s ? [s.scrollHeight, s.clientHeight] : [0, 0]; }"
        )
        total, visible = heights
        offsets = [0]
        while total and offsets[-1] + visible < total:
            offsets.append(min(offsets[-1] + step, total - visible))
        for i, y in enumerate(offsets):
            self.scroll_to(y)
            self.settle(350)
            suffix = "" if len(offsets) == 1 else "_" + "abcdefghijklmnop"[i]
            self.shot(f"{name}{suffix}")
        self.scroll_to(0)
        self.settle(200)

    def click(
        self,
        *,
        role: str = "button",
        name: str | None = None,
        text: str | None = None,
        exact: bool = False,
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

    def type_and_send(self, message: str, wait: int = 1600) -> None:
        box = self.page.get_by_label("Message Curo")
        box.fill(message)
        box.press("Enter")
        self.settle(wait)


def run(page: Page) -> list[str]:
    s = Shooter(page)

    # --- Home ---------------------------------------------------------------
    s.long_shot("01_home")
    for i in range(2, 5):
        s.click(name=f"Show reel {i}", exact=True)
        s.shot(f"01_home_reel{i}")
    s.click(name="Show reel 1", exact=True)

    # --- Insights (one per reel) -----------------------------------------------
    s.click(text="View insights", exact=True)
    s.long_shot("02_insights_reel1")
    for i in range(2, 5):
        s.click(name=f"Show reel {i}", exact=True)
        s.long_shot(f"02_insights_reel{i}")
    s.click(name="Back", exact=True)

    # --- Opportunity pages (swipe via dots) -----------------------------------
    s.click(text="Explore more", exact=True)
    s.long_shot("03_opportunity_1")
    for i in range(2, 6):
        s.click(name=f"Opportunity {i}", exact=True, wait=900)
        s.long_shot(f"03_opportunity_{i}")
    s.click(name="Opportunity 1", exact=True, wait=900)
    s.click(name="Save for later", exact=True, wait=500)
    s.shot("03_opportunity_saved_toast")

    # --- Saved -------------------------------------------------------------
    s.click(name="Back", exact=True, wait=3200)  # let the toast clear
    s.click(name="Saved opportunities and drafts", exact=True)
    s.long_shot("04_saved")
    s.click(name="Back", exact=True)

    # --- Studio: validate chat (empty) ------------------------------------------
    s.click(name="Studio", exact=True)
    s.shot("05_studio_empty")
    s.click(name="Speak instead of typing", exact=True, wait=500)
    s.shot("05_studio_composer_listening")
    s.settle(2000)  # the prototype fills a sample voice transcript
    s.shot("05_studio_composer_voice_text")

    # --- Studio: from an opportunity --------------------------------------------
    s.click(name="Home", exact=True)
    s.click(text="Explore more", exact=True)
    s.click(text="Open in Studio", exact=True, nth=0)
    s.long_shot("06_studio_1_ideas")
    s.click(text="Styling the same outfit 3 different ways for Ganpati.", exact=True)
    s.long_shot("06_studio_1_idea_picked")
    s.type_and_send("Something quick I can shoot at home with what I already own", wait=1500)
    s.long_shot("06_studio_1_ideas_own_note")
    s.click(text="Styling the same outfit 3 different ways for Ganpati.", exact=True)
    s.click(text="Develop this idea", exact=True)
    s.shot("07_studio_2_before_script")
    s.click(text="Generate Script", exact=True, wait=300)
    s.shot("07_studio_2_script_loading")
    s.settle(1400)
    s.long_shot("07_studio_2_script")
    s.click(text="Why?", exact=True, nth=0)
    s.shot("07_studio_2_script_why_open")
    s.type_and_send("Can you make the hook punchier", wait=1400)
    s.long_shot("07_studio_2_script_revised")

    s.click(text="Proceed to visuals", exact=True, wait=300)
    s.shot("08_studio_3_storyboard_loading")
    s.settle(1200)
    s.long_shot("08_studio_3_storyboard")
    s.click(name="Go to frame 3", exact=True)
    s.shot("08_studio_3_storyboard_frame3")
    s.type_and_send("Make this shot easier to record on my own", wait=1200)
    s.long_shot("08_studio_3_storyboard_easier")

    s.click(text="Proceed to caption & hashtags", exact=True)
    s.long_shot("09_studio_4_caption")
    s.click(text="#mumbaistyle", exact=False, wait=500)
    s.shot("09_studio_4_sixth_hashtag_blocked")
    s.settle(2600)

    s.click(text="Continue to final draft", exact=True)
    s.long_shot("10_studio_5_final")
    s.click(text="Save draft", exact=True, wait=500)
    s.shot("10_studio_5_draft_saved_toast")
    s.settle(2600)
    s.click(name="Saved opportunities and drafts", exact=True)
    s.long_shot("04_saved_with_draft")
    s.click(name="Back", exact=True)

    # --- Simulator ---------------------------------------------------------
    s.click(name="Simulator", exact=True)
    s.long_shot("11_sim_1_intro")
    s.click(text="Upload your recorded reel", exact=True, wait=400)
    s.shot("11_sim_1_uploading")
    s.settle(1200)
    s.long_shot("11_sim_1_uploaded")
    s.click(text="Run simulation", exact=True, wait=900)
    s.shot("12_sim_2_running")
    s.settle(2600)
    s.long_shot("13_sim_3_result")
    s.click(text="See evidence", exact=True, nth=0)
    s.shot("13_sim_3_evidence_open")
    for label in ("Production", "Trend"):
        s.click(role="tab", name=label, exact=True)
    s.click(text="Open on Look 3, then rewind", exact=True, wait=400)
    s.click(text="End with a send prompt", exact=True, wait=400)
    s.long_shot("13_sim_3_edits_selected")
    s.click(text="Edit & re-run (2)", exact=True, wait=300)
    s.settle(2800)
    s.long_shot("14_sim_4_rerun_result")
    s.type_and_send("Why might new audiences skip this reel", wait=1300)
    s.long_shot("14_sim_4_ask_curo")
    for name in ("Followers", "New audiences"):
        s.click(role="radio", name=name, exact=True)
        s.shot(f"14_sim_4_audience_{name.lower().replace(' ', '_')}")
    return s.taken


def shoot_components(page: Page) -> list[str]:
    """The standalone component boards (Nav, Composer, ReelThumb, Sketch)."""
    taken = []
    boards = {
        "bottom-navigation": (390, 100),
        "chat-voice-composer": (390, 120),
        "reel-thumbnail": (180, 280),
        "storyboard-sketch": (240, 320),
    }
    for slug, (w, h) in boards.items():
        page.set_viewport_size({"width": w, "height": h})
        page.goto((PAGES / slug / "bundle.html").as_uri())
        page.wait_for_timeout(1500)
        name = f"20_component_{slug}.png"
        page.screenshot(path=str(OUT / name))
        taken.append(name)
    return taken


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", default="msedge", help="msedge | chrome | chromium")
    args = parser.parse_args()

    main_page = PAGES / "main-screen" / "bundle.html"
    if not main_page.exists():
        raise SystemExit("Run tools/extract_prototype.py first.")
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
        page.goto(main_page.as_uri())
        page.get_by_text("Previous content").wait_for(timeout=20000)
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(800)

        taken = run(page) + shoot_components(page)
        browser.close()

    index = ["# Prototype screens", "", "Generated by `tools/screenshot_prototype.py`.", ""]
    index += [f"- [{name}]({name})" for name in taken]
    (OUT / "README.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    print(f"{len(taken)} screenshots in {OUT}")
    if errors:
        print("page errors:", *errors, sep="\n  ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
