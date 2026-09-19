import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class", '[data-theme="dark"]'],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        // "Iris" -- signature primary (violet), replaces the generic SaaS blue
        brand: {
          50: "#f5f0fe",
          100: "#ebe0fd",
          200: "#d3b9fb",
          300: "#b892f7",
          400: "#9a68f2",
          500: "#7c3aed",
          600: "#6423d6",
          700: "#511bad",
          800: "#3f1687",
          900: "#33146d",
        },
        // "Champagne" -- premium accent, reserved for highlights
        accent: {
          50: "#fdf8ec",
          100: "#faf1dc",
          200: "#f3e0ae",
          300: "#eccd7d",
          400: "#e4b74f",
          500: "#c9971c",
          600: "#a87a15",
          700: "#835f10",
          800: "#5f450c",
          900: "#463309",
        },
      },
      boxShadow: {
        xs: "0 1px 2px rgba(23, 20, 31, 0.05)",
        card: "0 4px 18px -4px rgba(23, 20, 31, 0.12), 0 2px 6px -2px rgba(23, 20, 31, 0.06)",
        pop: "0 20px 48px -14px rgba(23, 20, 31, 0.22), 0 6px 14px -4px rgba(23, 20, 31, 0.10)",
      },
      transitionTimingFunction: {
        smooth: "cubic-bezier(0.16, 1, 0.3, 1)",
      },
    },
  },
  plugins: [],
};
export default config;
