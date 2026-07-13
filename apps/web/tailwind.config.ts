import type { Config } from "tailwindcss";
// eslint-disable-next-line @typescript-eslint/no-var-requires
const sharedPreset = require("@leadflow/config/tailwind-preset.js");

const config: Config = {
  presets: [sharedPreset],
  content: [
    "./src/**/*.{ts,tsx}",
    "../../packages/ui/src/**/*.{ts,tsx}",
  ],
  darkMode: "media",
  theme: {
    extend: {},
  },
  plugins: [],
};

export default config;
