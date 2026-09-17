# UI controls and table capability integration matrix

Date: 2026-09-17
Status: confirmed by source comparison and focused tests
Sources: `codex/ui-controls-plan@1fb58e18`, `codex/global-table-system@2a29ac0d`

| Capability | Decision | Evidence and reason | Verification |
| --- | --- | --- | --- |
| Drawer and field grouping | port | `Drawer`, `FieldGroup`, and their focus/label tests were absent from the current tree and import without replacing any page. | shared component tests |
| Disclosure and password input | port | The primitives and their tests were absent; both use the current tokens and overlay host. | shared component tests |
| Alert, empty state, progress, feedback tests | port | These are isolated primitives missing from the current tree and have no competing abstraction. | shared component tests |
| Overlay hosting and focus restoration | already-current plus test | Current `overlay-host.tsx`, Dialog, Modal, Select, Dropdown, and Popover are newer; the source integration test passes unchanged. | `overlay-integration.test.tsx` and shared component suite |
| Combobox from the controls branch | exclude | It has no production caller and requires the removed `react-aria-components` package. Reintroducing a dependency for an unused primitive is not a valid capability port. | import and consumer audit |
| Checkbox, radio group, tabs, tooltip | already-current | Current components have later option-based APIs and current tests. Old source tests encode superseded child-based/manual-activation contracts and are not copied. | shared component suite and typecheck |
| Fine-grid table primitives and CSS | already-current | Fifty files changed by the table branch are byte-identical in the current tree, including table CSS, toolbar/status primitives, Studio table stylesheet, and verification script. | table tests and `verify-table-system.mjs` |
| Project data record/status/query tables | current-newer | Current versions include the table branch behavior plus later PM2/PM4 project identity, typed record keys, generation fencing, bulk status, and Excel changes. Replacing them would remove newer behavior. | project-data renderer tests |
| Studio DataTable and table consumers | current-newer | Current versions retain compact density/fixed columns while adding the later Studio runtime, result, debug, and transport work. | Studio data-table test, typecheck, build |
| Radius/token system | already-current | `radii.css`, `tables.css`, `controls.css`, and `tokens.css` are present; table verification enforces small-radius and density rules. | table verifier and lint |
| UI Lab production entry points and historical screenshot output | exclude | These are audit artifacts and isolated-lab scaffolding, not runtime capability. | source-path audit |

The two source branches are reconciled with tree-preserving merges only after this matrix and the focused verification pass.
