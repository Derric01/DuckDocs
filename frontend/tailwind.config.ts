import type { Config } from 'tailwindcss';

/**
 * Editorial legal-tech theme.
 *
 * The reference points are document-work tools — Hebbia, Legora — rather than
 * a phone OS or a generic SaaS kit: warm paper neutrals, an ink-inverted
 * primary, hairline rules instead of soft shadows, small radii, a serif
 * display face, and a dense type scale that suits tables and long passages.
 *
 * Colours are HSL triples in CSS variables (shadcn convention) so light/dark
 * swap without duplicating utility classes.
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
        grouped: 'hsl(var(--grouped))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
          muted: 'hsl(var(--primary-muted))',
          vivid: 'hsl(var(--primary-vivid))',
        },
        /**
         * The single chromatic accent. Reserved for interactive meaning —
         * selection, focus, links, citation markers — so it never competes
         * with the semantic colours that carry the product's honesty signals.
         */
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
          muted: 'hsl(var(--accent-muted))',
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
        /**
         * Document-kind index. The same hue always means the same kind of
         * file, so a long library is scannable by shape and colour together.
         */
        kind: {
          doc: 'hsl(var(--kind-doc))',
          sheet: 'hsl(var(--kind-sheet))',
          slide: 'hsl(var(--kind-slide))',
          image: 'hsl(var(--kind-image))',
          code: 'hsl(var(--kind-code))',
          text: 'hsl(var(--kind-text))',
        },
      },
      borderRadius: {
        // Small and even. Large radii read as consumer software; document
        // tools stay close to the rectangle of the page.
        sm: '3px',
        DEFAULT: '5px',
        md: '6px',
        lg: '8px',
        xl: '10px',
        '2xl': '12px',
        '3xl': '16px',
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        display: ['var(--font-display)', 'Georgia', 'Times New Roman', 'serif'],
        mono: ['var(--font-mono-jetbrains)', 'SF Mono', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        // Denser than the previous scale at the small end (tables and metadata
        // live there) and taller at the top, where the serif display runs.
        '2xs': ['0.6875rem', { lineHeight: '0.9375rem', letterSpacing: '0.005em' }],
        xs: ['0.75rem', { lineHeight: '1.0625rem' }],
        sm: ['0.8125rem', { lineHeight: '1.1875rem' }],
        base: ['0.875rem', { lineHeight: '1.375rem' }],
        md: ['0.9375rem', { lineHeight: '1.5rem' }],
        lg: ['1.0625rem', { lineHeight: '1.625rem', letterSpacing: '-0.005em' }],
        xl: ['1.25rem', { lineHeight: '1.75rem', letterSpacing: '-0.01em' }],
        '2xl': ['1.5rem', { lineHeight: '1.9375rem', letterSpacing: '-0.014em' }],
        '3xl': ['2rem', { lineHeight: '2.375rem', letterSpacing: '-0.018em' }],
        '4xl': ['2.75rem', { lineHeight: '3.125rem', letterSpacing: '-0.022em' }],
        '5xl': ['3.75rem', { lineHeight: '4rem', letterSpacing: '-0.026em' }],
      },
      boxShadow: {
        xs: 'var(--shadow-xs)',
        sm: 'var(--shadow-sm)',
        DEFAULT: 'var(--shadow-md)',
        md: 'var(--shadow-md)',
        lg: 'var(--shadow-lg)',
        xl: 'var(--shadow-xl)',
      },
      transitionTimingFunction: {
        // Kept: a decelerating curve still reads as settled, and every surface
        // in the app already moves on it.
        spring: 'cubic-bezier(0.32, 0.72, 0, 1)',
        'out-quart': 'cubic-bezier(0.25, 1, 0.5, 1)',
      },
      transitionDuration: {
        fast: '130ms',
        DEFAULT: '180ms',
        slow: '280ms',
      },
      keyframes: {
        'fade-in': { from: { opacity: '0' } },
        'scale-in': {
          from: { opacity: '0', transform: 'scale(0.98)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
        'slide-up': {
          from: { opacity: '0', transform: 'translate3d(0, 6px, 0)' },
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
        'fade-in': 'fade-in 180ms cubic-bezier(0.32, 0.72, 0, 1)',
        'scale-in': 'scale-in 180ms cubic-bezier(0.32, 0.72, 0, 1)',
        'slide-up': 'slide-up 220ms cubic-bezier(0.32, 0.72, 0, 1)',
        'slide-down': 'slide-down 160ms cubic-bezier(0.32, 0.72, 0, 1)',
        'slide-in-right': 'slide-in-right 280ms cubic-bezier(0.32, 0.72, 0, 1)',
        shimmer: 'shimmer 1.6s ease infinite',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};

export default config;
