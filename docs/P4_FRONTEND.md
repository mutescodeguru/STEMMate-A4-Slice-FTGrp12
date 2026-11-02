# STEMMate A4 slice: frontend (P4)

Plain HTML, CSS and JavaScript modules. No build step, no Node.
Built against P1's API contract, P3's handover and the A3 v3 Figma screens 6.2, 6.3 and 6.5.
All frontend files live in `stemmate/static/`, as P3's handover asks. No Python was changed.

## Files

| File | What it does | Requirements |
| --- | --- | --- |
| `stemmate/static/index.html` | All screens: sign in, my plans, plan editor, sync outbox, conflict dialog | FR-03, FR-05, AR-01 |
| `stemmate/static/css/app.css` | Styles, focus rings, contrast, reflow to 320 px | AR-01 |
| `stemmate/static/js/app.js` | Routing, sign in, plan list, outbox, sync polling, offline banner, session timeout | SR-01, FR-04, FR-05 |
| `stemmate/static/js/editor.js` | Plan form, autosave (C2), draft restore, error display, version conflict | FR-03, QR-02 |
| `stemmate/static/js/api.js` | Calls the Flask API; one error format for every failure | all |
| `stemmate/static/js/mock-api.js` | Fake backend with the same shapes, for working without the server | n/a |
| `stemmate/static/js/validation.js` | Draft and "mark complete" rules (pure functions, unit-testable) | FR-03 |
| `stemmate/static/js/status.js` | Text and icon for each sync status | FR-05, AR-01 |
| `stemmate/static/js/config.js` | Autosave delay, retry delays, level list, limits | QR-02 |
| `tools/ui_smoke.py` | Browser test of the whole UI in mock mode | evidence for P5 |

## Run it with the real backend

Follow P3's handover (init-db, seed-materials, create-user), then in two windows with the venv active:

```bat
python run_central.py
python run.py
```

Open http://127.0.0.1:5000/ and sign in with the user you created. On port 5000 the real API is used automatically.

## Run it without the backend (mock mode)

From the repo root:

```bat
python -m http.server 8000 -d stemmate
```

Open http://localhost:8000/static/index.html?mock=1 and sign in as `demo_facilitator` / `demo123` (mock only, fictional).

To try failures in mock mode, open the browser console (F12) and type:

- `stemmateMock.offline = true`: the local app "stops"; autosave shows "Not saved" and retries
- `stemmateMock.failSync = true`, then press Sync now: the plan becomes "Sync interrupted"
- `stemmateMock.storageLimit = 2000`: the next save hits the storage limit (507)
- `stemmateMock.reset()`: wipe the mock data

With the real backend, use P3's outage test instead: start `run_central.py` with `set STEMMATE_FAIL_AFTER_UNIT=1`.

## How the UI handles each API error (P3 handover section 6)

| Error | What the page does |
| --- | --- |
| 422 VALIDATION_FAILED | Message next to each field (`steps[0].duration` = step 1 minutes), ⚠ icon, `aria-invalid`, error summary that takes focus |
| 409 VERSION_CONFLICT | Dialog: keep my version, or load the saved version |
| 409 PLAN_SYNCING | Form goes read-only, message shown, save retried |
| 401 UNAUTHENTICATED | Login shown; after signing in, the form comes back as it was and unsaved edits are saved |
| 401 INVALID_CREDENTIALS | Message shown on the login form |
| 404 NOT_FOUND | Back to My plans |
| 507 STORAGE_LIMIT | "Storage full" message; changes not saved |
| 500 / no connection | "Not saved", retries after 2, 4, 8 s, then a Try again button; edits stay on screen |

## Changes from the A3 prototype (redesign evidence for P6 and P2)

1. Cards are white with a magenta edge instead of solid magenta: dark and blue text on the A3 magenta failed contrast (AR-01).
2. The inclusion prompt is a required text field, not fixed hint text (FR-03, A3 findings F1, F3).
3. Each step has its own minutes; total time is added up automatically instead of one timing box (matches `estimated_duration`).
4. Materials are picked from the catalogue with quantities, instead of free text (matches `PlanMaterial`).
5. Every status shows text plus an icon; errors show a ⚠ icon plus text, not red alone (AR-01).
6. The conflict dialog keeps "Keep my version" and offers "Load the saved version"; "Use server version" and side-by-side compare were dropped because sync is one-way (ADR-003).

## Accessibility built in

Skip link; real labels on every field; error summary that takes focus and links to each field;
`aria-invalid` and `aria-describedby` on fields with errors; status messages in live regions;
steps can be moved and removed by keyboard, with focus kept and the change announced;
visible focus ring; 48 px touch targets; reflows at 320 px; respects reduced motion.
Still to do for evidence: keyboard-only run, 200% zoom, NVDA check, Lighthouse screenshot with date.

## Browser test

`tools/ui_smoke.py` drives the UI in mock mode with Playwright: wrong login, error summary,
autosave timing, reorder, mark complete, draft restore after sign-out, offline save and recovery,
session timeout with unsaved edits kept, interrupted sync and retry, version conflict.
It sits outside `tests/` on purpose, so P3's `pytest` run (115 tests) is not affected.
Needs `pip install playwright` and `python -m playwright install chromium`,
then `python tools/ui_smoke.py stemmate` from the repo root.
