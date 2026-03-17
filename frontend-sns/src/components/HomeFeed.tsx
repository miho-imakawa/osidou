import React, { useState, useEffect, useCallback } from 'react';
import {
  UserProfile,
  UserMoodResponse,
  fetchFollowingMoods,
  authApi,
  fetchFriendsLogStatus,
  activateFriendsLog,
  startFriendsLogCheckout,
} from '../api';
import { Clock, Download } from 'lucide-react';
import MoodInput from './MoodInput';
import { useLocation, useNavigate } from 'react-router-dom';

// -------------------------------------------------------
// 型定義
// -------------------------------------------------------
interface FriendsLogStatus {
  has_active_purchase: boolean;
  days_remaining?: number;
  expires_at?: string;
  can_download_today?: boolean;
}

const MOOD_TYPES: Record<string, { label: string; emoji: string }> = {
  motivated: { label: 'On Fire! 熱', emoji: '🔥' },
  excited:   { label: 'Yay! 喜',    emoji: '🤩' },
  happy:     { label: 'Happy 幸',   emoji: '😊' },
  calm:      { label: 'Relax 穏',   emoji: '😌' },
  neutral:   { label: 'Meh 凪',     emoji: '😐' },
  anxious:   { label: 'Hmm 憂',     emoji: '😟' },
  tired:     { label: 'Ugh 倦',     emoji: '😥' },
  sad:       { label: 'Sigh 悲',    emoji: '😭' },
  angry:     { label: 'Grrr! 怒',   emoji: '😠' },
  grateful:  { label: 'Aww 感謝',   emoji: '🙏' },
};

