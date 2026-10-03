import { afterEach, expect, it, vi } from 'vitest';
import { withTimeout } from './runtime';

afterEach(() => vi.useRealTimers());
it('bounds an unresponsive desktop bridge so health cannot remain live indefinitely', async () => {
  vi.useFakeTimers();
  const result = withTimeout(new Promise<never>(() => {}));
  const assertion = expect(result).rejects.toThrow('Desktop bridge timed out');
  await vi.advanceTimersByTimeAsync(2500);
  await assertion;
});
it('returns successful IPC responses without leaving timeout work pending', async () => {
  vi.useFakeTimers();
  expect(await withTimeout(Promise.resolve('ready'))).toBe('ready');
  expect(vi.getTimerCount()).toBe(0);
});
