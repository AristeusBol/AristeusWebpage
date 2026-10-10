/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Aristeus Corporate Palette
        'aristeus': {
          'navy': 'rgb(var(--tw-aristeus-navy) / <alpha-value>)',
          'green': 'rgb(var(--tw-aristeus-green) / <alpha-value>)',
          'secondary': 'rgb(var(--tw-aristeus-secondary) / <alpha-value>)',
        },
        // Backgrounds
        'bg': {
          'primary': 'rgb(var(--tw-bg-primary) / <alpha-value>)',
          'secondary': 'rgb(var(--tw-bg-secondary) / <alpha-value>)',
          'card': 'rgb(var(--tw-bg-card) / <alpha-value>)',
        },
        // Text
        'text': {
          'primary': 'rgb(var(--tw-text-primary) / <alpha-value>)',
          'secondary': 'rgb(var(--tw-text-secondary) / <alpha-value>)',
          'inverse': 'rgb(var(--tw-text-inverse) / <alpha-value>)',
        },
        'border-subtle': 'rgb(var(--tw-border-subtle) / <alpha-value>)',
        // Grass Gauge Palette
        'gg': {
          'green-dark': 'rgb(var(--tw-gg-green-dark) / <alpha-value>)',
          'green-mid': 'rgb(var(--tw-gg-green-mid) / <alpha-value>)',
          'green-light': 'rgb(var(--tw-gg-green-light) / <alpha-value>)',
        },
        // CattleVision Palette
        'cv': {
          'charcoal': 'rgb(var(--tw-cv-charcoal) / <alpha-value>)',
          'gold': 'rgb(var(--tw-cv-gold) / <alpha-value>)',
          'dark': 'rgb(var(--tw-cv-dark) / <alpha-value>)',
        }
      },
      fontFamily: {
        'heading': ['"Space Grotesk"', 'sans-serif'],
        'body': ['"IBM Plex Sans"', 'sans-serif'],
        'data': ['"JetBrains Mono"', 'monospace'],
      },
      animation: {
        'fade-up': 'fadeUp 0.6s ease-out forwards',
        'fade-in': 'fadeIn 0.4s ease-out forwards',
        'slide-left': 'slideLeft 0.5s ease-out forwards',
        'slide-right': 'slideRight 0.5s ease-out forwards',
        'counter': 'counter 1s ease-out forwards',
      },
      keyframes: {
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(24px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideLeft: {
          '0%': { opacity: '0', transform: 'translateX(32px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        slideRight: {
          '0%': { opacity: '0', transform: 'translateX(-32px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
      },
      backdropBlur: {
        'xs': '2px',
      },
      backgroundImage: {
        'gg-gradient': 'linear-gradient(135deg, #355E3B, #6BA539)',
        'cv-gradient': 'linear-gradient(135deg, #2B2F36, #B8963E)',
      },
    },
  },
  plugins: [],
}
