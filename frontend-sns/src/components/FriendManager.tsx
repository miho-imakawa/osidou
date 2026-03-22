import React, { useState, useEffect, useCallback } from 'react';
import {
    searchUsers,
    sendFriendRequest,
    fetchFriendRequests,
    acceptFriendRequest,
    rejectFriendRequest,
    fetchMyFriends,
    UserProfileType,
    FriendRequest
} from '../api';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { authApi } from '../api';

/* ======================
   ユーザー検索
====================== */
const UserSearch: React.FC<{ currentUserId: number | null }> = ({ currentUserId }) => {
    const [searchQuery, setSearchQuery] = useState('');
    const [results, setResults] = useState<UserProfileType[]>([]);
    const [loading, setLoading] = useState(false);
    const [status, setStatus] = useState<Record<number, 'sent' | 'pending'>>({});

    const handleSearch = async () => {
        if (!searchQuery.trim()) return;
        setLoading(true);
        try {
            const res = await searchUsers(searchQuery);
            setResults(res);
        } finally {
            setLoading(false);
        }
    };

    const handleSend = async (receiverId: number, name: string) => {
        if (status[receiverId]) return;
        setStatus(prev => ({ ...prev, [receiverId]: 'pending' }));

        try {
            await sendFriendRequest(receiverId);
            setStatus(prev => ({ ...prev, [receiverId]: 'sent' }));
            alert(`${name} に申請しました`);
        } catch (err: any) {
            if (err.response?.status === 402 && err.response.data.detail?.requires_setup) {
                // 人数超過 → SetupIntent（カード登録）へ誘導
                const { msg } = err.response.data.detail;

                if (window.confirm(`${msg}\n\nカード登録画面に移動しますか？`)) {
                    try {
                        const res = await authApi.post('/api/stripe/friend-manager-setup-intent', {
                            requesterId: currentUserId,
                            receiverId:  receiverId,
                        });
                        if (res.data.checkout_url) {
                            window.location.href = res.data.checkout_url;
                        }
                    } catch {
                        alert('エラーが発生しました。もう一度お試しください。');
                    }
                } else {
                    // キャンセル時はボタンをリセット
                    setStatus(prev => {
                        const next = { ...prev };
                        delete next[receiverId];
                        return next;
                    });
                }
            } else {
                setStatus(prev => {
                    const next = { ...prev };
                    delete next[receiverId];
                    return next;
                });
                alert('送信に失敗しました');
            }
        }
    };

    return (
        <>
            <div className="flex gap-2 mb-6">
                <input
                    className="flex-grow border p-2 rounded"
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleSearch()}
                    placeholder="ユーザー検索"
                />
                <button onClick={handleSearch} className="bg-pink-500 text-white px-4 rounded">
                    検索
                </button>
            </div>

            <ul className="divide-y bg-white rounded shadow">
                {results.map(u => (
                    <li key={u.id} className="p-4 flex justify-between">
                        <div>
                            <p className="font-bold">{u.nickname || u.username}</p>
                            <p className="text-sm text-gray-500">{u.email}</p>
                        </div>
                        <button
                            onClick={() => handleSend(u.id, u.nickname || u.username)}
                            disabled={!!status[u.id]}
                            className="bg-pink-100 px-3 py-1 rounded disabled:opacity-50"
                        >
                            {status[u.id] === 'sent'    ? '申請済み'  :
                             status[u.id] === 'pending' ? '送信中...' : 'フレンド申請'}
                        </button>
                    </li>
                ))}
            </ul>
        </>
    );
};

