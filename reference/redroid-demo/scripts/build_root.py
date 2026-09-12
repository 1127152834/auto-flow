#!/usr/bin/env python3
"""Build the fixed redroid-script Magisk-only Android 13 image on Linux amd64/arm64.

Downloads and Docker builds happen only when this command is explicitly run.
The reference checkout is archived at the pinned commit and never modified.
"""
import argparse
import ast
import hashlib
import io
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
from pathlib import Path

SOURCE_SHA = "a4951b782fc8e06c845d9553bf07bb643fd8c158"
BASE_IMAGE = "redroid/redroid:13.0.0-latest"
OUTPUT_IMAGE = "autoflow/redroid:13-magisk"


def architecture(value):
    return {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(value)


def command(argv, **kwargs):
    return subprocess.run(argv, check=True, text=True, capture_output=True, timeout=60, **kwargs).stdout.strip()


def inspect_image(name):
    return json.loads(command(["docker", "image", "inspect", name]))[0]


def replace_once(path, old, new):
    text = path.read_text()
    if text.count(old) != 1:
        raise RuntimeError(f"Pinned source patch no longer matches: {path.name}")
    path.write_text(text.replace(old, new))


def patch_source(source, work, base_ref, unique_tag):
    """Small guarded patches; exact source matches are mandatory."""
    redroid = source / "redroid.py"
    replace_once(redroid, 'subprocess.run([args.container, "build", "-t", new_image_name, "."])',
                 'subprocess.run([args.container, "build", "-t", new_image_name, "."], check=True)')
    replace_once(redroid, 'new_image_name = "redroid/redroid:"+"_".join(tags)',
                 'new_image_name = ' + repr(unique_tag))
    replace_once(redroid, '"FROM redroid/redroid:{}-latest\\n".format(\n            args.android)',
                 repr("FROM " + base_ref + "\n"))
    replace_once(source / "stuff/magisk.py", 'extract_to = "/tmp/magisk_unpack"',
                 'extract_to = ' + repr(str(work / "magisk-unpack")))
    helper = source / "tools/helper.py"
    replace_once(helper, '"aarch64": ("arm64", 64),',
                 '"aarch64": ("arm64", 64),\n        "arm64": ("arm64", 64),\n        "amd64": ("x86_64", 64),')
    replace_once(helper, 'if result.stderr:', 'if result.returncode != 0:')
    replace_once(helper, 'response = requests.get(url, stream=True)',
                 'response = requests.get(url, stream=True, timeout=(15, 60))\n    response.raise_for_status()')
    general = source / "stuff/general.py"
    replace_once(general, 'while not os.path.isfile(self.dl_file_name) or loc_md5 != self.act_md5:',
                 'for attempt in range(3):\n            if os.path.isfile(self.dl_file_name) and loc_md5 == self.act_md5:\n                break')
    replace_once(general, 'loc_md5 = download_file(self.dl_link, self.dl_file_name)',
                 'loc_md5 = download_file(self.dl_link, self.dl_file_name)\n        if loc_md5 != self.act_md5:\n            raise ValueError("Magisk download MD5 mismatch after at most three attempts")')
    return ["Docker build check=True", "Unique temporary image tag", "Base FROM uses immutable digest or a unique local tag for the inspected image ID",
            "Magisk extraction directory isolated", "Helper subprocess failures use returncode",
            "HTTP status checked and connect/read timeouts set", "Download checksum retries limited to three",
            "Native amd64/arm64 aliases map to the upstream Magisk ABI branch"]


def run_logged(argv, cwd, env, log, timeout):
    # A total deadline also bounds slow/trickling downloads; kill children on failure.
    process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        code = process.wait(timeout=timeout)
        if code:
            raise RuntimeError(f"Command exited {code}: {' '.join(map(str, argv))}; inspect build.log")
    except BaseException:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        raise


def build(source, output, base_image=None):
    base_image = base_image or os.getenv("REDROID_BASE_IMAGE", BASE_IMAGE)
    native_arch = architecture(platform.machine())
    if platform.system() != "Linux" or native_arch is None:
        raise RuntimeError("Root image build requires native Linux amd64/arm64 (run inside the Linux VM or WSL)")
    for executable in ("docker", "git"):
        if not shutil.which(executable):
            raise RuntimeError(f"Missing command: {executable}")
    info = json.loads(command(["docker", "info", "--format", "{{json .}}"] ))
    if info.get("OSType") != "linux" or architecture(info.get("Architecture")) != native_arch:
        raise RuntimeError("Docker daemon must match the native Linux amd64/arm64 host")
    if "docker desktop" in info.get("OperatingSystem", "").lower() or "docker-desktop" in info.get("Name", "").lower():
        raise RuntimeError("Use the WSL/Linux Docker Engine; Docker Desktop is outside the supported baseline")
    if os.environ.get("DOCKER_HOST", "unix:///var/run/docker.sock") != "unix:///var/run/docker.sock":
        raise RuntimeError("Use the local WSL/Linux Docker Engine socket")
    if not os.environ.get("DOCKER_HOST"):
        context = command(["docker", "context", "show"])
        endpoint = command(["docker", "context", "inspect", context, "--format", "{{.Endpoints.docker.Host}}"])
        if endpoint != "unix:///var/run/docker.sock":
            raise RuntimeError("Select the local WSL/Linux Docker Engine context explicitly")
    base = inspect_image(base_image)
    if architecture(base.get("Architecture")) != native_arch or base.get("Os") != "linux":
        raise RuntimeError(f"Cached Android 13 base image must be Linux {native_arch}, matching this Engine")
    resolved = command(["git", "-C", str(source), "rev-parse", SOURCE_SHA + "^{commit}"])
    if resolved != SOURCE_SHA:
        raise RuntimeError("Pinned redroid-script commit is unavailable")

    # No kernel/image builds are parallelized; flock is automatically released on exit.
    import fcntl
    with open(Path(tempfile.gettempdir()) / "autoflow-redroid-magisk.lock", "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("Another Demo Magisk build is running") from error
        output.mkdir(parents=True, exist_ok=False)
        report = {"status": "failed", "source": {"repository": "https://github.com/ayasa520/redroid-script", "sha": SOURCE_SHA},
                  "base_image": {"ref": base_image, "id": base["Id"], "digests": base.get("RepoDigests", []),
                                 "architecture": base.get("Architecture")},
                  "target": OUTPUT_IMAGE, "platform": "linux/" + native_arch,
                  "app_root": "unverified", "android_boot": "unverified"}
        unique_tag = "autoflow/redroid-build:" + uuid.uuid4().hex
        temporary_base = None
        try:
            base_ref = next((digest for digest in base.get("RepoDigests", []) if digest.startswith("redroid/redroid@sha256:")), None)
            if not base_ref:
                temporary_base = "autoflow/redroid-base:" + uuid.uuid4().hex
                command(["docker", "tag", base["Id"], temporary_base])
                base_ref = temporary_base
            report["base_image"]["build_ref"] = base_ref
            with tempfile.TemporaryDirectory(prefix="autoflow-redroid-build-") as temp:
                work = Path(temp)
                checkout = work / "source"
                checkout.mkdir()
                archive = subprocess.run(["git", "-C", str(source), "archive", SOURCE_SHA],
                                         check=True, capture_output=True, timeout=60).stdout
                with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
                    tar.extractall(checkout, filter="data")
                report["patches"] = patch_source(checkout, work, base_ref, unique_tag)
                shutil.copytree(checkout, output / "patched-source")
                # Read constants without importing external modules or triggering download-cache creation.
                tree = ast.parse((checkout / "stuff/magisk.py").read_text())
                magisk_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Magisk")
                values = {node.targets[0].id: ast.literal_eval(node.value) for node in magisk_class.body
                          if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                          and node.targets[0].id in ("dl_link", "act_md5")}
                report["download"] = {"url": values["dl_link"], "upstream_md5": values["act_md5"],
                                      "integrity_note": "MD5 follows upstream; recorded SHA-256 is not an independent signature"}
                env = dict(os.environ, XDG_CACHE_HOME=str(work / "cache"), TMPDIR=str(work / "tmp"),
                           PIP_CACHE_DIR=str(work / "pip-cache"), PIP_DISABLE_PIP_VERSION_CHECK="1",
                           DOCKER_DEFAULT_PLATFORM="linux/" + native_arch)
                (work / "tmp").mkdir()
                apk = work / "cache/redroid/downloads/magisk.apk"
                try:
                    with (output / "build.log").open("w") as log:
                        print(f"Build output: {output / 'build.log'}", flush=True)
                        run_logged([sys.executable, "-m", "venv", str(work / "venv")], checkout, env, log, 120)
                        python = str(work / "venv/bin/python")
                        run_logged([python, "-m", "pip", "install", "-r", "requirements.txt"], checkout, env, log, 600)
                        report["python_packages"] = command([python, "-m", "pip", "freeze"], env=env).splitlines()
                        run_logged([python, "redroid.py", "-a", "13.0.0", "-m"], checkout, env, log, 3600)
                finally:
                    if apk.is_file():
                        data = apk.read_bytes()
                        report["download"].update(sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data),
                            md5_matches_upstream=hashlib.md5(data).hexdigest() == values["act_md5"])
                if not apk.is_file() or not report["download"]["md5_matches_upstream"]:
                    raise RuntimeError("Build finished without a verified Magisk APK")
                shutil.copy2(checkout / "Dockerfile", output / "Dockerfile.generated")
                image = inspect_image(unique_tag)
                if image["Id"] == base["Id"] or architecture(image.get("Architecture")) != native_arch or image.get("Os") != "linux":
                    raise RuntimeError(f"Build did not produce a distinct Linux {native_arch} image")
                if not (checkout / "magisk/system/etc/init/magisk/magisk.apk").is_file():
                    raise RuntimeError("Expected Magisk build content is missing")
                command(["docker", "tag", image["Id"], OUTPUT_IMAGE])
                tagged = inspect_image(OUTPUT_IMAGE)
                if tagged["Id"] != image["Id"]:
                    raise RuntimeError("Final image tag does not match the verified build")
                report["image"] = {"ref": OUTPUT_IMAGE, "id": tagged["Id"], "digests": tagged.get("RepoDigests", []),
                                   "created": tagged.get("Created"), "architecture": tagged.get("Architecture")}
                report["status"] = "built_not_boot_verified"
        except BaseException as error:
            report["error"] = str(error)
            raise
        finally:
            # Remove only our random build alias; preserve the explicitly produced target image.
            report["temporary_tag_cleanup"] = []
            try:
                for tag in (unique_tag, temporary_base):
                    if tag:
                        try:
                            cleanup = subprocess.run(["docker", "image", "rm", tag], capture_output=True, text=True, timeout=60)
                            report["temporary_tag_cleanup"].append({"tag": tag, "exit_code": cleanup.returncode,
                                                                   "output": (cleanup.stdout + cleanup.stderr).strip()})
                        except Exception as error:
                            report["temporary_tag_cleanup"].append({"tag": tag, "error": str(error)})
            finally:
                (output / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[2] / "redroid-script")
    parser.add_argument("--output", type=Path, default=Path(".data/root-builds"))
    parser.add_argument("--base-image", default=os.getenv("REDROID_BASE_IMAGE", BASE_IMAGE),
                        help="Cached Android 13 image matching the native daemon architecture (or REDROID_BASE_IMAGE)")
    args = parser.parse_args()
    output = args.output.resolve() / (time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
    try:
        result = build(args.source.resolve(), output, args.base_image)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:
        print(f"Root build failed: {error}\nEvidence directory (when build started): {output}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
