import { useEffect, useRef, useState } from 'react';
import { errorMessage, post, request, type Instance } from './api';

type Session = { phase: string; instance_id: string | null; message: string; name?: string; log?: string };
type Status = { instances: Instance[]; session: Session };
const activePhases = ['starting', 'connecting', 'open', 'closing'];

export default function NativeMonitor() {
  const [state, setState] = useState<Status | null>(null);
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState('');
  const [pending, setPending] = useState(false);
  const submitting = useRef(false);
  const opening = useRef(false);
  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    const refresh = async () => {
      try {
        const result = await request<Status>('/native', { signal: controller.signal });
        if (!stopped && !opening.current) { setState(result); setLoadError(''); }
      } catch (reason) { if (!stopped) { setLoadError(errorMessage(reason)); setState(null); } }
      if (!stopped) timer = setTimeout(refresh, 2000);
    };
    void refresh();
    return () => { stopped = true; controller.abort(); clearTimeout(timer); };
  }, []);
  const open = async (instanceId: string) => {
    if (submitting.current) return;
    submitting.current = true; opening.current = true; setPending(true); setError('');
    try {
      const session = await post<Session>('/native/open', { instance_id: instanceId });
      setState(previous => previous ? { ...previous, session } : null);
    } catch (reason) { setError(errorMessage(reason)); }
    finally { submitting.current = false; opening.current = false; setPending(false); }
  };
  const active = pending || Boolean(state && activePhases.includes(state.session.phase));
  return <div className="native-monitor"><header className="page-header"><div>
    <p className="eyebrow">AUTOFLOW / MAC NATIVE DEMO</p><h1>安卓设备监控</h1>
    <p>页面查看状态，点击后在 Mac 原生窗口操作真实 Android。</p>
  </div><span className="badge">redroid + scrcpy</span></header>
    <main><section className="panel" aria-label="原生窗口状态"><h2>原生窗口</h2>
      {(loadError || error) && <p className="error" role="alert">{loadError || error}</p>}
      <p role="status" className={state?.session.phase === 'failed' ? 'error' : ''}>{state?.session.message || '正在连接本机服务…'}</p>
      {state?.session.log && <p className="hint">诊断日志：{state.session.log}</p>}
      <p className="hint">本次验证每次打开一台。关闭窗口保留设备和数据；不会停止 Android。</p>
    </section><div className="native-grid">{state?.instances.map(device => <article className="panel" key={device.id}>
      <div className="section-heading"><h2>{device.name}</h2><span className="badge">{device.android_status === 'ready' ? 'Android 已就绪' : device.android_status === 'stopped' ? '已停止' : device.android_status}</span></div>
      <p>Android {device.android_version || '—'} · {device.width} × {device.height}</p>
      <p className="hint">{device.id}</p><p className="hint">{device.image}</p>
      <button className="primary" disabled={active || device.busy || !['ready', 'stopped'].includes(device.android_status)} onClick={() => { void open(device.id); }}>
        {active && state.session.instance_id === device.id ? '原生窗口启动或使用中' : device.android_status === 'stopped' ? '启动并打开原生窗口' : '打开原生窗口'}
      </button>
    </article>)}</div>{state?.instances.length === 0 && <p>当前没有实例，请先在原 Demo 创建。</p>}</main>
    <footer>独立验证入口：页面不发送 Android 点击或键盘事件。请在弹出的 scrcpy 窗口操作。</footer>
  </div>;
}
