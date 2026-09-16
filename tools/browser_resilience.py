"""Additional real-browser failure, session and accessibility evidence."""

import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
reports = []
with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    context = browser.new_context(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
    page = context.new_page()
    page.goto("http://127.0.0.1:8787")
    page.get_by_role("button", name="Enter workspace").click()
    expect(page.get_by_role("heading", name="Every invoice. Accounted for.")).to_be_visible()
    expect(page.locator("tbody tr").first).to_be_visible()
    expect(page.locator(".environment")).to_contain_text("Worker connected", timeout=10000)
    # Audit instrumentation through the browser debugger; production CSP stays unchanged.
    page.evaluate((ROOT / "frontend/node_modules/axe-core/axe.min.js").read_text(encoding="utf-8"))
    audit = page.evaluate(
        "async()=>await axe.run(document, {runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})"
    )
    reports.append({"screen": "inbox", "violations": audit["violations"]})
    # A real fetch failure must produce a persistent error and recoverable retry.
    page.route("**/api/invoices?**", lambda route: route.abort("failed"))
    page.get_by_role("button", name="Refresh invoice inbox").click()
    expect(page.locator(".error-bar")).to_be_visible()
    page.unroute("**/api/invoices?**")
    page.get_by_role("button", name="Retry", exact=True).click()
    expect(page.locator(".error-bar")).not_to_be_visible()
    # Original exception example remains in the eight-row demo queue.
    page.get_by_role("button", name="Review INV-2026-1001", exact=True).click()
    page.get_by_role("button", name="Review & correct fields").click()
    page.get_by_label("supplier", exact=True).fill("Unsaved session test")
    page.evaluate("async()=>await fetch('/api/logout',{method:'POST'})")
    page.get_by_role("button", name="Save verified revision").click()
    expect(page.get_by_role("heading", name="Restore your session")).to_be_visible()
    page.get_by_role("button", name="Restore session", exact=True).click()
    expect(page.get_by_role("heading", name="Restore your session")).not_to_be_visible()
    expect(page.get_by_label("supplier", exact=True)).to_have_value("Unsaved session test")
    page.get_by_role("button", name="Back to inbox").click()
    page.get_by_role("button", name="Discard changes").click()
    page.get_by_role("button", name="Review INV-2026-1001", exact=True).click()
    expect(page.get_by_role("heading", name="Nordline Supply", exact=True)).to_be_visible()
    audit = page.evaluate(
        "async()=>await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})"
    )
    reports.append({"screen": "review", "violations": audit["violations"]})
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    page.screenshot(path=str(ROOT / "docs/screenshots/07-mobile-review.png"), full_page=True)
    audit = page.evaluate(
        "async()=>await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})"
    )
    reports.append({"screen": "mobile-review", "violations": audit["violations"]})
    browser.close()
(ROOT / "docs/evidence/accessibility.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
print([(x["screen"], [(v["id"], len(v["nodes"])) for v in x["violations"]]) for x in reports])
assert not any(x["violations"] for x in reports), "Fix the reported accessibility violations."
