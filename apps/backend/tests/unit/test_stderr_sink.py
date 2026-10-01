"""Remediation M1 R1-14: stderr is always drained, bounded and decoded safely."""

import asyncio
from pathlib import Path

import pytest

from autoflow.infrastructure.process.stderr_sink import (
    READ_BYTES,
    TRUNCATED_MARKER,
    StderrSink,
)


async def feed(sink: StderrSink, *chunks: bytes) -> None:
    reader = asyncio.StreamReader()
    task = asyncio.create_task(sink.drain(reader))
    for chunk in chunks:
        reader.feed_data(chunk)
        await asyncio.sleep(0)
    reader.feed_eof()
    await asyncio.wait_for(task, 10)
    await sink.close()


@pytest.mark.asyncio
async def test_plain_lines_reach_the_file_and_the_tail(tmp_path: Path):
    sink = StderrSink(tmp_path / "w.log")
    await feed(sink, b"one\ntwo\r\nthree")
    assert sink.tail() == ["one", "two", "three"]
    assert (tmp_path / "w.log").read_bytes() == b"one\ntwo\r\nthree"
    assert not sink.truncated and not sink.write_failed


@pytest.mark.asyncio
async def test_a_70k_line_without_newline_is_consumed_and_the_tail_line_is_cut(tmp_path: Path):
    sink = StderrSink(tmp_path / "w.log", line_bytes=8192)
    await feed(sink, b"x" * 70_000, b"y" * 1000)  # never a newline: must still be fully read
    tail = sink.tail()
    assert len(tail) == 1 and len(tail[0]) <= 8192 + 2
    assert (tmp_path / "w.log").stat().st_size == 71_000


@pytest.mark.asyncio
async def test_output_past_the_limit_is_truncated_with_a_marker_and_keeps_draining(tmp_path: Path):
    limit = 20_000
    sink = StderrSink(tmp_path / "w.log", limit_bytes=limit)
    chunks = [(b"line %06d\n" % index) * 100 for index in range(200)]  # ~200 KB
    await feed(sink, *chunks)
    data = (tmp_path / "w.log").read_bytes()
    assert sink.truncated and data.endswith(TRUNCATED_MARKER) and len(data) <= limit
    assert sink.tail()[-1].startswith("line 000199")  # reading continued after the cap


@pytest.mark.asyncio
async def test_tail_respects_line_and_byte_limits(tmp_path: Path):
    sink = StderrSink(tmp_path / "w.log", tail_lines=5, tail_bytes=60)
    await feed(sink, b"".join(b"row-%02d-padding\n" % index for index in range(40)))
    tail = sink.tail(50)
    assert len(tail) <= 5 and sum(len(line) for line in tail) <= 60
    assert tail[-1] == "row-39-padding"


@pytest.mark.asyncio
async def test_utf8_split_across_reads_and_invalid_bytes_are_decoded_safely(tmp_path: Path):
    sink = StderrSink(tmp_path / "w.log")
    encoded = "错误：失败\n".encode()
    await feed(sink, encoded[:4], encoded[4:], b"bad \xff\xfe byte\n")
    assert sink.tail()[0] == "错误：失败"
    assert "�" in sink.tail()[1]


@pytest.mark.asyncio
async def test_an_unwritable_destination_still_drains_and_reports_unavailable(tmp_path: Path):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("x")
    sink = StderrSink(blocker / "w.log")  # parent is a file: opening must fail
    await feed(sink, b"still read\n" * 10_000)
    assert sink.write_failed
    assert sink.tail()[-1] == "still read"


@pytest.mark.asyncio
async def test_a_producer_faster_than_the_disk_is_never_back_pressured(tmp_path: Path, monkeypatch):
    sink = StderrSink(tmp_path / "w.log")
    gate = asyncio.Event()
    original = sink._write_loop

    def slow_loop():
        import time

        while not gate.is_set():
            time.sleep(0.01)
        original()

    monkeypatch.setattr(sink, "_write_loop", slow_loop)
    reader = asyncio.StreamReader()
    task = asyncio.create_task(sink.drain(reader))
    for _ in range(600):  # more chunks than the bounded queue holds
        reader.feed_data(b"z" * READ_BYTES)
        await asyncio.sleep(0)
    reader.feed_eof()
    await asyncio.wait_for(task, 10)  # drain finished although the writer was stalled
    assert sink.dropped
    gate.set()
    await sink.close()
