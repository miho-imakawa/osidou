import React, { useState, useEffect } from 'react';
import { useParams, Link, useLocation } from 'react-router-dom';
import { 
  User, Globe, Twitter, Facebook, Instagram, BookOpen,
  Edit, MessageSquare, Heart, Download, Save, X, Eye, EyeOff,
  AtSign, MapPin, Clock, Flame, Calendar, CheckCircle, Lock, ShoppingCart
} from 'lucide-react';
import { 
  authApi, 
  fetchMyCommunities,
  HobbyCategory, 
  fetchMyMoodHistory, 
  MoodLog,
  startFeelingLogCheckout,
  fetchFriendsLogStatus,
  activateFriendsLog,
  startFriendsLogCheckout,
} from '../api';
import PendingFriendBanner from './PendingFriendBanner';

// -------------------------------------------------------
// 型定義
// -------------------------------------------------------
interface FriendsLogStatus {
  has_active_purchase: boolean;
  days_remaining?: number;
  expires_at?: string;
  can_download_today?: boolean;
}

interface UserProfileProps {
  profile: any;
  fetchProfile: () => void;
}

// -------------------------------------------------------
// コンポーネント
// -------------------------------------------------------
const UserProfile: React.FC<UserProfileProps> = ({ profile: myProfile, fetchProfile: fetchMyProfile }) => {
  const { userId } = useParams<{ userId: string }>();
  const location = useLocation();

  const [displayProfile, setDisplayProfile] = useState<any>(null);
  const [isMe, setIsMe] = useState(true);
  const [loading, setLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [tempProfile, setTempProfile] = useState<any>(null);
  const [myCategories, setMyCategories] = useState<HobbyCategory[]>([]);
  const [moodLogs, setMoodLogs] = useState<MoodLog[]>([]);
  const [myMeetups, setMyMeetups] = useState<any[]>([]);
  const [myAdsStats, setMyAdsStats] = useState<any[]>([]);
  const [pendingCount, setPendingCount] = useState(0);

  // ── Friends' Feeling Log DL 関連 ──────────────────
  const [friendsLogStatus, setFriendsLogStatus] = useState<FriendsLogStatus | null>(null);
  const [isActivating, setIsActivating] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [dlMessage, setDlMessage] = useState<string | null>(null);

  // -------------------------------------------------------
  // プロフィール取得
  // -------------------------------------------------------
  useEffect(() => {
    if (userId) {
      const fetchTarget = async (id: string) => {
        try {
          setLoading(true);
          const response = await authApi.get(`/users/${id}`);
          setDisplayProfile(response.data);
          setIsMe(false);
        } finally {
          setLoading(false);
        }
      };
      fetchTarget(userId);
    } else {
      setDisplayProfile(myProfile);
      setTempProfile({ ...myProfile });
      setIsMe(true);
      setLoading(false);
    }
  }, [userId, myProfile]);

  // -------------------------------------------------------
  // データ読み込み（プロフィール確定後）
  // -------------------------------------------------------
  useEffect(() => {
    if (!displayProfile?.id) return;

    const loadData = async () => {
      try {
        const categories = await fetchMyCommunities();
        setMyCategories(categories);

        const [joinedRes, hostedRes] = await Promise.all([
          authApi.get('/posts/my-meetups'),
          authApi.get('/posts/my-hosted-meetups'),
        ]);

        const joined = joinedRes.data || [];
        const hosted = hostedRes.data || [];
        const allMeetups = [...hosted];
        joined.forEach((m: any) => {
          if (!allMeetups.find((e: any) => e.id === m.id)) allMeetups.push(m);
        });
        setMyMeetups(
          allMeetups.filter((m: any) => !m.meetup_date || new Date(m.meetup_date) > new Date())
        );

        // ── 自分のページのみ追加データ取得 ──
        if (isMe) {
          const [pendingRes, adsRes, logs] = await Promise.all([
            authApi.get('/friends/pending/count'),
            authApi.get('/posts/my-ads-stats'),
            fetchMyMoodHistory(),
          ]);
          setPendingCount(pendingRes.data.pending_count);
          setMyAdsStats(adsRes.data);
          setMoodLogs(logs);
        }
      } catch (err) {
        console.error('データ取得失敗:', err);
      }
    };

    loadData();
  }, [displayProfile?.id, isMe, location.pathname]);

  // -------------------------------------------------------
  // Friends' Feeling Log ステータス取得（他人ページのみ）
  // -------------------------------------------------------
  useEffect(() => {
    if (!displayProfile?.id || isMe) return;
    const load = async () => {
      try {
        const data = await fetchFriendsLogStatus(displayProfile.id);
        setFriendsLogStatus(data);
      } catch {
        setFriendsLogStatus({ has_active_purchase: false });
      }
    };
    load();
  }, [displayProfile?.id, isMe]);

  // -------------------------------------------------------
  // Stripe 成功後のアクティベート（URLパラメータ監視）
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
        setDlMessage(`⚠️ ${e?.response?.data?.detail || 'アクティベートに失敗しました'}`);
      } finally {
        setIsActivating(false);
      }
    };
    activate();
  }, [location.search, isActivating]);

  // -------------------------------------------------------
  // 自分の Feeling Log DL（200円）
  // -------------------------------------------------------
  const handleFeelingLogDownload = async (targetUserId: string | number) => {
    try {
      await startFeelingLogCheckout(targetUserId);
    } catch {
      alert('エラーが発生しました。もう一度お試しください。');
    }
  };

  // -------------------------------------------------------
  // 他人の Friends' Feeling Log 購入（1,000円）
  // -------------------------------------------------------
  const handleFriendsPurchase = async () => {
    try {
      await startFriendsLogCheckout(myProfile.id, displayProfile.id);
    } catch (e: any) {
      if (e?.response?.status === 409) {
        setDlMessage(`ℹ️ ${e.response.data.detail}`);
        const data = await fetchFriendsLogStatus(displayProfile.id);
        setFriendsLogStatus(data);
      } else {
        alert(e?.response?.data?.detail || 'エラーが発生しました。');
      }
    }
  };

  // -------------------------------------------------------
  // 他人の Friends' Feeling Log ダウンロード
  // -------------------------------------------------------
  const handleFriendsDownload = async () => {
    if (!friendsLogStatus?.can_download_today) {
      setDlMessage('⏳ 本日のダウンロードは完了しています。明日また試してください。');
      return;
    }
    setIsDownloading(true);
    setDlMessage(null);
    try {
      const res = await authApi.get(
        `/api/download/friends-feeling-log?user_id=${displayProfile.id}`,
        { responseType: 'blob' }
      );
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `friends_feeling_log_${new Date().toISOString().slice(0, 10)}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      setDlMessage('✅ ダウンロード完了！');
      setFriendsLogStatus(prev => (prev ? { ...prev, can_download_today: false } : prev));
    } catch (e: any) {
      setDlMessage(`❌ ${e?.response?.data?.detail || 'ダウンロードに失敗しました'}`);
    } finally {
      setIsDownloading(false);
    }
  };

  // -------------------------------------------------------
  // Friends' Feeling Log DLバー（他人ページ用）
  // -------------------------------------------------------
  const renderFriendsLogBar = () => {
    if (isActivating) {
      return (
        <div className="flex items-center gap-2 px-4 py-2 bg-purple-50 rounded-2xl text-xs font-bold text-purple-500 animate-pulse">
          <div className="w-3 h-3 rounded-full border-2 border-purple-400 border-t-transparent animate-spin" />
          購入を確認中...
        </div>
      );
    }

    if (!friendsLogStatus?.has_active_purchase) {
      return (
        <button
          onClick={handleFriendsPurchase}
          className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-2xl text-xs font-bold hover:opacity-90 transition-all shadow-sm active:scale-95"
        >
          <ShoppingCart size={13} />
          Friends' Log DL — ¥1,000 / 30日
        </button>
      );
    }

    const { days_remaining = 0, can_download_today } = friendsLogStatus;

    return (
      <div className="flex items-center gap-2 flex-wrap">
        {/* 残り日数バッジ */}
        <div className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-50 border border-purple-100 rounded-xl">
          <CheckCircle size={11} className="text-purple-500" />
          <span className="text-[10px] font-black text-purple-600 tabular-nums">残り {days_remaining} 日</span>
          <div className="w-14 h-1.5 bg-purple-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-purple-400 rounded-full transition-all"
              style={{ width: `${(days_remaining / 30) * 100}%` }}
            />
          </div>
        </div>

        {can_download_today ? (
          <button
            onClick={handleFriendsDownload}
            disabled={isDownloading}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-500 text-white rounded-xl text-[10px] font-black hover:bg-purple-600 transition-all active:scale-95 disabled:opacity-60"
          >
            {isDownloading
              ? <div className="w-3 h-3 rounded-full border-2 border-white border-t-transparent animate-spin" />
              : <Download size={11} />}
            {isDownloading ? 'DL中...' : '今日分をDL'}
          </button>
        ) : (
          <div className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-100 text-gray-400 rounded-xl text-[10px] font-black">
            <Lock size={11} />
            本日DL済 — 明日また
          </div>
        )}
      </div>
    );
  };

  // -------------------------------------------------------
  // ユーティリティ
  // -------------------------------------------------------
  const getRankClasses = (count: number) => {
    if (count >= 10000) return 'bg-yellow-50 text-yellow-700 border-yellow-300 shadow-sm';
    if (count >= 500) return 'bg-pink-50 text-pink-700 border-pink-200';
    return 'bg-gray-50 text-gray-500 border-gray-100';
  };

  const getDynamicXIcon = (url: string | null) => {
    const isThreads = url?.includes('threads.net');
    return {
      Icon: isThreads ? AtSign : Twitter,
      label: isThreads ? 'Threads' : 'Twitter (X)',
      classes: isThreads
        ? 'bg-gray-800 text-white hover:bg-black'
        : 'bg-blue-50 text-blue-500 hover:bg-blue-500 hover:text-white',
    };
  };

  const groupedLogs = moodLogs.reduce((acc: any, log) => {
    const date = new Date(log.created_at.endsWith('Z') ? log.created_at : log.created_at + 'Z');
    const monthKey = `${date.getFullYear()} - ${String(date.getMonth() + 1).padStart(2, '0')}`;
    if (!acc[monthKey]) acc[monthKey] = [];
    acc[monthKey].push(log);
    return acc;
  }, {});

  const toggleEdit = () => {
    setTempProfile({ ...displayProfile });
    setIsEditing(!isEditing);
  };

  const handleSave = async () => {
    if (!tempProfile) return;
    try {
      await authApi.put('/users/me', tempProfile);
      fetchMyProfile();
      setIsEditing(false);
      alert('プロフィールを更新しました！');
    } catch {
      alert('更新に失敗しました。');
    }
  };

  const handleCancelMeetup = async (postId: number) => {
    if (!window.confirm('このミートアップの参加をキャンセルしますか？')) return;
    try {
      await authApi.delete(`/responses/cancel/${postId}`);
      setMyMeetups(prev => prev.filter(m => m.id !== postId));
      alert('キャンセルを完了しました。');
    } catch {
      alert('キャンセルの実行に失敗しました。');
    }
  };

  const moodMap: Record<string, string> = {
    motivated: '🔥', excited: '🤩', happy: '😊', calm: '😌', neutral: '😐',
    anxious: '😟', tired: '😥', sad: '😭', angry: '😠', grateful: '🙏',
  };

  // -------------------------------------------------------
  // ローディング・エラー
  // -------------------------------------------------------
  if (loading) return <div className="text-center py-10">読み込み中...</div>;
  if (!displayProfile) return <div className="text-center py-10 text-gray-400">ユーザーが見つかりません。</div>;

  // -------------------------------------------------------
  // レンダリング
  // -------------------------------------------------------
  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start mb-4">
        <h1 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
          <User className="text-pink-600" size={24} />
          {displayProfile.nickname || displayProfile.username}'s PAGE
        </h1>
        {isMe && (
          <button
            onClick={toggleEdit}
            className="ml-4 px-3 py-2 bg-pink-600 text-white rounded-2xl flex items-center gap-1.5 text-sm font-bold shrink-0 transition-all hover:bg-pink-700 shadow-md active:scale-95"
          >
            {isEditing ? <><X size={16} /> 戻る</> : <><Edit size={16} /> 編集</>}
          </button>
        )}
      </div>

      {isEditing && tempProfile ? (
        /* ── EDIT MODE ───────────────────────────────── */
        <div className="bg-white p-8 rounded-[32px] shadow-sm border border-gray-100 space-y-8 animate-in fade-in">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div className="space-y-6">
              <div className="space-y-2">
                <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest ml-1">Nickname</label>
                <input
                  type="text"
                  className="w-full p-4 bg-gray-50 rounded-[20px] border-none focus:ring-2 focus:ring-pink-500 font-bold"
                  value={tempProfile.nickname || ''}
                  onChange={e => setTempProfile({ ...tempProfile, nickname: e.target.value })}
                />
              </div>

              {[
                { id: 'x', label: 'Twitter or Threads', urlKey: 'x_url', visibleKey: 'is_x_visible' },
                { id: 'facebook', label: 'Facebook', icon: Facebook, urlKey: 'facebook_url', visibleKey: 'is_facebook_visible' },
                { id: 'instagram', label: 'Instagram', icon: Instagram, urlKey: 'instagram_url', visibleKey: 'is_instagram_visible' },
                { id: 'note', label: 'note', icon: BookOpen, urlKey: 'note_url', visibleKey: 'is_note_visible' },
              ].map((sns) => {
                const xConfig = sns.id === 'x' ? getDynamicXIcon(tempProfile.x_url) : null;
                const IconComp = sns.icon || xConfig?.Icon || Globe;
                return (
                  <div key={sns.id} className="space-y-2">
                    <div className="flex justify-between items-center px-1">
                      <label className="text-[9px] font-bold text-gray-400 uppercase">
                        {sns.id === 'x' ? xConfig?.label : sns.label}
                      </label>
                      <button
                        type="button"
                        onClick={() => setTempProfile({ ...tempProfile, [sns.visibleKey]: !tempProfile[sns.visibleKey] })}
                        className={`flex items-center gap-1.5 text-[9px] font-bold px-2.5 py-1 rounded-full transition-colors ${tempProfile[sns.visibleKey] ? 'bg-pink-100 text-pink-600' : 'bg-gray-100 text-gray-400'}`}
                      >
                        {tempProfile[sns.visibleKey] ? <><Eye size={10} /> 公開</> : <><EyeOff size={10} /> 非公開</>}
                      </button>
                    </div>
                    <div className="relative">
                      <div className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400">
                        <IconComp size={16} />
                      </div>
                      <input
                        type="text"
                        placeholder="https://..."
                        className="w-full p-3.5 pl-12 bg-gray-50 rounded-2xl border-none text-sm focus:ring-2 focus:ring-pink-500"
                        value={tempProfile[sns.urlKey] || ''}
                        onChange={e => setTempProfile({ ...tempProfile, [sns.urlKey]: e.target.value })}
                      />
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest ml-1">Birth</label>
                  <input
                    type="text" placeholder="1990-01"
                    className="w-full p-4 bg-gray-50 rounded-2xl border-none text-sm"
                    value={tempProfile.birth_year_month || ''}
                    onChange={e => setTempProfile({ ...tempProfile, birth_year_month: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest ml-1">Gender</label>
                  <select
                    className="w-full p-4 bg-gray-50 rounded-2xl border-none text-sm"
                    value={tempProfile.gender || ''}
                    onChange={e => setTempProfile({ ...tempProfile, gender: e.target.value })}
                  >
                    <option value="">未設定</option>
                    <option value="male">男🚹</option>
                    <option value="female">女🚺</option>
                    <option value="other">その他</option>
                  </select>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest ml-1 flex items-center gap-1">
                  <MapPin size={10} /> Residence Location
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {(['prefecture', 'city', 'town'] as const).map(key => (
                    <input
                      key={key}
                      placeholder={key.charAt(0).toUpperCase() + key.slice(1)}
                      className="p-3.5 bg-gray-50 rounded-2xl border-none text-xs focus:ring-2 focus:ring-pink-500"
                      value={tempProfile[key] || ''}
                      onChange={e => setTempProfile({ ...tempProfile, [key]: e.target.value })}
                    />
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest ml-1">Bio</label>
                <textarea
                  className="w-full p-5 bg-gray-50 rounded-[32px] border-none text-sm h-32 focus:ring-2 focus:ring-pink-500"
                  value={tempProfile.bio || ''}
                  onChange={e => setTempProfile({ ...tempProfile, bio: e.target.value })}
                />
              </div>

              <div className="pt-4 border-t border-gray-50 space-y-4">
                {[
                  { key: 'is_mood_visible', icon: Eye, offIcon: EyeOff, label: 'Feeling Logs を表示する' },
                  { key: 'is_mood_comment_visible', icon: MessageSquare, offIcon: EyeOff, label: '気分のコメントを表示する', sub: '災害時など、言葉を伝えたい時にONにしてください' },
                ].map(({ key, icon: OnIcon, offIcon: OffIcon, label, sub }) => (
                  <label key={key} className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox" className="hidden"
                      checked={tempProfile[key]}
                      onChange={e => setTempProfile({ ...tempProfile, [key]: e.target.checked })}
                    />
                    <div className={`p-2 rounded-xl transition-all ${tempProfile[key] ? 'bg-pink-100 text-pink-600' : 'bg-gray-100 text-gray-400'}`}>
                      {tempProfile[key] ? <OnIcon size={18} /> : <OffIcon size={18} />}
                    </div>
                    <div>
                      <span className="text-xs font-bold text-gray-500">{label}</span>
                      {sub && <p className="text-[10px] text-gray-400">{sub}</p>}
                    </div>
                  </label>
                ))}
              </div>
            </div>
          </div>
          <button
            onClick={handleSave}
            className="w-full py-5 bg-gray-900 text-white rounded-[24px] font-bold flex items-center justify-center gap-3 hover:bg-black transition-all shadow-xl active:scale-[0.98]"
          >
            <Save size={20} /> プロフィールを保存
          </button>
        </div>
      ) : (
        /* ── VIEW MODE ───────────────────────────────── */
        <div className="space-y-6">
          {/* SNS Links & Bio */}
          <div className="bg-white p-8 rounded-[32px] shadow-sm border border-gray-100">
            <div className="flex flex-wrap gap-4 mb-6">
              {displayProfile.x_url && displayProfile.is_x_visible !== false && (
                <a href={displayProfile.x_url} target="_blank" rel="noopener noreferrer"
                  className={`p-3 rounded-full transition-all shadow-sm ${getDynamicXIcon(displayProfile.x_url).classes}`}>
                  {React.createElement(getDynamicXIcon(displayProfile.x_url).Icon, { size: 20 })}
                </a>
              )}
              {displayProfile.facebook_url && displayProfile.is_facebook_visible !== false && (
                <a href={displayProfile.facebook_url} target="_blank" rel="noopener noreferrer"
                  className="p-3 bg-blue-50 rounded-full text-blue-600 hover:bg-blue-600 hover:text-white transition-all shadow-sm"><Facebook size={20} /></a>
              )}
              {displayProfile.instagram_url && displayProfile.is_instagram_visible !== false && (
                <a href={displayProfile.instagram_url} target="_blank" rel="noopener noreferrer"
                  className="p-3 bg-pink-50 rounded-full text-pink-600 hover:bg-pink-600 hover:text-white transition-all shadow-sm"><Instagram size={20} /></a>
              )}
              {displayProfile.note_url && displayProfile.is_note_visible !== false && (
                <a href={displayProfile.note_url} target="_blank" rel="noopener noreferrer"
                  className="p-3 bg-green-50 rounded-full text-green-600 hover:bg-green-600 hover:text-white transition-all shadow-sm"><BookOpen size={20} /></a>
              )}
            </div>
            <div className="space-y-4">
              <p className="text-gray-700 whitespace-pre-wrap leading-relaxed text-base">
                {displayProfile.bio || '自己紹介はまだありません。'}
              </p>
              {(displayProfile.prefecture || displayProfile.city) && (
                <div className="flex items-center gap-1.5 text-[10px] font-bold text-gray-300 uppercase tracking-widest border-t border-gray-50 pt-4">
                  <MapPin size={12} /> {displayProfile.prefecture} {displayProfile.city} {displayProfile.town}
                </div>
              )}
            </div>
          </div>

          {/* 申請バナー（自分のみ） */}
          {isMe && <PendingFriendBanner count={pendingCount} />}

          {/* Communities */}
          <div className="bg-white p-6 rounded-[32px] shadow-sm border border-gray-100 space-y-4">
            <h2 className="font-bold flex items-center gap-2 text-gray-400 uppercase tracking-widest text-[10px]">
              <MessageSquare className="text-pink-600" size={14} /> Communities
            </h2>
            <div className="flex flex-wrap gap-2">
              {myCategories.length > 0 ? myCategories.map(cat => {
                const totalCount = cat.member_count || 0;
                return (
                  <Link key={cat.id} to={`/community/${cat.id}`}
                    className={`px-4 py-1.5 rounded-full text-xs border flex items-center gap-3 font-black shadow-sm transition-all hover:scale-105 ${getRankClasses(totalCount)}`}>
                    <span>{cat.name.split(' (')[0]}</span>
                    <div className="flex items-center gap-1 opacity-60 text-[10px] tabular-nums">
                      <User size={10} strokeWidth={3} />
                      <span>{totalCount.toLocaleString()}</span>
                      {totalCount >= 500 && <Flame size={10} className="text-orange-500" />}
                    </div>
                  </Link>
                );
              }) : (
                <p className="text-gray-300 text-[10px] font-bold uppercase tracking-widest">No communities</p>
              )}
            </div>
          </div>

          {/* Meetups（自分のみ） */}
          {isMe && (
            <div className="bg-white p-4 rounded-[24px] shadow-sm border border-gray-100 space-y-3">
              <h2 className="font-bold flex items-center gap-2 text-gray-400 uppercase tracking-widest text-[9px]">
                <Calendar className="text-orange-500" size={12} /> Joining & My Meetups
              </h2>
              {myMeetups.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {myMeetups.map(meetup => (
                    <Link key={meetup.id} to={`/community/${meetup.hobby_category_id}`}
                      className="flex items-center gap-2 px-3 py-1.5 bg-orange-50 border border-orange-200 rounded-full hover:bg-orange-100 transition-all">
                      <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded-full shrink-0 ${meetup.user_id === displayProfile.id ? 'bg-orange-500 text-white' : 'bg-orange-200 text-orange-700'}`}>
                        {meetup.user_id === displayProfile.id ? '主催' : '参加'}
                      </span>
                      <span className="font-bold text-gray-700 text-[11px] max-w-[120px] truncate">
                        {meetup.content.split('\n')[0]}
                      </span>
                      {meetup.meetup_date && (
                        <span className="text-[9px] text-gray-400 shrink-0">
                          {meetup.meetup_date.slice(5, 10).replace('-', '/')}
                        </span>
                      )}
                    </Link>
                  ))}
                </div>
              ) : (
                <p className="text-[10px] font-bold text-gray-300 uppercase text-center py-2">予定はありません</p>
              )}
            </div>
          )}

          {/* AD Stats（自分のみ） */}
          {isMe && myAdsStats.length > 0 && (
            <div className="bg-white p-4 rounded-[24px] shadow-sm border border-gray-100 space-y-3">
              <h2 className="font-bold flex items-center gap-2 text-gray-400 uppercase tracking-widest text-[9px]">
                <span className="text-green-500">📢</span> My AD Stats
              </h2>
              <div className="flex flex-wrap gap-2">
                {myAdsStats.map((ad: any) => (
                  <div key={ad.id} className="flex items-center gap-3 px-4 py-1.5 bg-green-50 border border-green-200 rounded-full">
                    <span className="text-[11px] font-bold text-green-800 truncate max-w-[120px]">{ad.title}</span>
                    <div className="flex items-center gap-2 shrink-0 border-l border-green-200 pl-2">
                      <span className="text-[11px] font-black text-pink-500">👍 {ad.like_count}</span>
                      <span className="text-[11px] font-black text-yellow-500">📌 {ad.pin_count}</span>
                      {ad.ad_end_date && (
                        <span className="text-[9px] text-green-400">〜{ad.ad_end_date.slice(0, 10)}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Feeling Logs ─────────────────────────────── */}
          {/*
            表示条件:
            - 自分のページ → is_mood_visible に関わらず常に表示（自分のログは見える）
            - 他人のページ → is_mood_visible が true の時のみ表示
          */}
          {(isMe || displayProfile.is_mood_visible) && (
            <div className="bg-white p-6 rounded-[32px] shadow-sm border border-gray-100 space-y-2">
              <div className="flex justify-between items-center border-b border-gray-50 pb-3 mb-2 flex-wrap gap-2">
                <h2 className="font-bold flex items-center gap-2 text-gray-400 uppercase tracking-widest text-[10px]">
                  <Heart className="text-pink-600" size={14} /> Feeling Logs
                </h2>

                {/* 自分のページ → 200円DL */}
                {isMe && (
                  <button
                    onClick={() => handleFeelingLogDownload(displayProfile.id)}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 text-blue-600 rounded-xl text-xs font-bold hover:bg-blue-100 transition-colors shadow-sm"
                  >
                    <Download size={14} /> DL — ¥200
                  </button>
                )}

                {/* 他人のページ → 1,000円 / 30日 カウントダウンDLバー */}
                {!isMe && (
                  <div className="flex flex-col gap-1">
                    {renderFriendsLogBar()}
                    {dlMessage && (
                      <p className="text-[10px] font-bold text-gray-500 pl-1">{dlMessage}</p>
                    )}
                  </div>
                )}
              </div>

              {/* ログ一覧 */}
              {isMe ? (
                // 自分のページ：fetchMyMoodHistory のデータを表示
                <div className="space-y-10">
                  {Object.keys(groupedLogs).sort().reverse().map(month => (
                    <div key={month} className="space-y-4">
                      <div className="flex items-center gap-4">
                        <div className="px-4 py-1.5 bg-gray-900 text-white text-[12px] font-black rounded-xl tracking-tight shadow-sm">
                          {month}
                        </div>
                        <div className="flex-1 h-px bg-gray-100" />
                      </div>
                      <div className="space-y-4 pl-1">
                        {groupedLogs[month].map((log: any) => {
                          const date = new Date(log.created_at.endsWith('Z') ? log.created_at : log.created_at + 'Z');
                          return (
                            <div key={log.id} className="flex items-center gap-5 text-sm">
                              <div className="flex items-center gap-1 w-24 flex-shrink-0">
                                <span className="text-[12px] font-black text-gray-800 tabular-nums">
                                  {String(date.getDate()).padStart(2, '0')}
                                </span>
                                <span className="text-[10px] font-bold text-gray-400 tabular-nums flex items-center gap-1 opacity-80">
                                  <Clock size={10} strokeWidth={3} />
                                  {date.getHours()}:{String(date.getMinutes()).padStart(2, '0')}
                                </span>
                              </div>
                              <span className="text-xl hover:scale-125 transition-transform cursor-default">
                                {moodMap[log.mood_type] || '✨'}
                              </span>
                              <p className="text-gray-500 font-semibold flex-1">{log.comment}</p>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                  {moodLogs.length === 0 && (
                    <p className="text-gray-300 text-[10px] font-bold uppercase tracking-widest text-center py-4">
                      No logs yet
                    </p>
                  )}
                </div>
              ) : (
                // 他人のページ → ログはDL後に確認（ここでは購入誘導のみ）
                <div className="text-center py-6">
                  <p className="text-[11px] font-bold text-gray-300 uppercase tracking-widest">
                    購入後、CSVでダウンロードできます
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default UserProfile;
