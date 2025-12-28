import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { authApi, HobbyCategory } from '../api.ts';
import { ChevronRight, ArrowLeft, Users } from 'lucide-react';
import CommunityChat from './CommunityChat.tsx'; // 💡 追加

const CommunityDetail: React.FC = () => {
    const { categoryId } = useParams<{ categoryId: string }>();
    const [category, setCategory] = useState<HobbyCategory | null>(null);
    const [loading, setLoading] = useState(true);
    const [showChat, setShowChat] = useState(false); // 💡 追加

    useEffect(() => {
        const fetchDetail = async () => {
            try {
                const response = await authApi.get(`/hobby-categories/categories/${categoryId}`);
                setCategory(response.data);
            } catch (err) {
                console.error("詳細は取得できませんでした");
            } finally {
                setLoading(false);
            }
        };
        fetchDetail();
        setShowChat(false); // カテゴリが変わったらチャットを閉じる
    }, [categoryId]);

    if (loading) return <div className="p-8 text-center">読み込み中...</div>;
    if (!category) return <div className="p-8 text-center">カテゴリが見つかりません</div>;

    return (
        <div className="max-w-4xl mx-auto p-4 md:p-8">
            <Link to="/community" className="flex items-center gap-2 text-gray-500 hover:text-pink-600 mb-6 transition-colors">
                <ArrowLeft size={20} /> 一覧に戻る
            </Link>

            <div className="bg-white rounded-3xl p-8 shadow-sm border border-gray-100 mb-8">
                <h1 className="text-3xl font-bold text-gray-900 mb-2">{category.name}</h1>
                <p className="text-gray-500 flex items-center gap-2">
                    <span className="bg-gray-100 px-3 py-1 rounded-full text-sm font-mono">#{category.unique_code}</span>
                    {category.children.length > 0 && <span>{category.children.length} 個のサブカテゴリ</span>}
                </p>
            </div>

            {/* 子カテゴリがある場合 */}
            {category.children.length > 0 && (
                <>
                    <h2 className="text-xl font-bold text-gray-800 mb-4">もっと詳しく選ぶ</h2>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-8">
                        {category.children.map(child => (
                            <Link 
                                key={child.id}
                                to={`/community/${child.id}`}
                                className="p-4 bg-white rounded-2xl border border-gray-50 hover:border-pink-200 hover:shadow-sm transition-all flex justify-between items-center group"
                            >
                                <span className="font-medium text-gray-700 group-hover:text-pink-600">{child.name}</span>
                                <ChevronRight className="text-gray-300 group-hover:text-pink-400" />
                            </Link>
                        ))}
                    </div>
                </>
            )}

            {/* 子カテゴリがない（最深部）場合 */}
            {category.children.length === 0 && (
                <div className="mt-8">
                    {!showChat ? (
                        <div className="p-12 bg-pink-50 rounded-3xl text-center border-2 border-dashed border-pink-200">
                            <Users className="mx-auto text-pink-400 mb-4" size={48} />
                            <h3 className="text-xl font-bold text-pink-700 mb-2">ここは交流の場です</h3>
                            <button 
                                onClick={() => setShowChat(true)}
                                className="bg-pink-600 text-white px-8 py-3 rounded-full font-bold hover:bg-pink-700 transition-all shadow-lg shadow-pink-200"
                            >
                                掲示板を開く
                            </button>
                        </div>
                    ) : (
                        <div>
                            <h3 className="text-xl font-bold text-gray-800 mb-4 flex items-center gap-2">
                                <Users className="text-pink-500" size={24} />
                                リアルタイム掲示板
                            </h3>
                            <CommunityChat />
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default CommunityDetail;