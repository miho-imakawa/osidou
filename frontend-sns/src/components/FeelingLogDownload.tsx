import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { authApi } from '../api'; // 既存のAPI設定を使用

const FeelingLogDownload: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');

  useEffect(() => {
    const downloadFile = async () => {
      const params = new URLSearchParams(location.search);
      const sessionId = params.get('session_id');

      if (!sessionId) {
        setStatus('error');
        return;
      }

      try {
        // バックエンドのダウンロードエンドポイントを叩く
        const response = await authApi.get(`/api/download/feeling-log?session_id=${sessionId}`, {
          responseType: 'blob', // ファイルを受け取るための設定
        });

        // ブラウザでダウンロードを開始させる処理
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `feeling_log_${new Date().getTime()}.csv`);
        document.body.appendChild(link);
        link.click();
        link.remove();

        setStatus('success');
        // 3秒後にプロフィールへ戻す
        setTimeout(() => navigate('/profile'), 3000);
      } catch (err) {
        console.error('Failed Download:', err);
        setStatus('error');
      }
    };

    downloadFile();
  }, [location, navigate]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
      {status === 'loading' && (
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-pink-600"></div>
      )}
      <h2 className="text-xl font-bold text-gray-800">
        {status === 'loading' && "Verifying Payment... Download will start soon"}
        {status === 'success' && "🎉 Download Completed!"}
        {status === 'error' && "❌ ERROR; Payment failed or link is invalid."}
      </h2>
      <p className="text-gray-500">
        {status === 'success' && "Returning to MY PAGE automatically..."}
      </p>
    </div>
  );
};

export default FeelingLogDownload;