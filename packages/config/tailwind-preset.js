/**
 * Shared Tailwind design tokens: dark neutral operational UI with a
 * restrained orange accent. See docs/product for the design brief - no
 * glassmorphism, no gradients, no decorative animation.
 * @type {import('tailwindcss').Config}
 */
module.exports = {
  theme: {
    extend: {
      colors: {
        accent: {
          50: "#fff7ed",
          100: "#ffedd5",
          200: "#fed7aa",
          300: "#fdba74",
          400: "#fb923c",
          500: "#f97316",
          600: "#ea580c",
          700: "#c2410c",
          800: "#9a3412",
          900: "#7c2d12",
        },
        surface: {
          50: "#f7f7f8",
          100: "#eeeef0",
          200: "#d8d9dd",
          300: "#b7b9c0",
          400: "#8b8e99",
          500: "#6b6e79",
          600: "#4d4f59",
          700: "#34353d",
          800: "#212228",
          900: "#141519",
          950: "#0b0b0d",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
      },
    },
  },
};
