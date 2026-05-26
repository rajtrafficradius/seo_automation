import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#07111f",
        signal: "#f59e0b",
        mist: "#d8e1ea"
      }
    }
  },
  plugins: []
} satisfies Config;
