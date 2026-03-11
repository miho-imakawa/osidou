import React, { useState, useEffect } from 'react';
import { UserProfile, UserMoodResponse, fetchFollowingMoods, authApi } from '../api';
import { UserCircle } from 'lucide-react';
import MoodInput from './MoodInput';
import PendingFriendBanner from './PendingFriendBanner';

const HomeFeed: React.FC<{ profile: UserProfile }> = ({ profile }) => {
    const [friendMoods, setFriendMoods] = useState<UserMoodResponse[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [pendingCount, setPendingCount] = useState(0);

    const loadMoods = async () => {
        try {
            setLoading(true);
            const [data, pendingRes] = await Promise.all([
                fetchFollowingMoods(),
                authApi.get('/friends/pending/count')
            ]);
            setFriendMoods(data);
            setPendingCount(pendingRes.data.pending_count);
        } catch (err) {
            setError('Failed to load logs.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadMoods();
    }, []);

    const MOOD_TYPES: Record<string, { label: string; emoji: string }> = {
        'motivated': { label: 'On Fire! 熱',  emoji: '🔥' },
        'excited':   { label: 'Yay! 喜',      emoji: '🤩' },
        'happy':     { label: 'Happy 幸',     emoji: '😊' },
        'calm':      { label: 'Relax 穏',    emoji: '😌' },
        'neutral':   { label: 'Meh 凪',       emoji: '😐' },
        'anxious':   { label: 'Hmm 憂',    emoji: '😟' },
        'tired':     { label: 'Ugh 倦',    emoji: '😥' },
        'sad':       { label: 'Sigh 悲',      emoji: '😭' },
        'angry':     { label: 'Grrr! 怒',     emoji: '😠' },
        'grateful':  { label: 'Aww 感謝',       emoji: '🙏' },
    };

    return (
        <div className="max-w-2xl mx-auto p-4 md:p-8">
            <div className="mb-10">
            <h1 className="text-2xl font-bold text-gray-900 mb-1">
                ハロー⭐ {profile.nickname || profile.username},
            </h1>
                <p className="text-[10px] font-bold text-pink-500 opacity-70 tracking-widest uppercase mt-1">Welcome back</p>
            </div>

            <MoodInput onSuccess={loadMoods} />

            <div className="mt-12 space-y-6">
                <div className="mb-6 flex items-center justify-between">
                    <div>
                        <h2 className="text-[14px] font-black text-gray-900 tracking-[0.2em] uppercase leading-none">
                            ともだちs' LOG
                        </h2>
                        <p className="text-[8px] font-bold text-gray-400 mt-1 tracking-wider">The latest Friends’ feeling</p>
                    </div>
                    <PendingFriendBanner count={pendingCount} />
                </div>

                {loading && <p className="text-center py-10 text-[10px] font-black text-gray-300 animate-pulse">LOADING...</p>}
                {error && <p className="text-red-500 text-xs font-bold">{error}</p>}

                {!loading && friendMoods.length === 0 && (
                    <div className="bg-white p-10 rounded-[32px] border-2 border-dashed border-gray-100 text-center">
                        <p className="text-gray-300 text-[10px] font-bold uppercase tracking-widest">No activity found</p>
                    </div>
                )}

                <div className="grid gap-4">
                    {friendMoods.map((friendMood) => {
                        const moodDetail = MOOD_TYPES[friendMood.current_mood] || { label: '?', emoji: '✨' };
                        return (
                            <div
                                key={friendMood.user_id}
                                className="bg-white p-6 rounded-[32px] shadow-sm border border-gray-100 transition-all hover:shadow-md group"
                            >
                                <div className="flex items-center gap-3 mb-4">
                                    <div className="w-8 h-8 bg-gray-50 rounded-full flex items-center justify-center group-hover:bg-pink-50 transition-colors">
                                        <UserCircle className="w-5 h-5 text-gray-300 group-hover:text-pink-300" />
                                    </div>
                                    <div className="flex flex-col">
                                        <span className="font-black text-xs text-gray-900 tracking-tight uppercase">
                                            {friendMood.nickname || friendMood.username}
                                            {friendMood.friend_note && <span className="text-[9px] text-gray-400 font-medium ml-1">({friendMood.friend_note})</span>}
                                        </span>
                                        <span className="text-[8px] font-mono text-gray-300 uppercase">
                                            {friendMood.mood_updated_at && new Date(friendMood.mood_updated_at).toLocaleDateString()}
                                        </span>
                                    </div>
                                </div>
                                <div className="pl-11">
                                    <div className="flex items-center gap-2 mb-3">
                                        <span className="text-2xl">{moodDetail.emoji}</span>
                                        <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest">{moodDetail.label}</span>
                                    </div>
                                    {friendMood.current_mood_comment && (
                                        <div className="bg-gray-50 p-4 rounded-2xl border border-gray-50">
                                            <p className="text-sm text-gray-600 font-medium leading-relaxed">
                                                {friendMood.current_mood_comment}
                                            </p>
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
};

export default HomeFeed;