import React, { useState, useEffect, useMemo } from 'react';
import { useParams, Link, useLocation } from 'react-router-dom';
import { 
  User, Globe, Twitter, Facebook, Instagram, BookOpen,
  Edit, MessageSquare, Heart, Download, Save, X, Eye, 
  EyeOff, AtSign, MapPin, Clock, Flame, Calendar, BadgeCheck, 
  Tag, Plus, Trash2, BarChart2
} from 'lucide-react';
import { 
  authApi, 
  fetchMyCommunities,
  HobbyCategory, 
  fetchMyMoodHistory, 
  fetchMyTags, 
  createTag, 
  deleteTag, 
  UserTag,
  MoodLog,
  startFeelingLogCheckout, startFriendsLogCheckout, verifyFriendsLogSession, 
} from '../api';

interface UserProfileProps {
  profile: any; 
  fetchProfile: () => void;
}

const TAG_COLOR_OPTIONS = [
    { value: 'pink',   cls: 'bg-pink-400'    },
    { value: 'purple', cls: 'bg-purple-400'  },
    { value: 'blue',   cls: 'bg-blue-400'    },
    { value: 'green',  cls: 'bg-emerald-400' },
    { value: 'orange', cls: 'bg-orange-400'  },
    { value: 'gray',   cls: 'bg-gray-400'    },
];

const TAG_COLOR_MAP: Record<string, string> = {
    pink:   'bg-pink-100 text-pink-700 border-pink-200',
    purple: 'bg-purple-100 text-purple-700 border-purple-200',
    blue:   'bg-blue-100 text-blue-700 border-blue-200',
    green:  'bg-emerald-100 text-emerald-700 border-emerald-200',
    orange: 'bg-orange-100 text-orange-700 border-orange-200',
    gray:   'bg-gray-100 text-gray-600 border-gray-200',
};

const MOOD_SCORE: Record<string, number> = {
    motivated: 5, excited: 5, happy: 4, grateful: 4,
    calm: 3, neutral: 3,
    anxious: 2, tired: 2, sad: 1, angry: 1,
};

const BACKEND_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface TagManagerSectionProps {
    userTags: UserTag[];
    newTagLabel: string;
    setNewTagLabel: (v: string) => void;
    newTagColor: string;
    setNewTagColor: (v: string) => void;
    tagSaving: boolean;
    handleAddTag: () => void;
    handleDeleteTag: (id: number) => void;
}

const TagManagerSection: React.FC<TagManagerSectionProps> = ({
    userTags, newTagLabel, setNewTagLabel,
    newTagColor, setNewTagColor,
    tagSaving, handleAddTag, handleDeleteTag
}) => (
    <div className="pt-4 border-t border-gray-50 space-y-3">
        <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest flex items-center gap-1">
            <Tag size={10} /> My Tags（投稿時カテゴリ）
            <span className="ml-auto text-gray-300">{userTags.length}/10</span>
        </p>
        <div className="flex flex-wrap gap-1.5 min-h-[24px]">
            {userTags.length === 0 && (
                <p className="text-[10px] text-gray-300 font-bold">タグがまだありません</p>
            )}
            {userTags.map(tag => (
                <span key={tag.id} className={`flex items-center gap-1 pl-2.5 pr-1 py-0.5 rounded-full text-[11px] font-bold border ${TAG_COLOR_MAP[tag.color] ?? TAG_COLOR_MAP.gray}`}>
                    {tag.label}
                    <button type="button" onClick={() => handleDeleteTag(tag.id)} className="ml-0.5 hover:opacity-70 transition-opacity">
                        <Trash2 size={10} />
                    </button>
                </span>
            ))}
        </div>
        {userTags.length < 10 && (
            <div className="flex items-center gap-2 flex-wrap">
                <div className="flex gap-1">
                    {TAG_COLOR_OPTIONS.map(opt => (
                        <button key={opt.value} type="button" onClick={() => setNewTagColor(opt.value)}
                            className={`w-5 h-5 rounded-full ${opt.cls} transition-all ${newTagColor === opt.value ? 'ring-2 ring-offset-1 ring-gray-400 scale-110' : 'opacity-40 hover:opacity-75'}`}
                        />
                    ))}
                </div>
                <input type="text" placeholder="タグ名（例: 推し活）" maxLength={15} value={newTagLabel}
                    onChange={e => setNewTagLabel(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleAddTag(); } }}
                    className="flex-1 min-w-[120px] px-3 py-1.5 bg-gray-50 rounded-xl border-none text-xs focus:ring-2 focus:ring-pink-400 outline-none"
                />
                <button type="button" disabled={!newTagLabel.trim() || tagSaving} onClick={handleAddTag}
                    className="flex items-center gap-1 px-3 py-1.5 bg-pink-500 text-white rounded-xl text-[11px] font-bold disabled:opacity-40 hover:bg-pink-600 active:scale-95 transition-all">
                    <Plus size={12} />
                    {tagSaving ? '追加中…' : '追加'}
                </button>
            </div>
        )}
    </div>
);

