"""Allure HTML builder migrated from WebRPA@5ccb900e.

Source: backend/app/executors/allure_report_builder.py. License: LICENSE.WebRPA.
"""
# mypy: ignore-errors
# ruff: noqa: BLE001, DTZ005, DTZ006, I001, S110, UP045

"""
Allure 风格 HTML 报告生成器
纯 Python 实现，生成高度还原 Allure 官方风格的单页应用报告
无需 Java / allure-commandline
"""
import json
import base64
from pathlib import Path
from datetime import datetime
from typing import Optional


def _fmt_dur(ms: int) -> str:
    if ms <= 0:
        return "0ms"
    if ms < 1000:
        return f"{ms}ms"
    if ms < 60000:
        return f"{ms / 1000:.1f}s"
    m = ms // 60000
    s = (ms % 60000) / 1000
    return f"{m}m {s:.0f}s"


def _fmt_ts(ts_ms: int) -> str:
    try:
        return datetime.fromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "-"


def _img_b64(path: Path) -> Optional[str]:
    try:
        ext = path.suffix.lower().lstrip(".")
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                "png": "image/png", "gif": "image/gif",
                "webp": "image/webp"}.get(ext, "image/png")
        data = base64.b64encode(path.read_bytes()).decode()
        return f"data:{mime};base64,{data}"
    except Exception:
        return None


def build_report(results: list, suite_name: str, results_dir: Path) -> str:
    """构建完整的 Allure 风格 HTML 报告（单文件，无外部依赖）"""
    total   = len(results)
    passed  = sum(1 for r in results if r.get("status") == "passed")
    failed  = sum(1 for r in results if r.get("status") == "failed")
    broken  = sum(1 for r in results if r.get("status") == "broken")
    skipped = sum(1 for r in results if r.get("status") == "skipped")
    pass_rate = round(passed / total * 100) if total else 0

    # 时间范围
    starts = [r.get("start", 0) for r in results if r.get("start")]
    stops  = [r.get("stop",  0) for r in results if r.get("stop")]
    t_start = min(starts) if starts else 0
    t_stop  = max(stops)  if stops  else 0
    total_dur = t_stop - t_start if t_stop > t_start else 0
    gen_time = datetime.now().strftime("%Y/%m/%d")
    t_start_str = _fmt_ts(t_start).split(' ')[1] if t_start else '--'
    t_stop_str  = _fmt_ts(t_stop).split(' ')[1]  if t_stop  else '--'
    time_range  = f"{t_start_str} – {t_stop_str} ({_fmt_dur(total_dur)})"

    # 严重程度分布
    sev_map = {"blocker": 0, "critical": 0, "normal": 0, "minor": 0, "trivial": 0}
    for r in results:
        labels = r.get("labels", [])
        sev = next((l["value"] for l in labels if l["name"] == "severity"), "normal")
        if sev in sev_map:
            sev_map[sev] += 1

    # 构建每个测试用例的 JS 数据
    cases_data = []
    for r in results:
        labels = r.get("labels", [])
        cases_data.append({
            "uuid":        r.get("uuid", ""),
            "name":        r.get("name", "未命名"),
            "desc":        r.get("description", ""),
            "status":      r.get("status", "unknown"),
            "start":       r.get("start", 0),
            "stop":        r.get("stop", 0),
            "dur":         r.get("stop", 0) - r.get("start", 0),
            "suite":       next((l["value"] for l in labels if l["name"] == "suite"), suite_name),
            "severity":    next((l["value"] for l in labels if l["name"] == "severity"), "normal"),
            "testId":      next((l["value"] for l in labels if l["name"] == "testId"), ""),
            "steps":       _build_steps_data(r.get("steps", [])),
            "attachments": _build_attachments_data(r.get("attachments", []), results_dir),
            "failMsg":     r.get("statusDetails", {}).get("message", ""),
        })

    cases_json = json.dumps(cases_data, ensure_ascii=False)
    chart_json = json.dumps({
        "passed": passed, "failed": failed,
        "broken": broken, "skipped": skipped,
        "total": total, "passRate": pass_rate,
    })
    sev_json = json.dumps(sev_map)

    return (
        _HTML_HEAD.format(suite_name=suite_name)
        + _HTML_BODY.format(
            suite_name=suite_name, gen_time=gen_time, time_range=time_range,
            total=total, passed=passed, failed=failed, broken=broken, skipped=skipped,
            pass_rate=pass_rate,
        )
        + _HTML_SCRIPT.format(
            cases_json=cases_json, chart_json=chart_json, sev_json=sev_json,
        )
    )


def _build_steps_data(steps: list) -> list:
    return [
        {
            "name": s.get("name", "步骤"),
            "status": s.get("status", "passed"),
            "desc": s.get("description", "") or s.get("desc", ""),
        }
        for s in steps
    ]


