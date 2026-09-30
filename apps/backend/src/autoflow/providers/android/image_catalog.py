import re
from typing import Any

from autoflow.domain.android.image_models import ImageMetadata
from autoflow.domain.android.ports import AndroidError

_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_REFERENCE = re.compile(r"^[A-Za-z0-9._/-]+(?::[A-Za-z0-9._-]+|@sha256:[0-9a-f]{64})$")
_PULL_REPOSITORIES = {"redroid/redroid", "docker.io/redroid/redroid"}


class ImageCatalog:
    def __init__(self, runtime: Any | None = None) -> None:
        self.runtime = runtime

    @staticmethod
    def _validate_reference(reference: str) -> None:
        if not _REFERENCE.fullmatch(reference) and not _DIGEST.fullmatch(reference):
            raise AndroidError("ANDROID_IMAGE_REFERENCE_INVALID", "镜像引用格式无效", 422)

    async def inspect(self, reference: str) -> ImageMetadata:
        self._validate_reference(reference)
        if self.runtime is None:
            raise AndroidError("ANDROID_IMAGE_CATALOG_UNAVAILABLE", "镜像目录不可访问", 503)
        metadata = await self.runtime.inspect_image(reference)
        if metadata.get("os") != "linux" or metadata.get("architecture") not in {"arm64", "aarch64"}:
            raise AndroidError("ANDROID_IMAGE_UNTRUSTED", "镜像不是兼容的 Linux ARM64 镜像", 409)
        image_id = str(metadata.get("imageId") or "")
        if not _DIGEST.fullmatch(image_id):
            raise AndroidError("ANDROID_IMAGE_ID_INVALID", "镜像未返回固定摘要", 502)
        return ImageMetadata(
            image_id=image_id,
            source_digest=metadata.get("sourceDigest"),
            architecture="arm64",
            os="linux",
            android_version=metadata.get("androidVersion"),
            reference=reference,
            google_components=metadata.get("googleComponents", "unknown"),
        )

    async def pull(self, reference: str, *, allow_unknown_disk_estimate: bool = False) -> ImageMetadata:
        self._validate_reference(reference)
        if reference.split("@", 1)[0].split(":", 1)[0] not in _PULL_REPOSITORIES:
            raise AndroidError("ANDROID_IMAGE_SOURCE_NOT_ALLOWED", "镜像来源未获准拉取", 422)
        if self.runtime is not None and hasattr(self.runtime, "pull_image"):
            await self.runtime.pull_image(reference, allow_unknown_disk_estimate=allow_unknown_disk_estimate)
        return await self.inspect(reference)
