/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          50:  '#f0fdf4',
          100: '#dcfce7',
          300: '#86efac',
          400: '#4ade80',
          500: '#22c55e',
          700: '#15803d',
          900: '#0D2818',
        },
        accent: {
          400: '#fbbf24',
          500: '#F5A623',
          600: '#d97706',
        },
        sage: {
          300: '#86efac',
          500: '#7DAE8A',
        },
        surface: '#F8F6F1',
        dark: '#0D2818',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        heading: ['Sora', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
