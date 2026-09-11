class KernelError(RuntimeError):
    code = "KERNEL_ERROR"


class KernelCatalogError(KernelError):
    code = "KERNEL_CATALOG_INVALID"

    def __init__(self) -> None:
        super().__init__("CloakBrowser catalog response is invalid")


class KernelPlatformUnsupported(KernelError):
    code = "KERNEL_PLATFORM_UNSUPPORTED"

    def __init__(self) -> None:
        super().__init__("CloakBrowser is unavailable on this platform")


class KernelVersionInvalid(KernelError):
    code = "KERNEL_VERSION_INVALID"

    def __init__(self) -> None:
        super().__init__("CloakBrowser version is invalid")


class LicenseInvalid(KernelError):
    code = "LICENSE_INVALID"

    def __init__(self) -> None:
        super().__init__("CloakBrowser license is invalid or expired")


class LicenseValidationUnavailable(KernelError):
    code = "LICENSE_VALIDATION_UNAVAILABLE"

    def __init__(self) -> None:
        super().__init__("CloakBrowser license validation is unavailable")


class LicenseInUse(KernelError):
    code = "LICENSE_IN_USE"

    def __init__(self) -> None:
        super().__init__("CloakBrowser license is in use")


class KernelCredentialStoreUnavailable(KernelError):
    code = "CREDENTIAL_STORE_UNAVAILABLE"

    def __init__(self) -> None:
        super().__init__("System credential storage is unavailable")


class KernelNotFound(KernelError):
    code = "KERNEL_NOT_FOUND"

    def __init__(self) -> None:
        super().__init__("Installed kernel was not found")


class KernelDefaultConflict(KernelError):
    code = "KERNEL_DEFAULT_CONFLICT"

    def __init__(self) -> None:
        super().__init__("Default kernel revision is stale")


class KernelBusy(KernelError):
    code = "KERNEL_BUSY"

    def __init__(self) -> None:
        super().__init__("A kernel installation is already active")


class KernelPathInvalid(KernelError):
    code = "KERNEL_PATH_INVALID"

    def __init__(self) -> None:
        super().__init__("Managed kernel path is invalid")


class KernelOperationNotFound(KernelError):
    code = "KERNEL_OPERATION_NOT_FOUND"

    def __init__(self, _operation_id: str | None = None) -> None:
        super().__init__("Kernel operation was not found")


class KernelWorkerUnavailable(KernelError):
    code = "KERNEL_WORKER_ERROR"

    def __init__(self, message: str = "Kernel worker is unavailable") -> None:
        super().__init__(message)