// -------------------------------------------------------
// コンポーネント
// -------------------------------------------------------
const HomeFeed: React.FC<{ profile: UserProfile }> = ({ profile }) => {
  const location = useLocation();
  const navigate = useNavigate();

  const [friendMoods, setFriendMoods] = useState<UserMoodResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Friends' Feeling Log 関連
  const [friendsLogStatus, setFriendsLogStatus] = useState<FriendsLogStatus | null>(null);
  const [isActivating, setIsActivating] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [dlMessage, setDlMessage] = useState<string | null>(null);

  // -------------------------------------------------------
  // フレンドの気分ログ読み込み
  // -------------------------------------------------------
  const loadMoods = async () => {
    try {
      setLoading(true);
      const data = await fetchFollowingMoods();
      setFriendMoods(data);
    } catch (err) {
      setError('Failed to load logs.');
    } finally {
      setLoading(false);
    }
  };

  // -------------------------------------------------------
  // Friends' Feeling Log の購入状態を取得
  // -------------------------------------------------------
  const loadFriendsLogStatus = useCallback(async () => {
    try {
      const data = await fetchFriendsLogStatus(profile.id);
      setFriendsLogStatus(data);
    } catch {
      setFriendsLogStatus({ has_active_purchase: false });
    }
  }, [profile.id]);

  useEffect(() => {
    loadMoods();
    loadFriendsLogStatus();
  }, [loadFriendsLogStatus]);

  // -------------------------------------------------------
  // Stripe 成功後のアクティベート処理
  // URLパラメータ ?friends_log_session=xxx があれば自動処理
  // -------------------------------------------------------
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const sessionId = params.get('friends_log_session');
    if (!sessionId || isActivating) return;

    const activate = async () => {
      setIsActivating(true);
      try {
        const res = await activateFriendsLog(sessionId);
        setFriendsLogStatus({
          has_active_purchase: true,
          days_remaining: res.days_remaining,
          expires_at: res.expires_at,
          can_download_today: true,
        });
        setDlMessage('🎉 購入完了！30日間、毎日1回ダウンロードできます。');
      } catch (e: any) {
        const msg = e?.response?.data?.detail || 'アクティベートに失敗しました';
        setDlMessage(`⚠️ ${msg}`);
      } finally {
        setIsActivating(false);
        navigate('/', { replace: true });
      }
    };

    activate();
  }, [location.search, isActivating, navigate]);

  // -------------------------------------------------------
  // 購入ボタン → Stripe へ
  // -------------------------------------------------------
  const handlePurchase = async () => {
    try {
      await startFriendsLogCheckout(profile.id);
    } catch (e: any) {
      if (e?.response?.status === 409) {
        setDlMessage(`ℹ️ ${e.response.data.detail}`);
        loadFriendsLogStatus();
      } else {
        alert(e?.response?.data?.detail || 'エラーが発生しました。');
      }
    }
  };

  // -------------------------------------------------------
  // ダウンロード実行
  // -------------------------------------------------------
  const handleDownload = async () => {
    if (!friendsLogStatus?.can_download_today) {
      setDlMessage('⏳ 本日のダウンロードは完了しています。明日また試してください。');
      return;
    }
    setIsDownloading(true);
    setDlMessage(null);
    try {
      const res = await authApi.get(
        `/api/download/friends-feeling-log?user_id=${profile.id}`,
        { responseType: 'blob' }
      );
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute(
        'download',
        `friends_feeling_log_${new Date().toISOString().slice(0, 10)}.csv`
      );
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      setDlMessage('✅ ダウンロード完了！');
      setFriendsLogStatus(prev => (prev ? { ...prev, can_download_today: false } : prev));
    } catch (e: any) {
      const detail = e?.response?.data?.detail || 'ダウンロードに失敗しました';
      setDlMessage(`❌ ${detail}`);
    } finally {
      setIsDownloading(false);
    }
  };

  // -------------------------------------------------------
  // Friends' Feeling Log ステータスバー UI
  // -------------------------------------------------------
  const renderFriendsLogBar = () => {
    if (isActivating) {
      return <span className="text-[10px] text-purple-400 animate-pulse">確認中...</span>;
    }

    if (!friendsLogStatus?.has_active_purchase) {
      return (
        <button
          onClick={handlePurchase}
          className="px-2.5 py-1 bg-purple-50 border border-purple-200 text-purple-600 rounded-lg text-[10px] font-bold hover:bg-purple-100 transition-all"
        >
          とも' Log DL — ¥1,000/30日
        </button>
      );
    }

    const { days_remaining = 0, can_download_today } = friendsLogStatus;

    return (
      <div className="flex items-center gap-2">
        <span className="text-[10px] text-purple-400 tabular-nums">残り{days_remaining}日</span>
        <div className="w-10 h-1 bg-purple-100 rounded-full overflow-hidden">
          <div className="h-full bg-purple-400 rounded-full" style={{ width: `${(days_remaining / 30) * 100}%` }} />
        </div>
        {can_download_today ? (
          <button
            onClick={handleDownload}
            disabled={isDownloading}
            className="px-2 py-0.5 bg-purple-500 text-white rounded text-[10px] font-bold hover:bg-purple-600 disabled:opacity-50"
          >
            {isDownloading ? '...' : 'DL'}
          </button>
        ) : (
          <span className="text-[10px] text-gray-300">本日済</span>
        )}
      </div>
    );
  };

  // -------------------------------------------------------
  // レンダリング
  // -------------------------------------------------------
  return (
    <div className="max-w-2xl mx-auto p-4 md:p-8">
      {/* ヘッダーエリア */}
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">
          ハロー⭐ {profile.nickname || profile.username},
        </h1>
        <p className="text-[10px] font-bold text-pink-500 opacity-70 tracking-widest uppercase mt-1">
          Welcome back
        </p>
      </div>

      {/* 気分入力 */}
      <MoodInput onSuccess={loadMoods} />

      <div className="mt-12 space-y-6">
        {/* Friends' Log ヘッダー */}
        <div className="flex items-center justify-between">
          <h2 className="text-[14px] font-black text-gray-900 tracking-[0.2em] uppercase leading-none">
            ともだちs' LOG
          </h2>
          {renderFriendsLogBar()}
        </div>
        {dlMessage && <p className="text-[10px] text-gray-400">{dlMessage}</p>}

        {/* ローディング・エラー表示 */}
        {loading && (
          <p className="text-center py-10 text-[10px] font-black text-gray-300 animate-pulse">
            LOADING...
          </p>
        )}
        {error && <p className="text-red-500 text-xs font-bold">{error}</p>}

        {/* リストが空の場合 */}
        {!loading && friendMoods.length === 0 && (
          <div className="bg-white p-10 rounded-[32px] border-2 border-dashed border-gray-100 text-center">
            <p className="text-gray-300 text-[10px] font-bold uppercase tracking-widest">
              No activity found
            </p>
          </div>
        )}

        {/* フレンドの気分リスト */}
        <div className="grid gap-2">
          {friendMoods.map((friendMood) => {
            const moodDetail = MOOD_TYPES[friendMood.current_mood] || { label: '?', emoji: '✨' };
            const date = friendMood.mood_updated_at ? new Date(friendMood.mood_updated_at) : null;

            return (
              <div
                key={friendMood.user_id}
                className="flex items-center gap-4 py-3 border-b border-gray-50"
              >
                <div className="w-28 flex-shrink-0">
                  <span className="text-xs font-black text-gray-800">
                    {friendMood.nickname || friendMood.username}
                  </span>
                  {friendMood.friend_note && (
                    <span className="text-[9px] text-gray-400 font-medium ml-1">
                      ({friendMood.friend_note})
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-1 w-24 flex-shrink-0">
                  {date && (
                    <>
                      <span className="text-[12px] font-black text-gray-800 tabular-nums">
                        {String(date.getMonth() + 1)}/{String(date.getDate()).padStart(2, '0')}
                      </span>
                      <span className="text-[10px] font-bold text-gray-400 tabular-nums flex items-center gap-1">
                        <Clock size={10} />
                        {date.getHours()}:{String(date.getMinutes()).padStart(2, '0')}
                      </span>
                    </>
                  )}
                </div>

                <span className="text-xl">{moodDetail.emoji}</span>
                <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest">
                  {moodDetail.label}
                </span>

                {friendMood.is_mood_comment_visible && friendMood.current_mood_comment && (
                  <p className="text-sm text-gray-600 font-medium flex-1 truncate">
                    {friendMood.current_mood_comment}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default HomeFeed;
