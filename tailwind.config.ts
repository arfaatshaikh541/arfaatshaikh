import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        black: {
          DEFAULT: "#000000",
          near: "#050505",
          graphite: "#0A0A0A",
          surface: "#111111",
        },
        orange: {
          burnt: "#6E2200",
          industrial: "#C94700",
          primary: "#FF5A00",
          bright: "#FF7A1A",
          hot: "#FFA048",
        },
        warmwhite: "#F2EEE8",
        muted: "#8B8580",
      },
      borderColor: {
        line: "rgba(255, 90, 0, 0.22)",
      },
      fontFamily: {
        display: ["var(--font-display)", "sans-serif"],
        body: ["var(--font-body)", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      letterSpacing: {
        widest2: "0.28em",
      },
      backgroundImage: {
        "grid-lines":
          "linear-gradient(rgba(255,90,0,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(255,90,0,0.05) 1px, transparent 1px)",
      },
      keyframes: {
        "pulse-glow": {
          "0%, 100%": { opacity: "0.55" },
          "50%": { opacity: "1" },
        },
        marquee: {
          "0%": { transform: "translateX(0)" },
          "100%": { transform: "translateX(-50%)" },
        },
      },
      animation: {
        "pulse-glow": "pulse-glow 3.4s ease-in-out infinite",
        marquee: "marquee 26s linear infinite",
      },
    },
  },
  plugins: [],
};

export default config;
