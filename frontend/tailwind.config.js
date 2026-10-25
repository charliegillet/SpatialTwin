/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'system-ui', 'sans-serif'],
        display: ['"Rajdhani"', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      colors: {
        twin: {
          bg: "#050811",
          surface: "#0a0f1d",
          card: "#0e1526",
          border: "#1b253b",
          cyan: "#00f5ff",
          emerald: "#10b981",
          amber: "#f59e0b",
          rose: "#f43f5e",
        }
      },
      boxShadow: {
        'neon-cyan': '0 0 25px -4px rgba(0, 245, 255, 0.4)',
        'neon-emerald': '0 0 25px -4px rgba(16, 185, 129, 0.4)',
        'neon-rose': '0 0 25px -4px rgba(244, 63, 94, 0.4)',
        'neon-amber': '0 0 25px -4px rgba(245, 158, 11, 0.4)',
        'cockpit': '0 10px 40px -10px rgba(0, 0, 0, 0.7)',
      }
    },
  },
  plugins: [],
};
