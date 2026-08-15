import tailwindcssAnimate from 'tailwindcss-animate'

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: 'var(--bg)',
        surface: { DEFAULT: 'var(--surface)', 2: 'var(--surface-2)', 3: 'var(--surface-3)' },
        border: { DEFAULT: 'var(--border)', strong: 'var(--border-strong)' },
        foreground: 'var(--fg)',
        muted: { DEFAULT: 'var(--muted)', strong: 'var(--muted-strong)' },
        primary: {
          DEFAULT: 'var(--primary)',
          deep: 'var(--primary-deep)',
          soft: 'var(--primary-soft)',
        },
        accent: { DEFAULT: 'var(--accent)', strong: 'var(--accent-strong)' },
        accepted: 'var(--accepted)',
        rejected: 'var(--rejected)',
        indecisive: 'var(--indecisive)',
        failed: 'var(--failed)',
        seed: 'var(--seed)',
      },
      fontFamily: {
        // No webfont: system stacks only, so the SPA renders offline/air-gapped.
        // Defined once in src/index.css :root — referenced here so the utilities
        // and the raw body/.tnum rules can never drift apart.
        sans: 'var(--font-sans)',
        mono: 'var(--font-mono)',
      },
      fontVariantNumeric: ['tabular-nums'],
      boxShadow: {
        glow: '0 0 16px -2px var(--accent)',
        'glow-primary': '0 0 16px -2px var(--primary)',
      },
      transitionTimingFunction: {
        'spring-out': 'cubic-bezier(0.22, 1, 0.36, 1)',
      },
      keyframes: {
        'pulse-ring': {
          '0%': { transform: 'scale(0.95)', opacity: '0.7' },
          '70%': { transform: 'scale(1.6)', opacity: '0' },
          '100%': { transform: 'scale(1.6)', opacity: '0' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
      },
      animation: {
        'pulse-ring': 'pulse-ring 2s cubic-bezier(0.4,0,0.6,1) infinite',
      },
    },
  },
  plugins: [tailwindcssAnimate],
}
