"""Fixed scrcpy 3.3.4 transport. See docs/references/android-runtime/NOTICE.md.

Protocol source: Genymobile/scrcpy v3.3.4 app/src/control_msg.c and
server/src/main/java/com/genymobile/scrcpy/device/Streamer.java.
Video remains H264; Electron decodes it without adding a transcoder.
"""

import asyncio
import struct
import subprocess
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from autoflow.domain.android.ports import AndroidError
from autoflow.providers.android.mac_runtime import VENDOR, MacAndroidRuntime


class AndroidStream:
    def __init__(self, runtime: MacAndroidRuntime) -> None:
        self.runtime = runtime
        self.identifier = uuid4().hex
        self.scid = "0" + self.identifier[:7]
        self.remote = "/data/local/tmp/autoflow-" + self.identifier + ".jar"
        self.process: subprocess.Popen[bytes] | None = None
        self.video: asyncio.StreamReader | None = None
        self.video_writer: asyncio.StreamWriter | None = None
        self.control: asyncio.StreamWriter | None = None
        self.port: int | None = None
        self.lock = asyncio.Lock()
        self.read_task: asyncio.Task[None] | None = None
        self.control_task: asyncio.Task[None] | None = None
        self.subscribers: set[asyncio.Queue[bytes | None]] = set()
        self.header = b""
        self.config = b""
        self.keyframe = b""
        self.gop: list[bytes] = []
        self.gop_bytes = 0
        self.error: str | None = None
        self.frames = 0
        self.started = time.monotonic()
        self.width = self.height = 0

    async def start(self) -> None:
        try:
            await self.runtime._adb(
                "push", str(self.runtime.root / VENDOR / "scrcpy-server"), self.remote
            )
            self.port = int(
                (
                    await self.runtime._adb(
                        "forward", "tcp:0", "localabstract:scrcpy_" + self.scid
                    )
                ).strip()
            )
            self.process = subprocess.Popen(  # noqa: ASYNC220 -- register process identity before yielding.
                [
                    "adb",
                    "-s",
                    str(self.runtime.serial),
                    "shell",
                    "CLASSPATH=" + self.remote,
                    "app_process",
                    "/",
                    "com.genymobile.scrcpy.Server",
                    "3.3.4",
                    "scid=" + self.scid,
                    "tunnel_forward=true",
                    "audio=false",
                    "control=true",
                    "clipboard_autosync=false",
                    "max_fps=30",
                    "video_bit_rate=2000000",
                    "video_codec=h264",
                    "log_level=warn",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.runtime._remember("embedded", self.process)
            deadline = time.monotonic() + 15
            while True:
                try:
                    self.video, self.video_writer = await asyncio.open_connection(
                        "127.0.0.1", self.port
                    )
                    await asyncio.wait_for(self.video.readexactly(1), 1)
                    break
                except (OSError, asyncio.IncompleteReadError, TimeoutError):
                    if self.video_writer:
                        self.video_writer.close()
                    if time.monotonic() >= deadline or self.process.poll() is not None:
                        raise AndroidError(
                            "ANDROID_STREAM_FAILED",
                            "连续画面启动失败，请检查设备编码器",
                            502,
                        ) from None
                    await asyncio.sleep(0.1)
            reader, self.control = await asyncio.open_connection("127.0.0.1", self.port)
            await asyncio.wait_for(self.video.readexactly(64), 10)
            self.header = await asyncio.wait_for(self.video.readexactly(12), 10)
            codec, self.width, self.height = struct.unpack(">III", self.header)
            if codec != 0x68323634 or not (
                1 <= self.width <= 4096 and 1 <= self.height <= 4096
            ):
                raise AndroidError(
                    "ANDROID_STREAM_FORMAT", "设备未提供兼容的H264画面", 502
                )
            self.read_task = asyncio.create_task(self._read())
            self.control_task = asyncio.create_task(self._drain_control(reader))
        except BaseException:
            await self.close()
            raise

    async def _drain_control(self, reader: asyncio.StreamReader) -> None:
        # Clipboard autosync is disabled. Drain acknowledgments; never expose clipboard contents.
        while await reader.read(65536):
            pass

    async def _read(self) -> None:
        assert self.video is not None
        try:
            while True:
                header = await self.video.readexactly(12)
                pts, size = struct.unpack(">QI", header)
                if size > 8 * 1024 * 1024:
                    raise ValueError("Oversized frame")
                packet = header + await self.video.readexactly(size)
                if pts & (1 << 63):
                    self.config, self.keyframe = packet, b""
                    self.gop, self.gop_bytes = [], 0
                elif pts & (1 << 62):
                    self.keyframe = packet
                    self.gop, self.gop_bytes = [], 0
                if not pts & (1 << 63) and self.keyframe:
                    self.gop.append(packet)
                    self.gop_bytes += len(packet)
                    if self.gop_bytes > 32 * 1024 * 1024:
                        self.keyframe, self.gop, self.gop_bytes = b"", [], 0
                self.frames += 1
                for queue in list(self.subscribers):
                    if queue.full():
                        self.subscribers.discard(queue)
                        while not queue.empty():
                            queue.get_nowait()
                        queue.put_nowait(None)
                    else:
                        queue.put_nowait(packet)
        except (asyncio.IncompleteReadError, OSError, ValueError):
            self.error = "设备画面已断开，请重新连接"
        finally:
            for queue in self.subscribers:
                while queue.full():
                    queue.get_nowait()
                queue.put_nowait(None)

    async def packets(self) -> AsyncIterator[bytes]:
        if self.error or not self.read_task or self.read_task.done():
            raise AndroidError("ANDROID_STREAM_LOST", "设备画面已断开，请重新连接", 503)
        queue: asyncio.Queue[bytes | None] = asyncio.Queue(64)
        self.subscribers.add(queue)
        cached = [self.header, *([self.config] if self.config else []), *self.gop]
        try:
            for packet in cached:
                yield packet
            while (incoming := await queue.get()) is not None:
                yield incoming
        finally:
            self.subscribers.discard(queue)

    async def command(self, command: dict[str, Any]) -> None:
        if self.error or self.control is None or self.control.is_closing():
            raise AndroidError("ANDROID_STREAM_LOST", "设备连接已断开，未发送操作", 503)
        kind = command["kind"]
        if kind == "key":
            packet = struct.pack(
                ">BBIII", 0, command["action"], command["keycode"], 0, 0
            )
        elif kind == "text":
            text = command["text"].encode("utf-8")
            # SET_CLIPBOARD + paste uses Android's Unicode clipboard, not INJECT_TEXT.
            packet = struct.pack(">BQBI", 9, 0, 1, len(text)) + text
        elif kind == "touch":
            packet = struct.pack(
                ">BBQiiHHHII",
                2,
                command["action"],
                0xFFFFFFFFFFFFFFFE,
                command["x"],
                command["y"],
                command["width"],
                command["height"],
                0 if command["action"] in {1, 3} else 65535,
                0,
                0,
            )
        elif kind == "rotate":
            packet = bytes([11])
        else:
            raise AndroidError("ANDROID_INPUT_INVALID", "不支持的输入动作", 422)
        async with self.lock:
            self.control.write(packet)
            try:
                await asyncio.wait_for(self.control.drain(), 5)
            except (OSError, TimeoutError):
                self.error = "输入结果无法确认，请核实设备后再操作"
                raise AndroidError("ANDROID_INPUT_UNKNOWN", self.error, 503) from None

    async def close(self) -> None:
        for task in (self.read_task, self.control_task):
            if task:
                task.cancel()
        await asyncio.gather(
            *(t for t in (self.read_task, self.control_task) if t),
            return_exceptions=True,
        )
        for writer in (self.video_writer, self.control):
            if writer:
                writer.close()
                try:
                    await writer.wait_closed()
                except OSError:
                    pass
        await self.runtime._stop(self.process, "embedded")
        self.process = None
        if self.port is not None:
            await self.runtime._adb("forward", "--remove", "tcp:" + str(self.port))
            self.port = None
        if self.runtime.serial:
            await self.runtime._adb("shell", "rm", "-f", self.remote)
