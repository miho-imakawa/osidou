import React, { useState, useEffect } from 'react';
import { useParams, Link, useLocation } from 'react-router-dom';
import { 
  User, Globe, Twitter, Facebook, Instagram, BookOpen,
  Edit, MessageSquare, Heart, Download, Save, X, Eye, EyeOff, AtSign, MapPin, Clock, Flame, Calendar
} from 'lucide-react';
import { 
  authApi, 
  fetchMyCommunities,
  HobbyCategory, 
  fetchMyMoodHistory, 
  MoodLog,
  startFeelingLogCheckout, startFriendsLogCheckout, verifyFriendsLogSession, 
} from '../api';
import PendingFriendBanner from './PendingFriendBanner'; // 💡 パスは環境に合わせて調整してください

interface UserProfileProps {
  profile: any; 
  fetchProfile: () => void;
}

const BACKEND_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

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

  const [friendsLogUnlocked, setFriendsLogUnlocked] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [friendsLogExpires, setFriendsLogExpires] = useState<string | null>(null);

  // 💡 State を追加
const [pendingCount, setPendingCount] = useState(0);

// 1. まず executeDownload 関数をコンポーネント内に定義
const executeDownload = async (sessionId: string) => {
  try {
    setIsDownloading(true);
    const response = await fetch(
      `https://osidou-production.up.railway.app/api/stripe/feeling-log-checkout`
    );

    if (!response.ok) throw new Error('ダウンロードに失敗しました');

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `my_feeling_log_${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
    
    // URLからsession_idを消す（何度もDLされないようにするため）
    window.history.replaceState({}, '', window.location.pathname);
    alert("ダウンロードが完了しました！");
  } catch (error) {
    console.error("Download error:", error);
    alert("ダウンロード中にエラーが発生しました。");
  } finally {
    setIsDownloading(false);
  }
};

// 2. URLを監視して自動実行する useEffect
useEffect(() => {
  const query = new URLSearchParams(location.search);
  const sessionId = query.get('session_id');

  // URLに session_id が含まれていて、かつ現在ダウンロード中でなければ実行
  if (sessionId && !isDownloading) {
    executeDownload(sessionId);
  }
}, [location.search]);

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

// handleFeelingLogDownload の実装例
const handleFeelingLogDownload = async (profileId: string | number) => {
  try {
    setIsDownloading(true);

    // 1. Stripe Checkout セッションを作成
    const response = await fetch(`https://osidou-production.up.railway.app/api/stripe/feeling-log-checkout`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        userId: profileId,
        // 成功時の戻り先を「ダウンロード実行用URL」にする
      successUrl: window.location.origin + window.location.pathname + '?session_id={CHECKOUT_SESSION_ID}',
        cancelUrl: window.location.href 
      })
    });

    const data = await response.json();
    if (data.url) {
      // 2. Stripeの決済ページへリダイレクト
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
    if (!displayProfile?.id) return;

    const loadData = async () => {
      try {
        const categories = await fetchMyCommunities();
        setMyCategories(categories); 

        const [joinedRes, hostedRes] = await Promise.all([
          authApi.get('/posts/my-meetups'),
          authApi.get('/posts/my-hosted-meetups')
        ]);

        const joined = joinedRes.data || [];
        const hosted = hostedRes.data || [];
        
        const allMeetups = [...hosted];
        joined.forEach((m: any) => {
          if (!allMeetups.find((existing: any) => existing.id === m.id)) {
            allMeetups.push(m);
          }
        });

        console.log("主催:", hosted.length, "参加:", joined.length, "合計:", allMeetups.length);
        const futureMeetups = allMeetups.filter((m: any) => 
          !m.meetup_date || new Date(m.meetup_date) > new Date()
        );
        setMyMeetups(futureMeetups);

        const logs = await fetchMyMoodHistory();
        setMoodLogs(logs);
      } catch (err) {
        console.error("データ取得失敗:", err);
      }
    };

    loadData();
  }, [displayProfile?.id, isMe, location.pathname]);

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
      alert("プロフィールを更新しました！");
    } catch (err) { alert("更新に失敗しました。"); }
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
    <div className="max-w-4xl mx-auto p-6 space-y-6">
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
            <div className="space-y-6">
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

            <div className="space-y-6">
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

              <div className="pt-4 border-t border-gray-50">
                <label className="flex items-center gap-3 cursor-pointer group">
                  <input type="checkbox" className="hidden" checked={tempProfile.is_mood_visible} onChange={e => setTempProfile({...tempProfile, is_mood_visible: e.target.checked})} />
                  <div className={`p-2 rounded-xl transition-all ${tempProfile.is_mood_visible ? 'bg-pink-100 text-pink-600' : 'bg-gray-100 text-gray-400'}`}>
                    {tempProfile.is_mood_visible ? <Eye size={18}/> : <EyeOff size={18}/>}
                  </div>
                  <span className="text-xs font-bold text-gray-500">Feeling Logs を表示する</span>
                </label>
              </div>

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
            </div>
          </div>
          <button onClick={handleSave} className="w-full py-5 bg-gray-900 text-white rounded-[24px] font-bold flex items-center justify-center gap-3 hover:bg-black transition-all shadow-xl active:scale-[0.98]">
            <Save size={20} /> プロフィールを保存
          </button>
        </div>
      ) : (
        /* VIEW MODE */
        <div className="space-y-6">
          {/* SNS Links & Bio */}
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
                  <MapPin size={12} /> {displayProfile.prefecture} {displayProfile.city} {displayProfile.town}
                </div>
              )}
            </div>
          </div>
          {/* 🔔 自分の時だけ表示される申請バナー */}
          {isMe && <PendingFriendBanner count={pendingCount} />}

          {/* Communities */}
          <div className="bg-white p-6 rounded-[32px] shadow-sm border border-gray-100 space-y-4">
            <h2 className="font-bold flex items-center gap-2 text-gray-400 uppercase tracking-widest text-[10px]">
              <MessageSquare className="text-pink-600" size={14}/> Communities
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
              }) : <p className="text-gray-300 text-[10px] font-bold uppercase tracking-widest">No Feeling posts</p>}
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

          {/* MY ADS STATS */}
          {isMe && myAdsStats.length > 0 && (
              <div className="bg-white p-4 rounded-[24px] shadow-sm border border-gray-100 space-y-3">
                  <h2 className="font-bold flex items-center gap-2 text-gray-400 uppercase tracking-widest text-[9px]">
                      <span className="text-green-500">📢</span> My AD Stats
                  </h2>
                  <div className="flex flex-wrap gap-2">
                      {myAdsStats.map(ad => (
                      <div key={ad.id} className="flex items-center gap-3 px-4 py-1.5 bg-green-50 border border-green-200 rounded-full hover:bg-green-100 transition-all">
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
                      </div>
                      ))}
                  </div>
              </div>
          )}
          {/* Feeling Logs */}
          {displayProfile.is_mood_visible && (
            <div className="bg-white p-6 rounded-[32px] shadow-sm border border-gray-100 space-y-2">
              <div className="flex justify-between items-center border-b border-gray-50 pb-2 mb-2">
                <h2 className="font-bold flex items-center gap-2 text-gray-400 uppercase tracking-widest text-[10px]">
                  <Heart className="text-pink-600" size={14}/> Feeling Logs
                </h2>
                <button 
                  // 1. ダウンロード中はボタンを押せなくする
                  disabled={isDownloading} 
                  // 2. ダウンロード中のスタイル（半透明・禁止マーク）を適用
                  className={`flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 text-blue-600 rounded-xl text-xs font-bold hover:bg-blue-100 transition-colors shadow-sm ${
                    isDownloading ? 'opacity-50 cursor-not-allowed' : ''
                  }`}
                  onClick={() => handleFeelingLogDownload(displayProfile.id)}
                >
                  <Download size={14} /> <span>🤝DL¥200</span>
                </button>
              </div>
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
                        const moodMap: any = { motivated: '🔥', excited: '🤩', happy: '😊', calm: '😌', neutral: '😐', anxious: '😟', tired: '😥', sad: '😭', angry: '😠', grateful: '🙏' };
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
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default UserProfile;