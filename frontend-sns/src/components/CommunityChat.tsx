import React, { useState, useEffect, useCallback } from 'react';
import { createPost, fetchPostsByCategory, Post, authApi, toggleAttendance, adInteraction, fetchMyAdInteractions, createSubCategory  } from '../api';
import { 
  Send, MessageSquare, MapPin, Users, CheckSquare, Square, Clock, Coins, Pin, Calendar
} from 'lucide-react';
import MeetupChatModal from './MeetupChatModal';
import AdPostModal from './AdPostModal';

interface CommunityChatProps {
    categoryId: string;
    masterId?: number | null;
    currentUserId: number;
    currentCategoryName?: string;
}

const CommunityChat: React.FC<CommunityChatProps> = ({ categoryId: propCategoryId, masterId, currentUserId, currentCategoryName }) => {
    const chatTargetId = masterId ? String(masterId) : propCategoryId;

    const [posts, setPosts] = useState<Post[]>([]);
    const [newPost, setNewPost] = useState<string>(''); 
    const [loading, setLoading] = useState(true);
    const [expandedThreads, setExpandedThreads] = useState<Set<number>>(new Set());
    const [postType, setPostType] = useState<'normal' | 'meetup'>('normal');
    const [activeChat, setActiveChat] = useState<{id: number, title: string} | null>(null);
    const [showAdModal, setShowAdModal] = useState(false);
    const [adInteractions, setAdInteractions] = useState<Record<number, {
        is_liked: boolean, 
        is_pinned: boolean, 
        is_closed: boolean,
        is_attended?: boolean // 👈 ここを追加（? を付けると「無い場合もある」という意味になります）
    }>>({});
    const [closedAds, setClosedAds] = useState<Set<number>>(() => {
        const saved = localStorage.getItem('closedAds');
        return saved ? new Set(JSON.parse(saved)) : new Set();
    });
    const [meetupDetails, setMeetupDetails] = useState({
        title: '', date: '', pref: '', city_town: '', capacity: 5, fee: ''
    });
    const [pinnedAds, setPinnedAds] = useState<any[]>([]);
    const [showSubChatModal, setShowSubChatModal] = useState(false);
    const [subChatName, setSubChatName] = useState('');
    const [isCreating, setIsCreating] = useState(false);
    const [searchResults, setSearchResults] = useState<any[]>([]);
    const [selectedMasterId, setSelectedMasterId] = useState<number | null>(null);
    const [selectedMasterName, setSelectedMasterName] = useState<string>('');
    const [selectedRoleType, setSelectedRoleType] = useState<string | null>(null);
    const [showPaymentConfirm, setShowPaymentConfirm] = useState(false);

    const MEETUP_TEMPLATE = `📍 集合場所：

📍 開催場所：

🗺️ 開催場所URLまたはMapURL：

💰【支払い方法】： 当日現金 / Stripe決済 / お茶代のみ各自
※カフェ開催のためお茶代が必要です。

❌【キャンセルポリシー】： 当日0時以降のキャンセル50%、NoShow100%`;

    const toggleAdCollapse = (postId: number) => {
        setClosedAds(prev => {
            const newSet = new Set(prev);
            if (newSet.has(postId)) newSet.delete(postId);
            else newSet.add(postId);
            localStorage.setItem('closedAds', JSON.stringify([...newSet]));
            return newSet;
        });
    };

    const fetchPosts = useCallback(async () => {
        if (!chatTargetId) return;
        try {
            const data = await fetchPostsByCategory(parseInt(chatTargetId));
            setPosts(data || []);
        } catch (err) {
            console.error('Fetch Error:', err);
        } finally {
            setLoading(false);
        }
    }, [chatTargetId]);

    useEffect(() => {
        fetchPosts();
        const interval = setInterval(fetchPosts, 5000);
        return () => clearInterval(interval);
    }, [fetchPosts]);

    useEffect(() => {
        const loadInteractions = async () => {
            try {
                const data = await fetchMyAdInteractions();
                setAdInteractions(data);
            } catch {}
        };
        loadInteractions();
    }, []);

    // 🔄 リロード時やデータ更新時に、PIN済みのものをリストに復元する
    useEffect(() => {
        if (posts.length > 0) {
            // 全投稿の中から、interactionデータで is_pinned が true のものを抽出
            const pinned = posts.filter(post => adInteractions[post.id]?.is_pinned);
            setPinnedAds(pinned);
        }
    }, [posts, adInteractions]); // posts か adInteractions が変わるたびに実行
   
    const handleAdAction = async (postId: number, action: 'like' | 'pin' | 'close') => {
        try {
            const result = await adInteraction(postId, action);
            
            // 1. まず全体のインタラクション状態を更新（ボタンの色が変わる）
            setAdInteractions(prev => ({ ...prev, [postId]: result }));

            // 2. PINアクションの場合、ヘッダーに表示するリスト(pinnedAds)を更新
            if (action === 'pin') {
                if (result.is_pinned) {
                    // PINされた場合：リストに追加
                    const targetedPost = posts.find(p => p.id === postId);
                    if (targetedPost) {
                        setPinnedAds(prev => {
                            // 重複を防ぎつつ追加
                            if (prev.find(p => p.id === postId)) return prev;
                            return [...prev, targetedPost];
                        });
                    }
                } else {
                    // PIN解除された場合：リストから削除
                    setPinnedAds(prev => prev.filter(p => p.id !== postId));
                }
            }
        } catch (err) {
            console.error('Action Error:', err);
        }
    };

    const switchPostType = (type: 'normal' | 'meetup') => {
        setPostType(type);
        if (type === 'meetup') {
            setNewPost(prev => (!prev || prev.trim() === '') ? MEETUP_TEMPLATE : prev);
        } else {
            setNewPost('');
        }
    };

    const handleSubChatNameChange = async (val: string) => {
        setSubChatName(val);
        setSelectedMasterId(null);
        setSelectedMasterName('');
        if (val.length >= 2) {
            try {
                const res = await authApi.get(`/hobby-categories/search?keyword=${encodeURIComponent(val)}`);
                setSearchResults(res.data.slice(0, 5));
            } catch {
                setSearchResults([]);
            }
        } else {
            setSearchResults([]);
        }
    };

    const handleSelectMaster = (id: number, name: string) => {
        setSelectedMasterId(id);
        setSelectedMasterName(name);
        setSearchResults([]);
    };

    const handleCreateSubChat = async () => {
        if (!subChatName.trim()) return;
        setIsCreating(true);
        try {
            const result = await createSubCategory({
                name: subChatName,
                parent_id: parseInt(chatTargetId),
                master_id: selectedMasterId || undefined,
                role_type: selectedRoleType || undefined,  
            });
            alert(`✅ 「${result.name}」を作成しました！`);
            setShowSubChatModal(false);
            setSubChatName('');
            setSelectedMasterId(null);
            setSelectedMasterName('');
            window.location.href = `/community/${result.id}`;
        } catch (err: any) {
            alert(err.response?.data?.detail || 'Sub Chatの作成に失敗しました');
        } finally {
            setIsCreating(false);
        }
    };

const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    const isMeetup = postType === 'meetup';
    if (isMeetup ? !meetupDetails.title?.trim() : !newPost?.trim()) return;
    if (!chatTargetId) return;

    // ★ MEETUPの場合は確認画面を出す
    if (isMeetup) {
        setShowPaymentConfirm(true);
        return;
    }

    await submitPost();
};

