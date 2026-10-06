# Comparison / workflow design QA

final result: passed

2026-10-06. Scope: isolated prototype and comparison artifact only; not production app verification.

## Grounding and comparison

- Selected target: the Codex sidebar example that the user chose, `approval-final.png` in the 20261006 visualization evidence folder.
- Rendered target comparison: `public/comparison/captures/qa-approval.png`. Source and implementation were opened together in one tool input, both at CSS 1440×900; native captures 1425×891/900 client crops. Sidebar, heading, summary, changes and decision controls remain aligned. Lower history is visible by scrolling.
- Intended content adaptations: first representative decision in the main walkthrough instead of a preloaded rejection/reapproval example; no ‘대표 결재 예시’ shortcut inside app navigation. Amount, corrected quotation and six documents match. No pixel identity or measured time improvement claimed.
- Additional opened evidence: request form, correctly resized mobile original view, and the rendered comparison board. Image columns show the old structure and Codex only.

## Fidelity surfaces

- Fonts/typography: reuse the existing Malgun Gothic/Apple SD Gothic Neo stack, heading/metadata weights and readable contrast overrides. No new font dependency.
- Spacing/layout: reuse 222px sidebar, page header, content tabs, summary/decision grid and panel anatomy. New registration/request states use the same panels and form rhythm. Mobile wraps into one column and switches original/fields.
- Colors/tokens: existing background, blue, status badges, borders and focus colors retained.
- Image quality: browser PNGs embedded at original aspect ratio; enlargement uses the same PNG. Official icon library retained. The quotation is explicitly synthetic HTML data, not a claimed OCR image.
- Copy/content: contract, 3,410,000 baseline, 3,520,000 initial quotation, 4/6 initial documents and 2+1 request consistently used. Receipt and validation remain separate. NTS is marked not queried. Existing structure reproduction and missing legacy captures are labeled.

## Findings resolved

1. Capture issue: full-page capture omitted the fixed sidebar; stale viewport binding produced desktop-shaped ‘mobile’ images. Replaced all with verified viewport captures, including correct 390×844 views.
2. State labeling: approval showed the document tab selected in accessibility state; fixed the common selected-state expression.
3. False confirmation in the corrected source snapshot: changed human confirmation from prefilled person/time to the actual prototype checkbox state. Recaptured the corrected source.
4. Comparison navigation: sticky stage links covered the card title after Next; stage list is now static. Post-fix card title top ~101px and visible below the comparison nav. Mobile step buttons do not split arrow/label.
5. Export escaping: corrected a generated script newline syntax error. Post-fix browser enhancement active, exactly one flow card shown and export contains real line breaks.
6. Partial-reply timing: the old S3 was after two receipts, while the new snapshot was before recording them. Aligned both to two received / one pending, disabled already received items, and prepared a separate zero-receipt WAIT copy. Retested selecting two items → receipt record → partial state → corrected-file view. Recaptured both states.

## Meaningful browser checks

- Clicked registration → basis → missing/mismatch → source confirmation → one 3-item request → two partial receipts → corrected quotation → source confirmation → representative delivery → representative decision → payment record → done.
- Sidebar close/open retained entered decision opinion; approval remained available after the required acknowledgment.
- Comparison flow links and Previous/Next update both sides together. Enlarged image closed with Escape and focus returned to its trigger.
- Collected selected preference and memo into the answer output with real line breaks. TXT save generated an actual Downloads file whose content was read back and matched the synthetic response.
- Clipboard button has manual-selection fallback. Do not infer OS clipboard content from the IAB clipboard API; that API returned empty in this environment.
- Standalone comparison and compiled standalone workflow opened in IAB. Workflow controls present; final compiled page console error/warning list empty.
- Fresh workflow console error/warning list empty. Gallery logs after repair empty. Production tests not repeated for this isolated docs prototype.

## Limits / follow-up

Prepared state transitions demonstrate intended UI behavior, not backend processing, file ingestion or model behavior. Exception legacy captures are missing for three states; mobile legacy captures are also missing. Three-to-five approvers remain future product work. These are labeled limitations, not hidden comparison results. No remaining P0/P1/P2 visual blockers within this artifact's scope.
