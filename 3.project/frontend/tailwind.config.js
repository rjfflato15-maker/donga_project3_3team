/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        indigo: { 50:'#f4f8ff', 100:'#edf3fd', 200:'#c7d7ee', 300:'#99baf0', 400:'#6b91c5', 500:'#4e78b5', 600:'#315eaa', 700:'#284f90', 800:'#243f70', 900:'#243349' },
        brand: {
          50: '#eff6ff',
          100: '#dbeafe',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
        }
      }
    },
  },
  plugins: [],
}
