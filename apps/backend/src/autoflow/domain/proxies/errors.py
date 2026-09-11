class ProxyError(Exception):
    code = "PROXY_ERROR"

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}


class ProxyNotFoundError(ProxyError):
    code = "RESOURCE_NOT_FOUND"


class RevisionConflictError(ProxyError):
    code = "STALE_PROJECTION"


class ProxyInUseError(ProxyError):
    code = "PROXY_IN_USE"


class ProxyGroupInUseError(ProxyError):
    code = "PROXY_GROUP_IN_USE"


class InvalidProxyGroupError(ProxyError):
    code = "VALIDATION_ERROR"


class ProxyMemberRiskError(ProxyError):
    code = "PROXY_MEMBER_RISK_CONFIRMATION_REQUIRED"


class NoAvailableProxyError(ProxyError):
    code = "PROXY_GROUP_NO_AVAILABLE_MEMBER"


class ProviderError(ProxyError):
    def __init__(
        self,
        message: str,
        *,
        retry_after_seconds: int | None = None,
        outcome_unknown: bool = False,
        details: dict | None = None,
    ):
        super().__init__(message, details=details)
        self.retry_after_seconds = retry_after_seconds
        self.outcome_unknown = outcome_unknown


class ProviderUnavailableError(ProviderError):
    code = "PROXYPANEL_UNAVAILABLE"


class ProviderAuthenticationError(ProviderError):
    code = "PROXYPANEL_AUTH_FAILED"


class ProviderSchemaError(ProviderError):
    code = "PROXYPANEL_SCHEMA_UNSUPPORTED"


class CredentialStoreError(ProxyError):
    code = "CREDENTIAL_STORE_UNAVAILABLE"


class CapabilityUnavailableError(ProxyError):
    code = "CAPABILITY_UNAVAILABLE"


class OperationInProgressError(ProxyError):
    code = "OPERATION_IN_PROGRESS"


class SelectionConflictError(ProxyError):
    code = "PROXY_SELECTION_CONFLICT"
