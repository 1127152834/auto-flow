import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ScreenPreview, screenPoint } from './ScreenPreview';

describe('actual screenshot coordinate mapping', () => {
  const rect = { left: 10, top: 20, width: 400, height: 400 };
  it('uses actual portrait dimensions and ignores horizontal letterboxing', () => {
    expect(screenPoint(210, 220, rect, 1080, 1920)).toEqual({ x: 540, y: 960 });
    expect(screenPoint(30, 220, rect, 1080, 1920)).toBeNull();
    expect(screenPoint(410, 220, rect, 1080, 1920)).toBeNull();
  });
  it('supports landscape and rejects vertical letterboxing and unloaded frames', () => {
    expect(screenPoint(210, 220, rect, 1920, 1080)).toEqual({ x: 960, y: 540 });
    expect(screenPoint(210, 25, rect, 1920, 1080)).toBeNull();
    expect(screenPoint(10, 20, rect, 0, 0)).toBeNull();
  });
});

describe('single-frame lifecycle', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn().mockReturnValueOnce('blob:first').mockReturnValue('blob:second') });
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
  });
  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); Object.defineProperty(document, 'hidden', { configurable: true, value: false }); });
  const png = () => new Response(new Blob(['png']), { headers: { 'content-type': 'image/png' } });
  it('never overlaps pending requests, waits a full second, and releases URLs', async () => {
    let finish!: (response: Response) => void;
    const fetchMock = vi.fn().mockImplementationOnce(() => new Promise<Response>(resolve => { finish = resolve; })).mockImplementation(() => Promise.resolve(png()));
    vi.stubGlobal('fetch', fetchMock);
    const view = render(<ScreenPreview id="one" enabled onInput={vi.fn()} />);
    await act(async () => { await vi.advanceTimersByTimeAsync(5_000); });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await act(async () => { finish(png()); });
    expect(screen.getByRole('img')).toHaveAttribute('src', 'blob:first');
    await act(async () => { await vi.advanceTimersByTimeAsync(999); });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:first');
    view.unmount();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:second');
    await act(async () => { await vi.advanceTimersByTimeAsync(5_000); });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
  it('pauses in a hidden page and when the device becomes busy', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(png()));
    vi.stubGlobal('fetch', fetchMock);
    const view = render(<ScreenPreview id="one" enabled onInput={vi.fn()} />);
    await act(async () => {});
    Object.defineProperty(document, 'hidden', { configurable: true, value: true });
    fireEvent(document, new Event('visibilitychange'));
    await act(async () => { await vi.advanceTimersByTimeAsync(6_000); });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
    fireEvent(document, new Event('visibilitychange'));
    await act(async () => { await vi.advanceTimersByTimeAsync(1_000); });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    view.rerender(<ScreenPreview id="one" enabled={false} onInput={vi.fn()} />);
    await act(async () => { await vi.advanceTimersByTimeAsync(5_000); });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });
  it('aborts an in-flight request when switching the selected device', async () => {
    const fetchMock = vi.fn().mockImplementation(() => new Promise(() => {}));
    vi.stubGlobal('fetch', fetchMock);
    const view = render(<ScreenPreview id="one" enabled onInput={vi.fn()} />);
    const signal = fetchMock.mock.calls[0][1].signal as AbortSignal;
    view.rerender(<ScreenPreview id="two" enabled onInput={vi.fn()} />);
    expect(signal.aborted).toBe(true);
    await act(async () => { await vi.advanceTimersByTimeAsync(1_000); });
    expect(fetchMock.mock.calls[1][0]).toBe('/api/instances/two/screen');
  });
  it('preserves the one-second rate limit across brief busy transitions', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(png()));
    vi.stubGlobal('fetch', fetchMock);
    const view = render(<ScreenPreview id="one" enabled onInput={vi.fn()} />);
    await act(async () => {});
    view.rerender(<ScreenPreview id="one" enabled={false} onInput={vi.fn()} />);
    view.rerender(<ScreenPreview id="one" enabled onInput={vi.fn()} />);
    await act(async () => { await vi.advanceTimersByTimeAsync(999); });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
  it('sends actual tap/swipe coordinates and ignores gestures starting in the letterbox', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(png())));
    const input = vi.fn().mockResolvedValue(undefined);
    render(<ScreenPreview id="one" enabled onInput={input} />);
    await act(async () => {});
    const img = screen.getByRole('img');
    Object.defineProperties(img, { naturalWidth: { value: 1080 }, naturalHeight: { value: 1920 } });
    vi.spyOn(img, 'getBoundingClientRect').mockReturnValue({ left: 10, top: 20, width: 400, height: 400 } as DOMRect);
    fireEvent.pointerDown(img, { clientX: 210, clientY: 220, button: 0, pointerId: 1 });
    fireEvent.pointerUp(img, { clientX: 210, clientY: 220, pointerId: 1 });
    expect(input).toHaveBeenCalledWith({ action: 'tap', x: 540, y: 960 });
    fireEvent.pointerDown(img, { clientX: 210, clientY: 220, button: 0, pointerId: 2 });
    fireEvent.pointerUp(img, { clientX: 210, clientY: 120, pointerId: 2 });
    expect(input).toHaveBeenCalledWith({ action: 'swipe', x1: 540, y1: 960, x2: 540, y2: 480 });
    fireEvent.pointerDown(img, { clientX: 20, clientY: 220, button: 0, pointerId: 3 });
    fireEvent.pointerUp(img, { clientX: 210, clientY: 220, pointerId: 3 });
    expect(input).toHaveBeenCalledTimes(2);
  });
  it('reports screenshot HTTP errors without rendering an image', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { message: '设备尚未启动' } }), { status: 409 })));
    render(<ScreenPreview id="one" enabled onInput={vi.fn()} />);
    await act(async () => {});
    expect(screen.getByText('截图失败：设备尚未启动')).toBeInTheDocument();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });
});
