import React, { useState, useEffect } from 'react';
import { UserProfile, UserMoodResponse, fetchFollowingMoods } from '../api.ts';
import { MessageSquare, Clock } from 'lucide-react'; // UserCircleは使わないので削除
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
        'motivated': { label: 'やる気', emoji: '🔥' },
        'excited': { label: 'ワクワク', emoji: '🤩' },
        'happy': { label: 'ハッピー', emoji: '😊' },
        'calm': { label: '落ち着き', emoji: '😌' },
        'neutral': { label: '普通', emoji: '😐' },
        'anxious': { label: '不安', emoji: '😟' },
        'tired': { label: '疲労困憊', emoji: '😥' },
        'sad': { label: '悲しい', emoji: '😭' },
        'angry': { label: 'イライラ', emoji: '😠' },
        'grateful': { label: '感謝', emoji: '🙏' },
    };

    return (
        <div className="max-w-2xl mx-auto p-4 md:p-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-6">
                ✨ ようこそ、{profile.nickname || profile.username}さん！
            </h1>
            
            <MoodInput onSuccess={loadMoods} />

            <div className="mt-8 space-y-8">
                <h2 className="text-2xl font-semibold text-gray-800 border-b pb-2">
                    ともだちのログ
                </h2>
                
                {loading && <p className="text-gray-500">読み込み中...</p>}
                {error && <p className="text-red-500">{error}</p>}

                {!loading && friendMoods.length === 0 && (
                    <div className="bg-gray-50 p-6 rounded-lg text-center">
                        <p className="text-gray-500 italic">まだ友達がいないか、投稿がありません</p>
                    </div>
                )}

                <div className="space-y-2"> {/* リストの間隔を狭くしました */}
                    {friendMoods.map((friendMood) => {
                        const moodInfo = MOOD_TYPES[friendMood.current_mood] || { 
                            label: '不明', 
                            emoji: '🤔' 
                        };
                        
                        return (
                            <div 
                                key={friendMood.user_id} 
                                className="bg-white px-4 py-2 rounded-lg shadow-sm border border-gray-100 hover:border-pink-200 transition duration-150"
                            >
                                {/* 💡 横一列（flex）に配置 */}
                                <div className="flex items-center gap-3 text-sm md:text-base">
                                    
                                    {/* 1. 名前（メモ）: 絵文字 */}
                                    <span className="font-bold text-gray-800 shrink-0">
                                        {(() => {
                                            const name = friendMood.nickname || (friendMood.email ? friendMood.email.split('@')[0] : 'ユーザー');
                                            const memo = friendMood.friend_note ? `（${friendMood.friend_note}）` : "";
                                            return `${name}${memo}`;
                                        })()}
                                        <span className="ml-1">: {moodInfo.emoji}</span>
                                    </span>

                                    {/* 2. 気分のラベル */}
                                    <span className="text-gray-600 shrink-0 font-medium">
                                        {moodInfo.label}
                                    </span>

                                    {/* 3. コメント（あれば） */}
                                    {friendMood.current_mood_comment && (
                                        <span className="text-gray-500 truncate italic border-l pl-3 hidden sm:inline">
                                            {friendMood.current_mood_comment}
                                        </span>
                                    )}

                                    {/* 4. 更新時間（右端に小さく） */}
                                    {friendMood.mood_updated_at && (
                                        <span className="text-[10px] text-gray-300 ml-auto shrink-0">
                                            {new Date(friendMood.mood_updated_at).toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' })}
                                        </span>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    ); // ここで return を閉じる
}; // ここで HomeFeed 関数を閉じる

export default HomeFeed;