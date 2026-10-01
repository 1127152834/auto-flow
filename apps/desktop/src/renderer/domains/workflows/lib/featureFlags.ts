// Remediation M1 R1-01: settings the backend does not execute yet stay hidden until M2 implements them.
// Mutable so tests of the preserved (hidden) controls can switch them on explicitly.
export const featureFlags = {
  nodeRetryPolicy: false,
}
