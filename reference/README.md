# Reference projects

## WebRPA

- Local source: [`reference/WebRPA`](./WebRPA)
- Upstream: <https://github.com/pmh1314520/WebRPA>
- Pinned commit: `5ccb900e8dcf1530aae66f676d87593c416c7ebb`
- License file: [`WebRPA/LICENSE`](./WebRPA/LICENSE)

WebRPA is retained as a read-only reference for selected web-automation capabilities and implementation ideas. It is not an AutoFlow runtime dependency, is not launched by AutoFlow, and is not treated as an integration or compatibility target. The initial Automation Studio scope will implement only the required basic web-automation capabilities on the CloakBrowser runtime.

The nested repository keeps its own Git metadata and is ignored by the AutoFlow parent repository. This prevents accidentally vendoring the upstream source into AutoFlow while preserving an exact, inspectable reference snapshot.
