import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, post, request, withBusyRetry } from './api';

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });
describe('HTTP client', () => {
  it('propagates the actual busy failure rather than treating JSON as success', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: 'busy', message: '设备正在安装 APK' } }), { status: 409 })));
    await expect(post('/instances/a/input', { action: 'key', code: 3 })).rejects.toMatchObject({ status: 409, code: 'busy', message: '设备正在安装 APK' });
  });
  it('reports a non-JSON service error clearly', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>gateway error</html>', { status: 503 })));
    await expect(request('/instances')).rejects.toEqual(new ApiError('请求失败（HTTP 503）', 503, 'http_error'));
  });
  it('sends JSON with the required content type and leaves upload FormData untouched', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response('{}')));
    vi.stubGlobal('fetch', fetchMock);
    await post('/instances', { count: 3 });
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{"count":3}' });
    const body = new FormData(); body.append('file', new Blob(['apk']), 'app.apk');
    await request('/apks', { method: 'POST', body });
    expect(fetchMock.mock.calls[1][1].body).toBe(body);
    expect(fetchMock.mock.calls[1][1].headers).toBeUndefined();
  });
});

describe('explicit busy contention', () => {
  const busy = () => new Response(JSON.stringify({ error: { code: 'busy', message: '设备正忙' } }), { status: 409 });
  it('waits for a rejected busy input and stops retrying after success', async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn().mockImplementationOnce(() => Promise.resolve(busy())).mockResolvedValue(new Response('{"ok":true}'));
    vi.stubGlobal('fetch', fetchMock);
    const result = withBusyRetry(() => post('/instances/one/input', { action: 'key', code: 4 }));
    await vi.advanceTimersByTimeAsync(199);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    await expect(result).resolves.toEqual({ ok: true });
    await vi.advanceTimersByTimeAsync(2_000);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls.every(([url, init]) => url === '/api/instances/one/input' && init.body === '{"action":"key","code":4}')).toBe(true);
  });
  it('ends the busy retry window after two seconds', async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(busy()));
    vi.stubGlobal('fetch', fetchMock);
    const result = withBusyRetry(() => post('/instances/one/input', { action: 'key', code: 4 })).catch(error => error);
    await vi.advanceTimersByTimeAsync(2_500);
    expect(await result).toMatchObject({ status: 409, code: 'busy' });
    expect(fetchMock).toHaveBeenCalledTimes(11);
  });
  it.each([
    ['network failure', () => Promise.reject(new TypeError('Connection lost'))],
    ['another conflict', () => Promise.resolve(new Response(JSON.stringify({ error: { code: 'not_ready' } }), { status: 409 }))],
    ['uncertain execution', () => Promise.resolve(new Response(JSON.stringify({ error: { code: 'exec_uncertain' } }), { status: 503 }))],
  ])('never retries %s', async (_name, response) => {
    const fetchMock = vi.fn().mockImplementation(response);
    vi.stubGlobal('fetch', fetchMock);
    await expect(withBusyRetry(() => post('/instances/one/input', { action: 'key', code: 4 }))).rejects.toBeInstanceOf(Error);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
