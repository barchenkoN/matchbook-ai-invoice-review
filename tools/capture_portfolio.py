"""Capture the actual application for the portfolio; no UI data is fabricated."""

from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / "docs/screenshots"
with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    context = browser.new_context(
        viewport={"width": 1440, "height": 1000},
        reduced_motion="reduce",
        record_video_dir=str(ROOT / "data/portfolio-video"),
        record_video_size={"width": 1440, "height": 1000},
    )
    page = context.new_page()
    page.goto("http://127.0.0.1:8787")
    expect(page.get_by_role("button", name="Enter workspace")).to_be_visible()
    page.screenshot(path=str(out / "01-welcome.png"), full_page=True)
    page.wait_for_timeout(2000)
    page.get_by_role("button", name="Enter workspace").click()
    expect(page.locator(".environment")).to_contain_text("Worker connected", timeout=10000)
    expect(page.locator("tbody tr")).to_have_count(8)
    page.screenshot(path=str(out / "02-inbox.png"), full_page=True)
    page.wait_for_timeout(3000)
    page.get_by_role("button", name="Review INV-2026-1001", exact=True).click()
    expect(page.get_by_role("heading", name="Nordline Supply", exact=True)).to_be_visible()
    page.wait_for_timeout(2500)
    page.get_by_role("button", name="Show source for Unit price differs from order").click()
    page.screenshot(path=str(out / "03-three-way-review.png"), full_page=True)
    page.locator(".match-columns").scroll_into_view_if_needed()
    page.wait_for_timeout(4500)
    page.get_by_role("button", name="Back to inbox").click()
    page.get_by_role("button", name="Review INV-2026-1005", exact=True).click()
    expect(page.get_by_text("Local AI extraction:", exact=False)).to_be_visible()
    page.screenshot(path=str(out / "08-local-ai-review.png"), full_page=True)
    page.get_by_role("button", name="Activity & revisions").click()
    page.wait_for_timeout(4000)
    page.screenshot(path=str(out / "09-decision-trail.png"), full_page=True)
    page.get_by_role("button", name="Back to inbox").click()
    page.get_by_role("button", name="Review INV-2026-1003", exact=True).click()
    expect(page.locator(".synced-card")).to_be_visible()
    page.screenshot(path=str(out / "04-draft-created.png"), full_page=True)
    page.wait_for_timeout(3000)
    page.get_by_role("button", name="Draft register", exact=True).click()
    page.wait_for_timeout(2500)
    page.get_by_role("button", name="System health", exact=True).click()
    expect(page.get_by_role("heading", name="Know what’s running.")).to_be_visible()
    page.screenshot(path=str(out / "05-system-health.png"), full_page=True)
    page.wait_for_timeout(3500)
    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_role("button", name="Invoice inbox", exact=True).click()
    page.screenshot(path=str(out / "06-mobile-inbox.png"), full_page=True)
    video = page.video
    context.close()
    video.save_as(str(ROOT / "docs/Matchbook-walkthrough.webm"))
    browser.close()
print("Screenshots and walkthrough captured from the running application.")
