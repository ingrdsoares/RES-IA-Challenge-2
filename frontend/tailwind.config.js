/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: 'var(--ink)',
        link: 'var(--ink-link)',
        info: 'var(--surface-info)',
        highlight: 'var(--citation-mark)',
        notice: 'var(--surface-notice)',
        accent: 'var(--palette-honey)',
        focus: 'var(--focus-color)',
      }
    },
  },
  plugins: [],
}