/* ======================
   承認待ち
====================== */
const RequestList: React.FC = () => {
    const [requests, setRequests] = useState<FriendRequest[]>([]);
    const [processing, setProcessing] = useState<Record<number, boolean>>({});

    const load = async () => {
        const res = await fetchFriendRequests();
        setRequests(res);
    };

    useEffect(() => { load(); }, []);

    const handleAccept = async (requestId: number) => {
        if (processing[requestId]) return;
        setProcessing(prev => ({ ...prev, [requestId]: true }));
        try {
            // 承認する → バックエンドが申請者のサブスクを自動開始
            await acceptFriendRequest(requestId);
            alert('承認しました！');
            load();
        } catch (err: any) {
            alert('エラーが発生しました。');
        } finally {
            setProcessing(prev => ({ ...prev, [requestId]: false }));
        }
    };

    const handleReject = async (requestId: number) => {
        if (processing[requestId]) return;
        setProcessing(prev => ({ ...prev, [requestId]: true }));
        try {
            // 拒否する → 課金なし。SetupIntentはStripe側で自然失効。
            await rejectFriendRequest(requestId);
            load();
        } catch {
            alert('エラーが発生しました。');
        } finally {
            setProcessing(prev => ({ ...prev, [requestId]: false }));
        }
    };

    if (requests.length === 0) {
        return <p className="text-gray-500 text-sm p-4">承認待ちの申請はありません。</p>;
    }

    return (
        <ul className="divide-y bg-white rounded shadow">
            {requests.map(r => (
                <li key={r.id} className="p-4 flex justify-between items-center">
                    <p>
                        <Link to={`/profile/${r.requester.id}`} className="text-pink-500">
                            {r.requester.nickname || r.requester.username}
                        </Link>
                        さんからの申請
                    </p>
                    <div className="space-x-2">
                        <button
                            className="bg-pink-500 text-white px-3 py-1 rounded text-sm disabled:opacity-50"
                            onClick={() => handleAccept(r.id)}
                            disabled={!!processing[r.id]}
                        >
                            {processing[r.id] ? '処理中...' : '承認'}
                        </button>
                        <button
                            className="px-3 py-1 rounded text-sm border disabled:opacity-50"
                            onClick={() => handleReject(r.id)}
                            disabled={!!processing[r.id]}
                        >
                            拒否
                        </button>
                    </div>
                </li>
            ))}
        </ul>
    );
};

/* ======================
   フレンド一覧
====================== */
const FriendList: React.FC = () => {
    const [friends, setFriends] = useState<any[]>([]);
    const [editingNotes, setEditingNotes] = useState<Record<number, string>>({});

    const load = async () => {
        const res = await fetchMyFriends();
        setFriends(res);
    };

    useEffect(() => { load(); }, []);

    const handleSaveNote = async (friendshipId: number) => {
        const note = editingNotes[friendshipId];
        if (note === undefined) return;
        try {
            await authApi.put(`/friends/friendships/${friendshipId}`, { friend_note: note });
            alert('メモを保存しました');
            load();
        } catch {
            alert('保存に失敗しました');
        }
    };

    const handleDelete = async (friendshipId: number) => {
        // 💡 確認ダイアログを追加
        if (!window.confirm('ともだちを解除しますか？\n解除しても相手には通知されません。')) return;

        try {
            await authApi.delete(`/friends/friendships/${friendshipId}`);
            // リロードして一覧を更新
            load();
        } catch {
            alert('解除に失敗しました');
        }
    };

    return (
        <ul className="divide-y bg-white rounded shadow">
            {friends.map(f => (
                <li key={f.id} className="p-4 flex justify-between items-center">
                    <div className="flex-grow mr-4">
                        <p className="font-bold text-gray-900">
                            {(() => {
                                const fInfo = f.friend;
                                if (!fInfo) return '読み込み中...';
                                if (fInfo.nickname) return fInfo.nickname;
                                if (fInfo.email) return fInfo.email.split('@')[0];
                                return fInfo.username;
                            })()}
                        </p>

                        <div className="flex gap-2 mt-2">
                            <input
                                defaultValue={f.friend_note || ''}
                                className="border text-xs p-1 flex-grow rounded"
                                placeholder="メモを追加..."
                                onChange={e => setEditingNotes(prev => ({
                                    ...prev,
                                    [f.id]: e.target.value
                                }))}
                            />
                            <button
                                onClick={() => handleSaveNote(f.id)}
                                className="bg-blue-500 text-white text-xs px-2 py-1 rounded hover:bg-blue-600"
                            >
                                保存
                            </button>
                        </div>
                    </div>

                    {/* 右側ボタン群 */}
                    <div className="flex flex-col gap-1 items-center">
                        {/* MUTE：感情のみ表示 */}
                        <button
                            onClick={() =>
                                authApi.put(`/friends/friendships/${f.id}`, {
                                    is_muted: !f.is_muted
                                }).then(load)
                            }
                            className={`p-2 rounded-full text-[10px] font-black transition-colors ${
                                f.is_muted
                                    ? 'bg-gray-200 text-gray-500'
                                    : 'bg-pink-100 text-pink-500'
                            }`}
                            title={f.is_muted ? '感情のみ表示中' : 'Feeling Log全表示'}
                        >
                            {f.is_muted ? '🔇' : '📣'}
                        </button>

                        {/* ともだち解除（確認なし・静かに） */}
                        <button
                            onClick={() => handleDelete(f.id)}
                            className="p-1 text-[9px] text-gray-300 hover:text-gray-400 transition-colors"
                            title="ともだち解除"
                        >
                            ❁
                        </button>
                    </div>
                </li>
            ))}
        </ul>
    );
};

