import React, { useState, useEffect, useCallback } from 'react';
// 💡 ポイント1: Linkの宣言を1か所にまとめ、Edit3を追加
import { Link, useParams, useNavigate } from 'react-router-dom';
import { authApi, HobbyCategory } from '../api.ts';
import { ArrowLeft, Users, Edit3 } from 'lucide-react'; 
import CommunityChat from './CommunityChat.tsx';

const CommunityDetail: React.FC = () => {
    const { categoryId } = useParams<{ categoryId: string }>();
    const [category, setCategory] = useState<HobbyCategory | null>(null);
    const [loading, setLoading] = useState(true);
    const [isJoined, setIsJoined] = useState(false);
    const [currentUserId, setCurrentUserId] = useState<number>(0);
    // 💡 ポイント2: detailデータの有無を管理するステートを追加
    const [detail, setDetail] = useState<any>(null);

    const getHeatStyles = (count: number) => {
        if (count >= 1000) return "bg-orange-50 text-orange-700 border-orange-200";
        if (count >= 500) return "bg-pink-50 text-pink-700 border-pink-200 animate-pulse";
        if (count >= 1) return "bg-pink-50 text-pink-600 border-pink-100";
        return "bg-gray-50 text-gray-400 border-gray-100";
    };

    const fetchDetail = useCallback(async () => {
        if (!categoryId) return;
        try {
            const response = await authApi.get(`/hobby-categories/categories/${categoryId}`);
            const categoryData = response.data;
            setCategory(categoryData);
            
            // 💡 ポイント3: detailを取得してステートに入れる
            const detailRes = await authApi.get(`/hobby-categories/categories/${categoryId}/detail`);
            setDetail(detailRes.data);

            const targetId = categoryData.master_id || categoryId;
            const joinStatus = await authApi.get(`/hobby-categories/check-join/${targetId}`);
            setIsJoined(joinStatus.data.is_joined);

            const me = await authApi.get('/users/me');
            setCurrentUserId(me.data.id);
        } catch (err) {
            console.error("データの取得に失敗しました");
            setDetail(null);
        } finally {
            setLoading(false);
        }
    }, [categoryId]);

    useEffect(() => {
        setLoading(true);
        fetchDetail();
    }, [fetchDetail]);

    const handleJoin = async () => {
        try {
            await authApi.post(`/hobby-categories/categories/${categoryId}/join`);
            setIsJoined(true);
            fetchDetail();
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
    
    if (loading) return <div className="p-8 text-center text-gray-400 italic">Exploring...</div>;
    if (!category) return <div className="p-8 text-center text-red-400 font-bold">Category not found</div>;

    const totalCount = category.member_count || 0;
    const heatStyle = getHeatStyles(totalCount);

    return (
        <div className="max-w-4xl mx-auto p-4 md:p-6 text-left">
            {/* ヘッダー */}
            <div className="flex items-center gap-4 mb-8">
                <button onClick={() => window.history.back()} className="p-2 hover:bg-gray-100 rounded-full transition-colors text-gray-400">
                    <ArrowLeft size={20} />
                </button>
                <h1 className="text-2xl font-bold text-gray-900 tracking-tight">{category.name}</h1>
                <div className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold border ${heatStyle}`}>
                    <Users size={12} className="opacity-60" />
                    <span>{totalCount.toLocaleString()}</span>
                </div>
                {isJoined && (
                    <div className="text-[9px] font-black text-green-500 uppercase tracking-widest bg-green-50 px-2 py-0.5 rounded-md border border-green-100">
                        Active
                    </div>
                )}
            </div>

            {/* 💡 ポイント4: DETAIL、子要素、そして【出演作品】をチップとして並べる */}
            <div className="mb-8 flex flex-wrap gap-2">
                {/* 1. DETAILボタン */}
                <Link 
                    to={`/community/${categoryId}/detail`} 
                    className={`px-3 py-1.5 rounded-md border flex items-center gap-2 transition-all shadow-sm
                        ${detail ? "bg-blue-50 border-blue-100 hover:bg-blue-100" : "bg-gray-50 border-gray-100 hover:bg-gray-200"}`}
                >
                    <Edit3 size={12} className={detail ? "text-blue-500" : "text-gray-400"} />
                    <span className={`text-[11px] font-black uppercase tracking-wider ${detail ? "text-blue-700" : "text-gray-500"}`}>
                        Detail
                    </span>
                </Link>

                {/* 2. 子カテゴリ（映画作品など） */}
                {category.children?.map(child => (
                    <Link 
                        key={child.id} 
                        to={`/community/${child.id}`} 
                        className="px-3 py-1.5 bg-gray-50 hover:bg-pink-50 rounded-md border border-gray-100 flex items-center gap-2 transition-all shadow-sm"
                    >
                        <span className="text-[11px] font-bold text-gray-500">{child.name}</span>
                        <span className="text-[9px] text-gray-300 font-mono">{child.member_count || 0}</span>
                    </Link>
                ))}

                {/* 3. 💡 新規：【出演作品】のチップを表示 */}
                {detail?.appearances?.map((work: any) => (
                    <Link 
                        key={work.id} 
                        to={`/community/${work.id}`} 
                        className="px-3 py-1.5 bg-orange-50 hover:bg-orange-100 rounded-md border border-orange-100 flex items-center gap-2 transition-all shadow-sm"
                    >
                        <span className="text-[10px]">🎬</span>
                        <span className="text-[11px] font-bold text-orange-700">{work.name}</span>
                    </Link>
                ))}
            </div>

            {/* チャットエリア */}
            <div className="min-h-[600px] border-t border-gray-100 pt-6">
                {!isJoined ? (
                    <div className="flex flex-col items-center justify-center h-[500px] bg-gray-50/30 rounded-[40px] border border-gray-100">
                        <p className="text-gray-400 text-sm mb-8">参加して会話を見る</p>
                        <button onClick={handleJoin} className="bg-gray-900 text-white px-10 py-4 rounded-full font-bold">JOIN</button>
                    </div>
                ) : (
                    <div className="relative">
                        {/* 右上はLEAVEのみにしてスッキリ */}
                        <div className="absolute -top-12 right-0">
                            <button onClick={handleLeave} className="text-[9px] font-bold text-gray-300 hover:text-red-400 uppercase tracking-widest">
                                Leave
                            </button>
                        </div>
                        <div className="bg-white rounded-[32px] overflow-hidden border border-gray-100">
                            <CommunityChat 
                                categoryId={categoryId!} 
                                masterId={category.master_id} 
                                currentUserId={currentUserId}
                            />
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default CommunityDetail;