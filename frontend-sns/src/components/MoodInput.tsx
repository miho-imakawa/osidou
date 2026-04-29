// frontend-sns/src/components/MoodInput.tsx
// 変更点: ① タグ一覧をAPIから取得 ② 投稿時にcategoryを送信

import React, { useState, useEffect } from 'react';
import { postMoodLog, authApi } from '../api';
import { Send, Smile, Tag } from 'lucide-react';

const MOOD_TYPES = [
    { type: 'MOTIVATED', label: 'On Fire！やるぞ～',  emoji: '🔥', group: 'green' },
    { type: 'EXCITED',   label: 'Yay！うれしい～',    emoji: '🤩', group: 'green' },
    { type: 'HAPPY',     label: 'Happy！しあわせ～',  emoji: '😊', group: 'green' },
    { type: 'GRATEFUL',  label: 'Aww～ありがとう～',  emoji: '🙏', group: 'green' },
    { type: 'CALM',      label: 'Relax～まったり～',  emoji: '😌', group: 'yellow' },
    { type: 'NEUTRAL',   label: 'Meh…まずまず',       emoji: '😶', group: 'yellow' },
    { type: 'ANXIOUS',   label: 'Hmm…もやもや～',    emoji: '💭', group: 'red' },
    { type: 'TIRED',     label: 'Ugh…つかれた～',    emoji: '😩', group: 'red' },
    { type: 'SAD',       label: 'Sigh…なける…',      emoji: '😭', group: 'red' },
    { type: 'ANGRYangry',     label: 'Grrr！むかつく！',  emoji: '😡', group: 'red' },
];

