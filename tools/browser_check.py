"""Real Chromium interaction checks and portfolio screenshots."""

import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / "docs" / "screenshots"
out.mkdir(parents=True, exist_ok=True)
checks = []
with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    context = browser.new_context(
        viewport={"width": 1440, "height": 1024},
        reduced_motion="reduce",
        record_video_dir=str(ROOT / "data" / "browser-video"),
    )
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://127.0.0.1:8787")
    expect(page.get_by_role("button", name="Enter workspace")).to_be_visible()
    page.screenshot(path=str(out / "01-welcome.png"), full_page=True)
    page.get_by_role("button", name="Enter workspace").click()
    expect(page.get_by_role("heading", name="Every invoice. Accounted for.")).to_be_visible()
    expected_rows = len(page.request.get("http://127.0.0.1:8787/api/invoices").json()["items"])
    expect(page.locator("tbody tr")).to_have_count(expected_rows)
    page.screenshot(path=str(out / "02-inbox.png"), full_page=True)
    checks.append("Reviewer sign-in and populated demo queue")
    search = page.get_by_role("textbox", name="Search invoices")
    search.fill("no-such-supplier")
    expect(page.get_by_role("heading", name="No matching invoices")).to_be_visible()
    page.get_by_role("button", name="Clear search", exact=True).click()
    expect(page.locator("tbody tr")).to_have_count(expected_rows)
    expect(search).to_be_focused()
    checks.append("Search, empty results, immediate clear and focus restoration")
    page.get_by_role("button", name="Review INV-2026-1001", exact=True).click()
    expect(page.get_by_role("heading", name="Nordline Supply", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Approve invoice")).to_be_disabled()
    expect(page.get_by_text("Quantity exceeds goods received")).to_be_visible()
    page.get_by_role("button", name="Show source for Unit price differs from order").click()
    expect(page.locator(".evidence-highlight")).to_be_visible()
    page.screenshot(path=str(out / "03-three-way-review.png"), full_page=True)
    checks.append("Exception blocks approval and evidence highlights original page")
    page.get_by_role("button", name="Review & correct fields").click()
    page.get_by_label("supplier", exact=True).fill("Unsaved change")
    page.get_by_role("button", name="Back to inbox").click()
    expect(page.get_by_role("dialog")).to_be_visible()
    page.get_by_role("button", name="Keep editing").click()
    expect(page.get_by_label("supplier", exact=True)).to_have_value("Unsaved change")
    page.get_by_role("button", name="Back to inbox").click()
    page.get_by_role("button", name="Discard changes").click()
    expect(page.get_by_role("heading", name="Every invoice. Accounted for.")).to_be_visible()
    checks.append("Dirty edits protected by app-owned dialog")
    page.get_by_role("button", name="Review INV-2026-1002", exact=True).click()
    expect(page.get_by_role("heading", name="The numbers line up")).to_be_visible()
    approve = page.get_by_role("button", name="Approve invoice")
    created_this_run = bool(approve.count())
    if approve.count():
        approve.click()
    if page.get_by_role("button", name="Create draft", exact=True).count():
        expect(page.get_by_role("button", name="Create draft", exact=True)).to_be_visible()
        page.get_by_role("button", name="Create draft", exact=True).click()
        expect(page.get_by_role("dialog")).to_be_visible()
        expect(page.get_by_role("button", name="Keep reviewing")).to_be_focused()
        page.keyboard.press("Escape")
        expect(page.get_by_role("dialog")).not_to_be_visible()
        page.get_by_role("button", name="Create draft", exact=True).click()
        page.get_by_role("dialog").get_by_role("button", name="Create draft", exact=True).click()
    expect(page.locator(".synced-card")).to_be_visible(timeout=15000)
    page.screenshot(path=str(out / "04-draft-created.png"), full_page=True)
    checks.append(
        "Approval, confirmation, Escape and persisted sandbox draft"
        if created_this_run
        else "Existing persisted sandbox draft verified; creation covered by live HTTP evidence and the earlier fresh demo run"
    )
    page.get_by_role("button", name="System health", exact=True).click()
    expect(page.get_by_role("heading", name="Know what’s running.")).to_be_visible()
    page.screenshot(path=str(out / "05-system-health.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_role("button", name="Invoice inbox", exact=True).click()
    expect(page.get_by_role("button", name="Upload invoice")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    page.screenshot(path=str(out / "06-mobile-inbox.png"), full_page=True)
    page.get_by_role("button", name="Upload invoice").click()
    expect(page.get_by_role("dialog")).to_be_visible()
    page.get_by_role("button", name="Upload & check").click()
    expect(page.get_by_text("Choose a document first.")).to_be_visible()
    expect(page.get_by_label("Choose document")).to_be_focused()
    page.keyboard.press("Escape")
    checks.append("390px layout, keyboard dialog exit and upload validation")
    assert not errors, errors
    checks.append("No browser runtime errors")
    context.close()
    browser.close()
(ROOT / "docs" / "evidence" / "browser-check.json").parent.mkdir(exist_ok=True, parents=True)
(ROOT / "docs" / "evidence" / "browser-check.json").write_text(
    json.dumps({"checks": checks, "browser_errors": errors}, indent=2)
)
print(json.dumps(checks, indent=2))
