import forms from "@tailwindcss/forms";

export default {
  content: [
    "./templates/**/*.html",
    "./core/**/*.py",
    "./apps/**/*.py",
    "./frontend/src/**/*.{js,css}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Manrope", "Inter", "Segoe UI", "system-ui", "sans-serif"],
        display: ["Fraunces", "Georgia", "serif"],
      },
      colors: {
        hearth: {
          ink: "#2f261f",
          clay: "#c8684b",
          rose: "#e6a6a0",
          sage: "#809978",
          honey: "#f3b85b",
          cream: "#fff6e8",
        },
      },
    },
  },
  plugins: [forms],
};