const GROUP_STYLES: Record<string, {
    selected: string; hover: string; bg: string;
    border: string; text: string; ring: string;
}> = {
    green:  { selected: 'bg-emerald-500 text-white shadow-lg', hover: 'hover:bg-emerald-50', bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-700', ring: 'ring-emerald-300' },
    yellow: { selected: 'bg-amber-400 text-white shadow-lg',   hover: 'hover:bg-amber-50',   bg: 'bg-amber-50',   border: 'border-amber-200',   text: 'text-amber-700',   ring: 'ring-amber-300'   },
    red:    { selected: 'bg-rose-600 text-white shadow-lg',    hover: 'hover:bg-rose-50',    bg: 'bg-rose-50',    border: 'border-rose-200',    text: 'text-rose-700',    ring: 'ring-rose-300'    },
};

const CONTAINER_STYLES: Record<string, string> = {
    green: 'bg-emerald-50 border-emerald-200', yellow: 'bg-amber-50 border-amber-200', red: 'bg-rose-50 border-rose-200',
};
const TITLE_STYLES: Record<string, string> = {
    green: 'text-emerald-800', yellow: 'text-amber-800', red: 'text-rose-800',
};
const SUBMIT_STYLES: Record<string, string> = {
    green: 'bg-emerald-500 hover:bg-emerald-600 text-white',
    yellow: 'bg-amber-400 hover:bg-amber-500 text-white',
    red: 'bg-rose-600 hover:bg-rose-700 text-white',
};

// タグのカラーパレット（MY PAGEで登録時に選択）
const TAG_COLOR_MAP: Record<string, string> = {
    pink:   'bg-pink-100 text-pink-700 border-pink-200',
    purple: 'bg-purple-100 text-purple-700 border-purple-200',
    blue:   'bg-blue-100 text-blue-700 border-blue-200',
    green:  'bg-emerald-100 text-emerald-700 border-emerald-200',
    orange: 'bg-orange-100 text-orange-700 border-orange-200',
    gray:   'bg-gray-100 text-gray-600 border-gray-200',
};

interface UserTag {
    id: number;
    label: string;
    color: string;
    sort_order: number;
}

interface MoodInputProps {
    onSuccess: () => void;
}

const MoodInput: React.FC<MoodInputProps> = ({ onSuccess }) => {
    const [selectedMood, setSelectedMood] = useState('neutral');
    const [comment, setComment]           = useState('');
    const [selectedTag, setSelectedTag]   = useState<string | null>(null); // ← 追加
    const [userTags, setUserTags]         = useState<UserTag[]>([]);        // ← 追加
    const [isSubmitting, setIsSubmitting] = useState(false);

    const currentMoodObj  = MOOD_TYPES.find(m => m.type === selectedMood);
    const currentGroup    = currentMoodObj?.group || 'yellow';
    const containerStyle  = CONTAINER_STYLES[currentGroup];
    const titleStyle      = TITLE_STYLES[currentGroup];
    const submitStyle     = SUBMIT_STYLES[currentGroup];

    // ── タグ一覧をAPIから取得 ──────────────────────────
    useEffect(() => {
        const loadTags = async () => {
            try {
                const res = await authApi.get('/users/me/tags');
                setUserTags(res.data || []);
            } catch {
                // タグ未登録やエラーは無視（投稿自体は可能）
            }
        };
        loadTags();
    }, []);

    // ── 投稿 ─────────────────────────────────────────
    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsSubmitting(true);
        try {
            await postMoodLog({
                mood_type:  selectedMood,
                comment:    comment,
                category:   selectedTag,  // ← シンプルにこれだけ
                is_visible: true,
            });

            onSuccess();
            setSelectedMood('neutral');
            setComment('');
            setSelectedTag(null);
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
                <span className="text-sm font-medium ml-2 opacity-60">いまの気分は？</span>
            </h3>

            <form onSubmit={handleSubmit} className="space-y-4">
                {/* 気分選択 */}
                <div className="flex flex-wrap gap-2 justify-center p-2 bg-white rounded-lg shadow-inner">
                    {MOOD_TYPES.map((mood) => {
                        const style    = GROUP_STYLES[mood.group];
                        const isSelected = selectedMood === mood.type;
                        return (
                            <button
                                key={mood.type}
                                type="button"
                                onClick={() => setSelectedMood(mood.type)}
                                className={`p-2 rounded-full text-sm font-medium transition-all duration-150 ease-in-out
                                    ${isSelected
                                        ? `${style.selected} ring-4 ${style.ring}`
                                        : `bg-gray-100 text-gray-600 ${style.hover}`
                                    }`}
                            >
                                <span className="text-xl">{mood.emoji}</span>
                            </button>
                        );
                    })}
                </div>

                {/* ── タグ選択（登録済みタグがある場合のみ表示）── */}
                {userTags.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 items-center">
                        <Tag size={12} className="text-gray-400 shrink-0" />
                        {userTags.map(tag => {
                            const colorClass = TAG_COLOR_MAP[tag.color] ?? TAG_COLOR_MAP.gray;
                            const isActive   = selectedTag === tag.label;
                            return (
                                <button
                                    key={tag.id}
                                    type="button"
                                    onClick={() => setSelectedTag(isActive ? null : tag.label)}
                                    className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold border transition-all
                                        ${isActive
                                            ? `${colorClass} ring-2 ring-offset-1 scale-105`
                                            : `${colorClass} opacity-60 hover:opacity-100`
                                        }`}
                                >
                                    {tag.label}
                                </button>
                            );
                        })}
                    </div>
                )}

                {/* コメント入力 */}
                <textarea
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder={`「${currentMoodObj?.label || '今日'}」な気分…何があったか教えて😉 `}
                    rows={2}
                    maxLength={200}
                    className="w-full p-3 border border-gray-300 rounded-lg focus:outline-none transition bg-white"
                />
                <p className="text-xs text-gray-400 text-right">{comment.length}/200文字</p>

                {/* 送信ボタン */}
                <div className="flex justify-end">
                    <button
                        type="submit"
                        disabled={isSubmitting}
                        className={`px-6 py-2 flex items-center font-semibold rounded-lg shadow-lg transition-all duration-150
                            ${isSubmitting ? 'bg-gray-400 cursor-not-allowed text-white' : submitStyle}`}
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
