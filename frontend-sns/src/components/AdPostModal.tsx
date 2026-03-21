import React, { useState, useEffect } from 'react';
import { authApi, fetchAdQuote, startAdCheckout } from '../api';
import { X, CheckCircle2, Users, CreditCard, Send, Megaphone, Calendar } from 'lucide-react';

interface RelatedCategory {
    id: number;
    name: string;
    member_count: number;
}

interface AdPostModalProps {
    profile: any;
    currentCategoryId: number;
    currentCategoryName: string;
    onClose: () => void;
    onPosted: () => void;
}

const AdPostModal: React.FC<AdPostModalProps> = ({
    profile,
    currentCategoryId,
    currentCategoryName,
    onClose,
    onPosted,
}) => {
    const [relatedCategories, setRelatedCategories] = useState<RelatedCategory[]>([]);
    const [selectedIds, setSelectedIds] = useState<number[]>([currentCategoryId]);
    const [quote, setQuote] = useState<{ unique_user_count: number; total_user_count: number; estimated_fee: number } | null>(null);
    const [loadingQuote, setLoadingQuote] = useState(false);
    const [posting, setPosting] = useState(false);

    const [adTitle, setAdTitle] = useState('');
    const [adContent, setAdContent] = useState('');
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');
    const [selectedColor, setSelectedColor] = useState('green');

    const colorOptions = [
        { id: 'green',  bg: 'bg-green-50',  border: 'border-green-300',  text: 'text-green-900',  label: '標準'   },
        { id: 'red',    bg: 'bg-red-50',    border: 'border-red-300',    text: 'text-red-900',    label: 'RED'    },
        { id: 'blue',   bg: 'bg-blue-50',   border: 'border-blue-300',   text: 'text-blue-900',   label: 'BLUE'   },
        { id: 'purple', bg: 'bg-purple-50', border: 'border-purple-300', text: 'text-purple-900', label: 'PURPLE' },
        { id: 'white',  bg: 'bg-slate-50',  border: 'border-slate-300',  text: 'text-slate-900',  label: 'WH/BK' },
    ];

    // 関連Chatを取得
    useEffect(() => {
        const loadRelated = async () => {
            try {
                const res = await authApi.get(`/hobby-categories/categories/${currentCategoryId}/related`);
                const others = res.data.filter((c: RelatedCategory) => c.id !== currentCategoryId);
                const current = res.data.find((c: RelatedCategory) => c.id === currentCategoryId) || {
                    id: currentCategoryId,
                    name: currentCategoryName,
                    member_count: 0,
                };
                setRelatedCategories([current, ...others]);
            } catch {
                setRelatedCategories([{ id: currentCategoryId, name: currentCategoryName, member_count: 0 }]);
            }
        };
        loadRelated();
    }, [currentCategoryId, currentCategoryName]);

    // 選択変更時に見積もりを取得
    useEffect(() => {
        if (selectedIds.length === 0) { setQuote(null); return; }
        const getQuote = async () => {
            setLoadingQuote(true);
            try {
                const data = await fetchAdQuote(selectedIds);
                setQuote(data);
            } catch {
                console.error('見積もり取得失敗');
            } finally {
                setLoadingQuote(false);
            }
        };
        getQuote();
    }, [selectedIds]);

    const toggleCategory = (id: number) => {
        setSelectedIds(prev => prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]);
    };

    const handlePost = async () => {
        if (!adTitle.trim() || !quote || posting) return;
        setPosting(true);
        try {
            await startAdCheckout(
                profile.id,
                quote.estimated_fee,
                adTitle,
                adContent,
                startDate,
                endDate,
                selectedIds,
                selectedColor,
            );
        } catch {
            alert('決済の準備に失敗しました');
        } finally {
            setPosting(false);
        }
    };

    const posterName = profile?.nickname || profile?.username || '';

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-[32px] w-full max-w-lg max-h-[90vh] overflow-y-auto shadow-2xl">

                {/* ヘッダー */}
                <div className="sticky top-0 bg-white px-6 py-4 border-b border-gray-100 flex justify-between items-center rounded-t-[32px] z-10">
                    <div className="flex items-center gap-2">
                        <div className="p-2 bg-green-100 rounded-xl">
                            <Megaphone size={18} className="text-green-600" />
                        </div>
                        <div>
                            <p className="text-[9px] font-black text-gray-300 uppercase tracking-widest">Create AD</p>
                            <h2 className="text-sm font-black text-gray-900">広告を投稿する</h2>
                        </div>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-full transition-colors">
                        <X size={18} className="text-gray-400" />
                    </button>
                </div>

                <div className="p-6 space-y-6">

                    {/* 投稿者名プレビュー */}
                    <div className="flex items-center gap-2 px-1">
                        <div className="w-6 h-6 rounded-full bg-green-200 flex items-center justify-center text-[10px] font-black text-green-800">
                            {posterName.charAt(0).toUpperCase()}
                        </div>
                        <span className="text-[11px] font-bold text-gray-500">{posterName}</span>
                        <span className="text-[9px] text-gray-300 uppercase tracking-widest">· 投稿者</span>
                    </div>

                    {/* 広告内容入力 */}
                    <div className="bg-green-50 border-2 border-green-200 rounded-[24px] p-4 space-y-3">
                        <p className="text-[9px] font-black text-green-700 uppercase tracking-widest">AD CONTENT</p>

                        {/* ★ ここが修正ポイント: bg-white/50 の div を正しく閉じる */}
                        <div className="bg-white/50 rounded-xl p-3 border border-green-100 space-y-3">
                            <div>
                                <label className="text-[10px] font-bold text-green-800 mb-1 block">広告タイトル *</label>
                                <input
                                    value={adTitle}
                                    onChange={e => setAdTitle(e.target.value)}
                                    placeholder="例: 〇〇で蚤の市開催！"
                                    className="w-full px-3 py-2.5 rounded-xl border-2 border-green-200 bg-white text-[13px] outline-none focus:border-green-400 font-bold"
                                />
                            </div>

                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="text-[10px] font-bold text-green-800 mb-1 flex items-center gap-1">
                                        <Calendar size={10} /> 掲載開始日
                                    </label>
                                    <input
                                        type="date"
                                        value={startDate}
                                        onChange={e => setStartDate(e.target.value)}
                                        className="w-full px-3 py-2 rounded-xl border-2 border-green-200 bg-white text-[12px] outline-none focus:border-green-400"
                                    />
                                </div>
                                <div>
                                    <label className="text-[10px] font-bold text-green-800 mb-1 flex items-center gap-1">
                                        <Calendar size={10} /> 掲載終了日
                                    </label>
                                    <input
                                        type="date"
                                        value={endDate}
                                        onChange={e => setEndDate(e.target.value)}
                                        className="w-full px-3 py-2 rounded-xl border-2 border-green-200 bg-white text-[12px] outline-none focus:border-green-400"
                                    />
                                </div>
                            </div>

                            <div>
                                <label className="text-[10px] font-bold text-green-800 mb-1 block">広告内容</label>
                                <textarea
                                    value={adContent}
                                    onChange={e => setAdContent(e.target.value)}
                                    placeholder="詳細内容を入力..."
                                    className="w-full px-3 py-2.5 rounded-xl border-2 border-green-200 bg-white text-[12px] h-[120px] resize-none outline-none focus:border-green-400 leading-relaxed"
                                />
                            </div>
                        </div> {/* ← bg-white/50 の閉じタグ */}
                    </div> {/* ← bg-green-50 の閉じタグ */}

                    {/* カラー選択 */}
                    <div>
                        <p className="text-[9px] font-black text-gray-400 uppercase tracking-widest mb-3">Pick Member Color / 投稿色を選択</p>
                        <div className="flex gap-4 p-4 bg-gray-50 rounded-[24px] border border-gray-100 items-center justify-around">
                            {colorOptions.map(col => (
                                <div key={col.id} className="flex flex-col items-center gap-1">
                                    <button
                                        type="button"
                                        onClick={() => setSelectedColor(col.id)}
                                        className={`w-10 h-10 rounded-full ${col.bg} border-2 transition-all transform hover:scale-110 ${
                                            selectedColor === col.id ? 'border-gray-900 scale-110 shadow-md' : col.border
                                        }`}
                                    />
                                    <span className="text-[8px] font-bold text-gray-400">{col.label}</span>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Chat選択 */}
                    <div>
                        <p className="text-[9px] font-black text-gray-400 uppercase tracking-widest mb-3">投稿するChat（複数選択可）</p>
                        <div className="space-y-2">
                            {relatedCategories.map(cat => (
                                <button
                                    key={cat.id}
                                    onClick={() => toggleCategory(cat.id)}
                                    className={`w-full flex items-center justify-between p-3.5 rounded-2xl border-2 transition-all ${
                                        selectedIds.includes(cat.id)
                                            ? 'border-green-400 bg-green-50 text-green-800'
                                            : 'border-gray-100 bg-gray-50 text-gray-400 hover:border-gray-200'
                                    }`}
                                >
                                    <div className="flex items-center gap-3">
                                        <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${selectedIds.includes(cat.id) ? 'border-green-500 bg-green-500' : 'border-gray-300'}`}>
                                            {selectedIds.includes(cat.id) && <CheckCircle2 size={14} className="text-white" />}
                                        </div>
                                        <span className="font-bold text-sm">{cat.name}</span>
                                        {cat.id === currentCategoryId && (
                                            <span className="text-[8px] bg-green-200 text-green-700 px-1.5 py-0.5 rounded-full font-black">現在のChat</span>
                                        )}
                                    </div>
                                    <div className="flex items-center gap-1 text-[10px] font-bold opacity-60">
                                        <Users size={10} />
                                        <span>{cat.member_count || '-'}</span>
                                    </div>
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* 見積もり表示 */}
                    {loadingQuote && (
                        <p className="text-center text-gray-400 text-[11px] animate-pulse">計算中...</p>
                    )}
                    {quote && !loadingQuote && (
                        <div className="bg-gray-900 rounded-[24px] p-5 text-white">
                            <p className="text-[9px] font-black text-gray-400 uppercase tracking-widest mb-4">Ad Quote</p>
                            <div className="space-y-3">
                                <div className="flex justify-between items-center">
                                    <div className="flex items-center gap-2 text-[11px] font-bold text-gray-400">
                                        <Users size={12} /> のべ人数
                                    </div>
                                    <span className="font-mono font-bold">{quote.total_user_count?.toLocaleString() || '-'} 人</span>
                                </div>
                                <div className="flex justify-between items-center">
                                    <div className="flex items-center gap-2 text-[11px] font-bold text-gray-400">
                                        <Users size={12} /> 実人数
                                    </div>
                                    <span className="font-mono font-bold">{quote.unique_user_count?.toLocaleString() || '-'} 人</span>
                                </div>
                                <div className="border-t border-white/10 pt-3 flex justify-between items-end">
                                    <div className="flex items-center gap-2 text-[11px] font-bold text-gray-400">
                                        <CreditCard size={12} /> 請求額
                                    </div>
                                    <div className="text-right">
                                        <span className="text-2xl font-black">¥{quote.estimated_fee?.toLocaleString()}</span>
                                        <p className="text-[8px] text-green-400 font-bold mt-0.5">Miho's Fair Pricing</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* 投稿ボタン */}
                    <button
                        onClick={handlePost}
                        disabled={!adTitle.trim() || selectedIds.length === 0 || posting}
                        className="w-full py-4 bg-green-500 text-white rounded-[20px] font-black text-sm flex items-center justify-center gap-2 hover:bg-green-600 transition-all shadow-lg disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                        <Send size={16} />
                        {posting ? '投稿中...' : `${selectedIds.length}個のChatに投稿する`}
                    </button>

                </div>
            </div>
        </div>
    );
};

export default AdPostModal;
