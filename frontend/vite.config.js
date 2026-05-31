import { fileURLToPath, URL } from 'node:url';

import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
  },
  base: '/static/vue/',
  build: {
    outDir: fileURLToPath(new URL('../static/vue', import.meta.url)),
    emptyOutDir: true,
    assetsDir: 'assets',
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('vue-router') || id.includes('/node_modules/vue/') || id.includes('/node_modules/@vue/')) {
              return 'vendor-core';
            }
            if (id.includes('ant-design-vue')) {
              return 'vendor-antd';
            }
            if (id.includes('@ant-design/icons-vue')) {
              return 'vendor-antd-icons';
            }
            if (id.includes('socket.io-client')) {
              return 'vendor-socket';
            }
            return 'vendor-misc';
          }

          if (id.includes('/src/pages/UserFeedPage.vue') || id.includes('/src/pages/UserPostPage.vue') || id.includes('/src/pages/UserVideoPage.vue')) {
            return 'page-user-flow';
          }

          if (id.includes('/src/pages/LibraryPage.vue') || id.includes('/src/pages/DatabasePage.vue') || id.includes('/src/pages/SearchPage.vue')) {
            return 'page-admin-data';
          }

          if (id.includes('/src/pages/TasksPage.vue') || id.includes('/src/pages/DashboardPage.vue') || id.includes('/src/pages/SettingsPage.vue')) {
            return 'page-admin-main';
          }
        },
      },
    },
  },
});
