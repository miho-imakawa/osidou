import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { createPost, fetchPostsByCategory, Post } from '../api';
import { Send, MessageSquare } from 'lucide-react';

const CommunityChat: React.FC = () => {
    const { categoryId } = useParams<{ categoryId: string }>();
    const [posts, setPosts] = useState<Post[]>([]);
    const [newPost, setNewPost] = useState('');
    const [loading, setLoading] = useState(true);

    // 投稿一覧の取得
    const fetchPosts = async () => {
        if (!categoryId) return;
        try {
            const data = await fetchPostsByCategory(parseInt(categoryId));
            setPosts(data);
        } catch (err) {
            console.error("投稿の取得に失敗しました", err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchPosts();
        const interval = setInterval(fetchPosts, 5000); // 5秒ごとに自動更新
        return () => clearInterval(interval);
    }, [categoryId]);

    // 投稿送信
    const handleSend = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!newPost.trim() || !categoryId) return;

        try {
            await createPost({
                content: newPost,
                hobby_category_id: parseInt(categoryId),
                is_meetup: false
            });
            setNewPost('');
            fetchPosts(); // 送信後に即更新
        } catch (err: any) {
            console.error("送信エラー:", err.response?.data);
            alert(`送信に失敗しました: ${err.response?.data?.detail || '不明なエラー'}`);
        }
    };

    if (loading) {
        return <div className="p-8 text-center">読み込み中...</div>;
    }

    return (
        <div className="flex flex-col h-[calc(100vh-180px)] bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden">
            {/* チャット履歴表示エリア */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-gray-50">
                {posts.length === 0 ? (
                    <div className="text-center py-20 text-gray-400">
                        <MessageSquare className="mx-auto mb-2 opacity-20" size={48} />
                        <p>まだ投稿がありません。最初のひとりになりましょう！</p>
                    </div>
                ) : (
                    posts.map((post) => (
                        <div key={post.id} className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100 max-w-[85%]">
                            <div className="flex items-center gap-2 mb-1">
                                <span className="font-bold text-gray-800">
                                    {post.author_nickname || `ユーザー${post.user_id}`}
                                </span>
                                {post.public_code && (
                                    <span className="text-[10px] text-gray-400 font-mono">
                                        #{post.public_code}
                                    </span>
                                )}
                            </div>
                            <p className="text-gray-700 leading-relaxed">{post.content}</p>
                            <span className="text-[9px] text-gray-400 block mt-2 text-right">
                                {new Date(post.created_at).toLocaleString('ja-JP')}
                            </span>
                        </div>
                    ))
                )}
            </div>

            {/* 入力エリア */}
            <form onSubmit={handleSend} className="p-4 bg-white border-t border-gray-100 flex gap-2">
                <input
                    type="text"
                    value={newPost}
                    onChange={(e) => setNewPost(e.target.value)}
                    placeholder="ここにメッセージを入力..."
                    className="flex-1 px-4 py-3 bg-gray-50 rounded-xl focus:outline-none focus:ring-2 focus:ring-pink-200 transition-all"
                />
                <button 
                    type="submit"
                    disabled={!newPost.trim()}
                    className="bg-pink-600 text-white p-3 rounded-xl hover:bg-pink-700 transition-all shadow-md shadow-pink-100 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    <Send size={20} />
                </button>
            </form>
        </div>
    );
};

export default CommunityChat;