const buildMonthlyReport = (logs: MoodLog[]) => {
    const now = new Date();
    const cutoff = new Date(now.getFullYear(), now.getMonth() - 1, now.getDate());
    const recent = logs.filter(l => {
        const d = new Date(l.created_at.endsWith('Z') ? l.created_at : l.created_at + 'Z');
        return d >= cutoff;
    });
    if (recent.length === 0) return null;

    // 曜日別平均
    const DAY_JP = ['日', '月', '火', '水', '木', '金', '土'];
    const buckets: Record<number, number[]> = {};
    for (let i = 0; i < 7; i++) buckets[i] = [];
    const catCount: Record<string, number> = {};

    recent.forEach(log => {
        const d = new Date(log.created_at.endsWith('Z') ? log.created_at : log.created_at + 'Z');
        buckets[d.getDay()].push(MOOD_SCORE[log.mood_type] ?? 3);
        if (log.category) catCount[log.category] = (catCount[log.category] ?? 0) + 1;
    });

    const weekdayAvg = Object.entries(buckets)
        .map(([day, scores]) => ({
            day: DAY_JP[Number(day)],
            avg: scores.length
                ? Math.round((scores.reduce((a, b) => a + b, 0) / scores.length) * 10) / 10
                : null,
            count: scores.length,
        }))
        .filter(d => d.count > 0);

    const overallAvg = Math.round(
        (recent.reduce((sum, l) => sum + (MOOD_SCORE[l.mood_type] ?? 3), 0) / recent.length) * 10
    ) / 10;

    const best  = weekdayAvg.length ? weekdayAvg.reduce((a, b) => (a.avg ?? 0) >= (b.avg ?? 0) ? a : b) : null;
    const worst = weekdayAvg.length ? weekdayAvg.reduce((a, b) => (a.avg ?? 5) <= (b.avg ?? 5) ? a : b) : null;

    const topCategories = Object.entries(catCount).sort((a, b) => b[1] - a[1]).slice(0, 3);

    type CatAvgScore = { label: string; avg: number; count: number };

    const catScores: Record<string, number[]> = {};
    recent.forEach(log => {
        if (log.category) {
            if (!catScores[log.category]) catScores[log.category] = [];
            catScores[log.category].push(MOOD_SCORE[log.mood_type] ?? 3);
        }
    });
    const catAvgScores: CatAvgScore[] = Object.entries(catScores).map(([label, scores]) => ({
        label,
        avg: Math.round((scores.reduce((a, b) => a + b, 0) / scores.length) * 10) / 10,
        count: scores.length,
    })).sort((a, b) => b.avg - a.avg);

    return { recent, weekdayAvg, overallAvg, best, worst, topCategories, catAvgScores };
};