/* ======================
   メイン
====================== */
const FriendManager: React.FC = () => {
    const location = useLocation();
    const navigate = useNavigate();

    const [tab, setTab] = useState<'search' | 'requests' | 'friends'>(
        location.state?.tab || 'search'
    );
    const [pendingCount, setPendingCount]       = useState(0);
    const [currentUserId, setCurrentUserId]     = useState<number | null>(null);
    const [isProcessingSetup, setIsProcessingSetup] = useState(false);
    const [setupMessage, setSetupMessage]       = useState<string | null>(null);

    // ── SetupIntent 完了後のリダイレクト処理（HomeFeed と同パターン）──
    useEffect(() => {
        const params        = new URLSearchParams(location.search);
        const setupDone     = params.get('fm_setup_done');
        const receiverIdStr = params.get('receiver_id');

        // パラメータがない or すでに処理中なら何もしない
        if (!setupDone || !receiverIdStr || isProcessingSetup) return;

        const processSetup = async () => {
            setIsProcessingSetup(true);
            try {
                const receiverId = Number(receiverIdStr);
                await sendFriendRequest(receiverId);
                setSetupMessage('カード登録が完了しました。承認後に課金が開始されます。');
            } catch (err: any) {
                if (err.response?.status === 400 && err.response.data.detail === '既に申請済みです。') {
                    setSetupMessage('カード登録が完了しました。申請は送信済みです。');
                } else {
                    setSetupMessage('カード登録は完了しましたが、申請の送信に失敗しました。再度お試しください。');
                }
            } finally {
                setIsProcessingSetup(false);
                // URLパラメータをクリア（HomeFeed 同様 replace: true）
                navigate('/friends', { replace: true });
            }
        };

        processSetup();
    }, [location.search, isProcessingSetup, navigate]);

    // ── 承認待ち件数・ユーザーID取得 ──
    const loadPendingCount = useCallback(async () => {
        try {
            const res = await authApi.get('/friends/pending/count');
            setPendingCount(res.data.pending_count || 0);
        } catch {}
    }, []);

    useEffect(() => {
        loadPendingCount();
        authApi.get('/users/me')
            .then(res => setCurrentUserId(res.data.id))
            .catch(() => {});
    }, [loadPendingCount]);

    return (
        <div className="p-6">
            <h1 className="text-2xl font-bold mb-4">ともだち管理</h1>

            {/* SetupIntent 完了後メッセージ */}
            {isProcessingSetup && (
                <p className="text-xs text-purple-400 animate-pulse mb-4">カード登録を確認中...</p>
            )}
            {setupMessage && (
                <p className="text-xs text-green-600 bg-green-50 border border-green-200 rounded p-3 mb-4">
                    {setupMessage}
                </p>
            )}

            <div className="flex gap-4 mb-6">
                <button
                    onClick={() => setTab('search')}
                    className={tab === 'search' ? 'font-bold border-b-2 border-pink-500' : ''}
                >
                    検索
                </button>
                <button
                    onClick={() => setTab('requests')}
                    className={`relative ${
                        tab === 'requests' ? 'font-bold border-b-2 border-pink-500' : ''
                    } ${pendingCount > 0 ? 'text-amber-500 font-bold' : ''}`}
                >
                    承認待ち
                    {pendingCount > 0 && (
                        <span className="ml-1 bg-amber-500 text-white text-[10px] font-black rounded-full px-1.5 py-0.5">
                            {pendingCount}
                        </span>
                    )}
                </button>
                <button
                    onClick={() => setTab('friends')}
                    className={tab === 'friends' ? 'font-bold border-b-2 border-pink-500' : ''}
                >
                    一覧
                </button>
            </div>

            {tab === 'search'   && <UserSearch currentUserId={currentUserId} />}
            {tab === 'requests' && <RequestList />}
            {tab === 'friends'  && <FriendList />}
        </div>
    );
};

export default FriendManager;
