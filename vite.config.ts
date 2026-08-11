import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Only scan the application entry. Browser profiles and visual-test artifacts
  // under tmp/ can contain extension scripts with non-npm imports such as `chrome`.
  optimizeDeps: {
    entries: ['index.html'],
    noDiscovery: true,
    include: ['react', 'react-dom', 'lucide-react', 'maplibre-gl'],
  },
  server: { port: 5173 },
})
