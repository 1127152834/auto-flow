import { useEffect, useRef, useState } from "react";
import {
  position,
  request,
  type Action,
  type Device,
  type Frame,
  type State,
} from "./api";

const labels: Record<string, string> = {
  platform: "宿主平台",
  binary: "运行程序",
  research: "研究虚拟机许可",
  sip: "系统保护状态",
  xcode: "开发工具",
  host: "虚拟化宿主",
};
function Environment({ state }: { state: State }) {
  return (
    <section className="environment">
      <div className="section-heading">
        <div>
          <span className="eyebrow">01 / 环境</span>
          <h2>运行前检查</h2>
        </div>
        <span
          className={
            state.environment.canAttemptLaunch ? "badge good" : "badge"
          }
        >
          {state.environment.canAttemptLaunch
            ? "可以尝试启动"
            : "尚未满足启动条件"}
        </span>
      </div>
      <div className="checks">
        {Object.entries(state.environment.checks).map(([key, check]) => (
          <div className="check" key={key}>
            <span
              className={
                check.ok === true
                  ? "dot good"
                  : check.ok === false
                    ? "dot warn"
                    : "dot"
              }
            />
            <div>
              <strong>{labels[key] ?? key}</strong>
              <p>{check.text}</p>
            </div>
          </div>
        ))}
      </div>
      {!state.environment.canAttemptLaunch && (
        <p className="notice">
          研究虚拟机许可关闭时，需要在 macOS
          恢复模式中配置。完成后重启，再刷新检查。详细步骤见本 Demo 的 README。
        </p>
      )}
      <p className="muted">
        {state.environment.note} · 可用磁盘 {state.environment.freeGiB} GiB
      </p>
    </section>
  );
}

function Screen({
  frame,
  enabled,
  onAction,
}: {
  frame: Frame | null;
  enabled: boolean;
  onAction: (a: Action) => void;
}) {
  const down = useRef<{ x: number; y: number } | null>(null);
  return (
    <div className="screen-stage">
      {frame ? (
        <img
          className="phone-screen"
          src={`data:image/jpeg;base64,${frame.image}`}
          alt="虚拟 iPhone 的实际截图；点击或拖动可操作"
          draggable={false}
          onPointerDown={(e) => {
            if (enabled)
              down.current = position(
                e.clientX,
                e.clientY,
                e.currentTarget.getBoundingClientRect(),
              );
          }}
          onPointerCancel={() => {
            down.current = null;
          }}
          onPointerLeave={() => {
            down.current = null;
          }}
          onPointerUp={(e) => {
            const start = down.current;
            down.current = null;
            if (!enabled || !start) return;
            const end = position(
              e.clientX,
              e.clientY,
              e.currentTarget.getBoundingClientRect(),
            );
            if (!end) return;
            onAction(
              Math.hypot(end.x - start.x, end.y - start.y) < 0.018
                ? { t: "tap", ...end }
                : {
                    t: "swipe",
                    x1: start.x,
                    y1: start.y,
                    x2: end.x,
                    y2: end.y,
                    ms: 350,
                  },
            );
          }}
        />
      ) : (
        <div className="screen-empty">
          <span className="phone-outline" aria-hidden="true">
            iOS
          </span>
          <h3>等待真实设备画面</h3>
          <p>
            启动虚拟 iPhone 后读取截图。
            <br />
            这里不会显示模拟设备或示意截图。
          </p>
        </div>
      )}
    </div>
  );
}

