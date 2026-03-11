import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';
import path from 'path'; 

// 💡 修正: PostCSSプラグインをimport構文で読み込む
import tailwindcss from 'tailwindcss';
import autoprefixer from 'autoprefixer';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  // 💡 修正: CSS設定を復活させ、PostCSSプラグインをimportした変数で明示的に定義
  css: {
    postcss: {
      plugins: [
        tailwindcss, // 読み込んだ tailwindcss 変数を使用
        autoprefixer, // 読み込んだ autoprefixer 変数を使用
      ],
    },
  },
  server: {
    // 💡 追加: 外部（スマホなど）からのアクセスを許可する設定
    host: true,
    // 開発サーバーのポート設定
    port: 5173,
  },
  // 内部的なパス解決を助けるためのエイリアス設定 (既存)
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
