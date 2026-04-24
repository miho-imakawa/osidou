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
import { Clock } from 'lucide-react';
import MoodInput from './MoodInput';
import { useLocation, useNavigate, Link } from 'react-router-dom';

// -------------------------------------------------------
// 型定義
// -------------------------------------------------------
interface FriendsLogStatus {
  has_active_purchase: boolean;
  credits_remaining?: number;
  can_download?: boolean;
  next_available_at?: string;
}

interface FriendCount {
  total: number;
  over: number;
  is_billing: boolean;
}

// ✅ 通知型定義
interface MyNotification {
  id: number;
  message: string;
  is_read: boolean;
  created_at: string;
  event_post_id: number | null;
  hobby_category_id: number | null;
}

const MOOD_TYPES: Record<string, { label: string; emoji: string }> = {
  motivated: { emoji: '🔥', label: 'On Fire！やるぞ～' },
  excited:   { emoji: '🤩', label: 'Yay！うれしい～' },
  happy:     { emoji: '😊', label: 'Happy！しあわせ～' },
  calm:      { emoji: '😌', label: 'Relax～まったり～' },
  neutral:   { emoji: '😶', label: 'Meh…まずまず' },
  anxious:   { emoji: '💭', label: 'Hmm…もやもや～' },
  tired:     { emoji: '😩', label: 'Ugh…つかれた～' },
  sad:       { emoji: '😭', label: 'Sigh…なける…' },
  angry:     { emoji: '😡', label: 'Grrr！むかつく！' },
  grateful:  { emoji: '🙏', label: 'Aww～ありがとう～' },
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
  const [unconfirmedMeetups, setUnconfirmedMeetups] = useState<any[]>([]);

  // Friends' Feeling Log 関連
  const [friendsLogStatus, setFriendsLogStatus] = useState<FriendsLogStatus | null>(null);
  const [isActivating, setIsActivating] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [dlMessage, setDlMessage] = useState<string | null>(null);
  const [tempProfile, setTempProfile] = useState({ goal: '' });

  // 友達数
  const [pendingCount, setPendingCount] = useState(0);
  const [friendCount, setFriendCount] = useState<FriendCount | null>(null);

  // ✅ 通知リスト（件数ではなく個別通知）
  const [notifications, setNotifications] = useState<MyNotification[]>([]);

  //友達申請
  const loadPendingCount = useCallback(async () => {
    try {
      const res = await authApi.get('/friends/pending/count');
      setPendingCount(res.data.pending_count || 0);
    } catch {}
  }, []);

  // ✅ 通知一覧を取得
  const loadNotifications = useCallback(async () => {
      try {
          const res = await authApi.get('/notifications/my');
          setNotifications(res.data || []);
          
          if (res.data && res.data.length > 0) {
              setTimeout(async () => {
                  await authApi.patch('/notifications/read-all');
                  setNotifications([]);
              }, 7000);
          }
      } catch {}
  }, []);

  // ✅ 個別通知を既読にしてリストから消す
  const handleNotifClick = async (notif: MyNotification) => {
    try {
      await authApi.patch(`/notifications/${notif.id}/read`);
      setNotifications(prev => prev.filter(n => n.id !== notif.id));
    } catch {}
    // 該当MEETUPのコミュニティへ飛ぶ
    if (notif.hobby_category_id) {
      navigate(`/community/${notif.hobby_category_id}`);
    }
  };

  const loadUnconfirmedMeetups = useCallback(async () => {
    try {
      const res = await authApi.get('/hobby-categories/my-unconfirmed-meetups');
      setUnconfirmedMeetups(res.data || []);
    } catch {}
  }, []);

  // -------------------------------------------------------
  // フレンドの気分ログ読み込み
  // -------------------------------------------------------

  const loadMoods = async () => {
    // トークンチェック
    const token = localStorage.getItem('access_token');
    if (!token) {
      setError('logout');
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const data = await fetchFollowingMoods();
      setFriendMoods(data);
    } catch (err: any) {
      if (err?.response?.status === 401) {
        setError('logout');
      } else {
        setError('failed');
      }
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

  // -------------------------------------------------------
  // 友達数取得
  // -------------------------------------------------------
  const loadFriendCount = useCallback(async () => {
    try {
      const res = await authApi.get('/friends/me/friends/count');
      setFriendCount(res.data);
    } catch {}
  }, []);

  useEffect(() => {
    loadMoods();
    loadFriendsLogStatus();
    loadFriendCount();
    loadPendingCount();
    loadNotifications(); // ✅ 件数ではなく一覧を取得
    loadUnconfirmedMeetups();
  }, [loadFriendsLogStatus, loadFriendCount, loadPendingCount, loadNotifications, loadUnconfirmedMeetups]);

  // -------------------------------------------------------
  // Stripe 成功後のアクティベート処理
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
          credits_remaining: res.credits_remaining,
          can_download: true,
        });
        setDlMessage('🎉 購入完了！30回分ダウンロードできます（4時間ごとに1回）。');
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
    if (!friendsLogStatus?.can_download) {
      const { next_available_at } = friendsLogStatus ?? {};
      if (next_available_at) {
        const minutes = Math.ceil(
          (new Date(next_available_at).getTime() - Date.now()) / 60000
        );
        setDlMessage(`⏳ 次のダウンロードまであと${minutes}分です。`);
      }
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
      setFriendsLogStatus(prev => prev ? {
        ...prev,
        credits_remaining: (prev.credits_remaining ?? 1) - 1,
        can_download: false,
      } : prev);
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
          👥'🤝Log DL 30回/¥1,000
        </button>
      );
    }

    const { credits_remaining = 0, can_download, next_available_at } = friendsLogStatus;

    const waitMinutes = next_available_at
      ? Math.ceil((new Date(next_available_at).getTime() - Date.now()) / 60000)
      : 0;

    return (
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-0.5">
          {Array.from({ length: 30 }).map((_, i) => (
            <div
              key={i}
              className={`w-0.5 h-2.5 rounded-full ${
                i < credits_remaining ? 'bg-purple-400' : 'bg-gray-100'
              }`}
            />
          ))}
        </div>
        <span className="text-[10px] text-purple-400 tabular-nums">{credits_remaining}</span>

        {can_download ? (
          <button
            onClick={handleDownload}
            disabled={isDownloading}
            className="px-2 py-0.5 bg-purple-500 text-white rounded text-[10px] font-bold hover:bg-purple-600 disabled:opacity-50"
          >
            {isDownloading ? '...' : 'DL'}
          </button>
        ) : (
          <span className="text-[10px] text-gray-300">
            {waitMinutes > 0 ? `あと${waitMinutes}分` : '待機中'}
          </span>
        )}
      </div>
    );
  };

  // -------------------------------------------------------
  // 友達数バッジ
  // -------------------------------------------------------
  const renderFriendCount = () => {
    if (!friendCount) return null;
    const { total, over, is_billing } = friendCount;

    if (!is_billing) {
      return (
        <span className="text-[10px] font-bold text-gray-400 tabular-nums">
          👥 {total}人
        </span>
      );
    }

    return (
      <span className="text-[10px] font-bold tabular-nums">
        <span className="text-gray-400">👥 {total}人</span>
        <span className="ml-1 text-indigo-400">({over} x¥100 💳)</span>
      </span>
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

      {/* 友達申請通知 */}
      {pendingCount > 0 && (
        <Link
          to="/friends"
          state={{ tab: 'requests' }}
          className="block text-xs font-bold text-amber-500 hover:text-amber-600 mb-4"
        >
          🔔 ともだち申請が{pendingCount}件あります
        </Link>
      )}

      {/* ✅ MEETUP通知：個別表示・クリックで既読＋該当コミュニティへ飛ぶ */}
      {notifications.length > 0 && (
        <div className="mb-4 space-y-1.5">
          {notifications.map(notif => (
            <button
              key={notif.id}
              onClick={() => handleNotifClick(notif)}
              className="w-full text-left block text-xs font-bold text-orange-500 hover:text-orange-600 hover:bg-orange-50 px-3 py-2 rounded-xl transition-colors"
            >
              🔔 {notif.message}
            </button>
          ))}
        </div>
      )}

      {/* 開催確定待ちMEETUP */}
      {unconfirmedMeetups.map(meetup => (
        <Link
          key={meetup.id}
          to={`/community/${meetup.hobby_category_id}`}
          className="block text-xs font-black text-orange-500 hover:text-orange-600 mb-4"
        >
          🎪 「{meetup.title}」の開催確定を押してください
        </Link>
      ))}

      {/* 気分入力 */}
      <MoodInput onSuccess={loadMoods} />

      {/* MoodInput の直後、ともだちs' LOG の直前に追加 */}
      {profile.goal && (
        <div className="mt-4 px-4 py-3 bg-gradient-to-r from-pink-50 to-white rounded-2xl border border-pink-100 flex items-start gap-2">
          <span className="text-base shrink-0"></span>
          <div>
            <p className="text-[9px] font-bold text-pink-400 uppercase tracking-widest mb-0.5">
              My Goal
            </p>
            <p className="text-sm font-bold text-gray-700">{profile.goal}</p>
          </div>
        </div>
      )}

      <div className="mt-8 space-y-3">
        {/* Friends' Log ヘッダー */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-[14px] font-black text-gray-900 tracking-[0.2em] uppercase leading-none">
            ともだちs' LOG
          </h2>
          {renderFriendCount()}
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/friends"
            state={{ tab: 'search' }}
            className="px-2.5 py-1 bg-pink-50 border border-pink-200 text-pink-600 rounded-lg text-[10px] font-bold hover:bg-pink-100 transition-all"
          >
            👤 追加
          </Link>
          <Link
            to="/friends"
            state={{ tab: 'friends' }}
            className="px-2.5 py-1 bg-gray-50 border border-gray-200 text-gray-500 rounded-lg text-[10px] font-bold hover:bg-gray-100 transition-all"
          >
            👥 管理
          </Link>
          {renderFriendsLogBar()}
        </div>
      </div>
      {dlMessage && <p className="text-[10px] text-gray-400">{dlMessage}</p>}

        {loading && (
          <p className="text-center py-10 text-[10px] font-black text-gray-300 animate-pulse">
            LOADING...
          </p>
        )}
        {error === 'logout' && (
          <div className="bg-white p-10 rounded-[32px] border-2 border-dashed border-gray-100 text-center space-y-2">
            <p className="text-gray-400 text-[11px] font-bold">
              🔒 Logged Out（ログアウト中）かもしれません
            </p>
            <Link to="/login" className="text-xs font-bold text-pink-500 hover:underline">
              Loginはこちら →
            </Link>
          </div>
        )}
        {error === 'failed' && (
          <p className="text-red-400 text-xs font-bold">Loading Failed…Logged Out（ログアウト中）かもしれません</p>
        )}

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
                  <Link to={`/profile/${friendMood.user_id}`} className="text-xs font-black text-gray-800 hover:text-pink-500 hover:underline transition-colors">
                    {friendMood.nickname || friendMood.username}
                  </Link>
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

                {!friendMood.is_muted && friendMood.current_mood_comment && (
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
