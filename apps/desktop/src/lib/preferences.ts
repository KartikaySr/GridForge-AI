export interface Preferences {
  version: 1;
  theme: 'dark' | 'light';
  compact: boolean;
}
export const defaults: Preferences = {
  version: 1,
  theme: 'dark',
  compact: true,
};
const KEY = 'gridforge.desktop.preferences.v1';
export function readPreferences(): Preferences {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(KEY) ?? 'null');
    if (typeof value !== 'object' || value === null) return defaults;
    const stored = value as Partial<Preferences>;
    if (
      stored.version !== 1 ||
      !['dark', 'light'].includes(stored.theme ?? '') ||
      typeof stored.compact !== 'boolean'
    )
      return defaults;
    return stored as Preferences;
  } catch {
    return defaults;
  }
}
export function savePreferences(value: Preferences): boolean {
  try {
    localStorage.setItem(KEY, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}
