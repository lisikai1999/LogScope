import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.VITE_API_TARGET || 'http://127.0.0.1:8000'
  
  console.log('Vite 代理目标:', apiTarget)
  
  return {
    plugins: [vue()],
    server: {
      port: 3000,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          ws: true,
          configure: (proxy, options) => {
            proxy.on('proxyReq', (proxyReq, req, res) => {
              console.log('代理请求:', req.method, req.url)
              if (req.headers.upgrade && req.headers.upgrade.toLowerCase() === 'websocket') {
                console.log('WebSocket 代理请求:', req.url)
              }
            })
            proxy.on('proxyRes', (proxyRes, req, res) => {
              console.log('代理响应:', proxyRes.statusCode, req.url)
            })
            proxy.on('error', (err, req, res) => {
              console.error('代理错误:', err)
            })
          }
        }
      }
    },
    build: {
      outDir: 'dist',
      emptyOutDir: true
    }
  }
})
