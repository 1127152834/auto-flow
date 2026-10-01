"""Bounded, never-blocking capture of a worker's stderr (remediation M1, R1-14).

The reader always consumes the pipe, whatever happens to the disk file: a full pipe would
stall the worker. The file is capped and ends with a marker once truncated; a short tail of
recent lines stays in memory for diagnostics. Disk trouble degrades to "no file", never to a
blocked worker or a task error.
"""

from __future__ import annotations

import asyncio
import codecs
import queue
import threading
from collections import deque
from pathlib import Path

READ_BYTES = 8192
QUEUE_CHUNKS = 256
TRUNCATED_MARKER = b"\n[... worker stderr truncated: size limit reached ...]\n"


class StderrSink:
    def __init__(
        self,
        path: Path,
        *,
        limit_bytes: int = 5 * 1024 * 1024,
        tail_lines: int = 200,
        tail_bytes: int = 256 * 1024,
        line_bytes: int = 8192,
    ) -> None:
        if limit_bytes <= len(TRUNCATED_MARKER):
            raise ValueError("limit_bytes must leave room for the truncation marker")
        self.path = path
        self.limit_bytes = limit_bytes
        self.truncated = False
        self.write_failed = False
        self.dropped = False
        self._tail_lines, self._tail_bytes, self._line_bytes = tail_lines, tail_bytes, line_bytes
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._lines: deque[str] = deque()
        self._lines_size = 0
        self._pending = ""
        self._pending_cut = False
        self._queue: queue.Queue[bytes] = queue.Queue(maxsize=QUEUE_CHUNKS)
        self._done = threading.Event()
        self._writer: threading.Thread | None = None
        self._written = 0
        self._lock = threading.Lock()

    @property
    def written_bytes(self) -> int:
        return self._written

    async def drain(self, stream: asyncio.StreamReader) -> None:
        """Consume the stream to EOF. Only cancellation or a broken pipe ends it early."""
        try:
            while chunk := await stream.read(READ_BYTES):
                self._feed(chunk)
                self._enqueue(chunk)
        finally:
            self._feed(b"", final=True)
            self._done.set()
            self._start_writer()

    def tail(self, lines: int = 50) -> list[str]:
        with self._lock:
            recent = list(self._lines)
            if self._pending:
                recent.append(self._pending + (" …" if self._pending_cut else ""))
        return recent[-lines:] if lines > 0 else []

    async def close(self) -> None:
        """Wait for the writer thread; never blocks the loop and never raises."""
        writer = self._writer
        if writer is not None:
            await asyncio.to_thread(writer.join, 10)

    # -- tail ---------------------------------------------------------------------------
    def _feed(self, chunk: bytes, *, final: bool = False) -> None:
        text = self._decoder.decode(chunk, final=final)
        with self._lock:
            for part in text.splitlines(keepends=True):
                complete = part.endswith(("\n", "\r"))
                body = part.rstrip("\r\n")
                room = self._line_bytes - len(self._pending)
                if len(body) > room:
                    body, self._pending_cut = body[: max(room, 0)], True
                self._pending += body
                if complete:
                    self._push(self._pending + (" …" if self._pending_cut else ""))
                    self._pending, self._pending_cut = "", False
            if final and self._pending:
                self._push(self._pending + (" …" if self._pending_cut else ""))
                self._pending, self._pending_cut = "", False

    def _push(self, line: str) -> None:
        self._lines.append(line)
        self._lines_size += len(line.encode("utf-8", errors="replace"))
        while self._lines and (len(self._lines) > self._tail_lines or self._lines_size > self._tail_bytes):
            self._lines_size -= len(self._lines.popleft().encode("utf-8", errors="replace"))

    # -- file ---------------------------------------------------------------------------
    def _start_writer(self) -> None:
        if self._writer is None:
            self._writer = threading.Thread(target=self._write_loop, name="worker-stderr-writer", daemon=True)
            self._writer.start()

    def _enqueue(self, chunk: bytes) -> None:
        if self.write_failed:
            return
        self._start_writer()
        try:
            self._queue.put_nowait(chunk)
        except queue.Full:
            self.dropped = True  # diagnostics only; the worker is never back-pressured

    def _write_loop(self) -> None:
        handle = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            handle = self.path.open("wb")
        except OSError:
            self.write_failed = True
        try:
            while True:
                try:
                    chunk = self._queue.get(timeout=0.05)
                except queue.Empty:
                    if self._done.is_set():
                        break
                    continue
                if handle is None or self.truncated:
                    continue
                room = self.limit_bytes - len(TRUNCATED_MARKER) - self._written
                try:
                    if len(chunk) > room:
                        handle.write(chunk[: max(room, 0)])
                        self._written += max(room, 0)
                        handle.write(TRUNCATED_MARKER)
                        self._written += len(TRUNCATED_MARKER)
                        self.truncated = True
                    else:
                        handle.write(chunk)
                        self._written += len(chunk)
                except OSError:
                    self.write_failed = True
                    handle.close()
                    handle = None
        finally:
            if handle is not None:
                try:
                    handle.close()
                except OSError:
                    self.write_failed = True
