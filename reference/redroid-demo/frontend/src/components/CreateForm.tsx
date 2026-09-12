import { useState } from 'react';
import type { CreateConfig, Environment } from '../api';

export function CreateForm({ environment, availableSlots, pending, onCreate }: {
  environment: Environment | null; availableSlots: number; pending: boolean; onCreate: (config: CreateConfig) => Promise<void>;
}) {
  const [image, setImage] = useState('');
  const [config, setConfig] = useState({ name: '安卓 Demo', width: 720, height: 1280, dpi: 320, cpu: 2, memory_mb: 2048, count: 1 });
  const images = environment?.images || [];
  const compatibleImages = images.filter(item => item.cached && item.compatible !== false);
  const selectedImage = compatibleImages.find(item => item.ref === image)?.ref || compatibleImages[0]?.ref || '';
  const canCreate = environment?.ready && compatibleImages.some(item => item.ref === selectedImage) && availableSlots > 0 && config.count <= availableSlots;
  return <section className="panel"><h2>创建实例</h2><p>最多 3 台独立实例。每台使用独立数据卷，复制配置会创建空白设备。</p>
    <form onSubmit={event => { event.preventDefault(); if (canCreate) void onCreate({ ...config, image: selectedImage }); }}>
      <fieldset disabled={pending}><label>实例名称<input required maxLength={64} value={config.name} onChange={event => setConfig({ ...config, name: event.target.value })} /></label>
        <label>Android 镜像<select value={selectedImage} onChange={event => setImage(event.target.value)}>{!selectedImage && <option value="">{images.length ? '没有兼容的已缓存镜像' : '等待环境检查'}</option>}{images.map(item => <option key={item.ref} value={item.ref} disabled={!item.cached || item.compatible === false}>{item.ref}{!item.cached ? '（未缓存）' : item.compatible === false ? `（架构不匹配：${item.architecture || '未知'}）` : ''}</option>)}</select></label>
        <div className="form-grid">{([
          ['width', '宽度 px', 128, 2160, 1], ['height', '高度 px', 128, 2160, 1], ['dpi', 'DPI', 120, 640, 1], ['cpu', 'CPU 核数', 0.5, 8, 0.5], ['memory_mb', '内存 MiB', 512, 8192, 1], ['count', '创建数量', 1, 3, 1],
        ] as const).map(([key, label, min, max, step]) => <label key={key}>{label}<input type="number" required min={min} max={max} step={step} value={Number.isNaN(config[key]) ? '' : config[key]} onChange={event => setConfig({ ...config, [key]: event.target.valueAsNumber })} /></label>)}</div>
        <button className="primary" type="submit" disabled={!canCreate}>{pending ? '正在提交…' : `创建 ${config.count || 1} 台实例`}</button><span className="hint">还可创建 {availableSlots} 台</span>
      </fieldset>
    </form>
  </section>;
}
