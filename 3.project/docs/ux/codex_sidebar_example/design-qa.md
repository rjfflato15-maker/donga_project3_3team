# Sidebar prototype design QA — 2026-10-06

## Target and intentional changes

- Source visual: Claude `a404409`, `C:/3조 색인-ui/3.project/docs/ux/erp_redesign/captures/W6.png` (1440×900).
- Source product: contract summary, changes after rejection, operator note, representative decision, opinion history. Same synthetic contract: 가상 새봄기획 / 업무지원 시스템 구축 / 3,410,000원.
- Approved adaptation: collapsible left sidebar, larger spacing/readable fields, mobile overlay menu, original/fields switching. This is a design example, not a pixel clone or a production replacement.
- Comparison input: source W6 and implementation `approval-final.png` opened together, at original image detail. Full composition plus the decision/changes regions were examined from those full-resolution inputs. No side-by-side collage is claimed.

Evidence root: `C:/Users/Donga/.codex/visualizations/2026/10/02/01a0fd2b-218b-7200-b673-7fa505fd8a21/codex-sidebar-example-20261006/`.

## Captures and size

| State | CSS viewport | Capture |
| --- | --- | --- |
| Approval, sidebar open | 1440×900, DPR≈1 | `approval-final.png`, native client capture 1425×891 |
| Approval, sidebar open | 1280×720, DPR≈1 | `approval-1280.png`, native client capture 1265×712 |
| Inbox | 1440×900 | `inbox-final.png`, 1440×900 |
| Contract documents | 1440×900 | `contract-final.png` |
| Original comparison | 1440×900 | `source-final.png` |
| Bundle request | 1440×900 | `request-desktop.png` |
| Partial reply | 1440×900 | `partial-reply-desktop.png` |
| Mobile menu/inbox | 390×844 | `mobile-menu.png`, `mobile-inbox.png` (client capture 375×812) |
| Mobile approval | 390×844 | `mobile-approval.png` (full page) |
| Mobile source/fields | 390×844 | `mobile-source-original.png`, `mobile-source-fields.png` (390×844) |

Source and implementation CSS viewports match for the desktop composition check. Native captures sometimes exclude scrollbar/client edges; this is a capture-region difference, not a layout mismatch. No stretching or resampling was used. The separate 1440×900 `approval-qa-1440.png` shows the collapsed-sidebar variant; it is not the sidebar-open comparison evidence. Prototype navigation strips in the source are excluded from product-layout judgments.

## Comparison history and fixes

1. **P2 — low contrast in supporting labels.** Initial screenshots showed light blue/gray metadata. Changed supporting text to darker tokens; sampled #63758a on white has contrast about 4.73:1. Inspected current source/approval/list/mobile captures afterward. This is a sample check, not a complete accessibility certification.
2. **P2 — approval buttons below 720px.** `approval-readable.png` showed the button bottom around y=743. Removed the repeated progress strip from the approval tab while retaining the contract state and approval line. In the revised 1280×720 state, approval button bottom is y≈689; the decision remains visible.
3. **P2 — unrelated records/data in other cases.** Confined historical changes/approval opinions to the complete example contract. Other contracts show preparation status. Unprovided originals are disabled rather than opening an unrelated quotation. Unverified quotation state is separate from an automatic match and previous confirmer.
4. **P2 — mobile menu background focus.** Added inert background content, focus containment, Esc dismissal and focus return for the mobile drawer. Opening it excludes main content from the accessibility tree. Selecting a menu closes the drawer and restores access to the page.
5. After fixes: opened source + latest implementation together, inspected visible information/decision regions, and captured the desktop/mobile states again. No remaining P0/P1/P2 issue was identified in the stated prototype scope.

During development a temporary CSS import error prevented a checkbox click. The extra stylesheet was merged into the existing stylesheet, then build/reload and successful checkbox/approval checks were completed. Final fresh-tab console logs contained no errors or warnings. This was a runtime repair, not visual QA evidence by itself.

## Fidelity surfaces

- **Typography:** existing Malgun Gothic/Apple system fallback; hierarchy from contract title to section label to numeric value. Larger table/field text than the source; explicit intentional adaptation. Amounts, names and actor/time are readable without the source's clipped confirmation column.
- **Spacing:** stable contract header, separate content tabs, balanced summary/decision columns, compact decision at upper right; sidebar can release width. No document-level horizontal overflow in the inspected 1280 desktop or 390 mobile states. Wide change/document tables can scroll locally.
- **Colors:** white surfaces, pale gray workspace, restrained blue primary action; green/amber/red retain their state meanings. Supporting labels were darkened. Disabled buttons remain visibly disabled.
- **Assets:** official Lucide UI icons, no missing decorative image assets. Original document is a synthetic table/text view using the same example quotation facts; it is not OCR output or a fabricated real attachment. Source stamp boxes become ordinary actor/stage UI, not generated image stamps.
- **Copy:** input requirements next to the action; representative opinion required, unverified acknowledgment separate, copy separate from external-request recording; receipt separate from validation; extraction source separate from unchanged-value confirmation.

## Primary interactions verified in the browser

- Opinion + acknowledgment enable approval; virtual approval changes state to 지급 대기 and records the opinion.
- Sidebar collapse/expand preserves entered opinion and checkbox. Contract/tab stay selected.
- Source dialog selects evidence/highlight; mobile tax row switches back to the original and highlights 부가세. Shift+Tab stays in the modal; Esc closes and restores the triggering source button.
- Two missing external documents default selected; one request record contains both. Receiving only the bank copy leaves the invoice waiting and the contract in 회신 대기.
- Numeric search `1,650,000원` produces the matching contract.
- Mobile overlay opens, moves focus inside, excludes background, and closes on menu selection. Mobile body scroll width equals client width; source dialog stays x=10..380 within 390px.
- Standalone exported HTML was opened in the local browser and renders the same initial contract/approval UI.
- Final `npm run build` passed. Fresh final preview console: 0 errors, 0 warnings.

## Limits and follow-up

- No production API, authentication, persistence, uploaded-file reading, actual send/payment or model evaluation is exercised.
- Not all app screens/exception states are covered; not all assistive-technology combinations are tested. 3–5-person approval is not implemented here.
- P3: user preference testing for density, tab wording and the amount of supporting text. This example can be added as a third design direction to the comparison page.

final result: passed
