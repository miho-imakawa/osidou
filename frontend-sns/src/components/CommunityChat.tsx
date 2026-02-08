import React, { useState, useEffect, useCallback } from 'react';
import { createPost, fetchPostsByCategory, Post, authApi } from '../api';
import { 
  Send, MessageSquare, Calendar, Megaphone, ShieldAlert, 
  EyeOff, ChevronDown, ChevronUp, Reply, MapPin, Users, Coins
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
    const [postType, setPostType] = useState<'normal' | 'meetup' | 'ad'>('normal');
    const [meetupDetails, setMeetupDetails] = useState({
        date: '',
        location: '',
        pref: '',      // 追加
        city_town: '', // 追加
        capacity: 5,
        fee: '500'
    });
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
            // 本文が空、またはターゲットIDがない場合は何もしない
            if (!newPost.trim() || !chatTargetId) return;
            
            try {
                await createPost({
                    content: newPost,                // テキストエリアの本文（Cafeの詳細など）
                    hobby_category_id: parseInt(chatTargetId),
                    parent_id: replyingTo?.id || null,
                    // 💡 ボタンで選択したタイプに基づいてフラグを立てる
                    is_meetup: postType === 'meetup',
                    is_ad: postType === 'ad',
                    // 💡 MeetUp専用フォームの値をセットする
                    meetup_date: postType === 'meetup' ? meetupDetails.date : undefined,
                    meetup_location: postType === 'meetup' ? `${meetupDetails.pref} ${meetupDetails.city_town}` : undefined,
                    meetup_capacity: postType === 'meetup' ? meetupDetails.capacity : undefined,
                    meetup_fee_info: postType === 'meetup' ? meetupDetails.fee : undefined,
                    is_system: false
                });

                // 送信が成功したら入力をリセット
                setNewPost('');
                setPostType('normal'); // 投稿後は通常モードに戻す
                setReplyingTo(null);
                fetchPosts();          // 投稿一覧を再取得
            } catch (err: any) {
                console.error('❌ 送信エラー:', err);
                alert(`送信失敗: ${err.response?.data?.detail || "Unknown error"}`);
            }
        };
    if (loading) return <div className="p-8 text-center text-gray-400 italic">Exploring logs...</div>;

// 💡 広告費用の計算ロジック
    // ※現在は仮の人数として posts.length * 10 を使っています。
    // 将来的には Chatグループの実際の参加人数（memberCountなど）をここに当てはめます。
    const memberCount = posts.length * 5; // 仮の人数設定
    
    const getAdPrice = (count: number) => {
        if (count < 200) return 100; // 199人までは一律100円
        return Math.floor(count / 100) * 100; // 200人以上は下2桁切り捨て（例：1765人 → 1700円）
    };

    const adPrice = getAdPrice(memberCount);

    // 💡 親投稿のみフィルタ
