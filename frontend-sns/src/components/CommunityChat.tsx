import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { createPost, fetchPostsByCategory, Post, authApi, toggleAttendance, adInteraction, fetchMyAdInteractions, createSubCategory  } from '../api';
import { 
  Send, MessageSquare, MapPin, Users, CheckSquare, Square, Clock, Coins, Pin, Calendar, EyeOff, AlertTriangle
} from 'lucide-react';
import MeetupChatModal from './MeetupChatModal';
import AdPostModal from './AdPostModal';

interface CommunityChatProps {
    categoryId: string;
    masterId?: number | null;
    currentUserId: number;
    currentCategoryName?: string;
    isPublic?: boolean;
}

const BACKEND_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const CommunityChat: React.FC<CommunityChatProps> = ({
    categoryId: propCategoryId, masterId, currentUserId, currentCategoryName, isPublic }) => {
    const chatTargetId = masterId ? String(masterId) : propCategoryId;
    const communityId = propCategoryId; 
    const [communityInfo, setCommunityInfo] = useState<any>(null);
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
    const [subChatAnswers, setSubChatAnswers] = useState({
        period: '',      // 推し活動期間
        baseCountry: '', // 推しのベースの国
        noHarm: false,   // 傷つく人はいないか
        noHarassment: false, // ハラスメント等に関わっていないか
        correctParent: false, // 親との関係は正しいか
    });
    // 1. 通報 (バックエンドの段階的制限を叩く)
    const handleReportPost = async (postId: number) => {
        if (!window.confirm("この投稿を不適切として通報しますか？\n(通報が重なると自動的に非表示になります)")) return;
        try {
            await authApi.post(`/posts/${postId}/report`, { reason: "User reported" });
            alert("通報を受け付けました。ご協力ありがとうございます。");
            fetchPosts(); // 非表示が発動したかもしれないので再取得
        } catch (err: any) {
            alert(err.response?.data?.detail || "通報に失敗しました。");
        }
    };

    // 2. ローカル非表示 (とりあえず今の画面から消す)
    const handleLocalHide = (postId: number) => {
        if (!window.confirm("この投稿を非表示にしますか？\n(リロードするまで表示されなくなります)")) return;
        setPosts(prev => prev.filter(p => p.id !== postId));
    };

    const MEETUP_TEMPLATE = `📍 集合場所：

📍 開催場所： 住所・ZOOM開催

🗺️ 開催場所 MapURL 又はURL：

💰【支払い方法】： 当日現金 / アプリ（Stripe）決済 / お茶代のみ各自
※カフェ開催のためお茶代が必要です。

❌【キャンセルポリシー】： アプリ（Stripe）決済の場合
    当日0時以降のキャンセル50%、NoShow100%`;

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
    const fetchCommunityDetail = async (id: string) => {
        const res = await authApi.get(`/communities/${id}`);
        return res.data;
    };
 
    // 🔄 リロード時やデータ更新時に、PIN済みのものをリストに復元する
    useEffect(() => {
        if (posts.length > 0) {
            // 全投稿の中から、interactionデータで is_pinned が true のものを抽出
            const pinned = posts.filter(post => adInteractions[post.id]?.is_pinned);
            setPinnedAds(pinned);
        }
    }, [posts, adInteractions]); // posts か adInteractions が変わるたびに実行
   
    useEffect(() => {
    if (posts.length > 0) {
        const pinned = posts.filter(post => adInteractions[post.id]?.is_pinned);
        setPinnedAds(pinned);
    }
}, [posts, adInteractions]);

useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const meetupSessionId = params.get('meetup_session_id');
    const meetupCancelled = params.get('meetup_cancelled');
    const adSessionId = params.get('ad_session_id');
    const adCancelled = params.get('ad_cancelled');

    if (meetupSessionId) {
        fetch(`${BACKEND_URL}/api/stripe/meetup-activate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sessionId: meetupSessionId }),
        })
        .then(res => res.json())
        .then(() => {
            alert('🎉 お支払い完了！MEET UPを楽しんで！');
            window.history.replaceState({}, '', window.location.pathname);
            fetchPosts();
        })
        .catch(() => alert('アクティベートに失敗しました'));
    }

    if (meetupCancelled) {
        alert('決済がキャンセルされました。投稿は保存されていません。');
        window.history.replaceState({}, '', window.location.pathname);
    }

    if (adSessionId) {
        fetch(`${BACKEND_URL}/api/stripe/ad-activate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sessionId: adSessionId }),
        })
        .then(res => res.json())
        .then(() => {
            alert('🎉 AD掲載完了！');
            window.history.replaceState({}, '', window.location.pathname);
            fetchPosts();
        })
        .catch(() => alert('ADのアクティベートに失敗しました'));
    }

    if (adCancelled) {
        alert('決済がキャンセルされました。');
        window.history.replaceState({}, '', window.location.pathname);
    }
}, []);

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
        setSubChatAnswers({ period: '', baseCountry: '', noHarm: false, noHarassment: false, correctParent: false });
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

    if (isMeetup) {
        // MEETUPはStripe経由
        try {
            const res = await fetch(`${BACKEND_URL}/api/stripe/meetup-checkout`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    userId: currentUserId,
                    postData: {
                        content: `${meetupDetails.title}\n${newPost}`,
                        hobby_category_id: parseInt(chatTargetId),
                        meetup_date: meetupDetails.date || null,
                        meetup_location: `${meetupDetails.pref || ''} ${meetupDetails.city_town || ''}`.trim(),
                        meetup_capacity: meetupDetails.capacity || 0,
                        meetup_fee_info: meetupDetails.fee || null,
                    }
                }),
            });
            const { url } = await res.json();
            window.location.href = url; // Stripeへリダイレクト
        } catch (err) {
            console.error('Stripe エラー:', err);
            alert("決済の開始に失敗しました");
        }
        return;
    }

    // 通常投稿・AD投稿はそのまま
    try {
        await createPost({
            content: newPost,
            hobby_category_id: parseInt(chatTargetId),
            is_meetup: false,
            is_ad: postType === ('ad' as string),
            is_system: false,
        });
        setNewPost('');
        setPostType('normal');
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

    const allParentPosts = posts.filter(p => {
        if (p.parent_id) return false;
        if (p.is_meetup && p.meetup_date && new Date(p.meetup_date) < new Date()) return false;
        return true;
    });

    // 2. その中で「システム投稿(ガイド)」と「通常の投稿」に分けて並び替える
    const parentPosts = [
        ...allParentPosts.filter(p => p.is_system), // 💡 ガイドを一番上へ
        ...allParentPosts.filter(p => !p.is_system) // 💡 通常の投稿をその下へ
    ];

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
                    {posts.filter(p => p.is_meetup 
                        && (p.user_id === currentUserId || adInteractions[p.id]?.is_attended)
                        && (!p.meetup_date || new Date(p.meetup_date) > new Date())
                    ).map(meetup => (
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
                                                    👍 Vibe
                                                </button>
                                                <button
                                                    onClick={() => handleAdAction(post.id, 'pin')}
                                                    className={`px-2 py-1 rounded-full text-[9px] font-black transition-all ${interaction?.is_pinned ? 'bg-yellow-400 text-white' : 'bg-white/70 text-gray-400 border border-gray-200'}`}
                                                >
                                                    📌 PIN
                                                </button>
                                                {post.ad_end_date && (
                                                    <span className="text-[9px] text-gray-400 ml-auto">〜{post.ad_end_date.slice(0, 10)}</span>
                                                )}
                                            </div>
                                        </div>
                                    ) : (
                                    /* フル表示 */
                                    <div className={`p-4 rounded-[28px] border-2 shadow-sm ${adBg} ${adBorder}`}>

                                        {/* ★ 投稿者名（上部：アイコン＋名義＋ADラベル） */}
                                        <div className="flex items-center gap-1.5 mb-2">
                                            <span className="text-[8px] font-black bg-gray-900 text-white px-1.5 py-0.5 rounded-full uppercase shrink-0">AD</span>
                                            <div className="w-5 h-5 rounded-full bg-black/10 flex items-center justify-center text-[9px] font-black shrink-0">
                                                {(post.author_nickname || '?').charAt(0).toUpperCase()}
                                            </div>
                                            <span className="text-[10px] font-bold opacity-60 truncate">
                                                {post.author_nickname || 'Unknown'}
                                            </span>
                                        </div>

                                        {/* タイトル */}
                                        <h3 className="font-black text-sm leading-tight mb-2">
                                            {post.content.split('\n')[0]}
                                        </h3>

                                        {/* 本文 */}
                                        <p className="text-[12px] opacity-90 whitespace-pre-wrap leading-relaxed mb-3">
                                            {post.content.split('\n').slice(1).join('\n')}
                                        </p>

                                        {/* 💡 広告主専用：編集・追記メニュー（本人にのみ表示） */}
                                        {post.user_id === currentUserId && (
                                            <div className="mb-3 pt-2 border-t border-dashed border-black/10">
                                                <button 
                                                    type="button"
                                                    onClick={async () => {
                                                        const addText = window.prompt("追記する内容を入力してください：");
                                                        if (addText && addText.trim()) {
                                                            try {
                                                                const updatedContent = `${post.content}\n\n📌 追記：${addText.trim()}`;
                                                                await authApi.patch(`/posts/${post.id}`, { content: updatedContent });
                                                                fetchPosts();
                                                            } catch (err) {
                                                                alert("追記に失敗しました。");
                                                            }
                                                        }
                                                    }}
                                                    className="text-[8px] font-black text-blue-600 hover:text-blue-800 flex items-center gap-1"
                                                >
                                                    <CheckSquare size={12} /> 文言を追記する
                                                </button>
                                            </div>
                                        )}

                                        {/* フッター：日付とアクションボタン */}
                                        <div className="pt-3 border-t border-black/5 space-y-1">
                                            {post.ad_end_date && (
                                                <span className="text-[9px] font-bold opacity-60 block">{post.ad_end_date.slice(0, 10)} 終了</span>
                                            )}
                                            <div className="flex gap-2 items-center">
                                                <button
                                                    type="button"
                                                    onClick={() => handleAdAction(post.id, 'like')}
                                                    className={`px-3 py-1.5 rounded-full text-[10px] font-black flex items-center gap-1 transition-all ${interaction?.is_liked ? 'bg-pink-500 text-white' : 'bg-white/70 text-gray-500 border border-gray-200'}`}
                                                >
                                                    👍 Vibe
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => handleAdAction(post.id, 'pin')}
                                                    className={`px-3 py-1.5 rounded-full text-[10px] font-black flex items-center gap-1 transition-all ${interaction?.is_pinned ? 'bg-yellow-400 text-white' : 'bg-white/70 text-gray-500 border border-gray-200'}`}
                                                >
                                                    📌 PIN
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => toggleAdCollapse(post.id)}
                                                    className="px-3 py-1.5 bg-white/70 border border-gray-200 rounded-full text-[10px] font-black text-gray-500 ml-auto"
                                                >
                                                    ✕
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                    )}
                                </div>
                            ) : post.is_meetup ? (
                                /* 🟠 MEETUP カード 完全復活版 */
                                <div className="space-y-2 mb-4">
                                    <div className={`p-3 rounded-[24px] border-2 shadow-sm bg-orange-50 border-orange-200 text-left`}>
                                        
                                        {/* 💡 1行目：開催名 & 日時 */}
                                        <div className="flex justify-between items-center mb-1.5 px-1">
                                            <h3 className="text-[13px] font-black text-orange-800 truncate flex-1 leading-tight">
                                                {post.content.split('\n')[0]}
                                            </h3>
                                            <div className="flex items-center gap-1 text-orange-700 font-black text-[11px] shrink-0 leading-none">
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
                                            <div className="flex flex-col gap-1">
                                                {/* 場所 */}
                                                <div className="flex items-center gap-1 text-[10px] text-gray-600 font-bold">
                                                    <MapPin size={11} className="text-orange-500" />
                                                    <span className="truncate max-w-[180px]">{post.meetup_location || '場所未定'}</span>
                                                </div>
                                                {/* 人数 & 費用 */}
                                                <div className="flex items-center gap-2 text-[10px] text-gray-600 font-bold">
                                                    <Users size={11} className="text-orange-400" />
                                                    <span>{dbParticipants.length}/{post.meetup_capacity}人</span>
                                                    <Coins size={11} className="text-orange-400" />
                                                    <span className="text-orange-600 font-black text-[10px]">
                                                        {post.meetup_fee_info && !isNaN(Number(post.meetup_fee_info)) && Number(post.meetup_fee_info) > 0 
                                                            ? `¥${post.meetup_fee_info}` 
                                                            : (post.meetup_fee_info || 'お茶代')}
                                                    </span>
                                                </div>
                                            </div>

                                            {/* ボタン類 */}
                                            <div className="flex flex-col gap-1 items-end">
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
                                        <div className="p-4 bg-white rounded-3xl border border-orange-100 shadow-inner animate-in fade-in slide-in-from-top-1 text-left">
                                        <p className="text-[12px] text-gray-700 whitespace-pre-wrap mb-4 leading-relaxed">
                                            {post.content}
                                        </p>

                                        {/* 💡 主催者専用：文言追記ボタン */}
                                        {isOwner && (
                                            <div className="mb-3 pb-3 border-b border-dashed border-orange-200">
                                                <button
                                                    type="button"
                                                    onClick={async () => {
                                                        const addText = window.prompt("追記する内容を入力してください：");
                                                        if (addText && addText.trim()) {
                                                            try {
                                                                const updatedContent = `${post.content}\n\n📌 追記：${addText.trim()}`;
                                                                await authApi.patch(`/posts/${post.id}`, { content: updatedContent });
                                                                fetchPosts();
                                                            } catch (err) {
                                                                alert("追記に失敗しました。");
                                                            }
                                                        }
                                                    }}
                                                    className="text-[9px] font-black text-blue-600 hover:text-blue-800 flex items-center gap-1"
                                                >
                                                    <CheckSquare size={12} /> 文言を追記する
                                                </button>
                                            </div>
                                        )}

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
                                                        <button
                                                            onClick={async () => {
                                                                // まずpost_responsesにレコード作成
                                                                await authApi.post(`/posts/${post.id}/responses`, {
                                                                    content: "Join!", is_participation: true
                                                                });
                                                                // 参加費が数値でありかつ0より大きい場合→カード登録へ
                                                                const fee = Number(post.meetup_fee_info);
                                                                if (post.meetup_fee_info && !isNaN(fee) && fee > 0) {
                                                                    const res = await fetch(`${BACKEND_URL}/api/stripe/meetup-join-setup`, {
                                                                        method: 'POST',
                                                                        headers: { 'Content-Type': 'application/json' },
                                                                        body: JSON.stringify({
                                                                            userId: currentUserId,
                                                                            postId: post.id,
                                                                            categoryId: chatTargetId,
                                                                        }),
                                                                    });
                                                                    const { checkout_url } = await res.json();
                                                                    window.location.href = checkout_url;
                                                                } else {
                                                                    // 参加費なし → そのまま参加完了
                                                                    fetchPosts();
                                                                }
                                                            }}
                                                            className="w-full py-2.5 bg-orange-600 text-white rounded-xl text-[11px] font-black hover:bg-orange-700 shadow-md"
                                                        >
                                                            JOIN THIS MEETUP / 参加を希望する
                                                        </button>
                                                    ) : (
                                                        <button
                                                            onClick={() => authApi.post(`/posts/${post.id}/responses`, {
                                                                content: "Waitlist", is_participation: true
                                                            }).then(fetchPosts)}
                                                            className="w-full py-2.5 bg-gray-800 text-white rounded-xl text-[11px] font-black hover:bg-gray-900 shadow-md"
                                                        >
                                                            JOIN WAITLIST / キャンセル待ち
                                                        </button>
                                                    )
                                                )}
                                                
                                                {(isJoined || isOwner) && (
                                                <div className="space-y-2">
                                                    {/* 参加者向け：キャンセルボタン */}
                                                    {isJoined && !isOwner && (
                                                        <button
                                                            onClick={async () => {
                                                                if (!window.confirm("キャンセルしますか？\n当日0時以降は参加費の50%が発生します。")) return;
                                                                try {
                                                                    const res = await fetch(`${BACKEND_URL}/api/stripe/meetup-cancel`, {
                                                                        method: 'POST',
                                                                        headers: { 'Content-Type': 'application/json' },
                                                                        body: JSON.stringify({
                                                                            userId: currentUserId,
                                                                            postId: post.id,
                                                                        }),
                                                                    });
                                                                    const result = await res.json();
                                                                    if (result.cancel_fee > 0) {
                                                                        alert(`キャンセル料 ¥${result.cancel_fee} が発生しました。`);
                                                                    } else {
                                                                        alert("キャンセルしました。");
                                                                    }
                                                                    if (result.waitlist_user) {
                                                                        alert(`キャンセル待ち中の ${result.waitlist_user.nickname} さんに通知しました。`);
                                                                    }
                                                                    fetchPosts();
                                                                } catch {
                                                                    alert("キャンセルに失敗しました。");
                                                                }
                                                            }}
                                                            className="w-full py-2 bg-gray-100 text-gray-500 rounded-xl text-[11px] font-black hover:bg-red-50 hover:text-red-400 transition-colors"
                                                        >
                                                            キャンセルする
                                                        </button>
                                                    )}

                                                    {/* ステータス表示 */}
                                                    <div className={`w-full py-2 rounded-xl text-[11px] font-black text-center ${
                                                        isOwner ? 'bg-orange-100 text-orange-600' : 'bg-green-50 text-green-600'
                                                    }`}>
                                                        {isOwner ? "YOU ARE HOSTING THIS EVENT" :
                                                        allParticipants.find(p => p.user_id === currentUserId)?.content === "Waitlist"
                                                            ? "ON WAITLIST (キャンセル待ち中)" : "YOU ARE JOINED! ✅"}
                                                    </div>

                                                    {/* 主催者向けボタン群 */}
                                                    {isOwner && (
                                                        <div className="space-y-2 pt-2 border-t border-orange-100">
                                                            {/* 文言追記 */}
                                                            <button
                                                                type="button"
                                                                onClick={async () => {
                                                                    const addText = window.prompt("追記する内容を入力してください：");
                                                                    if (addText && addText.trim()) {
                                                                        try {
                                                                            const updatedContent = `${post.content}\n\n📌 追記：${addText.trim()}`;
                                                                            await authApi.patch(`/posts/${post.id}`, { content: updatedContent });
                                                                            fetchPosts();
                                                                        } catch {
                                                                            alert("追記に失敗しました。");
                                                                        }
                                                                    }
                                                                }}
                                                                className="w-full py-2 bg-blue-50 text-blue-600 rounded-xl text-[11px] font-black hover:bg-blue-100 transition-colors flex items-center justify-center gap-1"
                                                            >
                                                                <CheckSquare size={12} /> 文言を追記する
                                                            </button>

                                                            {/* 開催決定 */}
                                                            {!post.meetup_confirmed_at && (
                                                                <button
                                                                    onClick={async () => {
                                                                        if (!window.confirm("開催を決定しますか？\n参加費ありの参加者に課金が発生します。")) return;
                                                                        try {
                                                                            const res = await fetch(`${BACKEND_URL}/api/stripe/meetup-confirm`, {
                                                                                method: 'POST',
                                                                                headers: { 'Content-Type': 'application/json' },
                                                                                body: JSON.stringify({
                                                                                    postId: post.id,
                                                                                    organizerId: currentUserId,
                                                                                }),
                                                                            });
                                                                            const result = await res.json();
                                                                            alert(`✅ 開催決定！${result.charged > 0 ? ` ${result.charged}名に課金しました。` : ' 参加費なし。'}`);
                                                                            fetchPosts();
                                                                        } catch {
                                                                            alert("開催決定に失敗しました。");
                                                                        }
                                                                    }}
                                                                    className="w-full py-2 bg-orange-500 text-white rounded-xl text-[11px] font-black hover:bg-orange-600 transition-colors"
                                                                >
                                                                    🎉 開催決定する
                                                                </button>
                                                            )}

                                                            {/* 開催済み表示 */}
                                                            {post.meetup_confirmed_at && (
                                                                <div className="w-full py-2 bg-green-500 text-white rounded-xl text-[11px] font-black text-center">
                                                                    ✅ 開催決定済み
                                                                </div>
                                                            )}

                                                            {/* No Show報告（参加者個別）は MeetupChatModal側で対応 */}
                                                        </div>
                                                    )}
                                                </div>
                                            )}
                                            </div>
                                        </div>
                                    )}
                                </div>
                                /* --- 既存コードの 340行目付近（通常チャットの開始部分） --- */
                                ) : ( /* 通常チャット */
                                    <div className="flex items-start gap-2 max-w-[85%] mb-4 group relative">
                                        {/* 💡 is_system が true なら背景を green-50（薄いグリーン）にする */}
                                        <div className={`${post.is_system ? 'bg-green-50 border-green-200 shadow-green-100' : 'bg-white border-gray-100'} p-4 rounded-3xl shadow-sm border min-w-[140px]`}>
                                            
                                            <div className="flex justify-between items-start mb-1">
                                                {/* 💡 システム投稿なら「OFFICIAL GUIDE」ラベルとピンを表示、そうでなければニックネーム */}
                                                {post.is_system ? (
                                                    <div className="flex items-center gap-1">
                                                        <Pin size={12} className="text-amber-500 fill-amber-500" />
                                                        <span className="font-black text-[10px] text-amber-600 uppercase block tracking-widest">
                                                            Official Guide
                                                        </span>
                                                    </div>
                                                ) : (
                                                    <span className="font-black text-[10px] text-pink-500 uppercase block">
                                                        {post.author_nickname}
                                                    </span>
                                                )}

                                                {/* 🛡️ 安全機能ボタン（ホバー時に現れる） */}
                                                <div className="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity ml-4">
                                                    <button 
                                                        onClick={() => handleLocalHide(post.id)}
                                                        className="p-1 hover:bg-gray-100 rounded-full text-gray-300 hover:text-gray-600 transition-colors"
                                                        title="自分だけに非表示"
                                                    >
                                                        <EyeOff size={12} />
                                                    </button>
                                                    
                                                    <button 
                                                        onClick={() => handleReportPost(post.id)}
                                                        className="p-1 hover:bg-red-50 rounded-full text-gray-300 hover:text-red-400 transition-colors"
                                                        title="通報する"
                                                    >
                                                        <AlertTriangle size={12} />
                                                    </button>
                                                </div>
                                            </div>
                                            
                                            <p className="text-gray-700 text-[13px] leading-relaxed whitespace-pre-wrap">{post.content}</p>
                                        </div>
                                    </div>
                                )}                        </div>
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
                                <div className="flex flex-col">
        <label className="text-[9px] font-bold text-orange-800 flex items-center gap-1">
            参加費用（アプリ決済）{meetupDetails.fee && <span className="bg-blue-500 text-white px-1 rounded-[4px] text-[7px] italic font-black">STRIPE</span>}
        </label>
        <input 
            value={meetupDetails.fee} 
            onChange={e => setMeetupDetails({...meetupDetails, fee: e.target.value})} 
            placeholder="金額入力でアプリ決済 / 空欄で詳細に記載"
            className="px-2 py-1.5 rounded-xl border-2 border-orange-200 bg-white text-[13px] outline-none" 
        />
    </div>
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
                        {/* ★ isPublic が false の時だけ MEETUP を表示 */}
                        {!isPublic && (
                        <button type="button" onClick={() => switchPostType('meetup')} className={`flex-1 py-2 rounded-xl text-[10px] font-black transition-all ${postType === 'meetup' ? 'bg-orange-500 text-white shadow-md' : 'bg-orange-50 text-orange-300'}`}>MEETUP</button>
                        )}
                        {/* ★ isPublic が false の時だけ AD を表示 */}
                        {!isPublic && (
                        <button type="button" onClick={() => setShowAdModal(true)} className="flex-1 py-2 rounded-xl text-[10px] font-black transition-all bg-green-50 text-green-400 hover:bg-green-500 hover:text-white">AD</button>
                        )}
                    </div>
                </form>
            </div>

            {activeChat && (
                <MeetupChatModal
                    postId={activeChat.id}
                    meetupTitle={activeChat.title}
                    onClose={() => setActiveChat(null)}
                    currentUserId={currentUserId}
                    isOrganizer={posts.find(p => p.id === activeChat.id)?.user_id === currentUserId}
                />
            )}
            {showAdModal && (
            <AdPostModal
                profile={{ id: currentUserId }}  // ← これを追加
                currentCategoryId={parseInt(chatTargetId)}
                currentCategoryName={currentCategoryName || ''}
                onClose={() => setShowAdModal(false)}
                onPosted={fetchPosts}
            />
        )}
{showSubChatModal && (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-[32px] shadow-2xl p-6 w-full max-w-sm space-y-4 max-h-[90vh] overflow-y-auto">
            <h3 className="text-sm font-black text-gray-800 flex items-center gap-2">
                <MessageSquare size={16} className="text-pink-500" />
                Sub Chat を作成
            </h3>

            {/* GUIDEへの案内 */}
            <p className="text-[11px] text-gray-400 leading-relaxed">
                新しいカテゴリーの追加をご希望の場合は、
                <Link to="/community/6" className="text-pink-500 font-bold underline">GUIDE</Link>
                のお問い合わせからご申請ください。
            </p>

            {/* 名前入力 */}
            <div className="space-y-1">
                <p className="text-[10px] font-black text-gray-400 uppercase">推しの正式名で入力ください</p>
                <input
                    type="text"
                    value={subChatName}
                    onChange={(e) => handleSubChatNameChange(e.target.value)}
                    placeholder="例：佐藤健、関東エリア、初心者歓迎..."
                    className="w-full p-4 bg-gray-50 rounded-2xl text-sm outline-none focus:ring-2 focus:ring-pink-300"
                    autoFocus
                />
            </div>

            {/* 本尊の候補リスト */}
            {searchResults.length > 0 && (
                <div className="space-y-2">
                    <p className="text-[10px] font-black text-gray-400 uppercase">既存の本尊が見つかりました</p>
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

            {/* 本尊が選択された場合 */}
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
                            onClick={() => setSelectedRoleType(selectedRoleType === type.value ? null : type.value)}
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

            {/* 質問フォーム */}
            <div className="bg-pink-50 rounded-2xl p-4 space-y-3 border border-pink-100">
                <p className="text-[10px] font-black text-pink-600 uppercase tracking-widest">作成前の確認</p>
                
                <div className="space-y-1">
                    <label className="text-[11px] font-bold text-gray-700">ファン歴 / Fan Period</label>
                    <select
                        value={subChatAnswers.period}
                        onChange={e => setSubChatAnswers({...subChatAnswers, period: e.target.value})}
                        className="w-full p-2 rounded-xl border border-pink-200 bg-white text-[12px] outline-none"
                    >
                        <option value="">選択 / Select</option>
                        <option value="1年未満"> Less than 1yr </option>
                        <option value="1〜3年"> 1-3yrs </option>
                        <option value="3〜5年"> 3-5yrs </option>
                        <option value="5年以上"> More than 5yrs</option>
                    </select>
                </div>

                <div className="space-y-1">
                    <label className="text-[11px] font-bold text-gray-700">活動拠点 / Base Country</label>
                    <input
                        type="text"
                        value={subChatAnswers.baseCountry}
                        onChange={e => setSubChatAnswers({...subChatAnswers, baseCountry: e.target.value})}
                        placeholder="例：日本、한국（韓国）、US、UK..."
                        className="w-full p-2 rounded-xl border border-pink-200 bg-white text-[12px] outline-none"
                    />
                </div>

                <div className="space-y-2 pt-1">
                    {[
                        { key: 'noHarm', label: '誰も傷つけない / No one will be hurt' },
                        { key: 'noHarassment', label: '嫌がらせ禁止 / No harassment' },
                        { key: 'correctParent', label: '親カテゴリの確認 / Category is correct' },
                    ].map(item => (
                        <label key={item.key} className="flex items-start gap-2 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={subChatAnswers[item.key as keyof typeof subChatAnswers] as boolean}
                                onChange={e => setSubChatAnswers({...subChatAnswers, [item.key]: e.target.checked})}
                                className="mt-0.5 accent-pink-500"
                            />
                            <span className="text-[11px] text-gray-600">{item.label}</span>
                        </label>
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
                        setSubChatAnswers({ period: '', baseCountry: '', noHarm: false, noHarassment: false, correctParent: false });
                    }}
                    className="flex-1 py-3 bg-gray-100 text-gray-500 rounded-2xl text-[12px] font-black"
                >
                    キャンセル
                </button>
                <button
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
