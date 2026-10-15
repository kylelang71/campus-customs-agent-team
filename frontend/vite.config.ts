import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// `npm run dev` serves the board at http://localhost:5173 and opens it in the browser.
// strictPort: the backend only allows this exact origin, so fail loudly instead of moving to another port.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true, open: true },
})
