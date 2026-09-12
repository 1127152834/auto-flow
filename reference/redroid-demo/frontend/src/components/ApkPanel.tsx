import { useRef, useState } from 'react';
import type { Apk } from '../api';

export function ApkPanel({ apks, pending, targetCount, busyTargets, onUpload, onInstall }: {
  apks: Apk[]; pending: boolean; targetCount: number; busyTargets: boolean; onUpload: (file: File) => Promise<void>; onInstall: (id: string) => void;
}) {
  const [selectedId, setSelectedId] = useState('');
  const [error, setError] = useState('');
  const fileInput = useRef<HTMLInputElement>(null);
  const apkId = apks.some(item => item.id === selectedId) ? selectedId : apks[0]?.id || '';
  return <section className="panel"><h2>APK 分发</h2><p>上传一个 APK，再安装到实例列表中勾选的设备。最多 256 MiB。</p>
    <form onSubmit={async event => {
      event.preventDefault(); const file = fileInput.current?.files?.[0]; if (!file) return;
      if (file.size > 256 * 1024 * 1024) { setError('APK 不能超过 256 MiB'); return; }
      setError(''); await onUpload(file);
    }}><label>APK 文件<input ref={fileInput} type="file" accept=".apk,application/vnd.android.package-archive" required disabled={pending} /></label><button type="submit" disabled={pending}>上传 APK</button></form>
    {error && <p className="error" role="alert">{error}</p>}
    <label>已上传 APK<select value={apkId} onChange={event => setSelectedId(event.target.value)}><option value="">选择 APK</option>{apks.map(apk => <option key={apk.id} value={apk.id}>{apk.name} · {(apk.size_bytes / 1024 / 1024).toFixed(1)} MiB</option>)}</select></label>
    <button className="primary" disabled={pending || busyTargets || !apkId || targetCount === 0} onClick={() => onInstall(apkId)}>安装到已选 {targetCount} 台设备</button>
  </section>;
}
