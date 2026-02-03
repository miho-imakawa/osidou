import React, { useState, useEffect, useCallback } from 'react';
import { createPost, fetchPostsByCategory, Post, authApi } from '../api';
import { 
  Send, MessageSquare, Calendar, Megaphone, ShieldAlert, 
  EyeOff, ChevronDown, ChevronUp, Reply 
} from 'lucide-react';
import { MeetupAccordion } from './MeetupAccordion';

interface CommunityChatProps {
    categoryId: string;
    masterId?: number | null;
}

const CommunityChat: React.FC<CommunityChatProps> = ({ categoryId: propCategoryId, masterId }) => {
    const chatTargetId = masterId ? String(masterId) : propCategoryId;

    const [posts, setPosts] = useState<Post[]>([]);
    const [newPost, setNewPost] = useState('');
    const [loading, setLoading] = useState(true);
    const [specialPosts, setSpecialPosts] = useState<Post[]>([]);
    const [isExpanded, setIsExpanded] = useState(false);

    const TEMPLATES = {
        MEETUP: "【Meet Up：視聴会】\n【番組名】: \n【DATE】: 2026/02/\n【TIME】: 21:00\n【PLACE】: \n【CONTENT】: みんなで一緒に語り合いましょう！",
        AD: "【地域の広告】\n【内容】: \n【詳細URL】: ",
    };

    const fetchPosts = useCallback(async () => {
        if (!chatTargetId) return;
        try {
            const data = await fetchPostsByCategory(parseInt(chatTargetId));
            setPosts(data);
            const specials = data.filter(p => (p.is_meetup || p.is_ad));
            setSpecialPosts(specials);
        } catch (err: any) {
            console.error('❌ 投稿取得エラー:', err);
        } finally {
            setLoading(false);
        }
    }, [chatTargetId]);

    useEffect(() => {
        fetchPosts();
        const interval = setInterval(fetchPosts, 5000);
        return () => clearInterval(interval);
    }, [fetchPosts]);

    // 💡 返信アンカーをセットする関数
    const handleReply = (nickname: string) => {
        // 💡 すでに入力がある場合はその前に、なければそのままセット
        setNewPost(prev => prev.includes(`>>${nickname}`) ? prev : `>>${nickname} ${prev}`);
    };

    const handleSend = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!newPost.trim() || !chatTargetId) return;
        const isMeetup = newPost.includes("【Meet Up");
        const isAd = newPost.includes("【地域の広告】");
        try {
            await createPost({
                content: newPost,
                hobby_category_id: parseInt(chatTargetId),
                is_meetup: isMeetup,
                is_ad: isAd,
                is_system: false
            });
            setNewPost('');
            fetchPosts();
        } catch (err: any) {
            alert(`送信失敗: ${err.response?.data?.detail || "Unknown error"}`);
        }
    };

    if (loading) return <div className="p-8 text-center text-gray-400 italic">Exploring logs...</div>;

    return (
        <div className="flex flex-col h-[600px] bg-white overflow-hidden">
            {/* 💡 ヘッダーから重複する人数表示を削除し、スッキリさせました */}
            <div className="px-6 py-3 border-b border-gray-50 flex justify-between items-center">
                <div className="flex items-center gap-2">
                    <MessageSquare size={16} className="text-gray-400" />
                    <span className="text-sm font-black text-gray-700 tracking-tighter uppercase">Board</span>
                </div>
            </div>

            {/* 重要なお知らせ（アコーディオン） */}
            {specialPosts.length > 0 && (
                <div className="bg-pink-50/50 border-b border-pink-100">
                    <button onClick={() => setIsExpanded(!isExpanded)} className="w-full p-2 flex justify-center items-center text-pink-700 font-bold text-[10px] gap-1 transition-colors">
                        <Megaphone size={12} /> 重要 ({specialPosts.length})
                        {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>
                    {isExpanded && (
                        <div className="max-h-32 overflow-y-auto p-3 space-y-2">
                            {specialPosts.map(post => (
                                <div key={post.id} className="bg-white p-2 rounded-lg shadow-sm border border-pink-100 text-[10px]">
                                    <p className="text-gray-800 line-clamp-1">{post.content}</p>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* メッセージリスト */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50/30">
                {posts.map((post) => (
                    <div key={post.id}>
                        {post.is_system ? (
                            <div className="flex justify-center my-4">
                                <div className="bg-white border border-gray-100 text-gray-400 px-4 py-1 rounded-full text-[10px] font-bold shadow-sm">
                                    {post.content}
                                </div>
                            </div>
                        ) : post.is_meetup ? (
                            <MeetupAccordion 
                                post={post} 
                                onJoin={(id: number) => console.log("参加申請:", id)} 
                            />
                        ) : (
                            <div className={`bg-white p-3 rounded-2xl shadow-sm border border-gray-100 max-w-[90%] relative group ${post.is_ad ? 'border-l-4 border-l-blue-400' : ''}`}>
                                <div className="flex justify-between items-center mb-1">
                                    {/* 💡 名前をタップで返信アンカーを入れる */}
                                    <button 
                                        onClick={() => handleReply(post.author_nickname)}
                                        className="font-black text-[11px] text-pink-600 hover:underline flex items-center gap-1"
                                    >
                                        {post.author_nickname}
                                        <Reply size={10} className="opacity-0 group-hover:opacity-100" />
                                    </button>
                                    <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <button onClick={() => authApi.post(`/posts/${post.id}/report`)} className="text-gray-300 hover:text-red-500"><ShieldAlert size={12}/></button>
                                    </div>
                                </div>
                                <p className="text-gray-700 whitespace-pre-wrap text-xs leading-relaxed">{post.content}</p>
                            </div>
                        )}
                    </div>
                ))}
            </div>
            
            {/* フォームエリア */}
            <div className="bg-white border-t border-gray-50 p-3">
                <div className="flex gap-2 mb-2">
                    <button type="button" onClick={() => setNewPost(TEMPLATES.MEETUP)} className="flex items-center gap-1 text-[9px] font-black bg-gray-50 text-gray-400 px-3 py-1 rounded-full hover:bg-pink-50 hover:text-pink-600 transition-all border border-gray-100">
                        <Calendar size={12} /> MEETUP
                    </button>
                    <button type="button" onClick={() => setNewPost(TEMPLATES.AD)} className="flex items-center gap-1 text-[9px] font-black bg-gray-50 text-gray-400 px-3 py-1 rounded-full hover:bg-blue-50 hover:text-blue-600 transition-all border border-gray-100">
                        <Megaphone size={12} /> AD/NOTICE
                    </button>
                </div>

                <form onSubmit={handleSend} className="flex gap-2">
                    <textarea
                        value={newPost}
                        onChange={(e) => setNewPost(e.target.value)}
                        placeholder="Type a message..."
                        rows={newPost.includes('\n') ? 3 : 1}
                        className="flex-1 px-4 py-2 bg-gray-50 rounded-xl focus:outline-none focus:ring-1 focus:ring-pink-100 transition-all resize-none text-sm"
                    />
                    <button type="submit" disabled={!newPost.trim()} className="bg-gray-900 text-white px-4 rounded-xl hover:bg-pink-600 disabled:opacity-20 transition-all">
                        <Send size={18} />
                    </button>
                </form>
            </div>
        </div>
    );
};

export default CommunityChat;