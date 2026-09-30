from dataclasses import dataclass


@dataclass(frozen=True)
class ImageMetadata:
    image_id: str
    source_digest: str | None
    architecture: str
    os: str
    android_version: str | None
    reference: str | None = None
    google_components: str = "unknown"
