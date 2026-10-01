"""Which rules decide whether a failure that an error branch caught fails the run.

`webrpa` (the default for documents without a marker) keeps the frozen product
rule: the failure is remembered even when the error branch ran, so the run still
fails. `autoflow-v2` records the caught failure as *handled* and leaves the run
outcome to what the rest of the graph does. The marker is a top-level document
field so that already saved documents never change behaviour silently.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

ERROR_SEMANTICS_WEBRPA = "webrpa"
ERROR_SEMANTICS_V2 = "autoflow-v2"
DOCUMENT_FIELD = "executionSemantics"


def document_error_semantics(document: Mapping[str, Any]) -> str:
    """Resolve a document's rule; only the exact v2 marker opts in."""
    if isinstance(document, Mapping) and document.get(DOCUMENT_FIELD) == ERROR_SEMANTICS_V2:
        return ERROR_SEMANTICS_V2
    return ERROR_SEMANTICS_WEBRPA


def has_marker(document: Mapping[str, Any]) -> bool:
    """True when the document states its own rule (even an unknown one)."""
    return isinstance(document, Mapping) and DOCUMENT_FIELD in document
