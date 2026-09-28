# Task3 initial review, 30ae0138

Spec: fail. Quality: Needs fixes. Critical0 / Important1 / Minor0.

Important (reviewer verbatim): ProjectInteractionHost.tsx:66–75 does not fully separate transport failures from operation failures. executeProjectScript() begins with another API read at interactions.ts:58, but the host starts it without awaiting that read, immediately clears connectionError, and maps every rejection to operationError. If pending() recovers but the script-request read still fails transiently, the communication notice disappears and the transport error becomes a persistent operation error. Because the target remains in scripts, later polls skip that read and cannot recover the notice. This violates “完成本轮所需读取后清除通信提示” and transport/operation separation.

Requested fix: Track the script request/claim phase separately so transient API-read failures remain connection failures and cannot be cleared before recovery. Preserve the existing no-replay rule. Add a regression where pending() succeeds with a JS target but its request read fails transiently, then recovers without executing the script twice.

Cannot verify from diff: SQLite archive supports one attempt/output and stable terminal result; live banner was observed through CUA but no screenshot or AX file was saved. No reconstruction performed.

AOCI: Reviewer received299entries fully but confirmation/attestation hit snapshot_unavailable after permitted pure schema correction. No semantic retry; review explicitly source-bound.

## Round1 scoped review dae16113

Original pre-claim read and missing UI evidence ADDRESSED. New Important (verbatim): claim confirmation now blocks the sole poll loop and can hide claim-stage transport outages. ProjectInteractionHost.tsx:85 awaits claimProjectScript() inline. interactions.ts:60–68 suppresses transient submit/query failures and loops until confirmation, so no later poll can set the connection notice or process other pending interactions during that outage. The archived outage occurred before or after this narrow in-flight claim window and does not cover it. Keep the stable command identity and no-replay behavior, but let claim-stage transient failures update connection state without serializing the global poll loop.

Out-of-scope observations none. Read-only source-bound scoped review, no repeated tests.

## Round2 scoped review d2bcae4f

Claim poll blockage ADDRESSED. New Important (verbatim): a connection revision abandons the original unknown claim instead of continuing its read-only recovery. ProjectInteractionHost.tsx:61–65 aborts every unresolved claim whose revision changed, while retaining its entry in scripts. Subsequent polls skip that identity at line87, so the original command is never queried again even though the documented backend semantics keep pending/claimed/submitted requests in the pending set. The new test at ProjectInteractionHost.test.tsx:131 explicitly locks in this abandonment. This violates the existing “unknown result queries the original operation” contract and can leave an applied claim without a worker until backend expiry. App.tsx:49 already remounts the host when workspace or sidecar instance identity changes; a same-instance connected/client revision should preserve or resume the original command query without issuing a second claim.

Out-of-scope observations none; no test reruns.
