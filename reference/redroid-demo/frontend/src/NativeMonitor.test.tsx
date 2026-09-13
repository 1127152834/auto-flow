import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import NativeMonitor from './NativeMonitor';

afterEach(() => vi.unstubAllGlobals());
const instance = { id: 'afd-ef3857a550924052', name: 'Mac 测试设备', android_status: 'stopped', busy: false, width: 720, height: 1280, image: 'redroid:13' };
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

it('opens a real native session through the host endpoint, with no Android input controls', async () => {
  const fetcher = vi.fn().mockImplementation((_url: string, init?: RequestInit) => Promise.resolve(response(init?.method === 'POST'
    ? { phase: 'starting', instance_id: instance.id, message: '正在启动 Android' }
    : { instances: [instance], session: { phase: 'idle', instance_id: null, message: '尚未打开' } })));
  vi.stubGlobal('fetch', fetcher);
  render(<NativeMonitor />);
  fireEvent.click(await screen.findByRole('button', { name: '启动并打开原生窗口' }));
  await waitFor(() => expect(fetcher).toHaveBeenCalledWith('/api/native/open', expect.objectContaining({ method: 'POST', body: JSON.stringify({ instance_id: instance.id }) })));
  expect(await screen.findByText('正在启动 Android')).toBeInTheDocument();
  expect(screen.getByRole('button')).toBeDisabled();
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  expect(fetcher.mock.calls.some(([url]) => url.includes('/input'))).toBe(false);
});

it('shows actual launcher failures and does not pretend the device window is open', async () => {
  vi.stubGlobal('fetch', vi.fn().mockImplementation((_url: string, init?: RequestInit) => Promise.resolve(init?.method === 'POST'
    ? response({ error: { message: '已有窗口' } }, 409)
    : response({ instances: [instance], session: { phase: 'idle', instance_id: null, message: '尚未打开' } }))));
  render(<NativeMonitor />);
  fireEvent.click(await screen.findByRole('button', { name: '启动并打开原生窗口' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('已有窗口');
  expect(screen.queryByText(/已出画面/)).not.toBeInTheDocument();
});
