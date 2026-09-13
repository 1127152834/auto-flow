# Android native runtime provenance

2026-09-13 · confirmed by source inspection and local `scrcpy --version`.

AutoFlow's formal Android adapter was extracted and rewritten from this repository's
`reference/redroid-demo` native Mac experiment (baseline `49637e9`): fixed scrcpy,
PTY frame readiness, dedicated SSH tunnel, process identities and scoped ADB cleanup.
The formal implementation adds workspace/device ownership, SQL registry, workflow
commands, handoff receipts, recovery and Python 3.11 compatibility. It does not call
the Demo HTTP services or import files from `reference` at runtime.

The external native viewer is the unmodified official **scrcpy 3.3.4** distribution:

- [Official release](https://github.com/Genymobile/scrcpy/releases/tag/v3.3.4)
- Archive: `scrcpy-macos-aarch64-v3.3.4.tar.gz`
- SHA-256: `8fef43520405dd523c74e1530ac68febcc5a405ea89712c874936675da8513dd`
- [Upstream license](https://github.com/Genymobile/scrcpy/blob/v3.3.4/LICENSE): Apache-2.0;
  verbatim local copy: [scrcpy-LICENSE.txt](scrcpy-LICENSE.txt).
- Copyright (C) 2018 Genymobile; Copyright (C) 2018–2025 Romain Vimont.
- Client and server remain paired; the preparation command verifies the archive
  before extraction. Its package has no separate third-party license directory.
- Local linked versions: SDL 2.32.8; libavcodec 61.19.101; libavformat 61.7.100;
  libavutil 59.39.100; libusb 1.0.29. System ADB is 36.0.2-14143358.

The Mac application artifact contains the AutoFlow sidecar, not the scrcpy archive
or Android image. The explicit preparation command installs the vendor archive to
`~/.autoflow/android-runtime`; it is not copied into a redistributed installer.
Any later offline bundle must separately inventory and carry the notices/source
obligations of its actual FFmpeg/SDL/libusb/ADB builds. This task has not produced
or approved such an offline bundle. The RedroidManager/redroid-script reference
repositories and their existing license records remain unchanged.
