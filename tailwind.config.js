/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/renderer/**/*.{html,js,jsx,ts,tsx}",
  ],
  theme: {
    /* ----------------------------------------------------------
       Colors — Construct v2 Design Tokens
       ---------------------------------------------------------- */
    colors: {
      transparent: "transparent",
      current:     "currentColor",

      /* Surfaces */
      "c-base":    "#0c0e11",
      "c-s1":      "#141619",
      "c-s2":      "#1e2023",
      "c-s3":      "#282a2d",
      "c-s4":      "#333538",

      /* Accent — Electric Cyan */
      "c-accent":  "#00f5ff",
      "c-accent-dim": "rgba(0, 245, 255, 0.15)",

      /* Gold — Memory/Context */
      "c-gold":    "#e9c349",
      "c-gold-dim": "rgba(233, 195, 73, 0.15)",

      /* Text */
      "c-text":    "#e2e2e6",
      "c-text2":   "#b9caca",
      "c-text3":   "#849495",
      "c-text4":   "#3a494a",

      /* Semantic */
      "c-ok":      "#4ade80",
      "c-ok-bg":   "rgba(74, 222, 128, 0.1)",
      "c-warn":    "#f59e0b",
      "c-err":     "#f87171",
      "c-err-bg":  "rgba(248, 113, 113, 0.1)",
      "c-info":    "#60a5fa",

      /* Running status */
      "c-running": "#22c55e",
      "c-running-bg": "rgba(34, 197, 94, 0.15)",

      /* Borders */
      "c-border":  "#282a2d",
      "c-border-active": "rgba(0, 245, 255, 0.30)",

      /* Diff */
      "diff-add":     "#4ade80",
      "diff-add-bg":  "rgba(74, 222, 128, 0.1)",
      "diff-remove":  "#f87171",
      "diff-remove-bg": "rgba(248, 113, 113, 0.1)",

      /* Status */
      "status-running": "#22c55e",
      "status-running-bg": "rgba(34, 197, 94, 0.15)",

      /* Onyx for backgrounds */
      "bg-onyx":    "#0c0e11",
      "panel-bg":   "#141619",
      "border-subtle": "#282a2d",
      "text-primary": "#e2e2e6",
      "text-secondary": "#849495",
      "accent-cyan": "#00f5ff",
      "accent-cyan-dim": "rgba(0, 245, 255, 0.15)",

      /* Gold accent aliases */
      "accent-gold": "#e9c349",
      "accent-gold-dim": "rgba(233, 195, 73, 0.15)",

      /* Tertiary / Error */
      "tertiary": "#ffb4ab",
      "tertiary-dim": "rgba(255, 180, 171, 0.15)",

      /* Success */
      "success": "#22c55e",
      "success-dim": "rgba(34, 197, 94, 0.15)",
    },

    /* ----------------------------------------------------------
       Font Family — Inter + JetBrains Mono
       ---------------------------------------------------------- */
    fontFamily: {
      sans: [
        '"Inter"',
        '"system-ui"',
        '"sans-serif"',
      ],
      mono: [
        '"JetBrains Mono"',
        '"Fira Code"',
        '"Consolas"',
        "monospace",
      ],
    },

    /* ----------------------------------------------------------
       Font Size
       ---------------------------------------------------------- */
    fontSize: {
      xs:   ["10px", { lineHeight: "1.4" }],
      sm:   ["11px", { lineHeight: "1.4" }],
      base: ["12px", { lineHeight: "1.4" }],
      lg:   ["13px", { lineHeight: "1.4" }],
      xl:   ["14px", { lineHeight: "1.4" }],
      "2xl": ["16px", { lineHeight: "1.2" }],
      "3xl": ["20px", { lineHeight: "1.2" }],
    },

    /* ----------------------------------------------------------
       Spacing
       ---------------------------------------------------------- */
    spacing: {
      0:  "0px",
      1:  "4px",
      2:  "6px",
      3:  "8px",
      4:  "12px",
      5:  "16px",
      6:  "24px",
      7:  "32px",
      8:  "48px",
    },

    /* ----------------------------------------------------------
       Border Radius
       ---------------------------------------------------------- */
    borderRadius: {
      none: "0px",
      sm:   "2px",
      DEFAULT: "4px",
      md:   "6px",
      lg:   "8px",
      full: "9999px",
    },

    /* ----------------------------------------------------------
       Line Height
       ---------------------------------------------------------- */
    lineHeight: {
      tight:  "1.2",
      normal: "1.4",
      relaxed: "1.6",
    },

    /* ----------------------------------------------------------
       Letter Spacing
       ---------------------------------------------------------- */
    letterSpacing: {
      tight:  "-0.01em",
      normal: "0em",
      wide:   "0.02em",
      wider:  "0.06em",
      widest: "0.1em",
    },

    /* ----------------------------------------------------------
       Transition Duration
       ---------------------------------------------------------- */
    transitionDuration: {
      fast:   "100ms",
      normal: "150ms",
    },

    /* ----------------------------------------------------------
       Transition Timing Function
       ---------------------------------------------------------- */
    transitionTimingFunction: {
      default: "cubic-bezier(0.4, 0, 0.2, 1)",
    },

    extend: {},
  },
  plugins: [],
};
