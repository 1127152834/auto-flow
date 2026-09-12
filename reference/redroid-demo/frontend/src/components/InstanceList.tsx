import type { BatchAction, Instance } from '../api';

export const androidLabels = { starting: 'Android 启动中', ready: 'Android 已就绪', stopped: 'Android 已停止', failed: 'Android 失败', unknown: 'Android 状态待确认' };
export function InstanceList({ instances, selectedId, checked, pending, onSelect, onCheck, onBatch }: {
  instances: Instance[]; selectedId: string; checked: string[]; pending: boolean;
  onSelect: (id: string) => void; onCheck: (id: string) => void; onBatch: (action: BatchAction) => void;
}) {
  const busy = pending || checked.length === 0 || instances.some(item => checked.includes(item.id) && item.busy);
  return <section className="panel"><div className="section-heading"><h2>实例 <span className="count">{instances.length}/3</span></h2><span className="hint">勾选批量操作 · 点击查看设备</span></div>
    <div className="instance-list">{instances.length === 0 && <p className="empty">暂无实例。环境通过后，在上方创建第一台 Android。</p>}{instances.map(instance => <div className={`instance-row ${selectedId === instance.id ? 'selected' : ''}`} key={instance.id}>
      <input type="checkbox" aria-label={`选择 ${instance.name} 进行批量操作`} checked={checked.includes(instance.id)} onChange={() => onCheck(instance.id)} />
      <button className="instance-choice" onClick={() => onSelect(instance.id)} aria-pressed={selectedId === instance.id}><strong>{instance.name}</strong><span><span className={`dot ${instance.android_status}`} />{androidLabels[instance.android_status]}{instance.busy && ' · 操作中'}</span><small>Docker: {instance.docker_status} · {instance.width} × {instance.height}</small></button>
    </div>)}</div>
    <div className="toolbar"><span className="hint">已选 {checked.length} 台</span>{([['start', '启动'], ['stop', '停止'], ['restart', '重启'], ['open_settings', '打开设置'], ['delete', '删除']] as const).map(([action, label]) => <button key={action} className={action === 'delete' ? 'danger' : ''} disabled={busy} onClick={() => onBatch(action)}>批量{label}</button>)}</div>
  </section>;
}
