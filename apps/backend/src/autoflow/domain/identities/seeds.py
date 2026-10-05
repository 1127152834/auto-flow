"""Fingerprint seed range for identities (remediation M4 R4-02).

CloakBrowser 0.5.9 accepts and deterministically maps 32-bit seeds (see
.ai/knowledge/2026-10-04-cloakbrowser-seed-range.md); the signed 31-bit bound stays clear of
any signed parsing. Older profiles used 10000..99999, all inside this range.
"""

SEED_MIN = 10_000
SEED_MAX = 2**31 - 1


def valid_seed(value: object) -> bool:
    return type(value) is int and SEED_MIN <= value <= SEED_MAX
