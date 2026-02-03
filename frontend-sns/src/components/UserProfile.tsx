import React, { useState, useEffect } from 'react';
import { useParams, Link, useLocation } from 'react-router-dom';
import { 
  User, Globe, Twitter, Facebook, Instagram, BookOpen,
  Edit, MessageSquare, Heart, Download, Save, X, Eye, EyeOff, AtSign, MapPin, Clock
} from 'lucide-react';

import { 
  authApi, 
  fetchMyCategories, 
  HobbyCategory, 
  fetchMyMoodHistory, 
  MoodLog 
} from '../api'; 

interface UserProfileProps {
  profile: any; 
  fetchProfile: () => void;
}

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
        const categories = await fetchMyCategories();
        const uniqueMap = new Map();
        categories.forEach(cat => {
          const key = cat.master_id || cat.id;
          if (!uniqueMap.has(key)) { uniqueMap.set(key, cat); }
        });
        setMyCategories(Array.from(uniqueMap.values()));
        const logs = await fetchMyMoodHistory();
        setMoodLogs(logs);
      } catch (err) { console.error(err); }
    };
    loadData();
  }, [displayProfile?.id, isMe, location.pathname]);

  const groupedLogs = moodLogs.reduce((acc: any, log) => {
    const date = new Date(log.created_at);
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

  if (loading) return <div className="text-center py-10">読み込み中...</div>;
  if (!displayProfile) return <div className="text-center py-10 text-gray-400">ユーザーが見つかりません。</div>;

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* 🏰 Header */}
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-3xl font-bold text-gray-800 flex items-center gap-3">
          <User className="text-pink-600" size={32} />
          {displayProfile.nickname || displayProfile.username} 's PAGE
        </h1>
        {isMe && (
          <button onClick={toggleEdit} className="px-5 py-2.5 bg-pink-600 text-white rounded-2xl flex items-center gap-2 transition-all hover:bg-pink-700 shadow-md font-bold active:scale-95">
            {isEditing ? <><X size={20}/> 戻る</> : <><Edit size={20}/> プロフィール編集</>}
          </button>
        )}
      </div>

      {isEditing && tempProfile ? (
        /* 🛠️ EDIT MODE */
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
                    <option value="male">男性</option>
                    <option value="female">女性</option>
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
                  <span className="text-xs font-bold text-gray-500">Activity Logs を表示する</span>
                </label>
              </div>
            </div>
          </div>
          <button onClick={handleSave} className="w-full py-5 bg-gray-900 text-white rounded-[24px] font-bold flex items-center justify-center gap-3 hover:bg-black transition-all shadow-xl active:scale-[0.98]"><Save size={20} /> プロフィールを保存</button>
        </div>
      ) : (
        /* 🏰 VIEW MODE */
        <div className="space-y-6">
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
                <div className="flex items-center gap-1.5 text-[10px] font-bold text-gray-300 uppercase tracking-widest border-t border-gray-50 pt-4"><MapPin size={12} /> {displayProfile.prefecture} {displayProfile.city} {displayProfile.town}</div>
              )}
            </div>
          </div>

          <div className="bg-white p-6 rounded-[32px] shadow-sm border border-gray-100 space-y-4">
            <h2 className="font-bold flex items-center gap-2 text-gray-400 uppercase tracking-widest text-[10px]"><MessageSquare className="text-pink-600" size={14}/> Communities</h2>
            <div className="flex flex-wrap gap-2">
              {myCategories.length > 0 ? myCategories.map(cat => (
                <Link key={cat.id} to={`/community/${cat.id}`} className={`px-4 py-1.5 rounded-full text-xs border flex items-center gap-3 font-bold shadow-sm transition-all hover:scale-105 ${getRankClasses(cat.member_count || 0)}`}>
                  <span>{cat.name}</span>
                  <div className="flex items-center gap-1 opacity-60 text-[10px] tabular-nums"><User size={10} strokeWidth={3} /><span>{(cat.member_count || 0).toLocaleString()}</span></div>
                </Link>
              )) : <p className="text-gray-400 text-xs italic">未参加</p>}
            </div>
          </div>

          {/* 💓 Activity Logs (顔の色を出し、月表示を大きく) */}
          {displayProfile.is_mood_visible && (
            <div className="bg-white p-6 rounded-[32px] shadow-sm border border-gray-100 space-y-2"> {/* space-y-6 から 2 に変更 */}
                <div className="flex justify-between items-center border-b border-gray-50 pb-2 mb-2"> {/* pb-4 mb-6 から変更 */}
                  <h2 className="font-bold flex items-center gap-2 text-gray-400 uppercase tracking-widest text-[10px]">
                    <Heart className="text-pink-600" size={14}/> Activity Logs
                  </h2>
                  <button className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 text-blue-600 rounded-xl text-xs font-bold hover:bg-blue-100 transition-colors shadow-sm" onClick={() => alert("DL準備中")}>
                          <Download size={14} /> <span>DL-200JPY</span>
                        </button>
                      </div>
              
            <div className="space-y-10"> {/* ここは月の間の余白なのでそのままか、お好みで調整 */}
                  {Object.keys(groupedLogs).sort().reverse().map(month => (
                    <div key={month} className="space-y-4">
                      <div className="flex items-center gap-4">
                        <div className="px-4 py-1.5 bg-gray-900 text-white text-[12px] font-black rounded-xl border border-gray-900 tracking-tight shadow-sm">{month}</div>
                        <div className="flex-1 h-px bg-gray-100"></div>
                      </div>
                    <div className="space-y-4 pl-1">
                      {groupedLogs[month].map((log: any) => {
                        const date = new Date(log.created_at);
                        const moodMap: any = { motivated: '🔥', excited: '🤩', happy: '😊', calm: '😌', neutral: '😐', anxious: '😟', tired: '😥', sad: '😭', angry: '😠', grateful: '🙏' };
                        return (
                          <div key={log.id} className="flex items-center gap-5 text-sm">
                            <div className="flex items-center gap-1 w-24 flex-shrink-0">
                              <span className="text-[12px] font-black text-gray-800 tabular-nums">{String(date.getDate()).padStart(2, '0')}</span>
                              <span className="text-[10px] font-bold text-gray-400 tabular-nums flex items-center gap-1 opacity-80"><Clock size={10} strokeWidth={3} />{date.getHours()}:{String(date.getMinutes()).padStart(2, '0')}</span>
                            </div>
                            {/* 💡 顔の色をグレースケール解除して可愛く */}
                            <span className="text-xl transform hover:scale-125 transition-transform cursor-default">
                              {moodMap[log.mood_type] || '✨'}
                            </span>
                            <p className="text-gray-500 font-semibold flex-1 truncate">{log.comment}</p>
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