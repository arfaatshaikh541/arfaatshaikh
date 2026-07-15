/**
 * GRIDKEEP shared Tailwind design tokens.
 * Dark-neutral command-centre surface with a restrained orange security accent
 * and an explicit severity colour system. Consumed by apps/web/tailwind.config.ts.
 */
module.exports = {
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        surface: {
          950: "#0a0b0d",
          900: "#101216",
          800: "#171a1f",
          700: "#20242b",
          600: "#2b3038",
          500: "#3a4048",
          border: "#2a2e35",
        },
        ink: {
          900: "#f4f5f6",
          700: "#c7cbd1",
          500: "#8b919b",
          300: "#5b6169",
        },
        accent: {
          DEFAULT: "#e8720c",
          strong: "#ff8a1f",
          muted: "#c25e0a",
          subtle: "#3a2410",
        },
        severity: {
          critical: "#e5484d",
          high: "#e8720c",
          medium: "#e0b400",
          low: "#3b82f6",
          info: "#8b919b",
          resolved: "#2fb767",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      borderRadius: {
        sm: "4px",
        DEFAULT: "6px",
        md: "8px",
        lg: "12px",
      },
    },
  },
  plugins: [],
};
