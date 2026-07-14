import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "../../packages/ui/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#0f1115",
          raised: "#161923",
          border: "#262b38",
        },
        ink: {
          DEFAULT: "#e5e7eb",
          muted: "#9aa1b1",
          faint: "#6b7280",
        },
        accent: {
          DEFAULT: "#e8722c",
          hover: "#f0863f",
          muted: "#5c3a24",
        },
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
