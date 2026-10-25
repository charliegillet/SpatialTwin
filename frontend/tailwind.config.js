/** @type {import('tailwindcss').Config} */
// Utility classes are not used in the markup; styling comes from the tokens in src/index.css.
// The theme mirrors those tokens so any future utility stays on the DESIGN.md palette.
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
      colors: {
        canvas: "#0c0f10",
        surface: "#151a1b",
        raised: "#1c2223",
        line: "#30383a",
        ink: "#f1f3ef",
        muted: "#a1ada7",
        accent: "#d3ed9c",
        warning: "#efa28c",
      },
    },
  },
  plugins: [],
};
