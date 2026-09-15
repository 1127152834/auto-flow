# Final unavailable-reference UUID E2E

Passed against the immutable isolated snapshot recorded in `uuid-final-snapshot.json`, with source HEAD `a5e7d48` plus the recorded PM3 working changes. The five screenshots cover semantic unavailable states and expanded options for a fixed environment, model provider, proxy, and browser profile.

The project was created through the UI. Workflows were created through the production application service, and canonical unavailable UUID references were saved through the public automation HTTP contract with idempotency keys. No database rows were edited directly. Screenshot `31a` uses a declared synthetic resource-read fault: the same profile URL receives three HTTP 500 responses, then “重新读取资料” restores the real API response. `result.json` is unchanged and `run.log` contains no runtime token.
