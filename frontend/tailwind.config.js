/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#FBF9F3",
        ink: "#1B211F",
        pine: {
          50: "#EEF4F1",
          100: "#D3E3DC",
          400: "#3F8A72",
          600: "#2F6F5E",
          700: "#255A4C",
          900: "#12271F",
        },
        line: "#DED8C8",
        muted: "#736C5C",
      },
      fontFamily: {
        display: ["'Source Serif 4'", "Georgia", "serif"],
        body: ["'Inter'", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
