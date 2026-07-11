import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx,md,mdx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        black: "#000000",
        "near-black": "#050505",
        graphite: "#0B0B0B",
        surface: "#111111",
        "surface-raised": "#161616",
        orange: {
          deep: "#7A2200",
          industrial: "#C84400",
          DEFAULT: "#FF5A00",
          bright: "#FF7A1A",
          hot: "#FF9A3D",
        },
        warm: "#F5F0E8",
        muted: "#8D8882",
        line: "rgba(255, 90, 0, 0.16)",
      },
      fontFamily: {
        display: ["var(--font-display)", "sans-serif"],
        sans: ["var(--font-sans)", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      letterSpacing: {
        widest2: "0.28em",
      },
      transitionTimingFunction: {
        cinematic: "cubic-bezier(0.16, 1, 0.3, 1)",
      },
      backgroundImage: {
        "grid-line":
          "linear-gradient(rgba(255,90,0,0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(255,90,0,0.08) 1px, transparent 1px)",
      },
    },
  },
  plugins: [],
};

export default config;
