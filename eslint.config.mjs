import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    // React Compiler-oriented rules (purity/immutability/set-state-in-effect)
    // assume plain React state. This directory drives Three.js/WebGL objects
    // imperatively inside useFrame/useMemo — mutating camera/material/buffer
    // state directly is the correct, performant pattern for React Three
    // Fiber, not a bug, so these specific rules are disabled here only.
    files: ["src/components/three/**/*.{ts,tsx}"],
    rules: {
      "react-hooks/purity": "off",
      "react-hooks/immutability": "off",
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/refs": "off",
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
