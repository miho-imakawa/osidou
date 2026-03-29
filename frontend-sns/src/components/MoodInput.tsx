// frontend-sns/src/components/MoodInput.tsx

import React, { useState } from 'react';
import { postMoodLog } from '../api';
import { Send, Smile } from 'lucide-react';

const MOOD_TYPES = [
    { type: 'motivated', label: 'SELECTED:「On Fire！やるぞ～」',  emoji: '🔥', group: 'green' },
    { type: 'excited',   label: 'SELECTED:「Yay！うれしい～」',    emoji: '🤩', group: 'green' },
    { type: 'happy',     label: 'SELECTED:「Happy！しあわせ～」',  emoji: '😊', group: 'green' },
    { type: 'grateful',  label: 'SELECTED:「Aww～ありがとう～」',  emoji: '🙏', group: 'green' },
    { type: 'calm',      label: 'SELECTED:「Relax～まったり～」',  emoji: '😌', group: 'yellow' },
    { type: 'neutral',   label: 'SELECTED:「Meh…まずまず」',    emoji: '😶', group: 'yellow' },
    { type: 'anxious',   label: 'SELECTED:「Hmm…もやもや～」',    emoji: '💭', group: 'red' },
    { type: 'tired',     label: 'SELECTED:「Ugh…つかれた～」',    emoji: '😩', group: 'red' },
    { type: 'sad',       label: 'SELECTED:「Sigh…なける…」',     emoji: '😭', group: 'red' },
    { type: 'angry',     label: 'SELECTED:「Grrr！むかつく！」',  emoji: '😡', group: 'red' },
];

// グループごとの色定義
const GROUP_STYLES: Record<string, {
    selected: string;
    hover: string;
    bg: string;
    border: string;
    text: string;
    ring: string;
}> = {
    green: {
        selected: 'bg-emerald-500 text-white shadow-lg',
        hover: 'hover:bg-emerald-50',
        bg: 'bg-emerald-50',
        border: 'border-emerald-200',
        text: 'text-emerald-700',
        ring: 'ring-emerald-300',
    },
    yellow: {
        selected: 'bg-amber-400 text-white shadow-lg',
        hover: 'hover:bg-amber-50',
        bg: 'bg-amber-50',
        border: 'border-amber-200',
        text: 'text-amber-700',
        ring: 'ring-amber-300',
    },
    red: {
        selected: 'bg-rose-600 text-white shadow-lg',
        hover: 'hover:bg-rose-50',
        bg: 'bg-rose-50',
        border: 'border-rose-200',
        text: 'text-rose-700',
        ring: 'ring-rose-300',
    },
};

// 現在選択中のグループに応じて外枠・背景を変える
const CONTAINER_STYLES: Record<string, string> = {
    green:  'bg-emerald-50 border-emerald-200',
    yellow: 'bg-amber-50 border-amber-200',
    red:    'bg-rose-50 border-rose-200',
};

const TITLE_STYLES: Record<string, string> = {
    green:  'text-emerald-800',
    yellow: 'text-amber-800',
    red:    'text-rose-800',
};

const SUBMIT_STYLES: Record<string, string> = {
    green:  'bg-emerald-500 hover:bg-emerald-600 text-white',
    yellow: 'bg-amber-400 hover:bg-amber-500 text-white',
    red:    'bg-rose-600 hover:bg-rose-700 text-white',
};

interface MoodInputProps {
    onSuccess: () => void;
}

const MoodInput: React.FC<MoodInputProps> = ({ onSuccess }) => {
    const [selectedMood, setSelectedMood] = useState('neutral');
    const [comment, setComment] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);

    const currentMoodObj = MOOD_TYPES.find(m => m.type === selectedMood);
    const currentGroup = currentMoodObj?.group || 'yellow';
    const containerStyle = CONTAINER_STYLES[currentGroup];
    const titleStyle = TITLE_STYLES[currentGroup];
    const submitStyle = SUBMIT_STYLES[currentGroup];

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsSubmitting(true);
        try {
            await postMoodLog({
                mood_type: selectedMood,
                comment: comment,
                is_visible: true,
            });
            onSuccess();
            setSelectedMood('neutral');
            setComment('');
        } catch (err) {
            console.error('Failed to submit mood:', err);
            alert('気分の投稿に失敗しました。');
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className={`p-6 rounded-xl border shadow-md transition-all duration-300 ${containerStyle}`}>
            <h3 className={`text-xl font-bold flex items-center mb-4 transition-colors duration-300 ${titleStyle}`}>
                <Smile className="w-6 h-6 mr-2" /> CURRENT FEELING
            </h3>

            <form onSubmit={handleSubmit} className="space-y-4">
                <div className="flex flex-wrap gap-2 justify-center p-2 bg-white rounded-lg shadow-inner">
                    {MOOD_TYPES.map((mood) => {
                        const style = GROUP_STYLES[mood.group];
                        const isSelected = selectedMood === mood.type;
                        return (
                            <button
                                key={mood.type}
                                type="button"
                                onClick={() => setSelectedMood(mood.type)}
                                className={`
                                    p-2 rounded-full text-sm font-medium transition-all duration-150 ease-in-out
                                    ${isSelected
                                        ? `${style.selected} ring-4 ${style.ring}`
                                        : `bg-gray-100 text-gray-600 ${style.hover}`
                                    }
                                `}
                            >
                                <span className="text-xl">{mood.emoji}</span>
                            </button>
                        );
                    })}
                </div>

                <textarea
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder={`${currentMoodObj?.label || '普通'} コメントを残してね`}
                    rows={2}
                    maxLength={200}
                    className="w-full p-3 border border-gray-300 rounded-lg focus:outline-none transition bg-white"
                />
                <p className="text-xs text-gray-400 text-right">{comment.length}/200文字</p>

                <div className="flex justify-end">
                    <button
                        type="submit"
                        disabled={isSubmitting}
                        className={`
                            px-6 py-2 flex items-center font-semibold rounded-lg shadow-lg transition-all duration-150
                            ${isSubmitting ? 'bg-gray-400 cursor-not-allowed text-white' : submitStyle}
                        `}
                    >
                        {isSubmitting ? '投稿中...' : '気分をPOST ✈'}
                        <Send className="w-4 h-4 ml-2" />
                    </button>
                </div>
            </form>
        </div>
    );
};

export default MoodInput;