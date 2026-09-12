import { useState } from 'react';
import { errorMessage, instancePath, request, withBusyRetry, type Input, type Instance, type InstanceAction } from '../api';
import { androidLabels } from './InstanceList';
import { ScreenPreview } from './ScreenPreview';

export function DevicePanel({ instance, pending, capacityFull, onAction, onInput }: {
  instance: Instance; pending: boolean; capacityFull: boolean; onAction: (action: InstanceAction, packageName?: string) => void; onInput: (input: Input) => Promise<void>;
}) {
  const [text, setText] = useState('');
  const [packages, setPackages] = useState<string[]>([]);
  const [packageName, setPackageName] = useState('');
  const [packageError, setPackageError] = useState('');
  const [loadingPackages, setLoadingPackages] = useState(false);
  const busy = pending || instance.busy || loadingPackages;
  const ready = instance.android_status === 'ready' && !busy;
  const validText = text.length > 0 && text.length <= 200 && /^[\x20-\x7e]+$/.test(text);
  return <section className="panel device-panel" aria-labelledby="device-title"><div className="section-heading"><div><h2 id="device-title">{instance.name}</h2><p>{androidLabels[instance.android_status]} · Docker: {instance.docker_status}{instance.busy && ' · 操作中'}</p></div><span className="badge">{instance.width} × {instance.height}</span></div>
    {instance.error && <p className="error" role="alert">{instance.error}</p>}
    <dl className="facts"><div><dt>Android 实际版本</dt><dd>{instance.android_version || '等待设备实际读取'}</dd></div><div><dt>资源</dt><dd>{instance.cpu} CPU · {instance.memory_mb} MiB · {instance.dpi} DPI</dd></div><div><dt>ADB（Docker 宿主 localhost）</dt><dd><code>{instance.adb_address || '当前无端口映射'}</code></dd></div><div><dt>镜像</dt><dd><code>{instance.image}</code></dd></div></dl>
    <div className="toolbar">{([['start', '启动'], ['stop', '停止'], ['restart', '重启'], ['clone', '复制配置'], ['delete', '删除实例']] as const).map(([action, label]) => <button key={action} disabled={busy || (action === 'clone' && capacityFull)} className={action === 'delete' ? 'danger' : ''} onClick={() => onAction(action)}>{label}</button>)}</div>
    <p className="hint">停止 / 重启保留数据；复制配置创建空白数据卷。</p>
    <ScreenPreview id={instance.id} enabled={ready} onInput={onInput} />
    <div className="toolbar">{([[3, 'Home'], [4, 'Back'], [187, 'Recent'], [19, '↑'], [20, '↓'], [21, '←'], [22, '→'], [66, 'Enter'], [67, '删除字符']] as const).map(([code, label]) => <button key={code} aria-label={`设备按键 ${label}`} disabled={!ready} onClick={() => { void onInput({ action: 'key', code }); }}>{label}</button>)}<button disabled={!ready} onClick={() => onAction('open_settings')}>打开设置</button></div>
    <form className="text-form" onSubmit={event => { event.preventDefault(); if (validText) void onInput({ action: 'text', text }); }}><label>向设备输入文字<input value={text} maxLength={200} placeholder="英文、数字、空格和 ASCII 符号" onChange={event => setText(event.target.value)} /></label><button type="submit" disabled={!ready || !validText}>发送文字</button></form>
    {text && !validText && <p className="error" role="status">本 Demo 只支持最多 200 个可打印 ASCII 字符，暂不支持中文输入。</p>}
    <div className="subsection"><h3>应用与 root 对照</h3><div className="toolbar"><button disabled={!ready} onClick={async () => {
      setLoadingPackages(true); setPackageError('');
      try { const result = await withBusyRetry(() => request<{ packages: string[] }>(`${instancePath(instance.id)}/packages`)); setPackages(result.packages); setPackageName(result.packages[0] || ''); }
      catch (reason) { setPackageError(errorMessage(reason)); }
      finally { setLoadingPackages(false); }
    }}>{loadingPackages ? '读取中…' : '读取第三方应用'}</button><button disabled={!ready} onClick={() => onAction('root_check')}>检查 root 状态</button></div>
      {packageError && <p role="alert" className="error">读取应用失败：{packageError}</p>}
      <div className="text-form"><label>已安装包名<select value={packageName} onChange={event => setPackageName(event.target.value)}><option value="">{packages.length ? '选择应用' : '尚未读取，或设备没有第三方应用'}</option>{packages.map(item => <option key={item}>{item}</option>)}</select></label><button disabled={!ready || !packageName} onClick={() => onAction('launch', packageName)}>启动应用</button></div>
      <p className="hint">root 实际输出显示在任务结果中。容器 UID、Magisk、shell su 分别检查；宿主 ADB 与应用内授权需另行实测。</p>
    </div>
  </section>;
}
