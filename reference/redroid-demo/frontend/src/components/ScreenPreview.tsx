import { useEffect, useRef, useState } from 'react';
import { errorMessage, instancePath, responseError, type Input } from '../api';

type Point = { x: number; y: number };
/** Map object-fit:contain pixels, excluding the letterbox rather than clamping it. */
export function screenPoint(clientX: number, clientY: number, rect: Pick<DOMRect, 'left' | 'top' | 'width' | 'height'>, width: number, height: number): Point | null {
  if (width <= 0 || height <= 0 || rect.width <= 0 || rect.height <= 0) return null;
  const scale = Math.min(rect.width / width, rect.height / height);
  const x = clientX - rect.left - (rect.width - width * scale) / 2;
  const y = clientY - rect.top - (rect.height - height * scale) / 2;
  if (x < 0 || y < 0 || x >= width * scale || y >= height * scale) return null;
  return { x: Math.floor(x / scale), y: Math.floor(y / scale) };
}

export function ScreenPreview({ id, enabled, onInput }: { id: string; enabled: boolean; onInput: (input: Input) => Promise<void> }) {
  const [watching, setWatching] = useState(true);
  const [src, setSrc] = useState('');
  const [error, setError] = useState('');
  const [dimensions, setDimensions] = useState('');
  const start = useRef<Point | null>(null);
  const lastRequest = useRef(0);
  const currentUrl = useRef('');
  useEffect(() => {
    setSrc(''); setDimensions(''); setError(''); start.current = null;
    return () => { if (currentUrl.current) URL.revokeObjectURL(currentUrl.current); currentUrl.current = ''; };
  }, [id]);
  useEffect(() => {
    if (!enabled || !watching) return;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | undefined;
    let inFlight = false;
    const frame = async () => {
      if (disposed || document.hidden || inFlight) return;
      inFlight = true;
      lastRequest.current = Date.now();
      controller = new AbortController();
      const timeout = setTimeout(() => controller?.abort(), 20_000);
      try {
        const response = await fetch(`/api${instancePath(id)}/screen`, { cache: 'no-store', signal: controller.signal });
        if (!response.ok) throw await responseError(response);
        if (!response.headers.get('content-type')?.startsWith('image/png')) throw new Error('截图接口未返回 PNG 图片');
        const blob = await response.blob();
        if (disposed || controller.signal.aborted || document.hidden) return;
        const nextUrl = URL.createObjectURL(blob);
        if (currentUrl.current) URL.revokeObjectURL(currentUrl.current);
        currentUrl.current = nextUrl;
        setSrc(nextUrl);
        setError('');
      } catch (reason) {
        if (!disposed && !document.hidden) setError(reason instanceof DOMException && reason.name === 'AbortError' ? '截图请求超时，请查看设备状态' : errorMessage(reason));
      } finally {
        clearTimeout(timeout);
        inFlight = false;
        if (!disposed && !document.hidden) timer = setTimeout(frame, 1_000);
      }
    };
    const visibility = () => {
      clearTimeout(timer);
      if (document.hidden) controller?.abort();
      else if (!inFlight) timer = setTimeout(frame, 1_000);
    };
    document.addEventListener('visibilitychange', visibility);
    const initialDelay = Math.max(0, 1_000 - (Date.now() - lastRequest.current));
    if (initialDelay) timer = setTimeout(frame, initialDelay);
    else void frame();
    return () => { disposed = true; clearTimeout(timer); controller?.abort(); document.removeEventListener('visibilitychange', visibility); start.current = null; };
  }, [id, enabled, watching]);
  return <div className="preview"><div className="section-heading"><span className="hint">截图预览 · 最多 1 帧/秒{dimensions && ` · ${dimensions}`}</span><button onClick={() => setWatching(!watching)}>{watching ? '暂停预览' : '继续预览'}</button></div>
    <div className="screen"><div className="screen-content">
      {src ? <img src={src} draggable={false} alt="当前 Android 屏幕，可点击或拖动操作" onLoad={event => setDimensions(`${event.currentTarget.naturalWidth} × ${event.currentTarget.naturalHeight}`)}
        onPointerDown={event => {
          if (!enabled || event.button !== 0 || !watching) return;
          const img = event.currentTarget;
          start.current = screenPoint(event.clientX, event.clientY, img.getBoundingClientRect(), img.naturalWidth, img.naturalHeight);
          if (start.current) img.setPointerCapture?.(event.pointerId);
        }}
        onPointerCancel={() => { start.current = null; }}
        onPointerUp={event => {
          const from = start.current; start.current = null;
          if (!enabled || !watching || !from) return;
          const img = event.currentTarget;
          const to = screenPoint(event.clientX, event.clientY, img.getBoundingClientRect(), img.naturalWidth, img.naturalHeight);
          if (!to) return;
          void onInput(Math.hypot(to.x - from.x, to.y - from.y) < 8 ? { action: 'tap', x: to.x, y: to.y } : { action: 'swipe', x1: from.x, y1: from.y, x2: to.x, y2: to.y });
        }} /> : <p>{!enabled ? '设备未就绪或正在执行操作' : !watching ? '预览已暂停' : '等待设备截图…'}</p>}
    </div></div>
    {src && (!enabled || !watching) && <p className="hint" role="status">保留上一帧 · {!watching ? '预览已暂停' : '设备操作中或未就绪，预览暂缓'}</p>}
    {error && <p className="error" role="status">截图失败：{error}</p>}
    <p className="hint">点击为轻触，拖动为滑动。留白不触发输入；切到后台会暂停请求。</p>
  </div>;
}