const defaultSteps = JSON.stringify(
  [{ t: "screenshot" }, { t: "key", name: "home" }, { t: "screenshot" }],
  null,
  2,
);
export function App() {
  const [state, setState] = useState<State | null>(null),
    [device, setDevice] = useState("");
  const [frame, setFrame] = useState<Frame | null>(null),
    [busy, setBusy] = useState(false);
  const [error, setError] = useState(""),
    [clipboard, setClipboard] = useState("");
  const [steps, setSteps] = useState(defaultSteps),
    [logs, setLogs] = useState<string[]>([]);
  const stop = useRef(false),
    pending = useRef(false);
  const current: Device | undefined = state?.devices.find(
    (d) => d.name === device,
  );
  const canControl = !!current?.socketPresent && !current.error && !busy;
  function log(text: string) {
    setLogs((old) =>
      [`${new Date().toLocaleTimeString()}  ${text}`, ...old].slice(0, 60),
    );
  }
  async function refresh() {
    try {
      const value = await request<State>("/api/state");
      setState(value);
      setError("");
      setDevice((old) =>
        value.devices.some((d) => d.name === old)
          ? old
          : (value.devices[0]?.name ?? ""),
      );
    } catch (e) {
      setError(String(e));
    }
  }
  useEffect(() => {
    void refresh();
  }, []);
  useEffect(() => {
    setFrame(null);
  }, [device]);
  useEffect(() => {
    if (!current?.managed || current.socketPresent) return;
    const timer = window.setTimeout(() => {
      void refresh();
    }, 2000);
    return () => clearTimeout(timer);
  }, [state, current]);
  async function action(a: Action) {
    const result = await request<Frame>("/api/action", state?.token, {
      device,
      action: a,
    });
    setFrame(result);
    log(`${a.t} · ${result.message}`);
    return result;
  }
  async function operation(task: () => Promise<unknown>) {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      await task();
    } catch (e) {
      setFrame(null);
      setError(String(e));
      log(`失败 · ${String(e)}`);
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }
  async function lifecycle(op: string) {
    const result = await request<{ message: string }>(
      "/api/lifecycle",
      state?.token,
      { device, operation: op },
    );
    setFrame(null);
    log(result.message);
    await refresh();
  }
  async function replay() {
    const parsed: unknown = JSON.parse(steps);
    if (
      !Array.isArray(parsed) ||
      parsed.length < 1 ||
      parsed.length > 20 ||
      parsed.some((a) => !a || typeof a !== "object" || typeof a.t !== "string")
    )
      throw new Error("步骤必须是 1–20 个动作组成的数组");
    stop.current = false;
    for (let i = 0; i < parsed.length; i++) {
      if (stop.current) {
        log("已停止：尚未发送下一步");
        return;
      }
      log(`步骤 ${i + 1}/${parsed.length}`);
      await action(parsed[i]);
    }
    log("回放完成 · 请检查截图中的业务结果");
  }
  return (
    <main>
      <header>
        <div>
          <span className="brand">
            AUTOFLOW <span>/ REFERENCE</span>
          </span>
          <h1>
            iOS 实验室<span className="pill">实验性</span>
          </h1>
          <p>在 Mac 上验证虚拟 iPhone 的控制与步骤回放。</p>
        </div>
        <button disabled={busy} onClick={() => void refresh()}>
          刷新检查
        </button>
      </header>
      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}
      {state ? (
        <Environment state={state} />
      ) : (
        <p role="status">正在读取本机环境…</p>
      )}
      <div className="workspace">
        <section className="device-panel">
          <span className="eyebrow">02 / 设备</span>
          <h2>虚拟 iPhone</h2>
          <label>
            当前设备
            <select
              value={device}
              disabled={busy || !state?.devices.length}
              onChange={(e) => setDevice(e.target.value)}
            >
              {!state?.devices.length && <option value="">尚未创建设备</option>}
              {state?.devices.map((d) => (
                <option key={d.name} value={d.name}>
                  {d.name}
                </option>
              ))}
            </select>
          </label>
          <p className="muted">
            {current
              ? (current.error ??
                `${current.width} × ${current.height} · ${current.socketPresent ? "发现控制接口，待读取画面" : current.managed ? "启动进程运行中" : "未发现控制接口"}${current.exitCode != null ? ` · 启动退出码 ${current.exitCode}` : ""}`)
              : "从终端创建首台设备后，点击刷新检查。"}
          </p>
          <div className="button-row">
            <button
              disabled={
                !current ||
                busy ||
                !state?.environment.canAttemptLaunch ||
                current.socketPresent ||
                current.managed ||
                !!current.error
              }
              onClick={() => void operation(() => lifecycle("start"))}
            >
              启动
            </button>
            <button
              disabled={!current?.managed || busy}
              onClick={() => void operation(() => lifecycle("stop"))}
            >
              停止
            </button>
            <button
              className="primary"
              disabled={!canControl}
              onClick={() => void operation(() => action({ t: "screenshot" }))}
            >
              读取截图
            </button>
          </div>
          <Screen
            frame={frame}
            enabled={canControl}
            onAction={(a) => void operation(() => action(a))}
          />
          <p className="muted">
            点击画面进行触控，拖动进行滑动。每次操作回读一张实际截图。
          </p>
          {frame && (
            <a
              download={`${device}.jpg`}
              href={`data:image/jpeg;base64,${frame.image}`}
            >
              保存当前截图
            </a>
          )}
        </section>
        <aside>
          <section>
            <span className="eyebrow">03 / 控制</span>
            <h2>设备操作</h2>
            <div className="button-row">
              {[
                ["home", "主屏幕"],
                ["power", "锁屏 / 唤醒"],
                ["volup", "音量＋"],
                ["voldown", "音量－"],
              ].map(([name, label]) => (
                <button
                  key={name}
                  disabled={!canControl}
                  onClick={() =>
                    void operation(() => action({ t: "key", name }))
                  }
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="button-row">
              <button
                disabled={!canControl}
                onClick={() =>
                  void operation(() =>
                    action({
                      t: "swipe",
                      x1: 0.5,
                      y1: 0.8,
                      x2: 0.5,
                      y2: 0.3,
                      ms: 350,
                    }),
                  )
                }
              >
                向上滑动
              </button>
              <button
                disabled={!canControl}
                onClick={() =>
                  void operation(() =>
                    action({
                      t: "swipe",
                      x1: 0.5,
                      y1: 0.3,
                      x2: 0.5,
                      y2: 0.8,
                      ms: 350,
                    }),
                  )
                }
              >
                向下滑动
              </button>
            </div>
            <label>
              设备剪贴板
              <textarea
                rows={2}
                value={clipboard}
                onChange={(e) => setClipboard(e.target.value)}
                placeholder="可输入中文；设置后仍需在 App 内粘贴"
              />
            </label>
            <button
              disabled={!canControl}
              onClick={() =>
                void operation(() =>
                  action({ t: "clipboard", text: clipboard }),
                )
              }
            >
              设置剪贴板
            </button>
            <p className="muted">
              当前不提供控件树定位，也不将设置剪贴板标为输入完成。
            </p>
          </section>
          <section>
            <span className="eyebrow">04 / 回放</span>
            <h2>运行一段步骤</h2>
            <label>
              动作 JSON
              <textarea
                className="code"
                rows={10}
                value={steps}
                disabled={busy}
                onChange={(e) => setSteps(e.target.value)}
              />
            </label>
            <div className="button-row">
              <button
                className="primary"
                disabled={!canControl}
                onClick={() => void operation(replay)}
              >
                运行步骤
              </button>
              <button
                disabled={!busy}
                onClick={() => {
                  stop.current = true;
                }}
              >
                停止后续步骤
              </button>
            </div>
            <p className="muted">
              最多 20 步。坐标使用 0–1
              比例；动作依次执行，失败即停止。日志中的成功仅代表指令与截图传输成功。
            </p>
          </section>
        </aside>
      </div>
      <section>
        <div className="section-heading">
          <div>
            <span className="eyebrow">05 / 记录</span>
            <h2>本次操作</h2>
          </div>
          <button onClick={() => setLogs([])}>清空显示</button>
        </div>
        <pre className="log" aria-live="polite">
          {logs.join("\n") || "尚未发送设备指令。"}
        </pre>
      </section>
      <footer>
        独立 reference Demo · 不连接 AutoFlow 正式工作流 ·{" "}
        {state?.environment.root}
      </footer>
    </main>
  );
}
