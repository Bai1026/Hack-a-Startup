import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// The kit's data folder is served as-is: /cases/<id>/..., /demo/demo_script.json
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: './', // relative, so the build works under /Hack-a-Startup/ on GitHub Pages
  publicDir: '../data',
  server: { port: 5173, strictPort: true },
  build: { copyPublicDir: true },
})
