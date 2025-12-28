// frontend-sns/src/components/HomeFeed.tsx

import React, { useState, useEffect } from 'react';
import { UserProfile, MoodLog, fetchFollowingMoods } from '../api.ts';
import { UserCircle, MessageSquare, Clock } from 'lucide-react';

// HomeFeedComponentはprofileのみをPropsとして受け取る
const HomeFeed: React.FC<{ profile: UserProfile }> = ({ profile }) => {
    const [moodLogs, setMoodLogs] = useState<MoodLog[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const loadMoods = async () => {
            try {
                setLoading(true);
                const data = await fetchFollowingMoods();
                setMoodLogs(data);
            } catch (err) {
                setError('気分ログの読み込みに失敗しました。');
                console.error(err);
            } finally {
                setLoading(false);
            }
        };
        loadMoods();
    }, []);
    
    return (
        <div className="max-w-2xl mx-auto p-4 md:p-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-6">
                ✨ ようこそ、{profile.nickname || profile.username}さん！
            </h1>
            
            <div className="mt-8 space-y-6">
                <h2 className="text-2xl font-semibold text-gray-800 border-b pb-2">みんなの最新の気分</h2>
                
                {loading && <p className="text-gray-500">読み込み中...</p>}
                {error && <p className="text-red-500">{error}</p>}

                {moodLogs.length === 0 && (
                    <p className="text-gray-500 italic">まだ誰も気分を投稿していません。</p>
                )}

                {moodLogs.map(log => (
                    <div key={log.id} className="bg-white p-5 rounded-xl shadow-md border border-gray-200">
                        <div className="flex items-center mb-3">
                            {log.user_avatar_url ? (
                                <img src={log.user_avatar_url} alt={log.user_nickname} className="w-10 h-10 rounded-full mr-3" />
                            ) : (
                                <UserCircle className="w-10 h-10 text-gray-400 mr-3" />
                            )}
                            <span className="font-bold text-gray-800">{log.user_nickname}</span>
                        </div>
                        <div className="pl-13">
                            <p className="text-2xl mb-2">{log.mood}</p>
                            {log.comment && (
                                <div className="flex items-start text-gray-600 bg-gray-50 p-3 rounded-md">
                                    <MessageSquare className="w-4 h-4 mr-2 mt-1 shrink-0" />
                                    <p className="text-sm">{log.comment}</p>
                                </div>
                            )}
                            <div className="flex items-center text-xs text-gray-400 mt-3">
                                <Clock className="w-3 h-3 mr-1" />
                                <span>{new Date(log.created_at).toLocaleString('ja-JP')}</span>
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default HomeFeed;