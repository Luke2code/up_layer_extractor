import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        accent: {
          DEFAULT: "#5F7600",
          soft: "#EEF3D8"
        }
      },
      fontFamily: {
        sans: ["Poppins", "Google Sans Flex", "Arial", "sans-serif"]
      }
    }
  },
  plugins: []
} satisfies Config;

