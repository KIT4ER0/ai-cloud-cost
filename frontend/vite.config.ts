import path from "path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            "@": path.resolve(__dirname, "./src"),
        },
    },
    server: {
        host: '0.0.0.0',
        port: 5173,
        strictPort: true,
        proxy: {
            '/api': {
                target: 'http://api:8000',
                changeOrigin: true,
                rewrite: (path) => path.replace(/^\/api/, ''),
            },
            '/forecast': {
                target: 'http://api:8000',
                changeOrigin: true,
            },
            '/sync': {
                target: 'http://api:8000',
                changeOrigin: true,
            },
            '/me': {
                target: 'http://api:8000',
                changeOrigin: true,
            },
        },
    },
})
