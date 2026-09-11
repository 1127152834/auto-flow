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
