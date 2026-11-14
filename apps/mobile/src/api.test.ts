import { expect, it } from 'vitest';
import { apiOrigin } from './api';
it('requires an HTTPS origin without embedded credentials or routing fragments', () => {
  expect(apiOrigin('https://demo.example')).toBe('https://demo.example');
  for (const url of [
    'http://demo.example',
    'https://user:password@demo.example',
    'https://demo.example/api',
    'https://demo.example?token=x',
    'https://demo.example#x',
  ])
    expect(() => apiOrigin(url)).toThrow();
});
