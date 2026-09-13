# Reference projects

## vphone iOS automation demo

- Start: [`vphone-demo/README.md`](./vphone-demo/README.md); [verification](./vphone-demo/VERIFICATION.md); [bounded experiment plan](./vphone-demo/PLAN.md).
- Date: 2026-09-13; status: demo implemented, upstream host/guest binaries built; actual iOS boot blocked by current host policy (research guests disabled, signed host binary exits 137).
- Independent Python standard-library + React console: <http://127.0.0.1:8083>. Real host checks, VM discovery, controlled lifecycle, screenshot/touch/swipe/keys/clipboard and step replay. No fake devices; not an AutoFlow production dependency.
- Default isolated runtime data: `~/.vphone-autoflow-demo`; generated evidence and logs: `vphone-demo/.data/` (ignored).

### vphone-cli

- Local source: [`vphone-cli`](./vphone-cli)
- Upstream: <https://github.com/Lakr233/vphone-cli>
- Pinned commit: `9c23c8adcd4b362120988ab9d228b959bcc23ae3` (detached HEAD, recursive submodules initialized).
- License: MIT; [`vphone-cli/LICENSE`](./vphone-cli/LICENSE).
- Sources remain unchanged; ignored `.build`, `.tools`, `.venv` contain this experiment's locally built artifacts. Host security settings were not changed.

### vphone-aio

- Local source: [`vphone-aio`](./vphone-aio)
- Upstream: <https://github.com/34306/vphone-aio>
- Pinned commit: `1db79dccd95391d6247c41f3cc4eac523567f295` (detached HEAD).
- Cloned with `GIT_LFS_SKIP_SMUDGE=1`; seven large archive files are LFS pointers. The approximately 12GB prebuilt iOS archive was not downloaded; no archive extraction or aio launcher execution occurred.
- No top-level license file was found in this snapshot. Retained for inspection; no aio code/archive copied into Demo.

Both nested repositories retain their Git metadata and are ignored by AutoFlow. Restore the same sources with:

```sh
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/34306/vphone-aio.git reference/vphone-aio
git -C reference/vphone-aio checkout --detach 1db79dccd95391d6247c41f3cc4eac523567f295
git clone --recurse-submodules https://github.com/Lakr233/vphone-cli.git reference/vphone-cli
git -C reference/vphone-cli checkout --detach 9c23c8adcd4b362120988ab9d228b959bcc23ae3
git -C reference/vphone-cli submodule update --init --recursive
```

## redroid management demo

- Start: [`redroid-demo/README.md`](./redroid-demo/README.md); [verification](./redroid-demo/VERIFICATION.md); [approved plan](./redroid-demo/PLAN.md).
- Mac: native ARM64 Android in a dedicated Lima Ubuntu VM; [actual Mac validation](./redroid-demo/MAC_TEST.md), browser entry `http://127.0.0.1:8081`. Windows and application-level root are not yet verified.
- Date: 2026-09-13; status: implemented; actual Android, Windows/WSL and Magisk validation remains pending.
- Scope: independent Python + React demos for lifecycle management, screen/input/APK operations, small batch tasks and Magisk image checks; Windows via WSL2 + Docker Engine.
- This user-requested demo is separate from the read-only upstream repositories. Its source is tracked by AutoFlow Git and is not an AutoFlow runtime dependency. The manager was built and exercised locally; unsupported Android hosts show diagnostics.

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
