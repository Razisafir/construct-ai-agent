/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/renderer/**/*.{html,js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        construct: {
          bg: {
            primary: '#0a0a0f',
            secondary: '#12121a',
            tertiary: '#1a1a25',
            elevated: '#22222f',
            glass: 'rgba(18, 18, 26, 0.85)',
          },
          accent: {
            primary: '#6366f1',
            primaryHover: '#818cf8',
            secondary: '#8b5cf6',
            glow: 'rgba(99, 102, 241, 0.4)',
          },
          text: {
            primary: '#f1f5f9',
            secondary: '#94a3b8',
            muted: '#64748b',
          },
          border: {
            DEFAULT: 'rgba(255, 255, 255, 0.06)',
            hover: 'rgba(255, 255, 255, 0.12)',
          },
          semantic: {
            success: '#10b981',
            successBg: 'rgba(16, 185, 129, 0.1)',
            warning: '#f59e0b',
            warningBg: 'rgba(245, 158, 11, 0.1)',
            error: '#ef4444',
            errorBg: 'rgba(239, 68, 68, 0.1)',
            info: '#60a5fa',
            infoBg: 'rgba(96, 165, 250, 0.1)',
          },
          memory: {
            episodic: '#60a5fa',
            semantic: '#c084fc',
            procedural: '#fbbf24',
          },
          agent: {
            code: '#6366f1',
            legal: '#f43f5e',
            security: '#10b981',
            ui: '#ec4899',
            devops: '#f59e0b',
            test: '#06b6d4',
            research: '#8b5cf6',
            pm: '#14b8a6',
          },
        },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
      fontSize: {
        '2xs': '0.625rem',
      },
      borderRadius: {
        '2xl': '1rem',
        '3xl': '1.5rem',
      },
      animation: {
        'mesh-move': 'meshMove 20s ease-in-out infinite',
        'mesh-move-slow': 'meshMove 25s ease-in-out infinite reverse',
        'pulse-glow': 'pulseGlow 2s ease-in-out infinite',
        'float': 'float 6s ease-in-out infinite',
        'typing': 'typingBounce 1.4s ease-in-out infinite',
        'shimmer': 'shimmer 2s infinite',
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
        'toast-in': 'toastIn 0.3s ease-out',
        'toast-out': 'toastOut 0.3s ease-in',
      },
      keyframes: {
        meshMove: {
          '0%, 100%': { transform: 'translate(0, 0) scale(1)' },
          '33%': { transform: 'translate(30px, -30px) scale(1.1)' },
          '66%': { transform: 'translate(-20px, 20px) scale(0.95)' },
        },
        pulseGlow: {
          '0%, 100%': { opacity: '1', transform: 'scale(1)' },
          '50%': { opacity: '0.5', transform: 'scale(1.3)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        typingBounce: {
          '0%, 60%, 100%': { transform: 'translateY(0)' },
          '30%': { transform: 'translateY(-4px)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        fadeIn: {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        slideUp: {
          from: { transform: 'translateY(20px)', opacity: '0' },
          to: { transform: 'translateY(0)', opacity: '1' },
        },
        toastIn: {
          from: { transform: 'translateX(100%)', opacity: '0' },
          to: { transform: 'translateX(0)', opacity: '1' },
        },
        toastOut: {
          from: { transform: 'translateX(0)', opacity: '1' },
          to: { transform: 'translateX(100%)', opacity: '0' },
        },
      },
      backdropBlur: {
        xs: '2px',
      },
      transitionTimingFunction: {
        'spring': 'cubic-bezier(0.175, 0.885, 0.32, 1.275)',
      },
    },
  },
  plugins: [],
};
