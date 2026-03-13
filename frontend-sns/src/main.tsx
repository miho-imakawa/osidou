// frontend-sns/src/main.tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import AppLayout from './AppLayout.tsx'; 
import './index.css'; 

// バックエンドをスリープさせないためのKeep-alive
const BACKEND_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
setInterval(() => {
  fetch(`${BACKEND_URL}/`)
    .catch(() => {}); // エラーは無視
}, 5 * 60 * 1000); // 5分ごとに起こす

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AppLayout />
    </BrowserRouter>
  </React.StrictMode>,
);