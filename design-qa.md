# Android management design QA

Date: 2026-09-13. Status: **passed** for the approved Mac first-version scope. Source: selected prototype images, implemented packaged Mac app, native accessibility interactions and screenshots. Confidence: high for the checked surfaces; this is not a claim of full prototype feature parity or pixel identity.

## Reference and evidence

- Selected reference: `reference/redroid-demo/prototypes/2026-09-13/00-resource-board.png` and `02-create-instances.png`.
- Side-by-side composites: [board](docs/migration/android-management-qa/ui/board-comparison.jpg), [create](docs/migration/android-management-qa/ui/create-comparison.jpg).
- Actual UI: [detail](docs/migration/android-management-qa/ui/detail.png), [native window](docs/migration/android-management-qa/ui/native.png).
- Reference aspect ratio about1.407; actual native capture1080×768. Both normalized to1080px width in the same composite and visually inspected together.

## Findings and resolution

| Area | Verified result |
| --- | --- |
| Hierarchy and composition | Warm canvas, horizontal global navigation, broad resource board with three columns, clay primary action; creation left2/3 form/right1/3 summary and bottom actions. |
| Typography and spacing | Existing application type tokens retained, card headings and controls made legible; labels, group headings and summary align consistently. |
| Colors and surfaces | Existing warm gray, off-white, clay and sage tokens reused; fine borders and restrained rounded cards consistent with reference family. |
| Assets and state | Real Android screenshots at natural aspect ratio; stopped device shows an explicit placeholder. No fictional device content or unsupported success badges. Existing logo and Phosphor icons reused. |
| Interaction | Create, advanced settings, detail tabs and native handoff checked in packaged Mac app. Session stays active on window close and ends explicitly. Form labels and enabled states visible in accessibility tree. |
| P2 fixed | Initial create form pushed the startup control below the first screen; resource inputs collapsed into advanced settings. Second pass found sticky footer overlap; section spacing reduced and recaptured. Final startup switch and label are fully above the footer. |

No unresolved P0–P2 visual issues found on these checked surfaces. Smaller windows can scroll; exhaustive viewport/accessibility auditing is not claimed.

## Intentional scope differences

The illustration has six fictitious devices, parallel/temporary task queues, quantity input and root badges. This version renders actual registered devices, supports one persistent creation request at a time and serial control, with root explicitly unverified. It omits the unsupported queue and temporary-type controls. The former browser-touch detail prototype is superseded by the user's native-window direction: detail shows read-only frames and opens an independent Mac operation window. Workflows use the existing Studio target picker, not a new allocation wizard. These are functional boundaries, not visual defects hidden by mock data.

The board evidence includes the stopped UI test instance. That test instance was subsequently cleaned up; see `docs/migration/android-management-qa/ui/cleanup.json`.
