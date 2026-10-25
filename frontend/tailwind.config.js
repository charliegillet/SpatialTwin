/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        twin: {
          bg: "#090d16",
          card: "#0f172a",
          border: "#1e293b",
          accent: "#38bdf8",
        }
      }
    },
  },
  plugins: [],
};
