import { defineConfig, loadEnv, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { localProxy } from './proxy';

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, process.cwd(), 'LLAMA_');
    const proxy = localProxy(process.env.LLAMA_SERVER_URL || env.LLAMA_SERVER_URL || 'http://127.0.0.1:8080');
    const plugin: Plugin = {
        name: 'llama-modes-loopback-proxy',
        configureServer(server) {
            server.middlewares.use(proxy);
        },
        configurePreviewServer(server) {
            server.middlewares.use(proxy);
        },
    };
    return {
        plugins: [react(), tailwindcss(), plugin],
        server: { host: '127.0.0.1', port: 5173, strictPort: true },
        preview: { host: '127.0.0.1', port: 4173, strictPort: true },
    };
});
