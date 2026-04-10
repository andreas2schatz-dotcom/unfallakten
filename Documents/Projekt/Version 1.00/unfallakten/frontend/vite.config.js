// vite.config.js – Unfallakten Frontend
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig(({ mode }) => ({
  plugins: [
    react({ fastRefresh: true }),
  ],

  server: {
    host:       '0.0.0.0',
    port:       5173,
    strictPort: true,

    proxy: {
      '/auth':          { target: process.env.VITE_BACKEND_URL || 'http://localhost:5000', changeOrigin: true },
      '/akten':         { target: process.env.VITE_BACKEND_URL || 'http://localhost:5000', changeOrigin: true },
      '/email':         { target: process.env.VITE_BACKEND_URL || 'http://localhost:5000', changeOrigin: true },
      '/wiedervorlage': { target: process.env.VITE_BACKEND_URL || 'http://localhost:5000', changeOrigin: true },
      '/word':          { target: process.env.VITE_BACKEND_URL || 'http://localhost:5000', changeOrigin: true },
      '/health':        { target: process.env.VITE_BACKEND_URL || 'http://localhost:5000', changeOrigin: true },
      '/aktensuche':    { target: process.env.VITE_BACKEND_URL || 'http://localhost:5000', changeOrigin: true },
      '/ramicro':       { target: process.env.VITE_BACKEND_URL || 'http://localhost:5000', changeOrigin: true },
      '/kuerzungsarten':{ target: process.env.VITE_BACKEND_URL || 'http://localhost:5000', changeOrigin: true },
      '/firmen':        { target: process.env.VITE_BACKEND_URL || 'http://localhost:5000', changeOrigin: true },
      '/distanz':       { target: process.env.VITE_BACKEND_URL || 'http://localhost:5000', changeOrigin: true },
      '/stellungnahme': { target: process.env.VITE_BACKEND_URL || 'http://localhost:5000', changeOrigin: true },
      '/dashboard':     { target: process.env.VITE_BACKEND_URL || 'http://localhost:5000', changeOrigin: true },
      '/einstellungen': { target: process.env.VITE_BACKEND_URL || 'http://localhost:5000', changeOrigin: true },
    },
  },

  preview: {
    host: '0.0.0.0',
    port: 4173,
  },

  build: {
    outDir:      'dist',
    emptyOutDir: true,
    sourcemap:   mode === 'development',
    rollupOptions: {
      output: {
        // Vendor-Chunks explizit trennen; Section-Chunks entstehen automatisch via React.lazy()
        manualChunks(id) {
          if (id.includes('node_modules/react') || id.includes('node_modules/react-dom')) {
            return 'react-vendor';
          }
          if (id.includes('node_modules/recharts') || id.includes('node_modules/d3-') ||
              id.includes('node_modules/victory-vendor')) {
            return 'recharts-vendor';
          }
        },
        assetFileNames: 'assets/[name]-[hash][extname]',
        chunkFileNames: 'assets/[name]-[hash].js',
        entryFileNames: 'assets/[name]-[hash].js',
      },
    },
    target:               'es2020',
    chunkSizeWarningLimit: 500,  // zurück auf Standard — Code-Splitting löst das Problem
  },

  envPrefix: 'VITE_',

  resolve: {
    alias: { '@': resolve(__dirname, 'src') },
  },

  optimizeDeps: {
    include: ['react', 'react-dom', 'recharts'],
  },
}));