const MonthlyReportSection: React.FC<{ logs: MoodLog[] }> = ({ logs }) => {
    const report = useMemo(() => buildMonthlyReport(logs), [logs]);

if (!report) return (
    <div className="mb-3 p-4 bg-gray-50 rounded-2xl space-y-2">
        <p className="text-[9px] font-bold text-gray-300 uppercase tracking-widest mb-1">
            📋 直近の記録
        </p>
        {logs.slice(0, 10).map(log => {
            const EMOJI: Record<string, string> = {
                motivated: '🔥', excited: '🤩', happy: '😊', calm: '😌',
                neutral: '😶', anxious: '💭', tired: '😩', sad: '😭',
                angry: '😡', grateful: '🙏',
            };
            const date = new Date(log.created_at.endsWith('Z') ? log.created_at : log.created_at + 'Z');
            return (
                <div key={log.id} className="flex items-center gap-3 text-[11px]">
                    <span className="text-gray-300 tabular-nums w-12 shrink-0">
                        {String(date.getMonth()+1)}/{String(date.getDate()).padStart(2,'0')}
                    </span>
                    <span>{EMOJI[log.mood_type] || '✨'}</span>
                    {log.category && (
                        <span className="px-1.5 py-0.5 bg-pink-50 text-pink-400 rounded-full text-[9px] font-bold">
                            {log.category}
                        </span>
                    )}
                    <span className="text-gray-400 truncate">{log.comment}</span>
                </div>
            );
        })}
        {logs.length === 0 && (
            <p className="text-[10px] text-gray-300 text-center py-2">気分を記録するとここに表示されます</p>
        )}
    </div>
);

    const { recent, weekdayAvg, overallAvg, best, worst, topCategories, catAvgScores } = report;
    
    const barColor = (avg: number | null) => {
        if (!avg) return 'bg-gray-200';
        if (avg >= 4) return 'bg-emerald-400';
        if (avg >= 3) return 'bg-amber-400';
        return 'bg-rose-400';
    };

    // スコアの絵文字
    const scoreEmoji = overallAvg >= 4 ? '😊' : overallAvg >= 3 ? '😌' : '😔';

    return (
        <div className="mb-3 p-4 bg-gradient-to-br from-pink-50/50 to-white rounded-2xl border border-gray-100 space-y-3">
            {/* ヘッダー */}
            <div className="flex items-center justify-between">
                <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest flex items-center gap-1.5">
                    <BarChart2 size={11} className="text-pink-400" />
                    直近1ヶ月レポート
                </p>
                <span className="text-[9px] text-gray-300">{recent.length}件の記録</span>
            </div>

            {/* 平均スコア */}
            <div className="flex items-baseline gap-2">
                <span className="text-3xl font-black text-gray-800 tabular-nums">{overallAvg}</span>
                <span className="text-[10px] text-gray-400 font-bold">/ 5.0</span>
                <span className="text-xl ml-1">{scoreEmoji}</span>
            </div>

            {/* 曜日バイオリズム */}
            <div className="space-y-1.5">
                <p className="text-[9px] font-bold text-gray-300 uppercase tracking-widest">曜日別バイオリズム</p>
                {weekdayAvg.map(({ day, avg, count }) => (
                    <div key={day} className="flex items-center gap-2">
                        <span className="text-[10px] font-black text-gray-500 w-4 shrink-0">{day}</span>
                        <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                            <div
                                className={`h-full rounded-full ${barColor(avg)}`}
                                style={{ width: avg !== null ? `${(avg / 5) * 100}%` : '0%' }}
                            />
                        </div>
                        <span className="text-[9px] text-gray-400 tabular-nums w-6 text-right shrink-0">
                            {avg ?? '-'}
                        </span>
                        <span className="text-[9px] text-gray-200 tabular-nums shrink-0">×{count}</span>
                    </div>
                ))}
                {best && worst && best.day !== worst.day && (
                    <p className="text-[9px] text-gray-400 pt-0.5">
                        <span className="text-emerald-500 font-bold">{best.day}曜</span>が最高 ·{' '}
                        <span className="text-rose-400 font-bold">{worst.day}曜</span>が最低
                    </p>
                )}
            </div>

            {/* よく使ったタグ */}
            {topCategories.length > 0 && (
                <div className="space-y-1">
                    <p className="text-[9px] font-bold text-gray-300 uppercase tracking-widest">よく使ったタグ</p>
                    <div className="flex flex-wrap gap-1">
                        {topCategories.map(([label, count], i) => (
                            <span
                                key={label}
                                className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                                    i === 0
                                        ? 'bg-pink-50 text-pink-600 border-pink-200'
                                        : 'bg-gray-50 text-gray-500 border-gray-200'
                                }`}
                            >
                                {label} <span className="opacity-50">×{count}</span>
                            </span>
                        ))}
                    </div>
                </div>
            )}

            {/* ✅ ここに追加：タグ別スコア平均 */}
            {catAvgScores.length > 0 && (
                <div className="space-y-1.5">
                    <p className="text-[9px] font-bold text-gray-300 uppercase tracking-widest">タグ別 気分スコア</p>
                    {catAvgScores.map(({ label, avg, count }) => (
                        <div key={label} className="flex items-center gap-2">
                            <span className="text-[10px] font-bold text-gray-500 w-16 truncate shrink-0">{label}</span>
                            <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                                <div
                                    className={`h-full rounded-full ${
                                        avg >= 4 ? 'bg-emerald-400' : avg >= 3 ? 'bg-amber-400' : 'bg-rose-400'
                                    }`}
                                    style={{ width: `${(avg / 5) * 100}%` }}
                                />
                            </div>
                            <span className="text-[9px] text-gray-400 tabular-nums w-6 text-right shrink-0">{avg}</span>
                            <span className="text-[9px] text-gray-200 tabular-nums shrink-0">×{count}</span>
                        </div>
                    ))}
                </div>
            )}

            {/* 200円AI診断への誘導（③の布石） */}
            <div className="pt-2 border-t border-gray-100 flex items-center justify-between">
                <p className="text-[9px] text-gray-300">3ヶ月分のAI詳細レポートは↗</p>
                <span className="text-[9px] text-pink-300 font-bold">準備中 🤖</span>
            </div>
        </div>
    );
};

const UserProfile: React.FC<UserProfileProps> = ({ profile: myProfile, fetchProfile: fetchMyProfile }) => {
  const { userId } = useParams<{ userId: string }>();
  const location = useLocation();
  
  const [displayProfile, setDisplayProfile] = useState<any>(null);
  const [isMe, setIsMe] = useState(true);
  const [loading, setLoading] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [tempProfile, setTempProfile] = useState<any>(null);
  const [myCategories, setMyCategories] = useState<HobbyCategory[]>([]);
  const [moodLogs, setMoodLogs] = useState<MoodLog[]>([]);
  const [moodError, setMoodError] = useState<'logout' | 'failed' | null>(null);
  const [myMeetups, setMyMeetups] = useState<any[]>([]); 

  const [myAdsStats, setMyAdsStats] = useState<any[]>([]);

  const [friendsLogUnlocked, setFriendsLogUnlocked] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [friendsLogExpires, setFriendsLogExpires] = useState<string | null>(null);

  const [pendingCount, setPendingCount] = useState(0);
  const [unconfirmedMeetups, setUnconfirmedMeetups] = useState<any[]>([]);

  const [connectStatus, setConnectStatus] = useState<{
    connected: boolean;
    is_ready?: boolean;
  } | null>(null);
  const [userTags, setUserTags]       = useState<UserTag[]>([]);
  const [newTagLabel, setNewTagLabel] = useState('');
  const [newTagColor, setNewTagColor] = useState('gray');
  const [tagSaving, setTagSaving]     = useState(false);

  const getRankClasses = (count: number) => {
    if (count >= 10000) return "bg-yellow-50 text-yellow-700 border-yellow-300 shadow-sm";
    if (count >= 500) return "bg-pink-50 text-pink-700 border-pink-200";
    return "bg-gray-50 text-gray-500 border-gray-100";
  };

  const getDynamicXIcon = (url: string | null) => {
    const isThreads = url?.includes('threads.net');
    return {
      Icon: isThreads ? AtSign : Twitter,
      label: isThreads ? 'Threads' : 'Twitter (X)',
      classes: isThreads 
        ? "bg-gray-800 text-white hover:bg-black" 
        : "bg-blue-50 text-blue-500 hover:bg-blue-500 hover:text-white"
    };
  };

  const executeDownload = async (sessionId: string) => {
    try {
      setIsDownloading(true);
      const response = await fetch(
        `${BACKEND_URL}/api/download/feeling-log?session_id=${sessionId}`
      );

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'ダウンロードに失敗しました');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `my_feeling_log_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      window.history.replaceState({}, '', window.location.pathname);
      alert("ダウンロードが完了しました！");
    } catch (error: any) {
      console.error("Download error:", error);
      alert(error.message || "ダウンロード中にエラーが発生しました。");
    } finally {
      setIsDownloading(false);
    }
  };

  const handleFeelingLogDownload = async (profileId: string | number) => {
    try {
      setIsDownloading(true);
      const successUrl = `${window.location.origin}${window.location.pathname}?session_id={CHECKOUT_SESSION_ID}`;

      const response = await fetch(`${BACKEND_URL}/api/stripe/feeling-log-checkout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          userId: profileId,
          successUrl: successUrl,
          cancelUrl: window.location.href,
        })
      });

      const data = await response.json();
      if (data.url) {
        window.location.href = data.url;
      }
    } catch (error) {
      console.error("Checkout error:", error);
      alert("決済の準備に失敗しました。");
    } finally {
      setIsDownloading(false);
    }
  };

  useEffect(() => {
    const query = new URLSearchParams(location.search);
    const sessionId = query.get('session_id');
    if (sessionId && !isDownloading) {
      executeDownload(sessionId);
    }
    // ✅ Connect完了後の再確認
    if (query.get('connect_done')) {
      authApi.get(`/api/stripe/connect/status?user_id=${myProfile?.id}`)
        .then(res => setConnectStatus(res.data))
        .catch(() => {});
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, [location.search]);

  useEffect(() => {
    if (userId) {
      const fetchTarget = async (id: string) => {
        try {
          setLoading(true);
          const response = await authApi.get(`/users/${id}`);
          setDisplayProfile(response.data);
          setIsMe(false);
        } finally { setLoading(false); }
      };
      fetchTarget(userId);
    } else {
      setDisplayProfile(myProfile);
      setTempProfile({ ...myProfile });
      setIsMe(true);
      setLoading(false);
    }
  }, [userId, myProfile]);

  useEffect(() => {
    const loadData = async () => {
      if (!isMe) return;
      try {
        const categories = await fetchMyCommunities();
        setMyCategories(categories);

        try {
          const tags = await fetchMyTags();
          setUserTags(tags);
        } catch {}

        const [joinedRes, hostedRes] = await Promise.all([
          authApi.get('/posts/my-meetups'),
          authApi.get('/posts/my-hosted-meetups')
        ]);

        if (isMe) {
          const adsRes = await authApi.get('/posts/my-ads-stats'); 
          setMyAdsStats(adsRes.data || []);

          const pendingRes = await authApi.get('/friends/pending/count');
          setPendingCount(pendingRes.data.pending_count || 0);

          try {
            const unconfirmedRes = await authApi.get('/hobby-categories/my-unconfirmed-meetups');
            setUnconfirmedMeetups(unconfirmedRes.data || []);
          } catch {}

          // Stripe Connect状態確認
          try {
            const connectRes = await authApi.get(`/api/stripe/connect/status?user_id=${myProfile?.id}`);
            setConnectStatus(connectRes.data);
          } catch {}
        }

        const joined = joinedRes.data || [];
        const hosted = hostedRes.data || [];

        const allMeetups = [...hosted];
        joined.forEach((m: any) => {
          if (!allMeetups.find((existing: any) => existing.id === m.id)) {
            allMeetups.push(m);
          }
        });

        const futureMeetups = allMeetups.filter((m: any) =>
          !m.meetup_date || new Date(m.meetup_date) > new Date()
        );
        setMyMeetups(futureMeetups);

        const token = localStorage.getItem('access_token');
        if (!token) {
          setMoodError('logout');
        } else {
          try {
            const logs = await fetchMyMoodHistory();
            setMoodLogs(logs);
          } catch (err: any) {
            if (err?.response?.status === 401) {
              setMoodError('logout');
            } else {
              setMoodError('failed');
            }
          }
        }

      } catch (err) {
        console.error("データ取得失敗:", err);
      }
    };

    loadData();
  }, [displayProfile?.id, isMe]);

  const groupedLogs = moodLogs.reduce((acc: any, log) => {
    const date = new Date(log.created_at.endsWith('Z') ? log.created_at : log.created_at + 'Z');
    const monthKey = `${date.getFullYear()} - ${String(date.getMonth() + 1).padStart(2, '0')}`;
    if (!acc[monthKey]) acc[monthKey] = [];
    acc[monthKey].push(log);
    return acc;
  }, {});

  const toggleEdit = () => {
    setTempProfile({ ...myProfile }); 
    setIsEditing(!isEditing);
  };

  const handleSave = async () => {
    if (!tempProfile) return;
    try {
      await authApi.put('/users/me', tempProfile);
      fetchMyProfile();
      setIsEditing(false);
      alert("プロフィールを更新しました！");
    } catch (err) { alert("更新に失敗しました。"); }
  };

  const handleAddTag = async () => {
    if (!newTagLabel.trim() || userTags.length >= 10) return;
    setTagSaving(true);
    try {
      const created = await createTag({
        label: newTagLabel.trim(),
        color: newTagColor,
        sort_order: userTags.length,
      });
      setUserTags(prev => [...prev, created]);
      setNewTagLabel('');
    } catch (e: any) {
      alert(e?.response?.data?.detail || 'タグの追加に失敗しました。');
    } finally {
      setTagSaving(false);
    }
  };

  const handleDeleteTag = async (tagId: number) => {
    try {
      await deleteTag(tagId);
      setUserTags(prev => prev.filter(t => t.id !== tagId));
    } catch {
      alert('タグの削除に失敗しました。');
    }
  };

  const handleCancel = async (postId: number) => {
    if (!window.confirm("このミートアップの参加をキャンセルしますか？\n※当日0時以降はキャンセル料が発生する場合があります。")) return;
    try {
      await authApi.delete(`/responses/cancel/${postId}`);
      setMyMeetups(prev => prev.filter(m => m.id !== postId));
      alert("キャンセルを完了しました。");
    } catch (err) {
      alert("キャンセルの実行に失敗しました。");
    }
  };

  if (loading) return <div className="text-center py-10">読み込み中...</div>;
  if (!displayProfile) return <div className="text-center py-10 text-gray-400">ユーザーが見つかりません。</div>;

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-3">
      {/* Header */}
      <div className="flex justify-between items-start mb-4">
        <h1 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
          <User className="text-pink-600" size={24} />
          <span>
            {displayProfile.nickname || displayProfile.username}'s PAGE
          </span>
        </h1>
        {isMe && (
          <button onClick={toggleEdit} className="ml-4 px-3 py-2 bg-pink-600 text-white rounded-2xl flex items-center gap-1.5 text-sm font-bold shrink-0 transition-all hover:bg-pink-700 shadow-md active:scale-95">
            {isEditing ? <><X size={16}/> 戻る</> : <><Edit size={16}/> 編集</>}
          </button>
        )}
      </div>

      {isEditing && tempProfile ? (
        /* EDIT MODE */
        <div className="bg-white p-8 rounded-[32px] shadow-sm border border-gray-100 space-y-8 animate-in fade-in">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div className="space-y-3">
              <div className="space-y-2">
                <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest ml-1">Nickname</label>
                <input type="text" className="w-full p-4 bg-gray-50 rounded-[20px] border-none focus:ring-2 focus:ring-pink-500 font-bold" value={tempProfile.nickname || ''} onChange={e => setTempProfile({...tempProfile, nickname: e.target.value})} />
              </div>

              <div className="grid grid-cols-1 gap-4">
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
                        <label className="text-[9px] font-bold text-gray-400 uppercase">{sns.id === 'x' ? xConfig?.label : sns.label}</label>
                        <button type="button" onClick={() => setTempProfile({...tempProfile, [sns.visibleKey]: !tempProfile[sns.visibleKey]})} className={`flex items-center gap-1.5 text-[9px] font-bold px-2.5 py-1 rounded-full transition-colors ${tempProfile[sns.visibleKey] ? 'bg-pink-100 text-pink-600' : 'bg-gray-100 text-gray-400'}`}>
                          {tempProfile[sns.visibleKey] ? <><Eye size={10}/> 公開</> : <><EyeOff size={10}/> 非公開</>}
                        </button>
                      </div>
                      <div className="relative">
                        <div className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400"><IconComp size={16} /></div>
                        <input type="text" placeholder={`https://...`} className="w-full p-3.5 pl-12 bg-gray-50 rounded-2xl border-none text-sm focus:ring-2 focus:ring-pink-500" value={tempProfile[sns.urlKey] || ''} onChange={e => setTempProfile({...tempProfile, [sns.urlKey]: e.target.value})} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest ml-1">Birth</label>
                  <input type="text" placeholder="1990-01" className="w-full p-4 bg-gray-50 rounded-2xl border-none text-sm" value={tempProfile.birth_year_month || ''} onChange={e => setTempProfile({...tempProfile, birth_year_month: e.target.value})} />
                </div>
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest ml-1">Gender</label>
                  <select className="w-full p-4 bg-gray-50 rounded-2xl border-none text-sm" value={tempProfile.gender || ''} onChange={e => setTempProfile({...tempProfile, gender: e.target.value})}>
                    <option value="">未設定</option>
                    <option value="male">男🚹</option>
                    <option value="female">女🚺</option>
                    <option value="other">その他</option>
                  </select>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest ml-1 flex items-center gap-1"><MapPin size={10} /> Residence Location</label>
                <div className="grid grid-cols-3 gap-2">
                  <input placeholder="Pref" className="p-3.5 bg-gray-50 rounded-2xl border-none text-xs focus:ring-2 focus:ring-pink-500" value={tempProfile.prefecture || ''} onChange={e => setTempProfile({...tempProfile, prefecture: e.target.value})} />
                  <input placeholder="City" className="p-3.5 bg-gray-50 rounded-2xl border-none text-xs focus:ring-2 focus:ring-pink-500" value={tempProfile.city || ''} onChange={e => setTempProfile({...tempProfile, city: e.target.value})} />
                  <input placeholder="Town" className="p-3.5 bg-gray-50 rounded-2xl border-none text-xs focus:ring-2 focus:ring-pink-500" value={tempProfile.town || ''} onChange={e => setTempProfile({...tempProfile, town: e.target.value})} />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest ml-1">Bio</label>
                <textarea className="w-full p-5 bg-gray-50 rounded-[32px] border-none text-sm h-32 focus:ring-2 focus:ring-pink-500" value={tempProfile.bio || ''} onChange={e => setTempProfile({...tempProfile, bio: e.target.value})} />
              </div>

              {/* 気分コメント表示設定 */}
              <div className="pt-4 border-t border-gray-50">
                <label className="flex items-center gap-3 cursor-pointer group">
                  <input type="checkbox" className="hidden" checked={tempProfile.is_mood_comment_visible} onChange={e => setTempProfile({...tempProfile, is_mood_comment_visible: e.target.checked})} />
                  <div className={`p-2 rounded-xl transition-all ${tempProfile.is_mood_comment_visible ? 'bg-pink-100 text-pink-600' : 'bg-gray-100 text-gray-400'}`}>
                    {tempProfile.is_mood_comment_visible ? <MessageSquare size={18}/> : <EyeOff size={18}/>}
                  </div>
                  <div className="flex flex-col">
                    <span className="text-xs font-bold text-gray-500">気分のコメントを表示する</span>
                    <span className="text-[10px] text-gray-400">災害時など、言葉を伝えたい時にONにしてください</span>
                  </div>
                </label>
              </div>

              {/* ✅ Stripe Connect 口座登録 — 気分コメントの直下 */}
              <div className="pt-4 border-t border-gray-50">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-ts font-bold text-gray-500 uppercase tracking-widest mb-1">
                      MEETUP 主催者登録
                    </p>
                    {connectStatus?.is_ready ? (
                      <p className="text-[10px] font-bold text-green-600">✅ 主催者登録済み 振込可能 👑</p>
                    ) : connectStatus?.connected ? (
                      <p className="text-[10px] font-bold text-amber-500">⚠️ 手続き中</p>
                    ) : (
                      <p className="text-[10px] text-gray-400">MEETUP参加費 受領用</p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={async () => {
                      try {
                        const res = await authApi.post('/api/stripe/connect/onboard', {
                          userId: displayProfile.id
                        });
                        if (res.data.url) window.location.href = res.data.url;
                      } catch {
                        alert('エラーが発生しました。');
                      }
                    }}
                    className={`flex items-center gap-1 px-2 py-2 rounded-xl text-[10px] font-black transition-all ${
                      connectStatus?.is_ready
                        ? 'bg-gray-100 text-gray-500 cursor-default'
                        : 'bg-orange-500 text-white hover:bg-orange-600 shadow-md'
                    }`}
                  >
                    <BadgeCheck size={14} />
                    {connectStatus?.is_ready ? '登録済み' : '口座登録'}
                  </button>
                </div>
              </div>
            </div>
          </div>
     
          {/* Bio の直後に追加 */}
          <div className="space-y-1">
            <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest ml-1 flex items-center gap-1">
              👣 GOAL・目標・標/導・BEACON・MILESTONE
            </label>
            <input
              type="text"
              maxLength={200}
              placeholder="例：今月は週3で運動する"
              className="w-full p-3 py bg-gray-50 rounded-2xl border-none text-sm focus:ring-2 focus:ring-pink-500"
              value={tempProfile.goal || ''}
              onChange={e => setTempProfile({ ...tempProfile, goal: e.target.value })}
            />
          </div>

        <TagManagerSection
            userTags={userTags}
            newTagLabel={newTagLabel}
            setNewTagLabel={setNewTagLabel}
            newTagColor={newTagColor}
            setNewTagColor={setNewTagColor}
            tagSaving={tagSaving}
            handleAddTag={handleAddTag}
            handleDeleteTag={handleDeleteTag}
          />
          <button onClick={handleSave} className="w-full py-5 bg-gray-900 text-white rounded-[24px] font-bold flex items-center justify-center gap-3 hover:bg-black transition-all shadow-xl active:scale-[0.98]">
            <Save size={20} /> プロフィールを保存
          </button>
        </div>
      ) : (
        /* VIEW MODE */
        <div className="space-y-3">
          {/* SNS Links & Bio — 常に表示 */}
          <div className="bg-white p-8 rounded-[32px] shadow-sm border border-gray-100">
            <div className="flex flex-wrap gap-4 mb-6">
              {displayProfile.x_url && displayProfile.is_x_visible !== false && (
                <a href={displayProfile.x_url} target="_blank" rel="noopener noreferrer" className={`p-3 rounded-full transition-all shadow-sm ${getDynamicXIcon(displayProfile.x_url).classes}`}>{React.createElement(getDynamicXIcon(displayProfile.x_url).Icon, { size: 20 })}</a>
              )}
              {displayProfile.facebook_url && displayProfile.is_facebook_visible !== false && (
                <a href={displayProfile.facebook_url} target="_blank" rel="noopener noreferrer" className="p-3 bg-blue-50 rounded-full text-blue-600 hover:bg-blue-600 hover:text-white transition-all shadow-sm"><Facebook size={20} /></a>
              )}
              {displayProfile.instagram_url && displayProfile.is_instagram_visible !== false && (
                <a href={displayProfile.instagram_url} target="_blank" rel="noopener noreferrer" className="p-3 bg-pink-50 rounded-full text-pink-600 hover:bg-pink-600 hover:text-white transition-all shadow-sm"><Instagram size={20} /></a>
              )}
              {displayProfile.note_url && displayProfile.is_note_visible !== false && (
                <a href={displayProfile.note_url} target="_blank" rel="noopener noreferrer" className="p-3 bg-green-50 rounded-full text-green-600 hover:bg-green-600 hover:text-white transition-all shadow-sm"><BookOpen size={20} /></a>
              )}
            </div>
            <div className="space-y-4">
              <p className="text-gray-700 whitespace-pre-wrap leading-relaxed text-base">{displayProfile.bio || '自己紹介はまだありません。'}</p>
              {(displayProfile.prefecture || displayProfile.city) && (
                <div className="flex items-center gap-1.5 text-[10px] font-bold text-gray-300 uppercase tracking-widest border-t border-gray-50 pt-4">
                  <MapPin size={12} /> {displayProfile.prefecture} 
                </div>
              )}
            </div>
          </div>

          {/* 自分のみ: フレンド申請通知 */}
          {isMe && pendingCount > 0 && (
            <Link
              to="/friends"
              state={{ tab: 'requests' }}
              className="block text-xs font-bold text-amber-500 hover:text-amber-600"
            >
              🔔 ともだち申請が{pendingCount}件あります
            </Link>
          )}
          {unconfirmedMeetups.map(meetup => (
              <Link
                  key={meetup.id}
                  to={`/community/${meetup.hobby_category_id}`}
                  className="block text-xs font-black text-orange-500 hover:text-orange-600 mb-4"
              >
                  🎪 「{meetup.title}」の開催確定を押してください
              </Link>
          ))}

          {/* 🔒 非公開バナー */}
          {isMe && (
            <div className="flex items-center gap-3">
              <div className="flex-1 h-px bg-gray-200"></div>
              <p className="text-[11px] font-bold text-gray-300 tracking-wide shrink-0">
                🙈 Under sections --- Only Visible to You 🙈
              </p>
              <div className="flex-1 h-px bg-gray-200"></div>
            </div>
          )}

          {isMe && (
            <>
              {/* Communities */}
              <div className="bg-white p-6 rounded-[32px] shadow-sm border border-gray-100 space-y-4">
                <h2 className="font-bold flex items-center gap-2 text-gray-400 uppercase tracking-widest text-[10px]">
                  <MessageSquare className="text-pink-600" size={14}/> Communities
                  {connectStatus?.is_ready && (
                    <span className="ml-1 text-[14px]" title="HOST登録済み">👑</span>
                  )}
                </h2>
                <div className="flex flex-wrap gap-2">
                  {myCategories.length > 0 ? myCategories.map(cat => {
                    const totalCount = cat.member_count || 0; 
                    return (
                      <Link 
                        key={cat.id} 
                        to={`/community/${cat.id}`} 
                        className={`px-4 py-1.5 rounded-full text-xs border flex items-center gap-3 font-black shadow-sm transition-all hover:scale-105 ${getRankClasses(totalCount)}`}
                      >
                        <span>{cat.name.split(' (')[0]}</span> 
                        <div className="flex items-center gap-1 opacity-60 text-[10px] tabular-nums">
                          <User size={10} strokeWidth={3} />
                          <span>{totalCount.toLocaleString()}</span>
                          {totalCount >= 500 && <Flame size={10} className="text-orange-500" />}
                        </div>
                      </Link>
                    );
                  }) : <p className="text-gray-300 text-[10px] font-bold uppercase tracking-widest">No Communities</p>}
                </div>
              </div>

              {/* JOINING & MY MEETUPS */}
              {isMe && (
                <div className="bg-white p-4 rounded-[24px] shadow-sm border border-gray-100 space-y-3">
                  <h2 className="font-bold flex items-center gap-2 text-gray-400 uppercase tracking-widest text-[9px]">
                    <Calendar className="text-orange-500" size={12}/> Joining & My Meetups
                  </h2>
                  {myMeetups.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {myMeetups.map(meetup => (
                        <Link
                          key={meetup.id}
                          to={`/community/${meetup.hobby_category_id}`}
                          className="flex items-center gap-2 px-3 py-1.5 bg-orange-50 border border-orange-200 rounded-full hover:bg-orange-100 transition-all"
                        >
                          <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded-full shrink-0 ${meetup.user_id === displayProfile.id ? 'bg-orange-500 text-white' : 'bg-orange-200 text-orange-700'}`}>
                            {meetup.user_id === displayProfile.id ? "主催" : "参加"}
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

              {/* ✅ MY ADS STATS — 期限切れフィルター修正 */}
              {(() => {
                const activeAds = myAdsStats.filter(ad => {
                  const expiry = ad.ad_end_date
                    ? new Date(new Date(ad.ad_end_date).getTime() + 1 * 86400000)
                    : new Date(new Date(ad.created_at).getTime() + 46 * 86400000);
                  return expiry > new Date();
                });
                if (activeAds.length === 0) return null;
                return (
                  <div className="bg-white p-4 rounded-[24px] shadow-sm border border-gray-100 space-y-3">
                    <h2 className="font-bold flex items-center gap-2 text-gray-400 uppercase tracking-widest text-[9px]">
                      My Ads
                    </h2>
                    <div className="flex flex-wrap gap-2">
                      {activeAds.map(ad => (
                        <Link
                          key={ad.id}
                          to={`/community/${ad.hobby_category_id}`}
                          className="flex items-center gap-3 px-4 py-1.5 bg-green-50 border border-green-200 rounded-full hover:bg-green-100 transition-all"
                        >
                          <span className="text-[11px] font-bold text-green-800 truncate max-w-[120px]">
                            {ad.title}
                          </span>
                          <div className="flex items-center gap-2 shrink-0 border-l border-green-200 pl-2">
                            <span className="text-[11px] font-black text-pink-500">👍 {ad.like_count}</span>
                            <span className="text-[11px] font-black text-yellow-500">📌 {ad.pin_count}</span>
                            {ad.ad_end_date && (
                              <span className="text-[9px] text-green-400">
                                〜{ad.ad_end_date.slice(0, 10)}
                              </span>
                            )}
                          </div>
                        </Link>
                      ))}
                    </div>
                  </div>
                );
              })()}

              {/* Feeling Logs */}
              <div className="bg-white p-6 rounded-[32px] shadow-sm border border-gray-100 space-y-2">
                <div className="flex justify-between items-center border-b border-gray-50 pb-2 mb-2">
                  <h2 className="font-bold flex items-center gap-2 text-gray-400 uppercase tracking-widest text-[10px]">
                    <Heart className="text-pink-600" size={14}/> Feeling Logs shows up to 100
                  </h2>
                  <button 
                    disabled={isDownloading} 
                    className={`flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 text-blue-600 rounded-xl text-xs font-bold hover:bg-blue-100 transition-colors shadow-sm ${
                      isDownloading ? 'opacity-50 cursor-not-allowed' : ''
                    }`}
                    onClick={() => handleFeelingLogDownload(displayProfile.id)}
                  >
                    <Download size={14} /> <span>🤝DL¥200</span>
                  </button>
                </div>
                {!moodError && <MonthlyReportSection logs={moodLogs} />}
                {moodError === 'logout' ? (
                  <div className="py-6 text-center space-y-2">
                    <p className="text-gray-400 text-[11px] font-bold">🔒 Logged out（ログアウト中）かもしれません</p>
                    <Link to="/login" className="text-xs font-bold text-pink-500 hover:underline">
                      Loginはこちら →
                    </Link>
                  </div>
                ) : moodError === 'failed' ? (
                  <p className="text-red-400 text-[11px] font-bold text-center py-4">Loading Failed…Logged Out（ログアウト中）かもしれません</p>
                ) : (
                  <div className="space-y-10">
                    {Object.keys(groupedLogs).sort().reverse().map(month => (
                      <div key={month} className="space-y-4">
                        <div className="flex items-center gap-4">
                          <div className="px-4 py-1.5 bg-gray-900 text-white text-[12px] font-black rounded-xl border border-gray-900 tracking-tight shadow-sm">{month}</div>
                          <div className="flex-1 h-px bg-gray-100"></div>
                        </div>
                        <div className="space-y-4 pl-1">
                          {groupedLogs[month].map((log: any) => {
                            const date = new Date(log.created_at.endsWith('Z') ? log.created_at : log.created_at + 'Z');
                            const moodMap: any = { 
                              motivated: '🔥', excited: '🤩', happy: '😊', calm: '😌', 
                              neutral: '😶', anxious: '💭', tired: '😩', sad: '😭', 
                              angry: '😡', grateful: '🙏',
                              MOTIVATED: '🔥', EXCITED: '🤩', HAPPY: '😊', CALM: '😌',
                              NEUTRAL: '😶', ANXIOUS: '💭', TIRED: '😩', SAD: '😭',
                              ANGRY: '😡', GRATEFUL: '🙏'
                            };
                            return (
                              <div key={log.id} className="flex items-center gap-5 text-sm">
                                <div className="flex items-center gap-1 w-24 flex-shrink-0">
                                  <span className="text-[12px] font-black text-gray-800 tabular-nums">{String(date.getDate()).padStart(2, '0')}</span>
                                  <span className="text-[10px] font-bold text-gray-400 tabular-nums flex items-center gap-1 opacity-80"><Clock size={10} strokeWidth={3} />{date.getHours()}:{String(date.getMinutes()).padStart(2, '0')}</span>
                                </div>
                                <span className="text-xl transform hover:scale-125 transition-transform cursor-default">
                                  {moodMap[log.mood_type] || '✨'}
                                </span>
                                <p className="text-gray-500 font-semibold flex-1">{log.comment}</p>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}

          {/* 非公開時に他のユーザーへ表示するメッセージ */}
          {!isMe && (
            <div className="bg-gray-50 rounded-[32px] p-8 text-center text-gray-400 text-sm">
              <EyeOff size={32} className="mx-auto mb-3 opacity-30" />
              <p className="font-bold">プロフィールのみ公開にしています</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default UserProfile;
