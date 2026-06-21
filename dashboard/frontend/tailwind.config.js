import tailwindcssAnimate from 'tailwindcss-animate'

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: 'var(--bg)',
        surface: { DEFAULT: 'var(--surface)', 2: 'var(--surface-2)' },
        border: 'var(--border)',
        foreground: 'var(--fg)',
        muted: 'var(--muted)',
        primary: { DEFAULT: 'var(--primary)', deep: 'var(--primary-deep)' },
        accent: { DEFAULT: 'var(--accent)', strong: 'var(--accent-strong)' },
        accepted: 'var(--accepted)',
        rejected: 'var(--rejected)',
        seed: 'var(--seed)',
      },
      fontFamily: {
        sans: ['"Fira Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"Fira Code"', 'ui-monospace', 'monospace'],
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
