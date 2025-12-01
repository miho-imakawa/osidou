import React from 'react';
import ReactDOM from 'react-dom/client';
// 💡 修正: AppLayout.tsxのパスを './AppLayout.tsx' から絶対パス './AppLayout.tsx' へ変更
import AppLayout from './AppLayout.tsx'; 
// Tailwind CSSのベーススタイルを読み込み 
import './index.css'; 

// ReactアプリケーションをHTMLの 'root' 要素にマウントする
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AppLayout />
  </React.StrictMode>,
);