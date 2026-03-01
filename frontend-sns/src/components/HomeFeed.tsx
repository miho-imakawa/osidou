import React, { useState, useEffect } from 'react';
import { UserProfile, UserMoodResponse, fetchFollowingMoods } from '../api.ts';
import { MessageSquare, Clock } from 'lucide-react';
import MoodInput from './MoodInput.tsx';

const HomeFeed: React.FC<{ profile: UserProfile }> = ({ profile }) => {
    const [friendMoods, setFriendMoods] = useState<UserMoodResponse[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const loadMoods = async () => {
        try {
            setLoading(true);
            const data = await fetchFollowingMoods();
            setFriendMoods(data);
        } catch (err) {
            setError('気分ログの読み込みに失敗しました。');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadMoods();
    }, []);

    const MOOD_TYPES: Record<string, { label: string; emoji: string }> = {
        'motivated': { label: 'On Fire!/活',   emoji: '🔥' },
        'excited':   { label: 'Yay/上々!',      emoji: '🤩' },
        'happy':     { label: 'Happy/幸',       emoji: '😊' },
        'calm':      { label: 'Relax/温',       emoji: '😌' },
        'neutral':   { label: '±Meh/中',         emoji: '😐' },
        'anxious':   { label: 'Hmm/焦',          emoji: '😟' },
        'tired':     { label: 'No Power/疲',     emoji: '😥' },
        'sad':       { label: 'SAD/悲',          emoji: '😭' }, 
        'angry':     { label: 'Grrr!/怒',        emoji: '😠' },
        'grateful':  { label: 'Aww/感謝',        emoji: '🙏' }, 
    };

    return (
        <div className="max-w-2xl mx-auto p-4 md:p-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-6">
                ✨ハロー、{profile.nickname || profile.username}
            </h1>
            
            <MoodInput onSuccess={loadMoods} />

            <div className="mt-8 space-y-8">
                <h2 className="text-2xl font-semibold text-gray-800 border-b pb-2">
                    ともだち's LOG
                </h2>
                
                {loading && <p className="text-gray-500">読み込み中...</p>}
                {error && <p className="text-red-500">{error}</p>}

                {!loading && friendMoods.length === 0 && (
                    <div className="bg-gray-50 p-6 rounded-lg text-center">
                        <p className="text-gray-500 italic">まだ友達がいないか、投稿がありません</p>
                    </div>
                )}

                <div className="space-y-2">
                    {friendMoods.map((friendMood) => {
                        const moodDetail = MOOD_TYPES[friendMood.current_mood] || { label: '不明', emoji: '🤔' };
                        
                        return (
                            <div 
                                key={friendMood.user_id} 
                                className="flex items-center justify-between p-3 bg-white rounded-lg border border-gray-200 hover:bg-gray-50 transition duration-150"
                            >
                                <div className="flex items-center overflow-hidden flex-1">
                                    {/* 1. 日付 */}
                                    <span className="text-xs text-gray-500 mr-4 shrink-0">
                                        {friendMood.mood_updated_at && new Date(friendMood.mood_updated_at).toLocaleString('ja-JP', {
                                            month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit'
                                        })}
                                    </span>

                                    {/* 2. ユーザー名・気分・コメント */}
                                    <p className="text-sm font-medium text-gray-800 flex items-center min-w-0 truncate">
                                        <span className="shrink-0 font-bold mr-2">
                                            {(() => {
                                                const name = friendMood.nickname || (friendMood.email ? friendMood.email.split('@')[0] : 'ユーザー');
                                                const memo = friendMood.friend_note ? `（${friendMood.friend_note}）` : "";
                                                return `${name}${memo}`;
                                            })()}
                                        </span>

                                        <span className="text-lg mr-2 shrink-0">{moodDetail.emoji}</span>
                                        <span className="shrink-0">{moodDetail.label}</span>

                                        {/* 💡 フラグが True の時だけコメントを表示する */}
                                        {friendMood.is_mood_comment_visible && friendMood.current_mood_comment && (
                                            <span className="text-sm text-gray-600 ml-2 truncate italic">
                                                : {friendMood.current_mood_comment}
                                            </span>
                                        )}
                                    </p>
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