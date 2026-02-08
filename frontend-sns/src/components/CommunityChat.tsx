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
    const [replyingTo, setReplyingTo] = useState<Post | null>(null);
    const [expandedThreads, setExpandedThreads] = useState<Set<number>>(new Set()); // 💡 展開状態を管理

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

    // 💡 スレッドの展開/折りたたみ
    const toggleThread = (postId: number) => {
        setExpandedThreads(prev => {
            const newSet = new Set(prev);
            if (newSet.has(postId)) {
                newSet.delete(postId);
            } else {
                newSet.add(postId);
            }
            return newSet;
        });
    };

    // 💡 返信アンカーをセットする関数
    const handleReply = (post: Post) => {
        setReplyingTo(post);
        const nickname = post.author_nickname;
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
                parent_id: replyingTo?.id || null,
                is_meetup: isMeetup,
                is_ad: isAd,
                is_system: false
            });
            setNewPost('');
            setReplyingTo(null);
            fetchPosts();
        } catch (err: any) {
            alert(`送信失敗: ${err.response?.data?.detail || "Unknown error"}`);
        }
    };

    if (loading) return <div className="p-8 text-center text-gray-400 italic">Exploring logs...</div>;

    // 💡 親投稿のみフィルタ
    const parentPosts = posts.filter(p => !p.parent_id);

    return (
        <div className="flex flex-col h-[600px] bg-white overflow-hidden">
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
                {parentPosts.map((post) => {
                    const replies = posts.filter(p => p.parent_id === post.id);
                    const isThreadExpanded = expandedThreads.has(post.id);

                    return (
                        <div key={post.id}>
                            {/* 親投稿 */}
                            <div className="flex gap-2">
                                <div className="bg-white p-3 rounded-2xl shadow-sm border border-gray-100 relative group max-w-[90%]">
                                    <div className="flex justify-between items-center mb-1">
                                        <button 
                                            onClick={() => handleReply(post)}
                                            className="font-black text-[11px] text-pink-600 hover:underline flex items-center gap-1"
                                        >
                                            {post.author_nickname}
                                            <Reply size={10} className="opacity-0 group-hover:opacity-100" />
                                        </button>
                                        <span className="text-[9px] text-gray-300 font-mono">{post.public_code}</span>
                                    </div>
                                    <p className="text-gray-700 whitespace-pre-wrap text-xs leading-relaxed">
                                        {post.content}
                                    </p>
                                </div>
                            </div>

                            {/* 💡 返信があれば展開ボタンを表示 */}
                            {replies.length > 0 && (
                                <>
                                    <button
                                        onClick={() => toggleThread(post.id)}
                                        className="ml-8 mt-1 flex items-center gap-1 text-[10px] text-gray-400 hover:text-pink-600 transition-colors"
                                    >
                                        {isThreadExpanded ? (
                                            <>
                                                <ChevronUp size={12} />
                                                返信を隠す ({replies.length})
                                            </>
                                        ) : (
                                            <>
                                                <ChevronDown size={12} />
                                                返信を表示 ({replies.length})
                                            </>
                                        )}
                                    </button>

                                    {/* 💡 展開時のみ返信を表示 */}
                                    {isThreadExpanded && (
                                        <div className="ml-8 mt-2 space-y-2">
                                            {replies.map(reply => (
                                                <div key={reply.id} className="flex gap-2">
                                                    <div className="flex flex-col items-center">
                                                        <div className="w-px h-4 bg-gray-200"></div>
                                                        <Reply size={12} className="text-gray-300 rotate-180" />
                                                    </div>
                                                    
                                                    <div className="bg-gray-50/50 p-3 rounded-2xl shadow-sm border border-gray-100 relative group max-w-[85%]">
                                                        <div className="flex justify-between items-center mb-1">
                                                            <button 
                                                                onClick={() => handleReply(reply)}
                                                                className="font-black text-[11px] text-pink-600 hover:underline flex items-center gap-1"
                                                            >
                                                                {reply.author_nickname}
                                                                <Reply size={10} className="opacity-0 group-hover:opacity-100" />
                                                            </button>
                                                            <span className="text-[9px] text-gray-300 font-mono">{reply.public_code}</span>
                                                        </div>
                                                        <p className="text-gray-700 whitespace-pre-wrap text-xs leading-relaxed">
                                                            {reply.content}
                                                        </p>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    );
                })}
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

                {/* 💡 返信中の表示 */}
                {replyingTo && (
                    <div className="mb-2 p-2 bg-pink-50 rounded-lg flex justify-between items-center">
                        <span className="text-[10px] text-pink-700">
                            💬 {replyingTo.author_nickname} に返信中
                        </span>
                        <button 
                            onClick={() => {
                                setReplyingTo(null);
                                setNewPost('');
                            }}
                            className="text-pink-400 hover:text-pink-600"
                        >
                            ✕
                        </button>
                    </div>
                )}

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