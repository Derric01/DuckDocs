import type { Config } from 'tailwindcss';

/**
 * Apple-flavoured theme.
 *
 * The reference points are iOS/macOS system conventions rather than a generic
 * SaaS palette: system greys, systemBlue as the single accent, larger corner
 * radii, layered soft shadows, translucent chrome, and Apple's standard
 * easing curve. Colours are HSL triples in CSS variables (shadcn convention)
 * so light/dark swap without duplicating utility classes.
 */
const config: Config = {
  darkMode: ['class', '[data-theme="dark"]'],
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        'border-strong': 'hsl(var(--border-strong))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        // Grouped-list background vs. the raised rows that sit on it — the
        // structural relationship iOS Settings is built from.
        grouped: 'hsl(var(--grouped))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
          muted: 'hsl(var(--primary-muted))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        success: {
          DEFAULT: 'hsl(var(--success))',
          muted: 'hsl(var(--success-muted))',
        },
        warning: {
          DEFAULT: 'hsl(var(--warning))',
          muted: 'hsl(var(--warning-muted))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
          muted: 'hsl(var(--destructive-muted))',
        },
      },
      borderRadius: {
        // Apple runs larger than the web default; continuous-ish corners are
        // a big part of why iOS surfaces read as soft rather than boxy.
        sm: '6px',
        DEFAULT: '8px',
        md: '10px',
        lg: '12px',
        xl: '14px',
        '2xl': '18px',
        '3xl': '24px',
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          'SF Pro Text',
          'var(--font-inter)',
          'system-ui',
          'sans-serif',
        ],
        mono: ['SF Mono', 'var(--font-mono-jetbrains)', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        // Roughly the iOS text styles, which are tighter at the top end than
        // Tailwind's defaults and give a calmer hierarchy.
        '2xs': ['0.6875rem', { lineHeight: '0.875rem', letterSpacing: '0.01em' }],
        xs: ['0.75rem', { lineHeight: '1rem' }],
        sm: ['0.8125rem', { lineHeight: '1.125rem' }],
        base: ['0.9375rem', { lineHeight: '1.4rem', letterSpacing: '-0.01em' }],
        lg: ['1.0625rem', { lineHeight: '1.5rem', letterSpacing: '-0.015em' }],
        xl: ['1.25rem', { lineHeight: '1.625rem', letterSpacing: '-0.02em' }],
        '2xl': ['1.5rem', { lineHeight: '1.875rem', letterSpacing: '-0.022em' }],
        '3xl': ['1.9375rem', { lineHeight: '2.25rem', letterSpacing: '-0.025em' }],
        '4xl': ['2.5rem', { lineHeight: '2.75rem', letterSpacing: '-0.03em' }],
        '5xl': ['3.25rem', { lineHeight: '3.5rem', letterSpacing: '-0.032em' }],
      },
      boxShadow: {
        // Layered and low-opacity: Apple depth comes from stacked soft
        // shadows, not one dark drop.
        xs: 'var(--shadow-xs)',
        sm: 'var(--shadow-sm)',
        DEFAULT: 'var(--shadow-md)',
        md: 'var(--shadow-md)',
        lg: 'var(--shadow-lg)',
        xl: 'var(--shadow-xl)',
      },
      transitionTimingFunction: {
        // Apple's standard curve — decelerates hard at the end, which is what
        // makes iOS motion feel settled rather than linear.
        spring: 'cubic-bezier(0.32, 0.72, 0, 1)',
        'out-quart': 'cubic-bezier(0.25, 1, 0.5, 1)',
      },
      transitionDuration: {
        fast: '150ms',
        DEFAULT: '200ms',
        slow: '320ms',
      },
      keyframes: {
        'fade-in': { from: { opacity: '0' } },
        'scale-in': {
          from: { opacity: '0', transform: 'scale(0.97)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
        'slide-up': {
          from: { opacity: '0', transform: 'translate3d(0, 8px, 0)' },
          to: { opacity: '1', transform: 'translate3d(0, 0, 0)' },
        },
        'slide-down': {
          from: { opacity: '0', transform: 'translate3d(0, -4px, 0)' },
          to: { opacity: '1', transform: 'translate3d(0, 0, 0)' },
        },
        'slide-in-right': {
          from: { transform: 'translate3d(100%, 0, 0)' },
          to: { transform: 'translate3d(0, 0, 0)' },
        },
        shimmer: {
          from: { backgroundPosition: '200% 0' },
          to: { backgroundPosition: '-200% 0' },
        },
      },
      animation: {
        'fade-in': 'fade-in 200ms cubic-bezier(0.32, 0.72, 0, 1)',
        'scale-in': 'scale-in 200ms cubic-bezier(0.32, 0.72, 0, 1)',
        'slide-up': 'slide-up 240ms cubic-bezier(0.32, 0.72, 0, 1)',
        'slide-down': 'slide-down 180ms cubic-bezier(0.32, 0.72, 0, 1)',
        'slide-in-right': 'slide-in-right 320ms cubic-bezier(0.32, 0.72, 0, 1)',
        shimmer: 'shimmer 1.6s ease infinite',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};

export default config;
