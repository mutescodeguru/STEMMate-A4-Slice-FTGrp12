# Accessibility and usability fixes (P4)

Branch `feat/p4-a11y-fixes`. Each fix is one commit and one file. Before/after images are in `docs/a11y/`.
Measured on the real backend at 390 px wide (phone size), 5 November 2026.

| # | Issue | Found by | Fix | File | Before | After |
|---|---|---|---|---|---|---|
| 1 | "Saved on this device" shown twice in the editor footer (save message and status chip) | P4 review, 2 Nov | Save message now says "Last saved 10:51"; the chip alone says where the plan is saved | `js/editor.js` | Same text twice | Each says something different |
| 2 | Sticky footer hid focused fields when tabbing (WCAG 2.2, 2.4.11 Focus Not Obscured, AA) | P4 keyboard check, 5 Nov | Footer made compact (one row on phones) and `scroll-padding-bottom` keeps focused fields above it | `css/app.css` | 8 of 21 fields fully hidden; footer 145 px tall | 0 fully hidden (3 touch the edge by 7–11%); footer 76 px |
| 3 | Privacy hint at the very bottom of the form, after all fields (PR-01) | P4 review, 2 Nov | Moved to the top, above the first field | `index.html` | About 2,100 px down the page | About 100 px down, read before typing |
| 4 | On sign-in the cursor started in Username, so the skip link was only reachable with Shift+Tab | P7 question, 4 Nov | Removed the autofocus; first Tab now reaches the skip link, as on every other page | `js/app.js` | First Tab went to Password | First Tab goes to "Skip to main content" |

After the fixes: `tools/ui_smoke.py` passes with no JavaScript errors, and P3's backend tests pass (115).
