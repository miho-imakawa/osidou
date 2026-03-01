import React, { useState, useEffect } from 'react';
import { fetchAdQuote } from '../api';
import { Calculator, Users, CreditCard, CheckCircle2 } from 'lucide-react';

const AdQuoteCalculator: React.FC = () => {
    // 💡 動作確認用のデモデータ（IDはバックエンドにあるものと合わせると動きます）
    const demoCategories = [
        { id: 1, name: '豊島区のママ会' },
        { id: 2, name: '千川・要町飲み仲間' },
        { id: 3, name: '推し道・ガジェット部' },
    ];

    const [selectedIds, setSelectedIds] = useState<number[]>([]);
    const [quote, setQuote] = useState<{ unique_user_count: number; estimated_fee: number } | null>(null);
    const [loading, setLoading] = useState(false);

    // 💡 選択が変わるたびにバックエンドの「誠実ロジック」を呼び出す
    useEffect(() => {
        const getQuote = async () => {
            if (selectedIds.length === 0) {
                setQuote(null);
                return;
            }
            setLoading(true);
            try {
                // api.ts に作った関数を呼び出し
                const data = await fetchAdQuote(selectedIds);
                setQuote(data);
            } catch (err) {
                console.error("見積もりの取得に失敗しました");
            } finally {
                setLoading(false);
            }
        };

        getQuote();
    }, [selectedIds]);

    const toggleCategory = (id: number) => {
        setSelectedIds(prev => 
            prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
        );
    };

    return (
        <div className="max-w-md mx-auto p-6 bg-white rounded-[32px] shadow-xl border border-gray-100 mt-10">
            <div className="flex items-center gap-2 mb-6">
                <Calculator className="text-pink-500" />
                <h2 className="text-xl font-black tracking-tighter uppercase">Ad Quote</h2>
            </div>

            <div className="space-y-3 mb-8">
                <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Select Communities</p>
                {demoCategories.map(cat => (
                    <button
                        key={cat.id}
                        onClick={() => toggleCategory(cat.id)}
                        className={`w-full flex items-center justify-between p-4 rounded-2xl border-2 transition-all ${
                            selectedIds.includes(cat.id) 
                            ? 'border-pink-500 bg-pink-50 text-pink-700' 
                            : 'border-gray-50 bg-gray-50 text-gray-400'
                        }`}
                    >
                        <span className="font-bold text-sm">{cat.name}</span>
                        {selectedIds.includes(cat.id) && <CheckCircle2 size={18} />}
                    </button>
                ))}
            </div>

            {loading && <p className="text-center text-gray-400 text-xs animate-pulse">Calculating...</p>}

            {quote && !loading && (
                <div className="bg-gray-900 rounded-[24px] p-6 text-white animate-in fade-in zoom-in duration-300">
                    <div className="flex justify-between items-center mb-4 opacity-70">
                        <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest">
                            <Users size={14} /> Total Reach
                        </div>
                        <span className="font-mono">{quote.unique_user_count} users</span>
                    </div>
                    
                    <div className="border-t border-white/10 pt-4 flex justify-between items-end">
                        <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest opacity-70">
                            <CreditCard size={14} /> Fee
                        </div>
                        <div className="text-right">
                            <span className="text-3xl font-black">¥{quote.estimated_fee.toLocaleString()}</span>
                            <p className="text-[8px] text-pink-400 font-bold mt-1 uppercase tracking-tighter">Miho's Fair Pricing applied</p>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default AdQuoteCalculator;