import React, { useState, useEffect } from 'react';
import { ExternalLink, Edit3, Save, Music, Film, Tv, Youtube, User, Users, Tag } from 'lucide-react';
import { authApi } from '../api';

// --- 型定義 ---
interface CastMember {
  name: string;
  role?: string;
  master_id?: number;
}

interface CommunityDetailTemplateProps {
categoryId: number;
  categoryName: string;
  categoryType: 'music_group' | 'movie' | 'tv' | 'youtube' | 'person' | 'other';
  description?: string;
  alias?: string; // ✅ Alias（別名）を追加
  cast?: CastMember[];
  memberCount?: number;
  onSave?: (data: any) => void;
  onNavigateToPeople?: (masterId: number) => void;
}

// --- ヘルパー: カテゴリアイコン ---
const CategoryIcon = ({ type }: { type: string }) => {
  switch (type) {
    case 'music_group': return <Music size={16} className="text-pink-500" />;
    case 'movie': return <Film size={16} className="text-blue-500" />;
    case 'tv': return <Tv size={16} className="text-purple-500" />;
    case 'youtube': return <Youtube size={16} className="text-red-500" />;
    case 'person': return <User size={16} className="text-green-500" />;
    default: return <Users size={16} className="text-gray-400" />;
  }
};

// --- メインコンポーネント ---
const CommunityDetailTemplate: React.FC<CommunityDetailTemplateProps> = ({
  categoryName,
  categoryType,
  description: initialDescription = '',
  alias: initialAlias = '',
  cast: initialCast = [],
  memberCount = 0,
  onSave,
  onNavigateToPeople,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [description, setDescription] = useState(initialDescription);
  const [alias, setAlias] = useState(initialAlias);
  const [cast, setCast] = useState<CastMember[]>(initialCast);
  const [newCastName, setNewCastName] = useState('');
  const [newCastRole, setNewCastRole] = useState('');
  const [castSuggestions, setCastSuggestions] = useState<any[]>([]);
  const [pendingMasterId, setPendingMasterId] = useState<number | null>(null);

  // ✅ Aliasの初期サンプル設定
  const ALIAS_SAMPLE = "例: ニックネーム, 苗字, alphabet_name (カンマ区切り)";

    const handleAddCast = () => {
    if (!newCastName.trim()) return;
    setCast([...cast, { name: newCastName.trim(), role: newCastRole.trim() || undefined, master_id: pendingMasterId || undefined }]);
    setNewCastName('');
    setNewCastRole('');
    setPendingMasterId(null);
    setCastSuggestions([]);
    };

  const handleSave = () => {
    // 💡 保存時にサンプル文字が含まれていたら空にする処理
    const finalAlias = alias === ALIAS_SAMPLE ? '' : alias;
    onSave?.({ description, alias: finalAlias, cast, sections: [] });
    setIsEditing(false);
  };

  return (
    <div className="bg-white rounded-[32px] border border-gray-100 shadow-sm overflow-hidden">
      
      {/* ヘッダー */}
      <div className="px-6 py-4 border-b border-gray-50 flex justify-between items-center">
        <div className="flex items-center gap-2">
          <CategoryIcon type={categoryType} />
          <h2 className="text-sm font-black text-gray-800 tracking-tight">{categoryName}</h2>
          {memberCount > 0 && (
            <div className="flex items-center gap-1 px-2 py-0.5 bg-pink-50 rounded-full border border-pink-100">
              <Users size={10} className="text-pink-400" />
              <span className="text-[10px] font-bold text-pink-600">{memberCount}</span>
            </div>
          )}
        </div>
        
        <div className="flex gap-2">
          {isEditing ? (
            <>
              <button onClick={handleSave} className="flex items-center gap-1 px-3 py-1.5 bg-gray-900 text-white rounded-full text-[10px] font-black">
                <Save size={11} /> SAVE
              </button>
              <button onClick={() => setIsEditing(false)} className="flex items-center gap-1 px-3 py-1.5 bg-gray-100 text-gray-500 rounded-full text-[10px] font-black">
                CANCEL
              </button>
            </>
          ) : (
            <button onClick={() => setIsEditing(true)} className="flex items-center gap-1 px-3 py-1.5 bg-gray-100 text-gray-500 rounded-full text-[10px] font-black hover:bg-gray-200">
              <Edit3 size={11} /> EDIT
            </button>
          )}
        </div>
      </div>

      <div className="p-6 space-y-8">
        {/* 1. ALIAS (名寄せ用：新設) */}
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <Tag size={10} className="text-gray-300" />
            <p className="text-[9px] font-black text-gray-300 uppercase tracking-widest">Search Alias / 別名</p>
          </div>
          {isEditing ? (
            <input 
              value={alias || ALIAS_SAMPLE} 
              onChange={e => setAlias(e.target.value)}
              onFocus={() => alias === '' && setAlias('')}
              className={`w-full px-3 py-2 bg-orange-50/50 rounded-xl text-[11px] outline-none border border-transparent focus:border-orange-200 ${alias === ALIAS_SAMPLE ? 'text-gray-300 italic' : 'text-orange-700 font-bold'}`}
            />
          ) : (
            <div className="flex flex-wrap gap-1">
              {alias ? alias.split(',').map((a, i) => (
                <span key={i} className="px-2 py-0.5 bg-gray-50 text-gray-400 rounded text-[10px] border border-gray-100">#{a.trim()}</span>
              )) : <span className="text-[10px] text-gray-200 italic">No alias set.</span>}
            </div>
          )}
        </div>

        {/* 2. CAST */}
        <div>
          <p className="text-[9px] font-black text-gray-300 uppercase tracking-widest mb-3">Cast / Related People</p>
          <div className="flex flex-wrap gap-2">
            {cast.map((member, i) => (
              <div key={i} className="relative group">
                {/* 既存のCastChipを使用 */}
                <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-[11px] font-bold ${member.master_id ? 'bg-orange-50 border-orange-200 text-orange-800' : 'bg-gray-50 border-gray-200 text-gray-600'}`}>
                  <span>{member.name}</span>
                </div>
                {isEditing && (
                  <button onClick={() => setCast(cast.filter((_, idx) => idx !== i))} className="absolute -top-1 -right-1 w-4 h-4 bg-red-400 text-white rounded-full text-[8px] flex items-center justify-center">×</button>
                )}
              </div>
            ))}
          </div>
            {isEditing && (
            <div className="mt-4 space-y-2">
                <div className="flex gap-2">
                <div className="flex-1 relative">
                    <input
                    value={newCastName}
                    onChange={async e => {
                        setNewCastName(e.target.value);
                        if (e.target.value.length >= 2) {
                        try {
                        const res = await authApi.get(`/hobby-categories/search?keyword=${encodeURIComponent(e.target.value)}`);
                        const data = res.data;
                        setCastSuggestions(data.slice(0, 8));
                        } catch { setCastSuggestions([]); }
                        } else {
                        setCastSuggestions([]);
                        }
                    }}
                    placeholder="Name"
                    className="w-full px-3 py-1.5 bg-gray-50 rounded-xl text-[12px] outline-none"
                    />
                    {/* サジェスト候補 */}
                    {castSuggestions.length > 0 && (
                    <div className="absolute top-full left-0 right-0 bg-white border border-gray-100 rounded-xl shadow-lg z-10 mt-1 overflow-hidden">
                        {castSuggestions.map(s => (
                        <button
                            key={s.id}
                            type="button"
                            onClick={() => {
                            setNewCastName(s.name);
                            setPendingMasterId(s.id);
                            setCastSuggestions([]);
                            }}
                            className="w-full px-3 py-2 text-left text-[11px] hover:bg-orange-50 flex items-center gap-2"
                        >
                            <User size={10} className="text-gray-300" />
                            <span className="font-bold text-gray-700">{s.name}</span>
                        </button>
                        ))}
                    </div>
                    )}
                </div>
                <input
                    value={newCastRole}
                    onChange={e => setNewCastRole(e.target.value)}
                    placeholder="Role"
                    className="w-24 px-3 py-1.5 bg-gray-50 rounded-xl text-[12px] outline-none"
                />
                <button type="button" onClick={handleAddCast} className="px-4 py-1.5 bg-orange-500 text-white rounded-xl text-[11px] font-black">Add</button>
                </div>

                {/* 本尊確認ダイアログ */}
                {pendingMasterId && (
                <div className="p-3 bg-orange-50 rounded-xl border border-orange-200 text-[11px]">
                    <p className="font-black text-orange-800 mb-2">「{newCastName}」はChatページと同一人物ですか？</p>
                    <div className="flex gap-2">
                    <button
                        type="button"
                        onClick={() => setPendingMasterId(null)}
                        className="px-3 py-1 bg-white border border-gray-200 rounded-lg text-gray-500 font-bold"
                    >
                        別人
                    </button>
                    <button
                        type="button"
                        onClick={() => {
                        setCast([...cast, { name: newCastName.trim(), role: newCastRole.trim() || undefined, master_id: pendingMasterId }]);
                        setNewCastName('');
                        setNewCastRole('');
                        setPendingMasterId(null);
                        }}
                        className="px-3 py-1 bg-orange-500 text-white rounded-lg font-bold"
                    >
                        同一人物としてリンク
                    </button>
                    </div>
                </div>
                )}
            </div>
            )}
        </div>

        <hr className="border-gray-50" />

        {/* 3. NOTES */}
        <div>
          <p className="text-[9px] font-black text-gray-300 uppercase tracking-widest mb-2">My Notes / About</p>
          {isEditing ? (
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Memo..."
              className="w-full p-3 bg-gray-50 rounded-2xl text-[12px] text-gray-700 h-[100px] outline-none resize-none focus:border-orange-100 border-2 border-transparent"
            />
          ) : (
            <p className="text-[12px] text-gray-600 leading-relaxed whitespace-pre-wrap">{description || <span className="text-gray-200 italic">No notes yet.</span>}</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default CommunityDetailTemplate;