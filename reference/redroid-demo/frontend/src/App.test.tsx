import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { DevicePanel } from './components/DevicePanel';
import { JobsPanel } from './components/JobsPanel';
import { CreateForm } from './components/CreateForm';
import type { Environment, Instance } from './api';

const environment: Environment = { docker_available: true, ready: true, checks: [{ name: '内核', status: 'pass', message: 'binder 可用' }], daemon: { OSType: 'linux' }, images: [{ ref: 'redroid/redroid:13.0.0-latest', cached: true, id: 'sha256:actual' }], limits: { max_instances: 3, concurrency: 2 } };
const instance: Instance = { id: 'demo-one', name: '测试设备', image: environment.images[0].ref, image_id: 'sha256:actual', docker_status: 'running', android_status: 'ready', android_version: '13', width: 720, height: 1280, dpi: 320, cpu: 2, memory_mb: 2048, adb_address: '127.0.0.1:32768', busy: false, error: null };
function response(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status, headers: { 'content-type': 'application/json' } }); }
afterEach(() => vi.unstubAllGlobals());

describe('real service states and interactions', () => {
  it('does not invent devices when Docker is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => {
      if (url === '/api/environment') return Promise.resolve(response({ ...environment, docker_available: false, ready: false, checks: [{ name: 'Docker', status: 'fail', message: 'socket 不存在' }] }));
      if (url === '/api/instances') return Promise.resolve(response({ error: { message: 'Docker 未连接' } }, 503));
      if (url === '/api/jobs') return Promise.resolve(response({ jobs: [], session_id: 'one' }));
      return Promise.resolve(response({ apks: [] }));
    }));
    render(<App />);
    expect(await screen.findByText('Docker 不可用，当前不能管理实例')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '创建 1 台实例' })).toBeDisabled();
    expect(screen.getByText('无法读取实例：Docker 未连接')).toBeInTheDocument();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });
  it('submits the configured batch count and presents actual HTTP failures', async () => {
    const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === 'POST') return Promise.resolve(response({ error: { code: 'capacity', message: '实例数量已满' } }, 409));
      if (url === '/api/environment') return Promise.resolve(response(environment));
      if (url === '/api/instances') return Promise.resolve(response({ instances: [] }));
      if (url === '/api/jobs') return Promise.resolve(response({ jobs: [], session_id: 'one' }));
      return Promise.resolve(response({ apks: [] }));
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);
    await waitFor(() => expect(screen.getByRole('button', { name: '创建 1 台实例' })).toBeEnabled());
    fireEvent.change(screen.getByLabelText('创建数量'), { target: { value: '3' } });
    fireEvent.click(screen.getByRole('button', { name: '创建 3 台实例' }));
    expect(await screen.findByText('操作失败：实例数量已满')).toBeInTheDocument();
    const call = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST');
    expect(JSON.parse(call?.[1]?.body as string)).toMatchObject({ count: 3, width: 720, height: 1280, image: environment.images[0].ref });
    expect(screen.queryByText(/创建任务已提交/)).not.toBeInTheDocument();
  });
  it('skips cached incompatible images and prevents creating when no compatible image remains', () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    const images = [
      { ref: 'redroid/amd64:13', cached: true, id: 'amd64-id', architecture: 'amd64', compatible: false },
      { ref: 'redroid/arm64:13', cached: true, id: 'arm64-id', architecture: 'arm64', compatible: true },
    ];
    const view = render(<CreateForm environment={{ ...environment, images }} availableSlots={3} pending={false} onCreate={onCreate} />);
    expect(screen.getByLabelText('Android 镜像')).toHaveValue('redroid/arm64:13');
    expect(screen.getByRole('option', { name: /redroid\/amd64.*架构不匹配/ })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '创建 1 台实例' }));
    expect(onCreate).toHaveBeenCalledWith(expect.objectContaining({ image: 'redroid/arm64:13' }));
    view.rerender(<CreateForm environment={{ ...environment, images: [images[0]] }} availableSlots={3} pending={false} onCreate={onCreate} />);
    expect(screen.getByLabelText('Android 镜像')).toHaveValue('');
    expect(screen.getByRole('button', { name: '创建 1 台实例' })).toBeDisabled();
    fireEvent.submit(screen.getByRole('button', { name: '创建 1 台实例' }).closest('form')!);
    expect(onCreate).toHaveBeenCalledTimes(1);
  });
  it('requires delete confirmation and does not call the API after cancelling', async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/environment') return Promise.resolve(response(environment));
      if (url === '/api/instances') return Promise.resolve(response({ instances: [{ ...instance, android_status: 'stopped' }] }));
      if (url === '/api/jobs') return Promise.resolve(response({ jobs: [], session_id: 'one' }));
      return Promise.resolve(response({ apks: [] }));
    });
    vi.stubGlobal('fetch', fetchMock); vi.spyOn(window, 'confirm').mockReturnValue(false);
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: '删除实例' }));
    expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('及其数据卷'));
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false);
  });
  it('signals that service restart lost job records', async () => {
    let session = 'one';
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => {
      if (url === '/api/environment') return Promise.resolve(response(environment));
      if (url === '/api/instances') return Promise.resolve(response({ instances: [] }));
      if (url === '/api/jobs') return Promise.resolve(response({ jobs: [], session_id: session }));
      return Promise.resolve(response({ apks: [] }));
    }));
    render(<App />);
    await waitFor(() => expect(screen.getByRole('button', { name: '重新检查' })).toBeEnabled());
    session = 'two';
    fireEvent.click(screen.getByRole('button', { name: '重新检查' }));
    expect(await screen.findByText(/管理服务已重启，之前的任务记录已丢失/)).toBeInTheDocument();
  });
  it('blocks non-ASCII text instead of pretending full Unicode input support', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => new Promise(() => {})));
    const input = vi.fn().mockResolvedValue(undefined);
    render(<DevicePanel instance={instance} pending={false} capacityFull={false} onAction={vi.fn()} onInput={input} />);
    fireEvent.change(screen.getByLabelText('向设备输入文字'), { target: { value: '中文' } });
    expect(screen.getByRole('button', { name: '发送文字' })).toBeDisabled();
    expect(screen.getByText(/暂不支持中文输入/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('向设备输入文字'), { target: { value: 'hello world' } });
    fireEvent.click(screen.getByRole('button', { name: '发送文字' }));
    expect(input).toHaveBeenCalledWith({ action: 'text', text: 'hello world' });
    fireEvent.click(screen.getByRole('button', { name: '设备按键 Home' }));
    expect(input).toHaveBeenCalledWith({ action: 'key', code: 3 });
  });
  it('retries a user action rejected busy before scheduling it', async () => {
    let actions = 0;
    const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (url === '/api/instances/demo-one/actions' && init?.method === 'POST') {
        actions += 1;
        return Promise.resolve(actions === 1 ? response({ error: { code: 'busy', message: '截图正在执行' } }, 409) : response({ job_id: 'started' }, 202));
      }
      if (url === '/api/environment') return Promise.resolve(response(environment));
      if (url === '/api/instances') return Promise.resolve(response({ instances: [{ ...instance, android_status: 'stopped' }] }));
      if (url === '/api/jobs') return Promise.resolve(response({ jobs: [], session_id: 'one' }));
      return Promise.resolve(response({ apks: [] }));
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: '启动' }));
    expect(await screen.findByText('设备任务已提交，请查看任务结果。')).toBeInTheDocument();
    expect(actions).toBe(2);
    expect(screen.queryByText(/操作失败/)).not.toBeInTheDocument();
  });
  it('waits out screenshot busy when the user reads third-party applications', async () => {
    let reads = 0;
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.endsWith('/packages')) {
        reads += 1;
        return Promise.resolve(reads === 1 ? response({ error: { code: 'busy', message: '截图正在执行' } }, 409) : response({ packages: ['org.example.app'] }));
      }
      return new Promise(() => {});
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<DevicePanel instance={instance} pending={false} capacityFull={false} onAction={vi.fn()} onInput={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: '读取第三方应用' }));
    expect(screen.getByRole('button', { name: '读取中…' })).toBeDisabled();
    expect(await screen.findByRole('option', { name: 'org.example.app' })).toBeInTheDocument();
    expect(reads).toBe(2);
    expect(screen.queryByText(/读取应用失败/)).not.toBeInTheDocument();
  });
  it('keeps failed per-device results and raw root findings visible', () => {
    render(<JobsPanel restarted={false} error="" jobs={[{ id: 'job', action: 'root_check', status: 'failed', total: 2, done: 2, results: [
      { instance_id: 'one', name: '设备 A', status: 'success', message: '已采集', data: { exec_uid: 'uid=0(root)', app_root: 'unverified' } },
      { instance_id: 'two', name: '设备 B', status: 'error', message: 'Android 启动超时' },
    ] }]} />);
    expect(screen.getByText('失败：Android 启动超时')).toBeInTheDocument();
    expect(screen.getByText(/"app_root": "unverified"/)).toBeInTheDocument();
  });
});
