import React, { useState, useEffect } from 'react';
import { authApi, HobbyCategory } from '../api.ts';
import { Search, ChevronRight, Users, MapPin, Music2, Trophy } from 'lucide-react';
import { Link } from 'react-router-dom';

const CommunityList: React.FC = () => {
    const [categories, setCategories] = useState<HobbyCategory[]>([]);
    const [searchQuery, setSearchQuery] = useState('');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchCategories = async () => {
            try {
                const response = await authApi.get('/hobby-categories');
                setCategories(response.data);
            } catch (err) {
                console.error("カテゴリの取得に失敗しました");
            } finally {
                setLoading(false);
            }
        };
        fetchCategories();
    }, []);

    // 💡 検索ロジック：名前またはコードでフィルタリング
    const filteredCategories = categories.filter(cat => 
        cat.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (cat.unique_code && cat.unique_code.toLowerCase().includes(searchQuery.toLowerCase()))
    );

    // 💡 初期表示は「親がいない（depth 0）」のものだけを表示（検索時は全件から探す）
    const displayCategories = searchQuery 
        ? filteredCategories.slice(0, 20) // 検索時はヒットしたものを表示
        : categories.filter(cat => cat.depth === 0);

    const getIcon = (name: string) => {
        if (name.includes('MUSIC')) return <Music2 className="text-purple-500" />;
        if (name.includes('REGIONS')) return <MapPin className="text-green-500" />;
        if (name.includes('SPORT')) return <Trophy className="text-orange-500" />;
        return <Users className="text-pink-500" />;
    };

    return (
        <div className="max-w-4xl mx-auto p-4 md:p-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-8 flex items-center gap-3">
                <Users size={32} className="text-pink-600" />
                Community Exploration
            </h1>

            {/* 🔍 検索ボックス */}
            <div className="relative mb-8">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" size={20} />
                <input
                    type="text"
                    placeholder="地域、アーティスト、スポーツ、またはコードで検索..."
                    className="w-full pl-12 pr-4 py-4 bg-white border-2 border-gray-100 rounded-2xl focus:border-pink-300 focus:outline-none shadow-sm transition-all"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                />
            </div>

            {loading ? (
                <p className="text-center text-gray-500">読み込み中...</p>
            ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {displayCategories.map(cat => (
                        <Link 
                            key={cat.id}
                            to={`/community/${cat.id}`}
                            className="group p-5 bg-white rounded-2xl border border-gray-100 hover:border-pink-200 hover:shadow-md transition-all flex items-center justify-between"
                        >
                            <div className="flex items-center gap-4">
                                <div className="p-3 bg-gray-50 rounded-xl group-hover:bg-pink-50 transition-colors">
                                    {getIcon(cat.name)}
                                </div>
                                <div>
                                    <h3 className="font-bold text-gray-800">{cat.name}</h3>
                                    <span className="text-[10px] font-mono text-gray-400 bg-gray-50 px-1.5 py-0.5 rounded">
                                        #{cat.unique_code}
                                    </span>
                                </div>
                            </div>
                            <ChevronRight className="text-gray-300 group-hover:text-pink-400 transition-colors" />
                        </Link>
                    ))}
                </div>
            )}
            
            {!loading && displayCategories.length === 0 && (
                <p className="text-center text-gray-500 mt-10 italic">該当するコミュニティが見つかりませんでした</p>
            )}
        </div>
    );
};

export default CommunityList;