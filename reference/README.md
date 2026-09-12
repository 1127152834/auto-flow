# Reference projects

## redroid management demo (planned)

- Plan: [`redroid-demo/PLAN.md`](./redroid-demo/PLAN.md)
- Date: 2026-09-13; status: proposed, awaiting plan confirmation.
- Scope: independent Python + React demos for lifecycle management, screen/input/APK operations, small batch tasks and Magisk image checks; Windows via WSL2 + Docker Engine.
- This user-requested demo is separate from the read-only upstream repositories. Its own source will be tracked by AutoFlow Git and will not be an AutoFlow runtime dependency. Only the plan exists at this stage.

## WebRPA

- Local source: [`reference/WebRPA`](./WebRPA)
- Upstream: <https://github.com/pmh1314520/WebRPA>
- Pinned commit: `5ccb900e8dcf1530aae66f676d87593c416c7ebb`
- License file: [`WebRPA/LICENSE`](./WebRPA/LICENSE)

WebRPA is retained as a read-only reference for selected web-automation capabilities and implementation ideas. It is not an AutoFlow runtime dependency, is not launched by AutoFlow, and is not treated as an integration or compatibility target. The initial Automation Studio scope will implement only the required basic web-automation capabilities on the CloakBrowser runtime.

The nested repository keeps its own Git metadata and is ignored by the AutoFlow parent repository. This prevents accidentally vendoring the upstream source into AutoFlow while preserving an exact, inspectable reference snapshot.

## RedroidManager

- Local source: [`reference/RedroidManager`](./RedroidManager)
- Upstream: <https://github.com/JinHisAndy/RedroidManager>
- Pinned commit: `853b786b29430886ae8db58eb2d9e3432e0c8684`
- License: MIT; [`RedroidManager/LICENSE`](./RedroidManager/LICENSE)
- Added: 2026-09-13; status: confirmed.
- Reference scope: Docker-based Android instance lifecycle, data volumes, display configuration, APK distribution and management UI.

The pinned implementation has an external ADB port-mapping issue for additional instances; its clone operation copies configuration, not application data. Treat it as a reference implementation, not a validated production manager.

## redroid-script

- Local source: [`reference/redroid-script`](./redroid-script)
- Upstream: <https://github.com/ayasa520/redroid-script>
- Pinned commit: `a4951b782fc8e06c845d9553bf07bb643fd8c158`
- License: MIT; [`redroid-script/LICENSE`](./redroid-script/LICENSE)
- Added: 2026-09-13; status: confirmed.
- Reference scope: redroid image customization and Magisk integration, including Android init setup.

The script license does not replace the licenses of downloaded components. Android-version and module compatibility require separate runtime validation.

Both Android reference projects retain their own Git metadata, use detached HEAD at the recorded commits, and are ignored by the AutoFlow parent repository, following the WebRPA storage convention. They are source references, not AutoFlow runtime dependencies. No upstream installer or application was executed during import.

To restore these local references in a new checkout:

```sh
git clone https://github.com/JinHisAndy/RedroidManager.git reference/RedroidManager
git -C reference/RedroidManager checkout --detach 853b786b29430886ae8db58eb2d9e3432e0c8684
git clone https://github.com/ayasa520/redroid-script.git reference/redroid-script
git -C reference/redroid-script checkout --detach a4951b782fc8e06c845d9553bf07bb643fd8c158
```