const parentPosts = posts.filter(p => !p.parent_id);

    return (
        /* 全体の外枠：高さを固定し、はみ出しを防ぐ */
        <div className="flex flex-col h-[600px] bg-white overflow-hidden border rounded-3xl shadow-xl relative">
            
            {/* 1. ヘッダー（固定） */}
            <div className="px-6 py-3 border-b border-gray-50 flex justify-between items-center flex-shrink-0 bg-white z-10">
                <div className="flex items-center gap-2">
                    <MessageSquare size={16} className="text-gray-400" />
                    <span className="text-sm font-black text-gray-700 tracking-tighter uppercase">Board</span>
                </div>
            </div>

            {/* 2. メッセージリスト（掲示板エリア：ここがスクロールします） */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50/30 text-left">
                {parentPosts.map((post) => {
                    const replies = posts.filter(p => p.parent_id === post.id);
                    const isThreadExpanded = expandedThreads.has(post.id);
                    const isMyTown = post.meetup_location?.includes("豊島区千川");

                    return (
                        <div key={post.id} className="mb-6">
                            {post.is_meetup ? (
                                /* 🟠 MEETUP看板（ご要望の2行レイアウト） */
                                <div className="flex flex-col gap-1">
                                    <div className={`p-3 rounded-[24px] border-2 shadow-sm transition-all ${isMyTown ? 'bg-orange-100 border-orange-400 shadow-md' : 'bg-orange-50 border-orange-200'} max-w-[95%]`}>
                                        
                                        {/* 💡 1行目：開催名 & 日時 */}
                                        <div className="flex justify-between items-center mb-1.5 px-1">
                                        <h3 className="text-[13px] font-black text-orange-800 truncate flex-1 leading-tight">
                                            {post.content.split('\n')[0]}
                                        </h3>

                                        {/* 右側：開催日（大）＋ POSTED（小） */}
                                        <div className="flex flex-col items-end ml-4 shrink-0 leading-tight">
                                            {/* 開催日 */}
                                            <div className="flex flex-col items-end ml-4 shrink-0 leading-tight">
                                            {/* 開催日（主） */}
                                            <div className="flex items-center gap-1 text-orange-700 font-black text-[12px]">
                                                <Calendar size={12} className="text-orange-500" />
                                                <span>
                                                開催日 / Date：
                                                {post.meetup_date
                                                    ? ` ${post.meetup_date.slice(5, 10)} ${post.meetup_date.slice(11, 16)}`
                                                    : ' 未定'}
                                                </span>
                                            </div>

                                            {/* 投稿日（従） */}
                                            <div className="text-[8px] text-gray-400 font-bold">
                                                POSTED：{post.created_at ? post.created_at.slice(5, 10) : '--/--'}
                                            </div>
                                            </div>

                                        </div>
                                        </div>


                                        {/* 💡 2行目：場所 & 人数 & 費用 & 詳細ボタン */}
                                        <div className="flex items-center justify-between px-1">
                                            <div className="flex items-center gap-3">
                                                {/* 場所情報 */}
                                                <div className="flex items-center gap-1 text-[10px] text-gray-600 font-bold">
                                                    <MapPin size={11} className="text-orange-500" />
                                                    <span className="truncate max-w-[120px]">{post.meetup_location}</span>
                                                </div>
                                                {/* 人数 & 費用をセットで表示 */}
                                                <div className="flex items-center gap-2 border-l pl-2 border-orange-200/50 text-[10px] text-gray-600 font-bold">
                                                    <Users size={11} className="text-orange-400" />
                                                    <span>{post.meetup_capacity}人</span>
                                                    <Coins size={11} className="text-orange-400 ml-1" />
                                                    <span className="text-orange-600 font-black">
                                                        {post.meetup_fee_info && Number(post.meetup_fee_info) > 0 ? `￥${post.meetup_fee_info}` : 'お茶代'}
                                                    </span>
                                                </div>
                                            </div>

                                            {/* 💡 詳細ボタン：これを押すまで詳細は表示されません */}
                                            <button 
                                                onClick={() => toggleThread(post.id)} 
                                                className="py-1 px-3 bg-orange-600 text-white rounded-full text-[9px] font-black flex items-center gap-1 shadow-sm hover:bg-orange-700 transition-all"
                                            >
                                                {isThreadExpanded ? "CLOSE" : "DETAILS"}
                                                <ChevronDown size={10} className={isThreadExpanded ? "rotate-180" : ""} />
                                            </button>
                                        </div>
                                    </div>

                                    {/* 💡 詳細展開エリア：ボタンを押したときだけ中身が出ます */}
                                    {isThreadExpanded && (
                                        <div className="ml-6 mt-1 space-y-2 border-l-2 border-orange-100 pl-4 animate-in fade-in slide-in-from-top-1">
                                            <div className="bg-white/80 p-3 rounded-2xl border border-orange-50 text-[11px] whitespace-pre-wrap leading-relaxed text-gray-700 relative text-left">
                                                {post.content}
                                                <div className="mt-3 border-t pt-2 flex justify-end">
                                                    <button onClick={() => handleReply(post)} className="px-3 py-1 bg-orange-600 text-white rounded-full text-[9px] font-black shadow-sm">JOIN REQUEST / 参加希望</button>
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                /* 通常投稿 */
                                <div className="flex gap-2">
                                    <div className="bg-white p-3 rounded-2xl shadow-sm border border-gray-100 max-w-[90%]">
                                        <button onClick={() => handleReply(post)} className="font-black text-[11px] text-pink-600 hover:underline block mb-1">{post.author_nickname}</button>
                                        <p className="text-gray-700 whitespace-pre-wrap text-[13px] leading-relaxed">{post.content}</p>
                                    </div>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

{/* 3. フォームエリア（下部に固定。入力項目が増えてもスクロールして送信ボタンが見えます） */}
<div className="bg-white border-t border-gray-100 p-3 flex-shrink-0 max-h-[55%] overflow-y-auto shadow-inner z-20">
    <div className="flex gap-2 mb-3">
        <button type="button" onClick={() => {
            const newType = postType === 'meetup' ? 'normal' : 'meetup';
            setPostType(newType);
            if (newType === 'meetup' && !newPost.trim()) {
                setNewPost("\n📍 集合場所：\n\n📍 開催場所：\n\n🗺️ 開催場所URLまたはMapURL：\n\n💰【支払い方法】： 当日現金 / Stripe決済 / お茶代のみ各自（※不要なものを消してください）\n※カフェ開催のためお茶代が必要です。\n\n❌【キャンセルポリシー】： 当日0時以降のキャンセル50%、NoShow100%\n※キャンセル待ちの方は当日参加が確定（繰り上げ）する場合があります。");
            }
        }} className={`px-4 py-1.5 rounded-full text-[10px] font-black border transition-all ${postType === 'meetup' ? 'bg-orange-600 text-white border-orange-600 shadow-sm' : 'bg-gray-50 text-gray-400'}`}>
            <Calendar size={12} className="inline mr-1" /> MEETUP / 募集
        </button>
        <button type="button" onClick={() => setPostType(postType === 'ad' ? 'normal' : 'ad')} className={`px-4 py-1.5 rounded-full text-[10px] font-black border transition-all ${postType === 'ad' ? 'bg-blue-600 text-white border-blue-600' : 'bg-gray-50 text-gray-400'}`}>
            <Megaphone size={12} className="inline mr-1" /> AD / 広告
        </button>
    </div>

    <form onSubmit={handleSend} className="space-y-3">
        {postType === 'meetup' ? (
            <div className="bg-orange-50 border-2 border-orange-200 rounded-[28px] p-3 space-y-2 text-left">
                
                {/* 1段目：開催名 ＋ 日時 */}
                <div className="grid grid-cols-[1fr,auto] gap-2 pb-2 border-b border-orange-200/30">
                    <div className="flex flex-col gap-1">
                        <label className="text-[9px] font-bold text-orange-800 flex items-center gap-1">
                            <MessageSquare size={10} />
                            EVENT TITLE / 開催名
                        </label>
                        <input 
                            type="text" 
                            placeholder="例：ミステリについて熱く語る会" 
                            className="px-2 py-1.5 rounded-xl border-2 border-orange-200 bg-white text-[13px] focus:border-orange-400 transition-all" 
                            value={newPost.split('\n')[0] || ''} 
                            onChange={(e) => {
                                const lines = newPost.split('\n'); 
                                lines[0] = e.target.value; 
                                setNewPost(lines.join('\n'));
                            }} 
                        />
                    </div>

                    <div className="flex flex-col gap-1" style={{minWidth: '160px'}}>
                        <label className="text-[9px] font-bold text-orange-800 flex items-center gap-1">
                            <Calendar size={10} />
                            DATE / 日時
                        </label>
                        <input 
                            type="datetime-local" 
                            className="px-2 py-1.5 rounded-xl border-2 border-orange-200 bg-white text-[13px] focus:border-orange-400 transition-all" 
                            value={meetupDetails.date} 
                            onChange={(e) => setMeetupDetails({...meetupDetails, date: e.target.value})} 
                        />
                    </div>
                </div>

                {/* 2段目：都道府県 ＋ 市区町村・町名 */}
                <div className="grid grid-cols-[120px,1fr] gap-2 pb-2 border-b border-orange-200/30">
                    <div className="flex flex-col gap-1">
                        <label className="text-[9px] font-bold text-orange-800 flex items-center gap-1">
                            <MapPin size={10} />
                            都道府県
                        </label>
                        <input 
                            type="text" 
                            placeholder="例：東京都" 
                            className="px-2 py-1.5 rounded-xl border-2 border-orange-200 bg-white text-[13px] focus:border-orange-400 transition-all" 
                            value={meetupDetails.pref} 
                            onChange={(e) => setMeetupDetails({...meetupDetails, pref: e.target.value})} 
                        />
                    </div>

                    <div className="flex flex-col gap-1">
                        <label className="text-[9px] font-bold text-orange-800">
                            市区町村・町名
                        </label>
                        <input 
                            type="text" 
                            placeholder="例：豊島区千川" 
                            className="px-2 py-1.5 rounded-xl border-2 border-orange-200 bg-white text-[13px] focus:border-orange-400 transition-all" 
                            value={meetupDetails.city_town} 
                            onChange={(e) => setMeetupDetails({...meetupDetails, city_town: e.target.value})} 
                        />
                    </div>
                </div>

                {/* 3段目：MAX定員 ＋ 費用 */}
                <div className="grid grid-cols-2 gap-2 pb-2 border-b border-orange-200/30">
                    <div className="flex flex-col gap-1">
                        <label className="text-[9px] font-bold text-orange-800 flex items-center gap-1">
                            <Users size={10} />
                            MAX / 定員
                        </label>
                        <input 
                            type="number" 
                            placeholder="5" 
                            min="1" 
                            max="10" 
                            className="px-2 py-1.5 rounded-xl border-2 border-orange-200 bg-white text-[13px] focus:border-orange-400 transition-all" 
                            value={meetupDetails.capacity} 
                            onChange={(e) => setMeetupDetails({...meetupDetails, capacity: parseInt(e.target.value) || 5})} 
                        />
                    </div>

                    <div className="flex flex-col gap-1">
                        <label className="text-[9px] font-bold text-orange-800 flex items-center gap-1">
                            <Coins size={10} className="text-orange-500" />
                            FEE / 費用
                        </label>
                        <div className="relative">
                            <input 
                                type="text" 
                                placeholder="金額 or お茶代" 
                                className="w-full px-2 py-1.5 rounded-xl border-2 border-orange-200 bg-white text-[13px] focus:border-orange-400 transition-all font-bold text-orange-600" 
                                value={meetupDetails.fee} 
                                onChange={(e) => setMeetupDetails({...meetupDetails, fee: e.target.value})} 
                            />
                            {meetupDetails.fee && !isNaN(Number(meetupDetails.fee)) && Number(meetupDetails.fee) > 0 && (
                                <span className="absolute right-1.5 top-1/2 -translate-y-1/2 text-[7px] bg-blue-500 text-white px-1 py-0.5 rounded font-black">
                                    STRIPE
                                </span>
                            )}
                        </div>
                    </div>
                </div>

                {/* 詳細情報 - 高さ固定 */}
                <div className="flex flex-col gap-1">
                    <label className="text-[9px] font-bold text-orange-800">
                        DETAILS / 詳細
                    </label>
                    <textarea 
                        placeholder="テンプレートを編集してください" 
                        className="px-2 py-1.5 rounded-xl border-2 border-orange-200 bg-white text-[12px] h-[90px] focus:border-orange-400 transition-all resize-none leading-relaxed" 
                        value={newPost.split('\n').slice(1).join('\n')} 
                        onChange={(e) => {
                            const firstLine = newPost.split('\n')[0] || ''; 
                            setNewPost(firstLine + '\n' + e.target.value);
                        }} 
                    />
                </div>
            </div>
        ) : null}

        {/* 送信ボタン：どのモードでも常に最後に表示 */}
<div className="flex gap-2 sticky bottom-0 bg-white pt-1">
    {replyingTo && (
        <div className="absolute -top-8 left-0 right-0 bg-pink-50 p-1 text-[9px] text-pink-700 font-bold flex justify-between rounded-t-lg border border-pink-100">
            <span>💬 {replyingTo.author_nickname} への返信</span>
            <button type="button" onClick={() => {
                setReplyingTo(null);
                setNewPost('');
            }}>✕</button>
        </div>
    )}

    {/* ⛔ meetup時は表示しない */}
    {postType !== 'meetup' && (
        <textarea 
            value={newPost} 
            onChange={(e) => setNewPost(e.target.value)} 
            placeholder="Type a message..." 
            className="flex-1 px-4 py-2 bg-gray-50 rounded-2xl focus:outline-none focus:ring-2 focus:ring-orange-100 transition-all resize-none text-sm" 
            rows={1} 
        />
    )}

    <button 
        type="submit" 
        disabled={!newPost.trim()} 
        className={`bg-gray-900 text-white rounded-2xl hover:bg-orange-600 disabled:opacity-20 transition-all shadow-lg flex items-center justify-center font-black tracking-tighter ${
            postType === 'normal' ? 'p-3 shrink-0' : 'flex-1 py-4 text-[14px]'
        }`}
    >
        <Send size={18} className={postType === 'normal' ? '' : 'mr-3'} /> 
        {postType === 'meetup' && "¥500：MEET UP POST"}
        {/* 💡 ここを adPrice に連動させます */}
        {postType === 'ad' && `¥${adPrice}：ADVERTIZEMENT POST`}
    </button>
</div>

    </form>
</div>
        </div>
    );
};

export default CommunityChat;