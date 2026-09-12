import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, post, request } from './api';

afterEach(() => vi.unstubAllGlobals());
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
