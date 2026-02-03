import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { authApi, HobbyCategory } from '../api.ts';
import { ChevronRight, ArrowLeft, Users, UserPlus, LogOut, User, Flame } from 'lucide-react'; // 💡 User, Flameを追加
import CommunityChat from './CommunityChat.tsx';

const CommunityDetail: React.FC = () => {
    const { categoryId } = useParams<{ categoryId: string }>();
    const [category, setCategory] = useState<HobbyCategory | null>(null);
    const [loading, setLoading] = useState(true);
    const [isJoined, setIsJoined] = useState(false);

    // 🎨 熱量（人数）に応じた色判定ロジック（一覧画面と統一）
    const getHeatStyles = (count: number) => {
        if (count >= 1000) return "bg-orange-50 text-orange-700 border-orange-200";
        if (count >= 500) return "bg-pink-50 text-pink-700 border-pink-200 animate-pulse";
        if (count >= 1) return "bg-pink-50 text-pink-600 border-pink-100";
        return "bg-gray-50 text-gray-400 border-gray-100";
    };

    useEffect(() => {
        const fetchDetail = async () => {
            try {
                const response = await authApi.get(`/hobby-categories/categories/${categoryId}`);
                setCategory(response.data);
                
                const joinStatus = await authApi.get(`/hobby-categories/check-join/${categoryId}`);
                setIsJoined(joinStatus.data.is_joined);
            } catch (err) {
                console.error("データの取得に失敗しました");
            } finally {
                setLoading(false);
            }
        };
        fetchDetail();
    }, [categoryId]);

    const handleJoin = async () => {
        try {
            await authApi.post(`/hobby-categories/join/${categoryId}`);
            setIsJoined(true);
            // 💡 参加後に人数を再取得して反映させるとより親切です
            const response = await authApi.get(`/hobby-categories/categories/${categoryId}`);
            setCategory(response.data);
        } catch (err) {
            alert("参加処理に失敗しました。");
        }
    };

    const handleLeave = async () => {
        if (!window.confirm("退会しますか？")) return;
        try {
            await authApi.delete(`/hobby-categories/leave/${categoryId}`);
            window.location.href = "/profile"; 
        } catch (err) {
            alert("退会処理に失敗しました。");
        }
    };
    
    if (loading) return <div className="p-8 text-center text-gray-400 italic">Exploring the community...</div>;
    if (!category) return <div className="p-8 text-center text-red-400 font-bold">Category not found</div>;

    const totalCount = category.member_count || 0;
    const heatStyle = getHeatStyles(totalCount);

return (
        <div className="max-w-4xl mx-auto p-4 md:p-6">
            {/* 🏰 シンプルヘッダー：名前と数。それ以外は何も置かない */}
            <div className="flex items-center gap-4 mb-8">
                <Link to="/community" className="p-2 hover:bg-gray-100 rounded-full transition-colors text-gray-400">
                    <ArrowLeft size={20} />
                </Link>
                <h1 className="text-2xl font-bold text-gray-900 tracking-tight">{category.name}</h1>
                
                {/* 📊 熱量バッジ：アイコン+数字のみ */}
                <div className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold border ${heatStyle}`}>
                    <Users size={12} className="opacity-60" />
                    <span className="tabular-nums">{totalCount.toLocaleString()}</span>
                </div>

                {isJoined && (
                    <div className="flex items-center gap-1 text-[9px] font-black text-green-500 uppercase tracking-widest bg-green-50 px-2 py-0.5 rounded-md border border-green-100">
                        Active
                    </div>
                )}
            </div>

            {/* 👥 子カテゴリ：大量になっても「2行」で食い止める設定 */}
            {category.children && category.children.length > 0 && (
                <div className="mb-4"> {/* 下のチャットとの隙間を mb-4 (16px) に設定 */}
                    <div className="flex flex-wrap gap-1.5 max-h-[80px] overflow-y-auto pr-2 custom-scrollbar"> 
                        {/* 💡 gap-1.5 (6px) で横の隙間も最小限に。max-h で高さに上限を設け、掲示板が沈むのを防ぐ */}
                        {category.children.map(child => (
                            <Link 
                                key={child.id} 
                                to={`/community/${child.id}`} 
                                className="px-2.5 py-1 bg-gray-50 hover:bg-pink-50 rounded-md border border-gray-100 flex items-center gap-2 transition-all group"
                            >
                                <span className="text-[11px] font-bold text-gray-500 group-hover:text-pink-600 truncate max-w-[100px]">
                                    {child.name}
                                </span>
                                <span className="text-[9px] text-gray-300 font-mono">
                                    {child.member_count || 0}
                                </span>
                            </Link>
                        ))}
                    </div>
                </div>
            )}

            {/* 💬 メイン：掲示板。ノイズを排除し、会話を主役に */}
            <div className="min-h-[600px] border-t border-gray-100 pt-6">
                {!isJoined ? (
                    <div className="flex flex-col items-center justify-center h-[500px] text-center bg-gray-50/30 rounded-[40px] border border-gray-100">
                        <Users className="text-gray-200 mb-6" size={48} />
                        <p className="text-gray-400 text-sm mb-8 font-medium">参加して会話を見る</p>
                        <button 
                            onClick={handleJoin} 
                            className="bg-gray-900 text-white px-10 py-4 rounded-full font-bold hover:bg-pink-600 transition-all shadow-xl hover:shadow-pink-100"
                        >
                            JOIN
                        </button>
                    </div>
                ) : (
                    <div className="relative">
                        {/* 🚪 退会は一番右上の目立たない場所に小さく */}
                        <div className="absolute -top-12 right-0">
                            <button 
                                onClick={handleLeave}
                                className="text-[9px] font-bold text-gray-300 hover:text-red-400 uppercase tracking-[0.2em] transition-colors"
                            >
                                Leave
                            </button>
                        </div>
                        <div className="bg-white rounded-[32px] overflow-hidden">
                            <CommunityChat 
                                categoryId={categoryId!} 
                                masterId={category.master_id} 
                            />
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default CommunityDetail;