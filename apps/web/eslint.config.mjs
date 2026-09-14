import { FlatCompat } from "@eslint/eslintrc";
import path from "node:path";
import { fileURLToPath } from "node:url";
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const compat = new FlatCompat({ baseDirectory: __dirname });
export default [
  // Flat config does not auto-ignore build output the way legacy .eslintrc
  // did - without this, `next build` followed by `next lint` sweeps
  // compiled/minified .next/** output into the lint run.
  { ignores: ["next-env.d.ts", ".next/**", "coverage/**"] },
  ...compat.extends("next/core-web-vitals", "next/typescript"),
];
