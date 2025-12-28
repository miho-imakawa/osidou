import React, { useState, useEffect } from 'react';
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
import { Link } from 'react-router-dom';
import { authApi } from '../api';

/* ======================
   ユーザー検索
====================== */
const UserSearch: React.FC = () => {
    const [searchQuery, setSearchQuery] = useState('');
    const [results, setResults] = useState<UserProfileType[]>([]);
    const [loading, setLoading] = useState(false);
    // ✅ 型を修正
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

    const handleSend = async (id: number, name: string) => {
        if (status[id]) return;
        setStatus({ ...status, [id]: 'pending' });
        try {
            await sendFriendRequest(id);
            setStatus({ ...status, [id]: 'sent' });
            alert(`${name} に申請しました`);
        } catch {
            const newStatus = { ...status };
            delete newStatus[id];
            setStatus(newStatus);
            alert('送信に失敗しました');
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
                            disabled={!!status[u.id]}  // <- u.id に修正
                            className="bg-pink-100 px-3 py-1 rounded"
                        >
                            {status[u.id] === 'sent' ? '申請済み' : 'フレンド申請'}
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

    const load = async () => {
        const res = await fetchFriendRequests();
        setRequests(res);
    };

    useEffect(() => { load(); }, []);

    return (
        <ul className="divide-y bg-white rounded shadow">
            {requests.map(r => (
                <li key={r.id} className="p-4 flex justify-between">
                    <p>
                        <Link to={`/profile/${r.requester.id}`} className="text-pink-500">
                            {r.requester.nickname || r.requester.username}
                        </Link>
                        さんからの申請
                    </p>
                    <div className="space-x-2">
                        <button onClick={() => acceptFriendRequest(r.id).then(load)}>承認</button>
                        <button onClick={() => rejectFriendRequest(r.id).then(load)}>拒否</button>
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
            await authApi.put(`/friends/friendships/${friendshipId}`, {
                friend_note: note
            });
            alert("メモを保存しました");
            load();
        } catch (err) {
            alert("保存に失敗しました");
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
                                if (!fInfo) return "読み込み中...";
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
                                onChange={e => setEditingNotes({
                                    ...editingNotes,
                                    [f.id]: e.target.value
                                })}
                            />
                            <button 
                                onClick={() => handleSaveNote(f.id)}
                                className="bg-blue-500 text-white text-xs px-2 py-1 rounded hover:bg-blue-600"
                            >
                                保存
                            </button>
                        </div>
                    </div>
                    
                    <button
                        onClick={() => authApi.put(`/friends/friendships/${f.id}`, {
                            is_muted: !f.is_muted
                        }).then(load)}
                        className={`p-2 rounded-full ${f.is_muted ? 'bg-gray-200' : 'bg-pink-100'}`}
                    >
                        {f.is_muted ? '🔇' : '📣'}
                    </button>
                </li>
            ))}
        </ul>
    );
};

/* ======================
   メイン
====================== */
const FriendManager: React.FC = () => {
    const [tab, setTab] = useState<'search' | 'requests' | 'friends'>('search');

    return (
        <div className="p-6">
            <h1 className="text-2xl font-bold mb-4">ともだち管理</h1>
            <div className="flex gap-4 mb-6">
                <button onClick={() => setTab('search')}>検索</button>
                <button onClick={() => setTab('requests')}>承認待ち</button>
                <button onClick={() => setTab('friends')}>一覧</button>
            </div>

            {tab === 'search' && <UserSearch />}
            {tab === 'requests' && <RequestList />}
            {tab === 'friends' && <FriendList />}
        </div>
    );
};

export default FriendManager;