const submitPost = async () => {
    const isMeetup = postType === 'meetup';
    try {
        await createPost({
            content: isMeetup ? `${meetupDetails.title}\n${newPost}` : newPost,
            hobby_category_id: parseInt(chatTargetId),
            is_meetup: isMeetup,
            is_ad: false,
            is_system: false,
            meetup_date: meetupDetails.date || undefined,
            meetup_location: `${meetupDetails.pref || ''} ${meetupDetails.city_town || ''}`.trim(),
            meetup_capacity: meetupDetails.capacity || 0,
            meetup_fee_info: meetupDetails.fee || undefined,
        });
        setNewPost('');
        setMeetupDetails({ title: '', date: '', pref: '', city_town: '', capacity: 5, fee: '' });
        setPostType('normal');
        setShowPaymentConfirm(false);
        fetchPosts();
    } catch (err) {
        console.error('送信エラー:', err);
        alert("送信に失敗しました");
    }
};

    if (loading) {
        return (
            <div className="h-[650px] bg-white rounded-3xl flex items-center justify-center">
                <p className="text-gray-400">Loading...</p>
            </div>
        );
    }

    const parentPosts = posts.filter(p => !p.parent_id);

    return (
        <div className="flex flex-col h-[650px] bg-white border rounded-3xl shadow-xl overflow-hidden text-left font-sans relative">
            {/* 1. Header */}
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-white shrink-0 z-20">
                <div className="flex items-center">
                    <MessageSquare size={18} className="text-pink-500 mr-2" />
                    <span className="text-sm font-black text-gray-800 uppercase tracking-tighter">Community Board</span>
                </div>
                <button
                    onClick={() => setShowSubChatModal(true)}
                    className="flex items-center gap-1 px-3 py-1.5 bg-pink-50 text-pink-600 rounded-full text-[11px] font-black hover:bg-pink-100 transition-colors"
                >
                    <span>＋</span> Sub Chat
                </button>
            </div>

        {/* 📌 新設：PIN済み広告 ＆ 参加予定ミートアップのお知らせバー */}
        {(pinnedAds.length > 0 || posts.some(p => p.is_meetup && (p.user_id === currentUserId || adInteractions[p.id]?.is_attended))) && (
            <div className="bg-rose-50/50 border-b border-rose-100 px-4 py-2 flex flex-col gap-2 shrink-0">
                {/* ミートアップ表示エリア */}
                <div className="flex flex-wrap gap-2">
                    {posts.filter(p => p.is_meetup && (p.user_id === currentUserId || adInteractions[p.id]?.is_attended)).map(meetup => (
                        <button
                            key={`meet-link-${meetup.id}`}
                            onClick={() => document.getElementById(`post-${meetup.id}`)?.scrollIntoView({ behavior: 'smooth' })}
                            className="flex items-center gap-1.5 bg-white border border-rose-200 px-3 py-1 rounded-full text-[11px] font-bold text-rose-800 shadow-sm hover:bg-rose-100 transition-colors"
                        >
                            <Calendar size={10} className="text-rose-500" />
                            <span>{meetup.user_id === currentUserId ? '主催：' : '参加：'}{meetup.content.split('\n')[0]}</span>
                        </button>
                    ))}
                </div>

                {/* 既存のPIN済み広告エリア */}
                {pinnedAds.length > 0 && (
                    <div className="flex flex-wrap gap-2 border-t border-amber-100 pt-1">
                        {pinnedAds.map(post => (
                            <button
                                key={`pin-link-${post.id}`}
                                onClick={() => document.getElementById(`post-${post.id}`)?.scrollIntoView({ behavior: 'smooth' })}
                                className="flex items-center gap-1.5 bg-white border border-gray-200 px-3 py-1 rounded-full text-[11px] font-bold text-amber-800 shadow-sm hover:bg-amber-100"
                            >
                                <Pin size={10} className="fill-amber-500 text-amber-500" />
                                <span className="truncate max-w-[150px]">{post.content.split('\n')[0]}</span>
                            </button>
                        ))}
                    </div>
                )}
            </div>
        )}

            {/* 2. Chat Timeline */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50/50">
                {parentPosts.map((post) => {
                    const rawResponses = post.responses || [];
                    const organizer = {
                        id: -1, user_id: post.user_id,
                        author_nickname: post.author_nickname || "HOST",
                        is_participation: true, is_attended: false
                    };
                    const uniqueParticipantsMap = new Map();
                    rawResponses.forEach(res => {
                        if (res.is_participation && res.user_id !== post.user_id) {
                            uniqueParticipantsMap.set(res.user_id, {
                                ...res,
                                author_nickname: res.author_nickname || `User-${res.user_id}`
                            });
                        }
                    });
                    const dbParticipants = Array.from(uniqueParticipantsMap.values());
                    const allParticipants = [organizer, ...dbParticipants];
                    const isExpanded = expandedThreads.has(post.id);
                    const isOwner = currentUserId === post.user_id;
                    const isJoined = allParticipants.some(p => p.user_id === currentUserId);
                    const interaction = adInteractions[post.id];
                    const isClosed = closedAds.has(post.id);

                    const adBg = post.ad_color === 'red' ? 'bg-red-50' : post.ad_color === 'blue' ? 'bg-blue-50' : post.ad_color === 'purple' ? 'bg-purple-50' : post.ad_color === 'white' ? 'bg-slate-50' : 'bg-green-50';
                    const adBorder = post.ad_color === 'red' ? 'border-red-200 text-red-900' : post.ad_color === 'blue' ? 'border-blue-200 text-blue-900' : post.ad_color === 'purple' ? 'border-purple-200 text-purple-900' : post.ad_color === 'white' ? 'border-slate-200 text-slate-900' : 'border-green-200 text-green-900';
                    const adBorderL = post.ad_color === 'red' ? 'border-red-400' : post.ad_color === 'blue' ? 'border-blue-400' : post.ad_color === 'purple' ? 'border-purple-400' : post.ad_color === 'white' ? 'border-slate-300' : 'border-green-400';

                    return (
                       <div key={post.id} id={`post-${post.id}`} className="animate-in fade-in slide-in-from-bottom-2">
                        {post.is_ad ? (
                            <div className="mb-4">
                                {isClosed ?(
                                        /* コンパクト表示 */
                                        <div className={`p-3 border-l-4 rounded-r-2xl ${adBg} ${adBorderL}`}>
                                        {/* --- ここから差し替え --- */}
                                        <div className="flex justify-between items-center">
                                            <div className="flex items-center gap-3 min-w-0 flex-1">
                                                <span className="text-[8px] font-black bg-gray-800 text-white px-1.5 py-0.5 rounded-full shrink-0">AD</span>
                                                
                                                {/* タイトルと日付を縦に並べるための div */}
                                                <div className="flex flex-col min-w-0">
                                                    <span className="text-[14px] font-bold text-gray-700 truncate">
                                                        {post.content.split('\n')[0]}
                                                    </span>
                                                    {/* ★ 掲載終了日をコンパクトに表示 */}
                                                    {post.ad_start_date && post.ad_end_date && (
                                                        <span className="text-[9px] font-bold opacity-80 leading-none mt-1">
                                                            掲載期間: {post.ad_start_date.slice(0, 10).replace(/-/g, '/')} 〜 {post.ad_end_date.slice(0, 10).replace(/-/g, '/')}
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                            <button
                                                onClick={() => toggleAdCollapse(post.id)}
                                                className="px-3 py-1 bg-white border border-gray-200 rounded-full text-[10px] font-black text-gray-600 shrink-0 ml-2 shadow-sm active:scale-95 transition-transform"
                                            >
                                                RE-OPEN
                                            </button>
                                        </div>
                                        {/* --- ここまで --- */}
                                            <div className="flex items-center gap-2 mt-2">
                                                <button
                                                    onClick={() => handleAdAction(post.id, 'like')}
                                                    className={`px-2 py-1 rounded-full text-[9px] font-black transition-all ${interaction?.is_liked ? 'bg-pink-500 text-white' : 'bg-white/70 text-gray-400 border border-gray-200'}`}
                                                >
                                                    👍 {interaction?.is_liked ? 'イイネ済' : 'イイネ'}
                                                </button>
                                                <button
                                                    onClick={() => handleAdAction(post.id, 'pin')}
                                                    className={`px-2 py-1 rounded-full text-[9px] font-black transition-all ${interaction?.is_pinned ? 'bg-yellow-400 text-white' : 'bg-white/70 text-gray-400 border border-gray-200'}`}
                                                >
                                                    📌 {interaction?.is_pinned ? 'PIN済' : 'PIN'}
                                                </button>
                                                {post.ad_end_date && (
                                                    <span className="text-[9px] text-gray-400 ml-auto">〜{post.ad_end_date.slice(0, 10)}</span>
                                                )}
                                            </div>
                                        </div>
                                    ) : (
                                        /* フル表示 */
                                        <div className={`p-4 rounded-[28px] border-2 shadow-sm ${adBg} ${adBorder}`}>
                                            <div className="flex justify-between items-start mb-2">
                                                <div className="flex items-center gap-2">
                                                    <span className="text-[9px] font-black bg-gray-900 text-white px-2 py-0.5 rounded-full uppercase">Sponsored AD</span>
                                                    <h3 className="font-black text-sm leading-tight">
                                                        {post.content.split('\n')[0]}
                                                    </h3>
                                                </div>
                                            </div>
                                            <p className="text-[12px] opacity-90 whitespace-pre-wrap leading-relaxed mt-2 mb-3">
                                                {post.content.split('\n').slice(1).join('\n')}
                                            </p>
                                            <div className="flex justify-between items-center pt-3 border-t border-black/5">
                                                <div className="flex gap-2">
                                                    <button
                                                        onClick={() => handleAdAction(post.id, 'like')}
                                                        className={`px-3 py-1.5 rounded-full text-[10px] font-black flex items-center gap-1 transition-all ${interaction?.is_liked ? 'bg-pink-500 text-white' : 'bg-white/70 text-gray-500 border border-gray-200'}`}
                                                    >
                                                        👍 {interaction?.is_liked ? 'イイネ済' : 'イイネ'}
                                                    </button>
                                                    <button
                                                        onClick={() => handleAdAction(post.id, 'pin')}
                                                        className={`px-3 py-1.5 rounded-full text-[10px] font-black flex items-center gap-1 transition-all ${interaction?.is_pinned ? 'bg-yellow-400 text-white' : 'bg-white/70 text-gray-500 border border-gray-200'}`}
                                                    >
                                                        📌 {interaction?.is_pinned ? 'PIN済' : 'PIN'}
                                                    </button>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    {post.ad_end_date && (
                                                        <span className="text-[9px] font-bold opacity-60">{post.ad_end_date.slice(0, 10)} 終了</span>
                                                    )}
                                                    <button
                                                        onClick={() => toggleAdCollapse(post.id)}
                                                        className="px-3 py-1.5 bg-white/70 border border-gray-200 rounded-full text-[10px] font-black text-gray-500"
                                                    >
                                                        ✕ 閉じる
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ) : post.is_meetup ? (
                                /* 🟠 MEETUP カード 完全復活版 */
                                <div className="space-y-2 mb-4">
                                    <div className={`p-3 rounded-[24px] border-2 shadow-sm bg-orange-50 border-orange-200 max-w-[95%] text-left`}>
                                        
                                        {/* 💡 1行目：開催名 & 日時 */}
                                        <div className="flex justify-between items-center mb-1.5 px-1">
                                            <h3 className="text-[13px] font-black text-orange-800 truncate flex-1 leading-tight">
                                                {post.content.split('\n')[0]}
                                            </h3>
                                            <div className="flex items-center gap-1 text-orange-700 font-black text-[11px] shrink-0 ml-4 leading-none">
                                                <Clock size={12} className="text-orange-500" />
                                                <span>
                                                    {post.meetup_date 
                                                        ? `${post.meetup_date.slice(5, 10).replace('-', '/')} ${post.meetup_date.slice(11, 16)}` 
                                                        : '日時未定'}
                                                </span>
                                            </div>
                                        </div>

                                        {/* 💡 2行目：場所 & 人数 & 費用 & ボタン */}
                                        <div className="flex items-center justify-between px-1">
                                            <div className="flex items-center gap-3">
                                                {/* 場所 */}
                                                <div className="flex items-center gap-1 text-[10px] text-gray-600 font-bold">
                                                    <MapPin size={11} className="text-orange-500" />
                                                    <span className="truncate max-w-[100px]">{post.meetup_location || '場所未定'}</span>
                                                </div>
                                                {/* 人数 & 費用 */}
                                                <div className="flex items-center gap-2 border-l pl-2 border-orange-200/50 text-[10px] text-gray-600 font-bold">
                                                    <Users size={11} className="text-orange-400" />
                                                    <span>{dbParticipants.length}/{post.meetup_capacity}人</span>
                                                    
                                                    <Coins size={11} className="text-orange-400 ml-1" />
                                                    <span className="text-orange-600 font-black">
                                                        {post.meetup_fee_info && !isNaN(Number(post.meetup_fee_info)) && Number(post.meetup_fee_info) > 0 ? (
                                                            <span className="flex items-center gap-1">
                                                                ¥{post.meetup_fee_info}
                                                                <span className="bg-blue-500 text-white px-1 rounded-[3px] text-[7px] italic font-black">STRIPE</span>
                                                            </span>
                                                        ) : (
                                                            post.meetup_fee_info || 'お茶代'
                                                        )}
                                                    </span>
                                                </div>
                                            </div>

                                            {/* ボタン類 */}
                                            <div className="flex gap-1.5">
                                                {(isJoined || isOwner) && (
                                                    <button 
                                                        onClick={() => setActiveChat({ id: post.id, title: post.content.split('\n')[0] })}
                                                        className="px-3 py-1 bg-blue-600 text-white rounded-full text-[9px] font-black shadow-sm flex items-center gap-1 hover:bg-blue-700 transition-colors"
                                                    >
                                                        <MessageSquare size={10} /> CHAT
                                                    </button>
                                                )}
                                                <button 
                                                    onClick={() => setExpandedThreads(p => { const n = new Set(p); n.has(post.id) ? n.delete(post.id) : n.add(post.id); return n; })} 
                                                    className="px-3 py-1 bg-orange-600 text-white rounded-full text-[9px] font-black shadow-sm hover:bg-orange-700 transition-colors"
                                                >
                                                    {isExpanded ? "CLOSE" : "DETAILS"}
                                                </button>
                                            </div>
                                        </div>
                                    </div>

                                    {/* 📖 詳細展開エリア（参加ボタン・参加者リストを含む） */}
                                    {isExpanded && (
                                        <div className="ml-4 p-4 bg-white rounded-3xl border border-orange-100 shadow-inner animate-in fade-in slide-in-from-top-1 text-left">
                                            <p className="text-[12px] text-gray-700 whitespace-pre-wrap mb-4 leading-relaxed">
                                                {post.content}
                                            </p>
                                            
                                            <div className="border-t border-orange-50 pt-3">
                                                <p className="text-[9px] font-black text-orange-400 mb-2 uppercase tracking-widest">Participants</p>
                                                <div className="flex flex-wrap gap-2 mb-4">
                                                    {allParticipants.map(p => (
                                                        <div key={p.id} className="flex items-center gap-1.5 bg-orange-50 px-3 py-1.5 rounded-full border border-orange-100">
                                                            {isOwner && p.id !== -1 && (
                                                                <button onClick={() => toggleAttendance(p.id).then(fetchPosts)} className="text-orange-500 hover:scale-110 transition-transform">
                                                                    {p.is_attended ? <CheckSquare size={14} /> : <Square size={14} />}
                                                                </button>
                                                            )}
                                                            <span className={`text-[11px] font-bold ${p.is_attended ? 'text-gray-400 line-through' : 'text-orange-900'}`}>
                                                                {p.author_nickname}
                                                                {p.id === -1 && <span className="ml-1 text-[8px] bg-orange-200 px-1 rounded text-orange-700">HOST</span>}
                                                            </span>
                                                        </div>
                                                    ))}
                                                </div>

                                                {/* 参加・キャンセル待ちボタン */}
                            {/* ✅ 参加者リストのすぐ下に続くロジック */}
                                                {!isJoined && !isOwner && (
                                                    dbParticipants.length < (post.meetup_capacity || 0) ? (
                                                        <button onClick={() => authApi.post(`/posts/${post.id}/responses`, { content: "Join!", is_participation: true }).then(fetchPosts)} 
                                                            className="w-full py-2.5 bg-orange-600 text-white rounded-xl text-[11px] font-black hover:bg-orange-700 shadow-md">
                                                            JOIN THIS MEETUP / 参加を希望する
                                                        </button>
                                                    ) : (
                                                        <button onClick={() => authApi.post(`/posts/${post.id}/responses`, { content: "Waitlist", is_participation: true }).then(fetchPosts)} 
                                                            className="w-full py-2.5 bg-gray-800 text-white rounded-xl text-[11px] font-black hover:bg-gray-900 shadow-md">
                                                            JOIN WAITLIST / キャンセル待ち
                                                        </button>
                                                    )
                                                )}
                                                
                                                {(isJoined || isOwner) && (
                                                    <div className="w-full py-2 bg-orange-100 text-orange-600 rounded-xl text-[11px] font-black text-center">
                                                        {isOwner ? "YOU ARE HOSTING THIS EVENT" : 
                                                        allParticipants.find(p => p.user_id === currentUserId)?.content === "Waitlist" ? "ON WAITLIST (キャンセル待ち中)" : "YOU ARE JOINED!"}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ) : (                                /* 通常チャット */
                                <div className="flex items-start gap-2 max-w-[85%] mb-4">
                                    <div className="bg-white p-4 rounded-3xl shadow-sm border border-gray-100">
                                        <span className="font-black text-[10px] text-pink-500 uppercase mb-1 block">{post.author_nickname}</span>
                                        <p className="text-gray-700 text-[13px] leading-relaxed">{post.content}</p>
                                    </div>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* 3. Footer */}
            <div className="flex-shrink-0 max-h-[55%] overflow-y-auto bg-white border-t border-gray-100 z-20 shadow-2xl p-3">
                <form onSubmit={handleSend}>
                    {postType === 'meetup' && (
                        <div className="bg-orange-50 border-2 border-orange-200 rounded-[28px] p-3 space-y-2 mb-3">
                            <div className="grid grid-cols-[1fr,auto] gap-2 pb-2 border-b border-orange-200/30">
                                <div className="flex flex-col"><label className="text-[9px] font-bold text-orange-800">開催名</label><input value={meetupDetails.title} onChange={e => setMeetupDetails({...meetupDetails, title: e.target.value})} className="px-2 py-1.5 rounded-xl border-2 border-orange-200 bg-white text-[13px] outline-none" /></div>
                                <div className="flex flex-col" style={{minWidth: '160px'}}><label className="text-[9px] font-bold text-orange-800">日時</label><input type="datetime-local" value={meetupDetails.date} onChange={e => setMeetupDetails({...meetupDetails, date: e.target.value})} className="px-2 py-1.5 rounded-xl border-2 border-orange-200 bg-white text-[13px] outline-none" /></div>
                            </div>
                            <div className="grid grid-cols-[120px,1fr] gap-2 pb-2 border-b border-orange-200/30">
                                <div className="flex flex-col"><label className="text-[9px] font-bold text-orange-800">都道府県</label><input value={meetupDetails.pref} onChange={e => setMeetupDetails({...meetupDetails, pref: e.target.value})} className="px-2 py-1.5 rounded-xl border-2 border-orange-200 bg-white text-[13px] outline-none" /></div>
                                <div className="flex flex-col"><label className="text-[9px] font-bold text-orange-800">市区町村</label><input value={meetupDetails.city_town} onChange={e => setMeetupDetails({...meetupDetails, city_town: e.target.value})} className="px-2 py-1.5 rounded-xl border-2 border-orange-200 bg-white text-[13px] outline-none" /></div>
                            </div>
                            <div className="grid grid-cols-2 gap-2 pb-2 border-b border-orange-200/30">
                                <div className="flex flex-col"><label className="text-[9px] font-bold text-orange-800">MAX定員</label><input type="number" value={meetupDetails.capacity} onChange={e => setMeetupDetails({...meetupDetails, capacity: parseInt(e.target.value) || 0})} className="px-2 py-1.5 rounded-xl border-2 border-orange-200 bg-white text-[13px] outline-none" /></div>
                                <div className="flex flex-col"><label className="text-[9px] font-bold text-orange-800 flex items-center gap-1">費用{meetupDetails.fee && <span className="bg-blue-500 text-white px-1 rounded-[4px] text-[7px] italic font-black">STRIPE</span>}</label><input value={meetupDetails.fee} onChange={e => setMeetupDetails({...meetupDetails, fee: e.target.value})} className="px-2 py-1.5 rounded-xl border-2 border-orange-200 bg-white text-[13px] outline-none" /></div>
                            </div>
                            <div className="flex flex-col gap-1">
                                <label className="text-[9px] font-bold text-orange-800">詳細</label>
                                <textarea value={newPost} onChange={e => setNewPost(e.target.value)} className="px-2 py-1.5 rounded-xl border-2 border-orange-200 bg-white text-[12px] h-[100px] resize-none outline-none leading-relaxed" />
                            </div>
                        </div>
                    )}
                    <div className="flex gap-2 items-end mb-3">
                        {postType === 'normal' && (
                            <textarea value={newPost} onChange={e => setNewPost(e.target.value)} placeholder="メッセージを入力..." className="flex-1 p-3 rounded-2xl bg-gray-50 border-2 border-transparent outline-none text-[13px] h-[90px] resize-none" />
                        )}
                        {postType === 'meetup' && <div className="flex-1" />}
                        <button type="submit" disabled={postType === 'normal' && !newPost.trim()} className="p-4 bg-gray-900 text-white rounded-2xl shrink-0 shadow-xl mb-1 disabled:opacity-40">
                            <Send size={20} />
                        </button>
                    </div>
                    <div className="flex gap-2">
                        <button type="button" onClick={() => switchPostType('normal')} className={`flex-1 py-2 rounded-xl text-[10px] font-black transition-all ${postType === 'normal' ? 'bg-gray-800 text-white shadow-md' : 'bg-gray-100 text-gray-400'}`}>CHAT</button>
                        <button type="button" onClick={() => switchPostType('meetup')} className={`flex-1 py-2 rounded-xl text-[10px] font-black transition-all ${postType === 'meetup' ? 'bg-orange-500 text-white shadow-md' : 'bg-orange-50 text-orange-300'}`}>MEETUP</button>
                        <button type="button" onClick={() => setShowAdModal(true)} className="flex-1 py-2 rounded-xl text-[10px] font-black transition-all bg-green-50 text-green-400 hover:bg-green-500 hover:text-white">AD</button>
                    </div>
                </form>
            </div>

            {activeChat && (
                <MeetupChatModal postId={activeChat.id} meetupTitle={activeChat.title} onClose={() => setActiveChat(null)} />
            )}
            {showAdModal && (
                <AdPostModal
                    currentCategoryId={parseInt(chatTargetId)}
                    currentCategoryName={currentCategoryName || ''}
                    onClose={() => setShowAdModal(false)}
                    onPosted={fetchPosts}
                />
            )}
{showSubChatModal && (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-[32px] shadow-2xl p-6 w-full max-w-sm space-y-4">
            <h3 className="text-sm font-black text-gray-800 flex items-center gap-2">
                <MessageSquare size={16} className="text-pink-500" />
                Sub Chat を作成
            </h3>

            {/* 名前入力 */}
            <input
                type="text"
                value={subChatName}
                onChange={(e) => handleSubChatNameChange(e.target.value)}
                placeholder="例：佐藤健、関東エリア、初心者歓迎..."
                className="w-full p-4 bg-gray-50 rounded-2xl text-sm outline-none focus:ring-2 focus:ring-pink-300"
                autoFocus
            />

            {/* 本尊の候補リスト */}
            {searchResults.length > 0 && (
                <div className="space-y-2">
                    <p className="text-[10px] font-black text-gray-400 uppercase">
                        既存の本尊が見つかりました
                    </p>
                    {searchResults.map((s) => (
                        <div key={s.id} className="flex justify-between items-center p-3 bg-pink-50 rounded-2xl">
                            <span className="text-xs font-bold text-gray-700">{s.name}</span>
                            <button
                                onClick={() => handleSelectMaster(s.id, s.name)}
                                className="text-[10px] bg-pink-500 text-white px-3 py-1 rounded-full font-black"
                            >
                                紐づける
                            </button>
                        </div>
                    ))}
                    <p className="text-[10px] text-gray-400 text-center pt-1">
                        該当しない場合はそのまま「作成する」を押してください
                    </p>
                </div>
            )}

                {/* 本尊が選択された場合の表示 */}
                    {selectedMasterId && (
                        <div className="flex items-center gap-2 p-3 bg-green-50 rounded-2xl border border-green-200">
                            <span className="text-[10px] font-black text-green-600">✅ 本尊：</span>
                            <span className="text-xs font-bold text-green-800">{selectedMasterName}</span>
                            <button
                                onClick={() => { setSelectedMasterId(null); setSelectedMasterName(''); }}
                                className="ml-auto text-[10px] text-gray-400 hover:text-red-400"
                            >
                                解除
                            </button>
                        </div>
                    )}

                    {/* タイプ選択 */}
                    <div className="space-y-2">
                        <p className="text-[10px] font-black text-gray-400 uppercase">タイプ（任意）</p>
                        <div className="flex gap-2">
                            {[
                                { value: 'DOERS', label: '🎸 Doers', desc: '実践者・演奏者' },
                                { value: 'FANS',  label: '💜 Fans',  desc: '推し・ファン' },
                            ].map((type) => (
                                <button
                                    key={type.value}
                                    type="button"
                                    onClick={() => setSelectedRoleType(
                                        selectedRoleType === type.value ? null : type.value
                                    )}
                                    className={`flex-1 py-2.5 rounded-2xl text-[11px] font-black transition-all border-2 ${
                                        selectedRoleType === type.value
                                            ? 'bg-pink-500 text-white border-pink-500'
                                            : 'bg-gray-50 text-gray-500 border-gray-100'
                                    }`}
                                >
                                    <div>{type.label}</div>
                                    <div className="text-[9px] opacity-70">{type.desc}</div>
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* ボタン */}
                    <div className="flex gap-2">
                        <button
                            onClick={() => {
                                setShowSubChatModal(false);
                                setSubChatName('');
                                setSelectedMasterId(null);
                                setSelectedMasterName('');
                                setSearchResults([]);
                            }}
                            className="flex-1 py-3 bg-gray-100 text-gray-500 rounded-2xl text-[12px] font-black"
                        >
                            キャンセル
                        </button>
                        <button
                            onClick={handleCreateSubChat}
                            disabled={!subChatName.trim() || isCreating}
                            className="flex-1 py-3 bg-pink-600 text-white rounded-2xl text-[12px] font-black disabled:opacity-40 hover:bg-pink-700 transition-colors"
                        >
                            {isCreating ? '作成中...' : '作成する'}
                        </button>
                    </div>
                </div>
            </div>
        )}
        {/* MEETUP投稿 支払い確認モーダル */}
        {showPaymentConfirm && (
            <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
                <div className="bg-white rounded-[32px] shadow-2xl p-6 w-full max-w-sm space-y-4">
                    
                    {/* タイトル */}
                    <h3 className="text-sm font-black text-gray-800 flex items-center gap-2">
                        <Coins size={16} className="text-orange-500" />
                        MEETUP投稿の確認
                    </h3>

                    {/* 投稿内容サマリー */}
                    <div className="bg-orange-50 rounded-2xl p-4 space-y-1">
                        <p className="text-[11px] font-black text-orange-800">{meetupDetails.title}</p>
                        {meetupDetails.date && (
                            <p className="text-[10px] text-orange-600">
                                📅 {meetupDetails.date.slice(0, 10).replace(/-/g, '/')}
                            </p>
                        )}
                        {meetupDetails.pref && (
                            <p className="text-[10px] text-orange-600">
                                📍 {meetupDetails.pref} {meetupDetails.city_town}
                            </p>
                        )}
                    </div>

                    {/* 料金説明 */}
                    <div className="bg-gray-50 rounded-2xl p-4 space-y-3">
                        <div className="flex justify-between items-center">
                            <span className="text-xs text-gray-600">MEETUP掲載料</span>
                            <span className="text-sm font-black text-gray-800">¥500</span>
                        </div>
                        <div className="border-t border-gray-200 pt-2 flex justify-between items-center">
                            <span className="text-xs font-black text-gray-800">合計</span>
                            <span className="text-base font-black text-orange-600">¥500</span>
                        </div>
                    </div>

                    {/* Stripe説明 */}
                    <p className="text-[10px] text-gray-400 text-center">
                        Stripeの安全な決済画面に移動します。
                    </p>

                    {/* ボタン */}
                    <div className="flex gap-2">
                        <button
                            onClick={() => setShowPaymentConfirm(false)}
                            className="flex-1 py-3 bg-gray-100 text-gray-500 rounded-2xl text-[12px] font-black"
                        >
                            キャンセル
                        </button>
                        <button
                            onClick={submitPost}
                            className="flex-1 py-3 bg-orange-500 text-white rounded-2xl text-[12px] font-black hover:bg-orange-600 transition-colors"
                        >
                            💳 ¥500 支払って投稿
                        </button>
                    </div>
                </div>
            </div>
        )}
        </div>
    );
};

export default CommunityChat;
