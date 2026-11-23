/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        border: "hsl(220 13% 87%)",
        background: "hsl(0 0% 100%)",
        foreground: "hsl(222 20% 12%)",
        muted: "hsl(220 14% 96%)",
        "muted-foreground": "hsl(220 9% 42%)",
        primary: "hsl(221 72% 42%)",
        "primary-foreground": "hsl(0 0% 100%)",
        danger: "hsl(0 65% 45%)",
      },
      fontFamily: {
        sans: ["system-ui", "Segoe UI", "Roboto", "Helvetica", "Arial", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
