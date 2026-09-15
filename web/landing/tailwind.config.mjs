/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Aristeus Corporate Palette
        'aristeus': {
          'navy': '#0B2341',
          'green': '#6BA539',
          'secondary': '#355E3B',
        },
        // Backgrounds
        'bg': {
          'primary': '#F5F7F4',
          'secondary': '#D8DEE3',
          'card': '#FFFFFF',
        },
        // Text
        'text': {
          'primary': '#2B2F36',
          'secondary': '#355E3B',
          'inverse': '#F5F7F4',
        },
        'border-subtle': '#D8DEE3',
        // Grass Gauge Palette
        'gg': {
          'green-dark': '#355E3B',
          'green-mid': '#6BA539',
          'green-light': '#6BA539',
        },
        // CattleVision Palette
        'cv': {
          'charcoal': '#2B2F36',
          'gold': '#B8963E',
          'dark': '#0B2341',
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
