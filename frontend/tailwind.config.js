/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Ultra-black palette
        surface: {
          DEFAULT: '#0a0a0a',
          1: '#111111',
          2: '#161616',
          3: '#1c1c1c',
          4: '#222222',
          5: '#2a2a2a',
        },
        accent: {
          DEFAULT: '#3b82f6',
          dim: '#1d4ed8',
          glow: 'rgba(59,130,246,0.15)',
        },
        border: {
          DEFAULT: '#2a2a2a',
          bright: '#3a3a3a',
        },
        text: {
          primary: '#f0f0f0',
          secondary: '#888888',
          muted: '#555555',
        }
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
      animation: {
        'fade-in': 'fadeIn 0.2s ease-out',
        'slide-up': 'slideUp 0.25s ease-out',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        fadeIn: { from: { opacity: '0' }, to: { opacity: '1' } },
        slideUp: { from: { opacity: '0', transform: 'translateY(8px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
      },
    },
  },
  plugins: [],
}
