"""Remediation M4 Task 1: which --fingerprint seeds does CloakBrowser 0.5.9 really distinguish?

Launches the real kernel per seed and hashes canvas, WebGL and audio fingerprints. A seed is
"deterministic" when two launches agree; two seeds "collide" when their hashes are equal.

Run: python -m tests.research.seed_range_probe <chrome executable>
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import tempfile

PROBE = """async () => {
  const canvas = document.createElement('canvas'); canvas.width = 240; canvas.height = 60;
  const c = canvas.getContext('2d'); c.textBaseline = 'top'; c.font = '16px Arial';
  c.fillStyle = '#f60'; c.fillRect(10, 10, 100, 30); c.fillStyle = '#069'; c.fillText('seed probe 种子', 4, 20);
  const gl = document.createElement('canvas').getContext('webgl');
  const debug = gl && gl.getExtension('WEBGL_debug_renderer_info');
  const audio = new OfflineAudioContext(1, 44100, 44100);
  const osc = audio.createOscillator(); osc.type = 'triangle'; osc.frequency.value = 10000;
  const comp = audio.createDynamicsCompressor(); osc.connect(comp); comp.connect(audio.destination); osc.start(0);
  const buffer = await audio.startRendering();
  let sum = 0; for (const v of buffer.getChannelData(0).slice(4500, 5000)) sum += Math.abs(v);
  return JSON.stringify({
    canvas: canvas.toDataURL(),
    gpu: debug ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : null,
    audio: sum,
    cores: navigator.hardwareConcurrency, memory: navigator.deviceMemory,
    screen: [screen.width, screen.height],
  });
}"""


async def fingerprint(seed: int) -> str:
    from cloakbrowser import launch_async  # type: ignore[import-untyped]

    browser = await launch_async(headless=True, stealth_args=False, args=["--no-sandbox", f"--fingerprint={seed}", "--fingerprint-platform=windows"])
    try:
        page = await browser.new_page()
        raw = await page.evaluate(PROBE)
    finally:
        await browser.close()
    return hashlib.sha256(raw.encode()).hexdigest()[:16] + " " + json.dumps({k: v for k, v in json.loads(raw).items() if k != "canvas"})


async def main(executable: str) -> None:
    os.environ["CLOAKBROWSER_BINARY_PATH"] = executable
    os.environ.setdefault("CLOAKBROWSER_CACHE_DIR", tempfile.mkdtemp())
    seeds = [10000, 12345, 99999, 102345, 1_012_345, 2_147_483_647, 4_000_000_000, 12345 + 90_000 * 3]
    results = {}
    for seed in seeds:
        first, second = await fingerprint(seed), await fingerprint(seed)
        results[seed] = first
        print(f"{seed:>12}  deterministic={first == second}  {first}")
    print("distinct hashes:", len({value.split()[0] for value in results.values()}), "of", len(results))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