def _build_attachments_data(attachments: list, results_dir: Path) -> list:
    out = []
    for att in attachments:
        src  = att.get("source", "")
        mime = att.get("type", "text/plain")
        name = att.get("name", "附件")
        path = results_dir / src
        if mime.startswith("image/") and path.exists():
            b64 = _img_b64(path)
            if b64:
                out.append({"name": name, "type": "image", "data": b64})
        elif mime.startswith("text/") and path.exists():
            try:
                content = path.read_text(encoding="utf-8", errors="replace")[:3000]
                out.append({"name": name, "type": "text", "data": content})
            except Exception:
                pass
    return out


# ─────────────────────────────────────────────────────────────────────────────
# HTML 模板（分三段：head/css、body结构、script逻辑）
# ─────────────────────────────────────────────────────────────────────────────

_HTML_HEAD = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{suite_name} - Allure Report</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;background:#f5f5f5;color:#333;display:flex;height:100vh;overflow:hidden}}
#nav{{width:56px;background:#2a2a2a;display:flex;flex-direction:column;align-items:center;padding:0;flex-shrink:0;z-index:100}}
#nav .logo{{width:56px;height:56px;background:#e05c3a;display:flex;align-items:center;justify-content:center;flex-shrink:0}}
#nav .logo svg{{width:28px;height:28px}}
.nav-item{{width:56px;height:52px;display:flex;flex-direction:column;align-items:center;justify-content:center;cursor:pointer;color:#aaa;font-size:9px;gap:3px;transition:all .15s;border-left:3px solid transparent;user-select:none}}
.nav-item:hover{{color:#fff;background:rgba(255,255,255,.06)}}
.nav-item.active{{color:#fff;border-left-color:#e05c3a;background:rgba(255,255,255,.08)}}
.nav-item svg{{width:18px;height:18px}}
#main{{flex:1;display:flex;flex-direction:column;overflow:hidden}}
#topbar{{background:#fff;border-bottom:1px solid #e8e8e8;padding:0 24px;height:56px;display:flex;align-items:center;gap:16px;flex-shrink:0}}
#topbar .report-title{{font-size:15px;font-weight:600;color:#333}}
#topbar .report-meta{{font-size:12px;color:#999;margin-left:4px}}
#pages{{flex:1;overflow-y:auto;background:#f5f5f5}}
.page{{display:none;padding:24px;animation:fadeIn .2s ease}}
.page.active{{display:block}}
@keyframes fadeIn{{from{{opacity:0;transform:translateY(4px)}}to{{opacity:1;transform:none}}}}
.overview-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.card{{background:#fff;border-radius:4px;box-shadow:0 1px 3px rgba(0,0,0,.08);overflow:hidden}}
.card-header{{padding:12px 16px;border-bottom:1px solid #f0f0f0;font-size:13px;font-weight:600;color:#555;display:flex;align-items:center;gap:8px}}
.card-body{{padding:16px}}
.stat-hero{{display:flex;align-items:center;gap:24px;padding:20px 24px}}
.stat-num .big{{font-size:48px;font-weight:300;color:#333;line-height:1}}
.stat-num .lbl{{font-size:12px;color:#999;margin-top:4px}}
.donut-wrap{{position:relative;width:120px;height:120px;flex-shrink:0}}
.donut-wrap canvas{{position:absolute;top:0;left:0}}
.donut-center{{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);text-align:center}}
.donut-center .pct{{font-size:22px;font-weight:600;color:#333}}
.donut-center .lbl{{font-size:11px;color:#999}}
.suite-row{{display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid #f5f5f5}}
.suite-row:last-child{{border-bottom:none}}
.suite-name{{font-size:13px;color:#555;width:120px;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.suite-bar{{flex:1;height:20px;display:flex;border-radius:2px;overflow:hidden}}
.suite-bar-seg{{height:100%;transition:opacity .15s}}
.suite-bar-seg:hover{{opacity:.8}}
.suite-count{{font-size:12px;color:#999;width:30px;text-align:right;flex-shrink:0}}
.sev-row{{display:flex;align-items:center;gap:10px;padding:6px 0}}
.sev-dot{{width:10px;height:10px;border-radius:50%;flex-shrink:0}}
.sev-name{{font-size:13px;color:#555;flex:1}}
.sev-bar-wrap{{flex:2;height:8px;background:#f0f0f0;border-radius:4px;overflow:hidden}}
.sev-bar-fill{{height:100%;border-radius:4px;transition:width .4s ease}}
.sev-val{{font-size:12px;color:#999;width:24px;text-align:right}}
.cases-toolbar{{display:flex;align-items:center;gap:8px;margin-bottom:16px;flex-wrap:wrap}}
.filter-btn{{padding:5px 12px;border-radius:3px;border:1px solid #ddd;background:#fff;font-size:12px;cursor:pointer;color:#555;transition:all .15s}}
.filter-btn:hover{{border-color:#e05c3a;color:#e05c3a}}
.filter-btn.active{{background:#e05c3a;border-color:#e05c3a;color:#fff}}
.search-box{{flex:1;max-width:280px;padding:5px 10px;border:1px solid #ddd;border-radius:3px;font-size:13px;outline:none}}
.search-box:focus{{border-color:#e05c3a}}
.case-table{{background:#fff;border-radius:4px;box-shadow:0 1px 3px rgba(0,0,0,.08);overflow:hidden}}
.case-table-header{{display:grid;grid-template-columns:32px 1fr 90px 80px 80px;padding:10px 16px;background:#fafafa;border-bottom:1px solid #eee;font-size:12px;color:#999;font-weight:600;text-transform:uppercase;letter-spacing:.04em}}
.case-row{{display:grid;grid-template-columns:32px 1fr 90px 80px 80px;padding:10px 16px;border-bottom:1px solid #f5f5f5;cursor:pointer;transition:background .1s;align-items:center}}
.case-row:hover{{background:#fafafa}}
.case-row:last-child{{border-bottom:none}}
.status-dot{{width:10px;height:10px;border-radius:50%;flex-shrink:0}}
.case-name{{font-size:13px;color:#333;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding-right:8px}}
.case-suite{{font-size:12px;color:#999;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.sev-badge{{display:inline-block;padding:2px 7px;border-radius:10px;font-size:11px;font-weight:500}}
#drawer{{position:fixed;top:0;right:-520px;width:520px;height:100vh;background:#fff;box-shadow:-4px 0 20px rgba(0,0,0,.12);z-index:200;transition:right .25s cubic-bezier(.4,0,.2,1);display:flex;flex-direction:column}}
#drawer.open{{right:0}}
#drawer-header{{padding:16px 20px;border-bottom:1px solid #eee;display:flex;align-items:flex-start;gap:12px;flex-shrink:0}}
#drawer-close{{margin-left:auto;cursor:pointer;color:#aaa;padding:4px;border-radius:3px;transition:all .15s;flex-shrink:0}}
#drawer-close:hover{{color:#333;background:#f5f5f5}}
#drawer-body{{flex:1;overflow-y:auto;padding:20px}}
.drawer-section{{margin-bottom:20px}}
.drawer-section-title{{font-size:11px;font-weight:700;color:#999;text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px}}
.step-item{{display:flex;align-items:flex-start;gap:10px;padding:8px 12px;border-radius:4px;margin-bottom:4px}}
.step-icon{{width:18px;height:18px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:#fff;flex-shrink:0;margin-top:1px}}
.step-name{{font-size:13px;color:#333;line-height:1.4}}
.step-desc{{font-size:12px;color:#999;margin-top:2px}}
.att-img{{max-width:100%;border-radius:4px;border:1px solid #eee;margin-top:6px}}
.att-text{{background:#f8f8f8;border:1px solid #eee;border-radius:4px;padding:10px;font-size:12px;font-family:monospace;white-space:pre-wrap;overflow-x:auto;margin-top:6px;max-height:200px;overflow-y:auto}}
.fail-box{{background:#fff5f5;border:1px solid #ffd0cc;border-radius:4px;padding:12px;font-size:13px;color:#c0392b;margin-bottom:16px}}
.timeline-wrap{{background:#fff;border-radius:4px;box-shadow:0 1px 3px rgba(0,0,0,.08);padding:20px;overflow-x:auto}}
.tl-row{{display:flex;align-items:center;gap:10px;margin-bottom:6px}}
.tl-label{{width:160px;font-size:12px;color:#555;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex-shrink:0;text-align:right}}
.tl-track{{flex:1;height:20px;background:#f5f5f5;border-radius:2px;position:relative;min-width:200px}}
.tl-bar{{position:absolute;height:100%;border-radius:2px;transition:opacity .15s;cursor:pointer}}
.tl-bar:hover{{opacity:.75}}
@media(max-width:900px){{.overview-grid{{grid-template-columns:1fr}}}}
::-webkit-scrollbar{{width:6px;height:6px}}
::-webkit-scrollbar-track{{background:transparent}}
::-webkit-scrollbar-thumb{{background:#ddd;border-radius:3px}}
::-webkit-scrollbar-thumb:hover{{background:#bbb}}
</style>
</head>
<body>
"""

_HTML_BODY = r"""
<nav id="nav">
  <div class="logo">
    <svg viewBox="0 0 32 32" fill="none"><circle cx="16" cy="16" r="14" fill="white" fill-opacity=".15"/><path d="M10 22 L16 10 L22 22" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M12.5 18 H19.5" stroke="white" stroke-width="2" stroke-linecap="round"/></svg>
  </div>
  <div class="nav-item active" data-page="overview" onclick="showPage('overview',this)" title="总览">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
    总览
  </div>
  <div class="nav-item" data-page="suites" onclick="showPage('suites',this)" title="测试套">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 7h18M3 12h18M3 17h18"/></svg>
    测试套
  </div>
  <div class="nav-item" data-page="cases" onclick="showPage('cases',this)" title="用例">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/><path d="M9 12l2 2 4-4"/></svg>
    用例
  </div>
  <div class="nav-item" data-page="timeline" onclick="showPage('timeline',this)" title="时间线">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 12h18M3 6h6M3 18h6M15 6h6M15 18h6"/></svg>
    时间线
  </div>
</nav>
<div id="main">
  <div id="topbar">
    <div>
      <span class="report-title">ALLURE REPORT {gen_time}</span>
      <span class="report-meta">{time_range}</span>
    </div>
    <div style="margin-left:auto;font-size:13px;color:#555;font-weight:500">{suite_name}</div>
  </div>
  <div id="pages">

    <!-- 总览页 -->
    <div class="page active" id="page-overview">
      <div class="overview-grid">
        <div style="display:flex;flex-direction:column;gap:16px">
          <div class="card">
            <div class="card-body">
              <div class="stat-hero">
                <div class="stat-num">
                  <div class="big">{total}</div>
                  <div class="lbl">测试用例</div>
                </div>
                <div class="donut-wrap">
                  <canvas id="donutCanvas" width="120" height="120"></canvas>
                  <div class="donut-center">
                    <div class="pct">{pass_rate}%</div>
                    <div class="lbl">通过率</div>
                  </div>
                </div>
                <div style="display:flex;flex-direction:column;gap:8px;font-size:13px">
                  <div style="display:flex;align-items:center;gap:8px"><span style="width:10px;height:10px;border-radius:50%;background:#97cc64;display:inline-block"></span><span style="color:#555">通过</span><strong style="margin-left:auto;padding-left:16px">{passed}</strong></div>
                  <div style="display:flex;align-items:center;gap:8px"><span style="width:10px;height:10px;border-radius:50%;background:#fd5a3e;display:inline-block"></span><span style="color:#555">失败</span><strong style="margin-left:auto;padding-left:16px">{failed}</strong></div>
                  <div style="display:flex;align-items:center;gap:8px"><span style="width:10px;height:10px;border-radius:50%;background:#ffa94d;display:inline-block"></span><span style="color:#555">中断</span><strong style="margin-left:auto;padding-left:16px">{broken}</strong></div>
                  <div style="display:flex;align-items:center;gap:8px"><span style="width:10px;height:10px;border-radius:50%;background:#aaa;display:inline-block"></span><span style="color:#555">跳过</span><strong style="margin-left:auto;padding-left:16px">{skipped}</strong></div>
                </div>
              </div>
            </div>
          </div>
          <div class="card">
            <div class="card-header">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 7h18M3 12h18M3 17h18"/></svg>
              测试套件
            </div>
            <div class="card-body" id="suitesOverview"></div>
          </div>
          <div class="card">
            <div class="card-header">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
              严重程度
            </div>
            <div class="card-body" id="severityOverview"></div>
          </div>
        </div>
        <div style="display:flex;flex-direction:column;gap:16px">
          <div class="card">
            <div class="card-header">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
              趋势
            </div>
            <div class="card-body"><canvas id="trendCanvas" width="400" height="120"></canvas></div>
          </div>
          <div class="card">
            <div class="card-header">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 6h16M4 10h16M4 14h8"/></svg>
              类别 <span style="font-weight:400;color:#aaa;font-size:12px;margin-left:4px">共 <span id="catTotal">0</span> 项</span>
            </div>
            <div class="card-body" id="categoryOverview"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- 测试套页 -->
    <div class="page" id="page-suites">
      <div class="card">
        <div class="card-header">测试套件详情</div>
        <div class="card-body" id="suitesDetail"></div>
      </div>
    </div>

    <!-- 用例列表页 -->
    <div class="page" id="page-cases">
      <div class="cases-toolbar">
        <button class="filter-btn active" onclick="filterCases('all',this)">全部 ({total})</button>
        <button class="filter-btn" onclick="filterCases('passed',this)" style="color:#97cc64">通过 ({passed})</button>
        <button class="filter-btn" onclick="filterCases('failed',this)" style="color:#fd5a3e">失败 ({failed})</button>
        <button class="filter-btn" onclick="filterCases('broken',this)" style="color:#ffa94d">中断 ({broken})</button>
        <button class="filter-btn" onclick="filterCases('skipped',this)" style="color:#aaa">跳过 ({skipped})</button>
        <input class="search-box" type="text" placeholder="搜索用例名称..." oninput="searchCases(this.value)">
      </div>
      <div class="case-table">
        <div class="case-table-header">
          <div></div><div>用例名称</div><div>严重程度</div>
          <div style="text-align:right">耗时</div><div style="text-align:right">状态</div>
        </div>
        <div id="casesList"></div>
      </div>
    </div>

    <!-- 时间线页 -->
    <div class="page" id="page-timeline">
      <div class="timeline-wrap" id="timelineWrap"></div>
    </div>

  </div>
</div>

<!-- 详情抽屉 -->
<div id="drawer">
  <div id="drawer-header">
    <div id="drawer-status-dot" style="width:12px;height:12px;border-radius:50%;flex-shrink:0;margin-top:3px"></div>
    <div>
      <div id="drawer-name" style="font-size:15px;font-weight:600;color:#333;line-height:1.3"></div>
      <div id="drawer-meta" style="font-size:12px;color:#999;margin-top:4px"></div>
    </div>
    <div id="drawer-close" onclick="closeDrawer()">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
    </div>
  </div>
  <div id="drawer-body"></div>
</div>
<div id="drawer-overlay" onclick="closeDrawer()" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.3);z-index:199"></div>
"""

_HTML_SCRIPT = r"""
<script>
const CASES = {cases_json};
const CHART = {chart_json};
const SEV   = {sev_json};
const STATUS_COLOR = {{passed:'#97cc64',failed:'#fd5a3e',broken:'#ffa94d',skipped:'#aaa',unknown:'#aaa'}};
const STATUS_LABEL = {{passed:'通过',failed:'失败',broken:'中断',skipped:'跳过',unknown:'未知'}};
const SEV_COLOR = {{blocker:'#fd5a3e',critical:'#ffa94d',normal:'#97cc64',minor:'#aaa',trivial:'#ccc'}};
const SEV_LABEL = {{blocker:'阻塞',critical:'严重',normal:'一般',minor:'次要',trivial:'轻微'}};
let currentFilter='all', currentSearch='';

function showPage(name,el){{
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
  document.getElementById('page-'+name).classList.add('active');
  el.classList.add('active');
  if(name==='timeline') renderTimeline();
}}

function drawDonut(){{
  const canvas=document.getElementById('donutCanvas');
  if(!canvas) return;
  const ctx=canvas.getContext('2d');
  if(!CHART.total) return;
  const segs=[
    {{v:CHART.passed,c:'#97cc64'}},{{v:CHART.failed,c:'#fd5a3e'}},
    {{v:CHART.broken,c:'#ffa94d'}},{{v:CHART.skipped,c:'#aaa'}}
  ].filter(s=>s.v>0);
  let angle=-Math.PI/2;
  const cx=60,cy=60,r=52,ir=36;
  segs.forEach(s=>{{
    const a=(s.v/CHART.total)*Math.PI*2;
    ctx.beginPath();ctx.moveTo(cx,cy);ctx.arc(cx,cy,r,angle,angle+a);
    ctx.closePath();ctx.fillStyle=s.c;ctx.fill();angle+=a;
  }});
  ctx.beginPath();ctx.arc(cx,cy,ir,0,Math.PI*2);ctx.fillStyle='#fff';ctx.fill();
}}

function drawTrend(){{
  const canvas=document.getElementById('trendCanvas');
  if(!canvas) return;
  const ctx=canvas.getContext('2d');
  const W=canvas.offsetWidth||400,H=120;
  canvas.width=W;
  const pts=[
    {{p:Math.max(0,CHART.passRate-15)}},{{p:Math.max(0,CHART.passRate-8)}},
    {{p:Math.max(0,CHART.passRate-3)}},{{p:CHART.passRate}},{{p:CHART.passRate}}
  ];
  const pad={{l:30,r:20,t:10,b:30}};
  const iW=W-pad.l-pad.r,iH=H-pad.t-pad.b;
  ctx.strokeStyle='#f0f0f0';ctx.lineWidth=1;
  [0,25,50,75,100].forEach(v=>{{
    const y=pad.t+iH-(v/100)*iH;
    ctx.beginPath();ctx.moveTo(pad.l,y);ctx.lineTo(W-pad.r,y);ctx.stroke();
    ctx.fillStyle='#bbb';ctx.font='10px sans-serif';ctx.textAlign='right';
    ctx.fillText(v+'%',pad.l-4,y+3);
  }});
  const xs=pts.map((_,i)=>pad.l+(i/(pts.length-1))*iW);
  const ys=pts.map(p=>pad.t+iH-(p.p/100)*iH);
  ctx.beginPath();ctx.moveTo(xs[0],ys[0]);
  for(let i=1;i<xs.length;i++) ctx.lineTo(xs[i],ys[i]);
  ctx.lineTo(xs[xs.length-1],pad.t+iH);ctx.lineTo(xs[0],pad.t+iH);ctx.closePath();
  ctx.fillStyle='rgba(151,204,100,.15)';ctx.fill();
  ctx.beginPath();ctx.moveTo(xs[0],ys[0]);
  for(let i=1;i<xs.length;i++) ctx.lineTo(xs[i],ys[i]);
  ctx.strokeStyle='#97cc64';ctx.lineWidth=2;ctx.stroke();
  xs.forEach((x,i)=>{{
    ctx.beginPath();ctx.arc(x,ys[i],4,0,Math.PI*2);ctx.fillStyle='#97cc64';ctx.fill();
    ctx.fillStyle='#fff';ctx.beginPath();ctx.arc(x,ys[i],2,0,Math.PI*2);ctx.fill();
  }});
}}

function renderSuitesOverview(){{
  const suites={{}};
  CASES.forEach(c=>{{
    if(!suites[c.suite]) suites[c.suite]={{passed:0,failed:0,broken:0,skipped:0,total:0}};
    suites[c.suite][c.status]=(suites[c.suite][c.status]||0)+1;
    suites[c.suite].total++;
  }});
  const el=document.getElementById('suitesOverview');
  if(!el) return;
  let html='';
  Object.entries(suites).forEach(([name,s])=>{{
    const t=s.total;
    html+=`<div class="suite-row">
      <div class="suite-name" title="${{name}}">${{name}}</div>
      <div class="suite-bar">
        ${{s.failed?`<div class="suite-bar-seg" style="width:${{s.failed/t*100}}%;background:#fd5a3e"></div>`:''}}
        ${{s.broken?`<div class="suite-bar-seg" style="width:${{s.broken/t*100}}%;background:#ffa94d"></div>`:''}}
        ${{s.skipped?`<div class="suite-bar-seg" style="width:${{s.skipped/t*100}}%;background:#aaa"></div>`:''}}
        ${{s.passed?`<div class="suite-bar-seg" style="width:${{s.passed/t*100}}%;background:#97cc64"></div>`:''}}
      </div>
      <div class="suite-count">${{t}}</div>
    </div>`;
  }});
  el.innerHTML=html||'<div style="color:#bbb;font-size:13px;padding:8px 0">暂无数据</div>';
}}

function renderSeverityOverview(){{
  const el=document.getElementById('severityOverview');
  if(!el) return;
  const total=Object.values(SEV).reduce((a,b)=>a+b,0)||1;
  const items=[
    {{key:'blocker',label:'阻塞',color:'#fd5a3e'}},
    {{key:'critical',label:'严重',color:'#ffa94d'}},
    {{key:'normal',label:'一般',color:'#97cc64'}},
    {{key:'minor',label:'次要',color:'#aaa'}},
    {{key:'trivial',label:'轻微',color:'#ddd'}},
  ];
  let html='';
  items.forEach(it=>{{
    const v=SEV[it.key]||0;
    html+=`<div class="sev-row">
      <div class="sev-dot" style="background:${{it.color}}"></div>
      <div class="sev-name">${{it.label}}</div>
      <div class="sev-bar-wrap"><div class="sev-bar-fill" style="width:${{v/total*100}}%;background:${{it.color}}"></div></div>
      <div class="sev-val">${{v}}</div>
    </div>`;
  }});
  el.innerHTML=html;
}}

function renderCategoryOverview(){{
  const cats={{}};
  CASES.forEach(c=>{{
    if(c.status!=='passed'){{
      const key=STATUS_LABEL[c.status]||c.status;
      cats[key]=(cats[key]||0)+1;
    }}
  }});
  const el=document.getElementById('categoryOverview');
  const totalEl=document.getElementById('catTotal');
  if(!el) return;
  const entries=Object.entries(cats);
  if(totalEl) totalEl.textContent=entries.length;
  if(!entries.length){{
    el.innerHTML='<div style="color:#bbb;font-size:13px;padding:8px 0;text-align:center">没有信息</div>';
    return;
  }}
  const maxV=Math.max(...entries.map(e=>e[1]));
  let html='';
  entries.forEach(([name,v])=>{{
    html+=`<div class="suite-row">
      <div class="suite-name">${{name}}</div>
      <div class="suite-bar"><div class="suite-bar-seg" style="width:${{v/maxV*100}}%;background:#fd5a3e"></div></div>
      <div class="suite-count">${{v}}</div>
    </div>`;
  }});
  el.innerHTML=html;
}}

function renderSuitesDetail(){{
  const el=document.getElementById('suitesDetail');
  if(!el) return;
  const suites={{}};
  CASES.forEach(c=>{{
    if(!suites[c.suite]) suites[c.suite]=[];
    suites[c.suite].push(c);
  }});
  let html='';
  Object.entries(suites).forEach(([name,cases])=>{{
    const p=cases.filter(c=>c.status==='passed').length;
    const f=cases.filter(c=>c.status==='failed').length;
    const b=cases.filter(c=>c.status==='broken').length;
    const s=cases.filter(c=>c.status==='skipped').length;
    html+=`<div style="margin-bottom:20px">
      <div style="font-size:14px;font-weight:600;color:#333;margin-bottom:10px;padding-bottom:8px;border-bottom:2px solid #f0f0f0;display:flex;align-items:center;gap:10px">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 7h18M3 12h18M3 17h18"/></svg>
        ${{name}}
        <span style="font-weight:400;font-size:12px;color:#aaa">${{cases.length}} 个用例</span>
        <div style="margin-left:auto;display:flex;gap:8px;font-size:12px">
          ${{p?`<span style="color:#97cc64">✓ ${{p}}</span>`:''}}
          ${{f?`<span style="color:#fd5a3e">✗ ${{f}}</span>`:''}}
          ${{b?`<span style="color:#ffa94d">! ${{b}}</span>`:''}}
          ${{s?`<span style="color:#aaa">– ${{s}}</span>`:''}}
        </div>
      </div>`;
    cases.forEach(c=>{{
      const color=STATUS_COLOR[c.status]||'#aaa';
      html+=`<div class="case-row" onclick="openDrawer(${{CASES.indexOf(c)}})" style="grid-template-columns:32px 1fr 90px 80px 80px">
        <div><span class="status-dot" style="background:${{color}}"></span></div>
        <div class="case-name">${{c.name}}</div>
        <div><span class="sev-badge" style="background:${{SEV_COLOR[c.severity]||'#aaa'}}22;color:${{SEV_COLOR[c.severity]||'#aaa'}}">${{SEV_LABEL[c.severity]||c.severity}}</span></div>
        <div style="font-size:12px;color:#999;text-align:right">${{fmtDur(c.dur)}}</div>
        <div style="text-align:right"><span style="color:${{color}};font-size:12px;font-weight:600">${{STATUS_LABEL[c.status]||c.status}}</span></div>
      </div>`;
    }});
    html+='</div>';
  }});
  el.innerHTML=html||'<div style="color:#bbb;padding:20px;text-align:center">暂无数据</div>';
}}

function renderCasesList(){{
  const el=document.getElementById('casesList');
  if(!el) return;
  const filtered=CASES.filter(c=>{{
    const matchStatus=currentFilter==='all'||c.status===currentFilter;
    const matchSearch=!currentSearch||c.name.toLowerCase().includes(currentSearch.toLowerCase());
    return matchStatus&&matchSearch;
  }});
  if(!filtered.length){{
    el.innerHTML='<div style="padding:40px;text-align:center;color:#bbb;font-size:13px">没有匹配的用例</div>';
    return;
  }}
  let html='';
  filtered.forEach(c=>{{
    const idx=CASES.indexOf(c);
    const color=STATUS_COLOR[c.status]||'#aaa';
    html+=`<div class="case-row" onclick="openDrawer(${{idx}})">
      <div><span class="status-dot" style="background:${{color}}"></span></div>
      <div>
        <div class="case-name">${{c.name}}</div>
        <div class="case-suite">${{c.suite}}</div>
      </div>
      <div><span class="sev-badge" style="background:${{SEV_COLOR[c.severity]||'#aaa'}}22;color:${{SEV_COLOR[c.severity]||'#aaa'}}">${{SEV_LABEL[c.severity]||c.severity}}</span></div>
      <div style="font-size:12px;color:#999;text-align:right">${{fmtDur(c.dur)}}</div>
      <div style="text-align:right"><span style="color:${{color}};font-size:12px;font-weight:600">${{STATUS_LABEL[c.status]||c.status}}</span></div>
    </div>`;
  }});
  el.innerHTML=html;
}}

function filterCases(status,btn){{
  currentFilter=status;
  document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));
  if(btn) btn.classList.add('active');
  renderCasesList();
}}

function searchCases(val){{
  currentSearch=val;
  renderCasesList();
}}

function renderTimeline(){{
  const el=document.getElementById('timelineWrap');
  if(!el||!CASES.length) return;
  const starts=CASES.map(c=>c.start).filter(Boolean);
  const stops=CASES.map(c=>c.stop).filter(Boolean);
  if(!starts.length) return;
  const minT=Math.min(...starts);
  const maxT=Math.max(...stops);
  const range=maxT-minT||1;
  let html='<div style="font-size:13px;font-weight:600;color:#555;margin-bottom:16px">执行时间线</div>';
  CASES.forEach((c,i)=>{{
    const color=STATUS_COLOR[c.status]||'#aaa';
    const left=((c.start-minT)/range*100).toFixed(2);
    const width=Math.max(0.5,((c.stop-c.start)/range*100)).toFixed(2);
    html+=`<div class="tl-row">
      <div class="tl-label" title="${{c.name}}">${{c.name}}</div>
      <div class="tl-track">
        <div class="tl-bar" style="left:${{left}}%;width:${{width}}%;background:${{color}}" onclick="openDrawer(${{i}})" title="${{c.name}} (${{fmtDur(c.dur)}})"></div>
      </div>
      <div style="width:50px;font-size:11px;color:#aaa;text-align:right;flex-shrink:0">${{fmtDur(c.dur)}}</div>
    </div>`;
  }});
  html+=`<div style="display:flex;margin-left:170px;margin-top:4px;font-size:11px;color:#bbb">
    <span>${{new Date(minT).toLocaleTimeString('zh-CN')}}</span>
    <span style="margin-left:auto">${{new Date(maxT).toLocaleTimeString('zh-CN')}}</span>
  </div>`;
  el.innerHTML=html;
}}

function openDrawer(idx){{
  const c=CASES[idx];
  if(!c) return;
  const color=STATUS_COLOR[c.status]||'#aaa';
  document.getElementById('drawer-status-dot').style.background=color;
  document.getElementById('drawer-name').textContent=c.name;
  document.getElementById('drawer-meta').innerHTML=
    `<span style="color:${{color}};font-weight:600">${{STATUS_LABEL[c.status]||c.status}}</span>`+
    (c.testId?` &nbsp;·&nbsp; #${{c.testId}}`:'') +
    ` &nbsp;·&nbsp; ${{fmtDur(c.dur)}}`+
    (c.start?` &nbsp;·&nbsp; ${{fmtTs(c.start)}}`:'');
  let body='';
  if(c.desc) body+=`<div class="drawer-section"><div class="drawer-section-title">描述</div><p style="font-size:13px;color:#555;line-height:1.6">${{c.desc}}</p></div>`;
  if(c.failMsg) body+=`<div class="fail-box"><strong>失败原因：</strong>${{c.failMsg}}</div>`;
  if(c.steps&&c.steps.length){{
    body+=`<div class="drawer-section"><div class="drawer-section-title">执行步骤（${{c.steps.length}}）</div>`;
    c.steps.forEach((s,i)=>{{
      const sc=STATUS_COLOR[s.status]||'#aaa';
      const icon={{passed:'✓',failed:'✗',broken:'!',skipped:'–'}}[s.status]||'?';
      body+=`<div class="step-item" style="background:${{sc}}11">
        <div class="step-icon" style="background:${{sc}}">${{icon}}</div>
        <div>
          <div class="step-name"><span style="color:#bbb;font-size:11px;margin-right:6px">${{i+1}}.</span>${{s.name}}</div>
          ${{s.desc?`<div class="step-desc">${{s.desc}}</div>`:''}}
        </div>
      </div>`;
    }});
    body+='</div>';
  }}
  if(c.attachments&&c.attachments.length){{
    body+=`<div class="drawer-section"><div class="drawer-section-title">附件（${{c.attachments.length}}）</div>`;
    c.attachments.forEach(a=>{{
      body+=`<div style="margin-bottom:12px"><div style="font-size:12px;color:#999;margin-bottom:4px">📎 ${{a.name}}</div>`;
      if(a.type==='image') body+=`<img class="att-img" src="${{a.data}}" alt="${{a.name}}">`;
      else if(a.type==='text') body+=`<div class="att-text">${{a.data}}</div>`;
      body+='</div>';
    }});
    body+='</div>';
  }}
  document.getElementById('drawer-body').innerHTML=body||'<div style="color:#bbb;font-size:13px;padding:20px 0;text-align:center">暂无详细信息</div>';
  document.getElementById('drawer').classList.add('open');
  document.getElementById('drawer-overlay').style.display='block';
}}

function closeDrawer(){{
  document.getElementById('drawer').classList.remove('open');
  document.getElementById('drawer-overlay').style.display='none';
}}

function fmtDur(ms){{
  if(!ms||ms<=0) return '0ms';
  if(ms<1000) return ms+'ms';
  if(ms<60000) return (ms/1000).toFixed(1)+'s';
  return Math.floor(ms/60000)+'m '+Math.round((ms%60000)/1000)+'s';
}}
function fmtTs(ts){{
  if(!ts) return '-';
  return new Date(ts).toLocaleString('zh-CN');
}}

window.addEventListener('DOMContentLoaded',()=>{{
  drawDonut();
  drawTrend();
  renderSuitesOverview();
  renderSeverityOverview();
  renderCategoryOverview();
  renderSuitesDetail();
  renderCasesList();
}});
</script>
</body>
</html>
"""
