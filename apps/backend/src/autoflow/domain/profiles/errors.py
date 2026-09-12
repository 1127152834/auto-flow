class ProfileValidationError(ValueError):
    """Raised when a profile value violates a domain rule."""


class ProfileNotFound(Exception):
    """Raised when a requested profile does not exist."""


class ProfileNameConflict(Exception):
    """Raised when a profile name is already in use."""


class ProfileDirectoryBusy(Exception):
    """Raised when profile data cannot be moved safely."""


class ProfileDataPathInvalid(Exception):
    """Raised when a profile data path is outside the managed boundary."""


class KernelNotInstalled(Exception):
    """Raised when a profile references an unavailable browser kernel."""


class ProxyUnavailable(Exception):
    """Raised when a profile references an unavailable proxy resource."""


class ProfileTestBrowserBusy(Exception):
    """Raised while the same profile already has a test browser starting."""


class ProfileTestBrowserUnavailable(Exception):
    """Raised when a temporary test browser cannot be started."""
