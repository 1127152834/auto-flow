"""Compare already captured client screenshots; does not automate a browser.

Run: uv run --no-project --with pillow python scripts/compare-android-prototype.py
Capture at 1487x1024 (board), 1489x1022 (others), with 100% zoom.
"""
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/validation/android-exact-2026-09-13'
REF = ROOT / 'docs/references/android-prototype-exact-2026-09-13'
for kind, name in [('board', '01-resource-board.png'), ('manual', '02-manual-console.png'), ('create', '03-create-instances.png'), ('takeover', '04-workflow-takeover.png')]:
    source = Image.open(REF / name).convert('RGB')
    source = source.crop((0, 34, source.width, source.height))
    actual = Image.open(OUT / (kind + '-actual.png')).convert('RGB')
    assert source.size == actual.size, (kind, source.size, actual.size)
    combined = Image.new('RGB', (source.width * 2, source.height))
    combined.paste(source, (0, 0))
    combined.paste(actual, (source.width, 0))
    combined.save(OUT / (kind + '-side-by-side.png'))
    Image.blend(source, actual, .5).save(OUT / (kind + '-overlay.png'))
    ImageEnhance.Contrast(ImageChops.difference(source, actual)).enhance(3).save(OUT / (kind + '-diff.png'))

# Rectangles independently measured from the archived reference, in client pixels.
anchors = {
    'board': [('ad-board', 0, [32,184,1425,600]), ('ad-waiting',0,[32,801,1425,202]), ('ad-device-card ad-card-0',0,[44,297,448,215]), ('ad-device-card ad-card-0',1,[44,539,448,215])],
    'manual': [('ad-screen-panel',0,[32,253,950,705]),('ad-console-sidebar',0,[993,253,467,705]),('ad-phone ',0,[360,319,326,572]),('ad-device-tools',0,[712,327,63,476])],
    'create': [('ad-create-form',0,[33,233,941,691]),('ad-create-preview',0,[990,233,467,691]),('ad-create-footer',0,[0,933,1489,89]),('ad-quantity',0,[795,303,151,42]),('ad-instance-types',0,[216,771,730,74])],
    'takeover': [('ad-screen-panel',0,[48,311,935,652]),('ad-console-sidebar',0,[998,311,445,652]),('ad-phone ',0,[369,355,297,561]),('ad-device-tools',0,[862,411,72,294])],
}
geometry = json.loads((OUT / 'geometry-actual.json').read_text())
checks = []
for page, targets in anchors.items():
    for cls, index, expected in targets:
        rect = [r for r in geometry[page] if r['className'] == cls][index]
        actual = [rect[key] for key in ['x','y','width','height']]
        delta = [round(abs(a-b),3) for a,b in zip(actual,expected,strict=True)]
        tolerance = 2 if cls in {'ad-device-tools','ad-quantity','ad-instance-types'} else 4
        checks.append({'page':page,'region':cls,'index':index,'source':expected,'actual':actual,'delta':delta,'tolerance':tolerance,'pass':max(delta)<=tolerance})
result = {'date':'2026-09-13','method':'reference rectangle measurements versus CUA DOM bounding rectangles; original OS titlebar excluded','checks':checks,'allMeasuredRegionsPass':all(c['pass'] for c in checks),'scope':'Measured regions only; not a claim that every image pixel or every text glyph is identical.'}
(OUT/'geometry-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print('Measured geometry:',sum(c['pass'] for c in checks),'/',len(checks))
