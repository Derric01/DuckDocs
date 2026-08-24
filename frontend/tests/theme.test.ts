/**
 * Theme persistence exists to stop the reload flash. These cover the two ways
 * that regresses: the stored choice not being read back, and `system` not
 * following the OS.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  DENSITY_KEY,
  THEME_BOOTSTRAP,
  THEME_KEY,
  applyDensity,
  applyTheme,
  readDensity,
  readTheme,
  resolveTheme,
} from '@/lib/theme';

function prefersLight(matches: boolean): void {
  vi.stubGlobal(
    'matchMedia',
    vi.fn((query: string) => ({
      matches: query.includes('light') ? matches : !matches,
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    })),
  );
}

beforeEach(() => {
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
  delete document.documentElement.dataset.density;
});

describe('resolveTheme', () => {
  it('returns an explicit choice unchanged', () => {
    expect(resolveTheme('light')).toBe('light');
    expect(resolveTheme('dark')).toBe('dark');
  });

  it('follows the OS when the choice is system', () => {
    prefersLight(true);
    expect(resolveTheme('system')).toBe('light');
    prefersLight(false);
    expect(resolveTheme('system')).toBe('dark');
  });
});

describe('persistence', () => {
  it('reads back what was stored', () => {
    applyTheme('light');
    expect(window.localStorage.getItem(THEME_KEY)).toBe('light');
    expect(readTheme()).toBe('light');
    expect(document.documentElement.dataset.theme).toBe('light');
  });

  it('ignores a corrupted stored value rather than applying it', () => {
    window.localStorage.setItem(THEME_KEY, 'chartreuse');
    expect(readTheme()).toBe('system');
  });

  it('stores density and reflects it on the root element', () => {
    applyDensity('comfortable');
    expect(window.localStorage.getItem(DENSITY_KEY)).toBe('comfortable');
    expect(readDensity()).toBe('comfortable');
    expect(document.documentElement.dataset.density).toBe('comfortable');
  });

  it('defaults density to dense', () => {
    expect(readDensity()).toBe('dense');
  });
});

describe('pre-paint bootstrap', () => {
  it('applies the stored choice before React runs', () => {
    window.localStorage.setItem(THEME_KEY, 'light');
    window.localStorage.setItem(DENSITY_KEY, 'comfortable');

    // eslint-disable-next-line no-eval
    eval(THEME_BOOTSTRAP);

    expect(document.documentElement.dataset.theme).toBe('light');
    expect(document.documentElement.dataset.density).toBe('comfortable');
  });

  it('references the same keys the app writes, so the two cannot drift', () => {
    expect(THEME_BOOTSTRAP).toContain(THEME_KEY);
    expect(THEME_BOOTSTRAP).toContain(DENSITY_KEY);
  });
});
