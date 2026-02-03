import React, { useState, useEffect } from 'react';
import { authApi, HobbyCategory } from '../api.ts';
import { Search, ChevronRight, Users, MapPin, Music2, Trophy, User, AlertCircle, Flame } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';

const CommunityList: React.FC = () => {
    const navigate = useNavigate();
    const [categories, setCategories] = useState<HobbyCategory[]>([]);
    const [searchQuery, setSearchQuery] = useState('');
    const [loading, setLoading] = useState(true);
    const [isChecking, setIsChecking] = useState(false);
    const [duplicateInfo, setDuplicateInfo] = useState<any>(null);

    // 🎨 熱量（人数）に応じた色判定ロジック
    const getHeatStyles = (count: number) => {
        if (count >= 10000) return "bg-yellow-50 text-yellow-700 border-yellow-200 ring-yellow-400"; // ゴールド
        if (count >= 5000) return "bg-slate-50 text-slate-700 border-slate-200 ring-slate-400";   // シルバー
        if (count >= 1000) return "bg-orange-50 text-orange-700 border-orange-200 ring-orange-400"; // ブロンズ
        if (count >= 500) return "bg-pink-50 text-pink-700 border-pink-200 ring-pink-400 animate-pulse"; // ピンク（熱狂！）
        return "bg-gray-50 text-gray-600 border-gray-100 ring-transparent"; // 通常
    };

    const fetchCategories = async (query: string = '') => {
        setLoading(true);
        try {
            let response;
            if (query.trim()) {
                response = await authApi.get(`/hobby-categories/search?keyword=${encodeURIComponent(query)}`);
            } else {
                response = await authApi.get('/hobby-categories');
            }
            setCategories(response.data);
        } catch (err) {
            console.error("カテゴリの取得に失敗しました");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        const timer = setTimeout(() => {
            fetchCategories(searchQuery);
        }, 500);
        return () => clearTimeout(timer);
    }, [searchQuery]);

    // 重複している本尊（master_id）を1つにまとめるロジック
    const filteredCategories = categories.filter((cat, index, self) => {
        const masterId = cat.master_id || cat.id;
        return index === self.findIndex((t) => (t.master_id || t.id) === masterId);
    });

    const handleCreateNew = async () => {
        if (!searchQuery) return;
        setIsChecking(true);
        try {
            const response = await authApi.get(`/hobby-categories/check-duplicate?name=${encodeURIComponent(searchQuery)}`);
            if (response.data.is_duplicate) {
                setDuplicateInfo(response.data);
            } else {
                navigate(`/community/create?name=${encodeURIComponent(searchQuery)}`);
            }
        } catch (err) {
            console.error("重複チェックに失敗しました");
        } finally {
            setIsChecking(false);
        }
    };

    const getIcon = (name: string) => {
        const n = name.toUpperCase();
        if (n.includes('MUSIC')) return <Music2 className="text-purple-500" />;
        if (n.includes('REGIONS')) return <MapPin className="text-green-500" />;
        if (n.includes('SPORT')) return <Trophy className="text-orange-500" />;
        return <Users className="text-pink-500" />;
    };

    return (
        <div className="max-w-4xl mx-auto p-4 md:p-8 relative">
            <h1 className="text-3xl font-bold text-gray-900 mb-8 flex items-center gap-3">
                <Users size={32} className="text-pink-600" />
                Community Exploration
            </h1>

            <div className="relative mb-8">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" size={20} />
                <input
                    type="text"
                    placeholder="コミュニティを検索..."
                    className="w-full pl-12 pr-4 py-4 bg-white border-2 border-gray-100 rounded-2xl focus:border-pink-300 focus:outline-none shadow-sm transition-all"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                />
            </div>

{loading ? (
                <div className="flex flex-col items-center py-12">
                    <div className="animate-spin h-8 w-8 border-4 border-pink-500 border-t-transparent rounded-full mb-4"></div>
                    <p className="text-gray-500 italic">街の全域を探索中...</p>
                </div>
            ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {/* 💡 修正後：0人の時はグレー、500人からピンクになる本来の姿 */}
                    {filteredCategories.map(cat => {
                        const count = cat.member_count || 0;
                        
                        const getHeatStylesReal = (c: number) => {
                            if (c >= 10000) return "bg-yellow-50 text-yellow-700 border-yellow-400";
                            if (c >= 5000)  return "bg-slate-50 text-slate-700 border-slate-300";
                            if (c >= 1000)  return "bg-orange-50 text-orange-700 border-orange-200";
                            if (c >= 500)   return "bg-pink-50 text-pink-700 border-pink-200";
                            return "bg-gray-50 text-gray-500 border-gray-100"; // 0〜499人は落ち着いたグレー
                        };
                        
                        const heatStyle = getHeatStylesReal(count);

                        return (
                            <Link 
                                key={cat.id}
                                to={`/community/${cat.id}`}
                                className="group p-5 bg-white rounded-2xl border border-gray-100 hover:border-pink-200 transition-all flex items-center justify-between"
                            >
                                <div className="flex items-center gap-4">
                                    <div className="p-3 bg-gray-50 rounded-xl">
                                        {getIcon(cat.name)}
                                    </div>
                                    <div>
                                        <h3 className="font-bold text-gray-800">{cat.name}</h3>
                                        <div className="flex items-center gap-2 mt-1">
                                            <span className="text-[10px] font-mono text-gray-400 bg-gray-50 px-1.5 py-0.5 rounded border border-gray-100">
                                                ID: #{cat.unique_code || cat.id}
                                            </span>
                                            {/* 💡 点滅を消し、0人の時はグレーになるバッジ */}
                                            <div className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold border ${heatStyle}`}>
                                                <Users size={12} className="opacity-60" />
                                                <span className="tabular-nums">{count.toLocaleString()}</span>
                                                {count >= 500 && <Flame size={12} className="ml-0.5 text-orange-500" />}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                <ChevronRight className="text-gray-300 group-hover:text-pink-400" />
                            </Link>
                        );
                    })}
                </div>
            )}

            {!loading && searchQuery && filteredCategories.length === 0 && (
                <div className="text-center py-12 bg-gray-50 rounded-3xl border-2 border-dashed border-gray-200 mt-6 animate-in fade-in zoom-in duration-300">
                    <p className="text-gray-500 mb-6 italic">「{searchQuery}」は見つかりませんでした</p>
                    <button
                        onClick={handleCreateNew}
                        disabled={isChecking}
                        className="px-8 py-4 bg-white border-2 border-pink-200 text-pink-600 rounded-2xl font-bold hover:bg-pink-50 hover:border-pink-300 transition-all shadow-sm flex items-center gap-2 mx-auto"
                    >
                        {isChecking ? '確認中...' : `「${searchQuery}」を新しく作る`}
                    </button>
                </div>
            )}

            {duplicateInfo && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white rounded-3xl p-8 max-w-md w-full shadow-2xl">
                        <div className="flex items-center gap-3 text-pink-600 mb-4">
                            <AlertCircle size={32} />
                            <h2 className="text-2xl font-bold">おや？</h2>
                        </div>
                        <p className="text-gray-600 mb-6 leading-relaxed">
                            <strong>{duplicateInfo.parent_path}</strong> の下に、すでに <strong>{duplicateInfo.existing_name}</strong> が存在します。
                        </p>
                        <div className="flex flex-col gap-3">
                            <Link 
                                to={`/community/${duplicateInfo.existing_id}`}
                                className="w-full py-4 bg-pink-600 text-white rounded-2xl font-bold text-center hover:bg-pink-700 transition-all"
                                onClick={() => setDuplicateInfo(null)}
                            >
                                既存のコミュニティに合流する
                            </Link>
                            <button 
                                onClick={() => setDuplicateInfo(null)}
                                className="w-full py-4 bg-gray-100 text-gray-600 rounded-2xl font-bold hover:bg-gray-200"
                            >
                                キャンセル
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default CommunityList;