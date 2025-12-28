import React, { useState } from 'react';
import { postMoodLog, MoodPostPayload } from '../api.ts'; 
import { Send, Smile } from 'lucide-react';

const MOOD_TYPES = [
    { type: 'motivated', label: 'やる気🔥', emoji: '🔥' },
    { type: 'excited', label: 'ワクワク🤩', emoji: '🤩' },
    { type: 'happy', label: 'ハッピー😊', emoji: '😊' },
    { type: 'calm', label: '落ち着き😌', emoji: '😌' },
    { type: 'neutral', label: '普通😐', emoji: '😐' },
    { type: 'anxious', label: '不安😟', emoji: '😟' },
    { type: 'tired', label: '疲労困憊😥', emoji: '😥' },
    { type: 'sad', label: '悲しい😭', emoji: '😭' },
    { type: 'angry', label: 'イライラ😠', emoji: '😠' },
    { type: 'grateful', label: '感謝🙏', emoji: '🙏' },
];

interface MoodInputProps {
    onSuccess: () => void;
}

const MoodInput: React.FC<MoodInputProps> = ({ onSuccess }) => {
    const [selectedMood, setSelectedMood] = useState('neutral');
    const [comment, setComment] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsSubmitting(true);
        try {
            const payload: MoodPostPayload = {
                mood_type: selectedMood,
                comment: comment || null,
                is_visible: true  // 🔥 追加: デフォルトで公開
            };
            
            await postMoodLog(payload);

            console.log(`気分「${MOOD_TYPES.find(m => m.type === selectedMood)?.label || selectedMood}」を投稿しました！`);
            
            onSuccess();
            
            setSelectedMood('neutral');
            setComment('');

        } catch (err) {
            console.error('Failed to submit mood:', err);
            console.error('気分の投稿に失敗しました。詳細をコンソールで確認してください。'); 
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="p-6 bg-blue-50 rounded-xl border border-blue-200 shadow-md">
            <h3 className="text-xl font-bold text-blue-800 flex items-center mb-4">
                <Smile className="w-6 h-6 mr-2 text-blue-500" /> 今日の気分を投稿
            </h3>
            
            <form onSubmit={handleSubmit} className="space-y-4">
                {/* 気分選択 */}
                <div className="flex flex-wrap gap-2 justify-center p-2 bg-white rounded-lg shadow-inner">
                    {MOOD_TYPES.map((mood) => (
                        <button
                            key={mood.type}
                            type="button"
                            onClick={() => setSelectedMood(mood.type)}
                            className={`
                                p-2 rounded-full text-sm font-medium transition duration-150 ease-in-out
                                ${selectedMood === mood.type 
                                    ? 'bg-blue-500 text-white shadow-lg ring-4 ring-blue-300' 
                                    : 'bg-gray-100 text-gray-700 hover:bg-blue-100'
                                }
                            `}
                        >
                            {mood.emoji} {mood.label}
                        </button>
                    ))}
                </div>

                {/* コメント入力 */}
                <div>
                    <textarea
                        value={comment}
                        onChange={(e) => setComment(e.target.value)}
                        placeholder={`「${MOOD_TYPES.find(m => m.type === selectedMood)?.label || '普通'}」を選びました。一言コメントを残しましょう！`}
                        rows={2}
                        maxLength={200}
                        className="w-full p-3 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 transition"
                    ></textarea>
                    <p className="text-xs text-gray-500 mt-1">
                        {comment.length}/200文字
                    </p>
                </div>

                {/* 投稿ボタン */}
                <div className="flex justify-end">
                    <button
                        type="submit"
                        disabled={isSubmitting}
                        className={`
                            px-6 py-2 flex items-center font-semibold rounded-lg shadow-lg transition duration-150
                            ${isSubmitting 
                                ? 'bg-gray-400 cursor-not-allowed' 
                                : 'bg-blue-600 text-white hover:bg-blue-700'
                            }
                        `}
                    >
                        {isSubmitting ? '投稿中...' : '気分を投稿'}
                        <Send className="w-4 h-4 ml-2" />
                    </button>
                </div>
            </form>
        </div>
    );
};

export default MoodInput;