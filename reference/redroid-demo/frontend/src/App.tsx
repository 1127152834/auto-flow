import { useCallback, useEffect, useRef, useState } from 'react';
import { errorMessage, instancePath, post, request, withBusyRetry, type Apk, type BatchAction, type CreateConfig, type Environment, type Input, type Instance, type InstanceAction, type Job } from './api';
import { ApkPanel } from './components/ApkPanel';
import { CreateForm } from './components/CreateForm';
import { DevicePanel } from './components/DevicePanel';
import { EnvironmentPanel } from './components/EnvironmentPanel';
import { InstanceList } from './components/InstanceList';
import { JobsPanel } from './components/JobsPanel';

export default function App() {
  const [environment, setEnvironment] = useState<Environment | null>(null);
  const [instances, setInstances] = useState<Instance[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [apks, setApks] = useState<Apk[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [checked, setChecked] = useState<string[]>([]);
  const [errors, setErrors] = useState({ environment: '', instances: '', jobs: '', apks: '' });
  const [notice, setNotice] = useState('');
  const [actionError, setActionError] = useState('');
  const [pending, setPending] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [restarted, setRestarted] = useState(false);
  const session = useRef('');
  const refreshingRef = useRef(false);
  const mutationRef = useRef(false);
  const mounted = useRef(true);
  const refresh = useCallback(async () => {
    if (refreshingRef.current) return;
    refreshingRef.current = true;
    if (mounted.current) setRefreshing(true);
    const results = await Promise.allSettled([
      request<Environment>('/environment'), request<{ instances: Instance[] }>('/instances'),
      request<{ jobs: Job[]; session_id: string }>('/jobs'), request<{ apks: Apk[] }>('/apks'),
    ]);
    if (mounted.current) {
      const [envResult, instanceResult, jobResult, apkResult] = results;
      setEnvironment(envResult.status === 'fulfilled' ? envResult.value : null);
      if (instanceResult.status === 'fulfilled') {
        setInstances(instanceResult.value.instances);
        setChecked(previous => previous.filter(id => instanceResult.value.instances.some(item => item.id === id)));
      } else { setInstances([]); setChecked([]); }
      if (jobResult.status === 'fulfilled') {
        if (session.current && session.current !== jobResult.value.session_id) setRestarted(true);
        session.current = jobResult.value.session_id;
        setJobs(jobResult.value.jobs);
      }
      if (apkResult.status === 'fulfilled') setApks(apkResult.value.apks);
      setErrors({
        environment: envResult.status === 'rejected' ? errorMessage(envResult.reason) : '',
        instances: instanceResult.status === 'rejected' ? errorMessage(instanceResult.reason) : '',
        jobs: jobResult.status === 'rejected' ? errorMessage(jobResult.reason) : '',
        apks: apkResult.status === 'rejected' ? errorMessage(apkResult.reason) : '',
      });
      setRefreshing(false);
    }
    refreshingRef.current = false;
  }, []);
  useEffect(() => {
    mounted.current = true;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => { if (!document.hidden) await refresh(); if (!stopped) timer = setTimeout(poll, 2_500); };
    void poll();
    return () => { mounted.current = false; stopped = true; clearTimeout(timer); };
  }, [refresh]);

  // ponytail: one local mutation at a time; the backend still enforces per-device ownership.
  const run = async (fn: () => Promise<unknown>, success: string) => {
    if (mutationRef.current) return;
    mutationRef.current = true; setPending(true); setActionError(''); setNotice('');
    try { await withBusyRetry(fn); setNotice(success); await refresh(); }
    catch (reason) { setActionError(errorMessage(reason)); }
    finally { mutationRef.current = false; setPending(false); }
  };
  const selected = instances.find(item => item.id === selectedId) || instances[0];
  const selectedTargets = checked.filter(id => instances.some(item => item.id === id));
  const maxInstances = environment?.limits.max_instances ?? 3;
  const batch = (action: BatchAction, apkId?: string) => {
    if (action === 'delete' && !window.confirm(`将永久删除已选 ${selectedTargets.length} 台实例及其各自数据卷，无法恢复。继续删除？`)) return;
    void run(() => post('/batches', { action, instance_ids: selectedTargets, ...(apkId ? { apk_id: apkId } : {}) }), '批量任务已提交，请查看逐台结果。');
  };
  const action = (value: InstanceAction, packageName?: string) => {
    if (!selected) return;
    if (value === 'delete' && !window.confirm(`将永久删除“${selected.name}”及其数据卷，无法恢复。继续删除？`)) return;
    void run(() => post(`${instancePath(selected.id)}/actions`, { action: value, ...(packageName ? { package: packageName } : {}) }), '设备任务已提交，请查看任务结果。');
  };
  const input = async (value: Input) => {
    if (!selected) return;
    await run(() => post(`${instancePath(selected.id)}/input`, value), '设备输入已执行。');
  };
  const create = (config: CreateConfig) => run(() => post('/instances', config), '创建任务已提交，Android 就绪前请等待实际启动结果。');
  const upload = (file: File) => run(() => { const body = new FormData(); body.append('file', file); return request('/apks', { method: 'POST', body }); }, 'APK 上传成功。勾选目标实例后即可安装。');
  return <><header className="page-header"><div><p className="eyebrow">REFERENCE / ANDROID LAB</p><h1>redroid Demo</h1><p>创建、操作与批量管理真实 Android 容器</p></div><span className="badge">Python + React · 本机管理</span></header>
    <main><EnvironmentPanel environment={environment} error={errors.environment} refreshing={refreshing} onRefresh={() => { void refresh(); }} />
      <div className="feedback" aria-live="polite">{actionError && <p className="error" role="alert">操作失败：{actionError}</p>}{notice && <p className="success" role="status">{notice}</p>}{errors.instances && <p className="error" role="alert">无法读取实例：{errors.instances}</p>}</div>
      <div className="workspace"><div className="management-column"><CreateForm environment={environment} availableSlots={Math.max(0, maxInstances - instances.length)} pending={pending} onCreate={create} />
        <InstanceList instances={instances} selectedId={selected?.id || ''} checked={selectedTargets} pending={pending} onSelect={setSelectedId} onCheck={id => setChecked(previous => previous.includes(id) ? previous.filter(item => item !== id) : [...previous, id])} onBatch={batch} />
        <ApkPanel apks={apks} pending={pending} targetCount={selectedTargets.length} busyTargets={instances.some(item => selectedTargets.includes(item.id) && item.busy)} onUpload={upload} onInstall={id => batch('install', id)} />
        {errors.apks && <p className="error" role="alert">无法读取 APK 列表：{errors.apks}</p>}
      </div><div>{selected ? <DevicePanel key={selected.id} instance={selected} pending={pending} capacityFull={instances.length >= maxInstances} onAction={action} onInput={input} /> : <section className="panel empty-device"><div className="device-outline" aria-hidden="true" /><h2>选择一台 Android</h2><p>实例创建后，可以在这里查看截图、操作设备、启动应用并检查 root。</p><p className="hint">这里展示真实设备状态，Docker 不可用时不会生成演示设备。</p></section>}</div></div>
      <JobsPanel jobs={jobs} restarted={restarted} error={errors.jobs} />
    </main><footer>Demo 仅管理带自身归属标签的实例。Mac / Linux 虚拟机、Windows / WSL2、目标 APK 与应用级 root 的实测结果以验证记录为准。</footer>
  </>;
}
