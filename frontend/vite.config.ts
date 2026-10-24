import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Le backend FastAPI écoute sur 8000 ; le frontend de développement le contacte par ce proxy.
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
