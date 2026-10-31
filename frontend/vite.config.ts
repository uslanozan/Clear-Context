import { fileURLToPath } from 'node:url';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

const projectRoot = fileURLToPath(new URL('../', import.meta.url));

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, projectRoot, '');
  const port = Number(env.WEB_PORT || 5173);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error('WEB_PORT must be an integer from 1 to 65535.');
  }
  const apiHost = ['0.0.0.0', '::'].includes(env.API_HOST)
    ? '127.0.0.1'
    : env.API_HOST || '127.0.0.1';
  const apiTarget = env.API_PROXY_TARGET || `http://${apiHost}:${env.API_PORT || 8000}`;
  const parsedTarget = new URL(apiTarget);
  if (
    !['http:', 'https:'].includes(parsedTarget.protocol) ||
    parsedTarget.username ||
    parsedTarget.password
  ) {
    throw new Error('API_PROXY_TARGET must be an HTTP(S) address without credentials.');
  }
  return {
    plugins: [react()],
    envDir: projectRoot,
    envPrefix: 'VITE_PUBLIC_',
    server: {
      host: env.WEB_HOST || '127.0.0.1',
      port,
      strictPort: true,
      // clearcontext.localhost resolves to this machine without DNS or hosts-file setup.
      allowedHosts: ['.localhost'],
      proxy: { '/api': { target: apiTarget, changeOrigin: true } },
    },
  };
});
