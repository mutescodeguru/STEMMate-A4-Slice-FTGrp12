"""P4 UI smoke test in mock mode (not part of pytest).
Usage from the repo root: python tools/ui_smoke.py stemmate
Needs: pip install playwright, then python -m playwright install chromium"""
import subprocess, time, sys
from playwright.sync_api import sync_playwright
root = sys.argv[1]
srv = subprocess.Popen([sys.executable, "-m", "http.server", "8765", "-d", root], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
errors = []
try:
  with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 390, "height": 844})
    pg.on("console", lambda m: m.type == "error" and errors.append(m.text))
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto("http://localhost:8765/static/index.html?mock=1")
    pg.wait_for_selector("#view-login:not([hidden])")
    pg.fill("#login-username", "demo_facilitator"); pg.fill("#login-password", "wrong"); pg.click("button[type=submit]")
    pg.wait_for_selector("#login-error:not([hidden])"); print("bad login:", pg.inner_text("#login-error"))
    pg.fill("#login-password", "demo123"); pg.click("button[type=submit]")
    pg.wait_for_selector("#view-plans:not([hidden])"); print("plans view ok")
    pg.click("#new-plan"); pg.wait_for_selector("#view-editor:not([hidden])")
    pg.click("#mark-complete"); pg.wait_for_selector("#error-summary:not([hidden])")
    print("summary items:", pg.locator("#error-summary li").count(), "| focused:", pg.evaluate("document.activeElement.id"))
    pg.fill("#f-title", "Simple circuits")
    t0 = time.time(); pg.wait_for_selector(".save-status--saved", timeout=4000); print("autosaved in %.1fs:" % (time.time()-t0), pg.inner_text("#save-status"))
    pg.select_option("#f-level", "junior secondary")
    pg.fill(".step__desc", "Show the parts"); pg.fill(".step__dur", "10")
    pg.click("#add-step"); pg.locator(".step__desc").nth(1).fill("Build the circuit"); pg.locator(".step__dur").nth(1).fill("20")
    pg.locator(".step__up").nth(1).click(); print("after move up, first step:", pg.locator(".step__desc").nth(0).input_value(), "| total:", pg.inner_text("#total-duration"))
    pg.check("#mat-1"); pg.check("#mat-3")
    pg.fill("#f-safety", "Batteries only, no mains.")
    pg.fill("#f-inclusion", "Pair learners so each can hold or read.")
    time.sleep(1.6)
    pg.click("#mark-complete"); pg.wait_for_selector("#mark-complete:has-text('Plan is complete')")
    print("complete:", pg.inner_text("#save-status"), "| badge:", pg.inner_text("#sync-badge"))
        # restore after reload + session loss
    pg.evaluate("sessionStorage.clear()"); pg.reload(); pg.wait_for_selector("#view-login:not([hidden])")
    pg.fill("#login-username", "demo_facilitator"); pg.fill("#login-password", "demo123"); pg.click("button[type=submit]")
    pg.wait_for_selector("#view-plans:not([hidden])"); print("no draft -> plans list, items:", pg.locator(".plan-item").count())
    # draft restore
    pg.click("#new-plan"); pg.wait_for_selector("#view-editor:not([hidden])"); pg.fill("#f-title", "Water filter draft")
    pg.wait_for_selector(".save-status--saved", timeout=4000)
    pg.evaluate("sessionStorage.clear()"); pg.reload(); pg.wait_for_selector("#view-login:not([hidden])")
    pg.fill("#login-username", "demo_facilitator"); pg.fill("#login-password", "demo123"); pg.click("button[type=submit]")
    pg.wait_for_selector("#view-editor:not([hidden])"); print("restored:", pg.input_value("#f-title"), "|", pg.inner_text("#save-status"))
    # offline save failure
    pg.evaluate("stemmateMock.offline = true"); pg.fill("#f-title", "Water filter v2")
    pg.wait_for_selector(".save-status--error", timeout=4000); print("offline:", pg.inner_text("#save-status"))
    pg.evaluate("stemmateMock.offline = false"); pg.wait_for_selector(".save-status--saved", timeout=6000); print("recovered:", pg.inner_text("#save-status"))
    # session expires mid-edit: sign in again, form comes back with the unsaved edit
    pg.evaluate("sessionStorage.removeItem('stemmate_mock_session')")
    pg.fill("#f-safety", "Edit typed after the session ended")
    pg.wait_for_selector("#view-login:not([hidden])", timeout=4000); print("401 notice:", pg.inner_text("#login-error"))
    pg.fill("#login-username", "demo_facilitator"); pg.fill("#login-password", "demo123"); pg.click("button[type=submit]")
    pg.wait_for_selector("#view-editor:not([hidden])"); pg.wait_for_selector(".save-status--saved", timeout=4000)
    print("kept after re-login:", pg.input_value("#f-safety"))
    # outbox + interrupted sync
    pg.evaluate("stemmateMock.failSync = true"); pg.goto("http://localhost:8765/static/index.html?mock=1#/outbox")
    pg.wait_for_selector("#view-outbox:not([hidden])"); pg.click("#sync-now"); time.sleep(3.5); pg.evaluate("stemmateMock.failSync = false")
    time.sleep(5.5); print("banner:", pg.inner_text("#banner") if pg.is_visible("#banner") else "(hidden)")
    print("outbox chips:", pg.locator("#outbox-list .status").all_inner_texts())
    pg.click("#outbox-list .plan-item--attention button"); time.sleep(3.2)
    pg.click("#sync-now"); time.sleep(0.3); time.sleep(3)
    pg.goto("http://localhost:8765/static/index.html?mock=1#/outbox"); pg.wait_for_selector("#view-outbox:not([hidden])"); time.sleep(0.5)
    print("after retry:", pg.locator("#outbox-list .status").all_inner_texts())
    # version conflict: bump stored version behind the editor's back
    pg.goto("http://localhost:8765/static/index.html?mock=1#/plans"); pg.wait_for_selector(".plan-item")
    pg.click(".plan-item a >> nth=0"); pg.wait_for_selector("#view-editor:not([hidden])")
    pg.evaluate("""() => { const db = JSON.parse(localStorage.stemmate_mock_db); Object.values(db.plans).forEach(p => p.version += 5); localStorage.stemmate_mock_db = JSON.stringify(db); }""")
    pg.fill("#f-safety", "Changed safety"); pg.wait_for_selector("#conflict-dialog[open]", timeout=4000); print("conflict dialog shown")
    pg.click("[data-choice=mine]"); pg.wait_for_selector(".save-status--saved", timeout=4000); print("after keep mine:", pg.inner_text("#save-status"))
    b.close()
finally:
  srv.terminate()
print("JS errors:", errors or "none")
sys.exit(1 if errors else 0)
