/**
 * Theme and density persistence.
 *
 * The previous build set the theme only from React state, so a reload always
 * flashed the default before the user's choice applied, and the choice was
 * lost entirely. Preference now lives in localStorage and is applied by a
 * blocking inline script before first paint (see `app/layout.tsx`).
 */

export type ThemeChoice = 'light' | 'dark' | 'system';
export type Density = 'dense' | 'comfortable';

export const THEME_KEY = 'duckdocs.theme';
export const DENSITY_KEY = 'duckdocs.density';

export function resolveTheme(choice: ThemeChoice): 'light' | 'dark' {
  if (choice !== 'system') return choice;
  if (typeof window === 'undefined') return 'dark';
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

export function readTheme(): ThemeChoice {
  if (typeof window === 'undefined') return 'system';
  const stored = window.localStorage.getItem(THEME_KEY);
  return stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system';
}

export function applyTheme(choice: ThemeChoice): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(THEME_KEY, choice);
  document.documentElement.dataset.theme = resolveTheme(choice);
}

export function readDensity(): Density {
  if (typeof window === 'undefined') return 'dense';
  return window.localStorage.getItem(DENSITY_KEY) === 'comfortable' ? 'comfortable' : 'dense';
}

export function applyDensity(density: Density): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(DENSITY_KEY, density);
  document.documentElement.dataset.density = density;
}

/**
 * Runs before paint. Kept dependency-free and small because it is inlined
 * into the document head.
 */
export const THEME_BOOTSTRAP = `(function(){try{
var t=localStorage.getItem('${THEME_KEY}')||'system';
var d=localStorage.getItem('${DENSITY_KEY}')||'dense';
var r=t==='system'?(matchMedia('(prefers-color-scheme: light)').matches?'light':'dark'):t;
document.documentElement.dataset.theme=r;
document.documentElement.dataset.density=d;
}catch(e){document.documentElement.dataset.theme='dark';}})();`;
