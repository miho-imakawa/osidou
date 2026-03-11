import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell } from 'lucide-react';

const PendingFriendBanner = ({ count }: { count: number }) => {
    const navigate = useNavigate();
    if (count === 0) return null;

    return (
        <div 
            onClick={() => navigate('/friends')} // 💡 適切なパスに変更してください
            className="mb-4 bg-amber-50 border border-amber-200 rounded-2xl p-4 flex items-center justify-between cursor-pointer hover:bg-amber-100 transition-all shadow-sm animate-pulse"
        >
            <div className="flex items-center gap-3">
                <div className="bg-amber-500 p-2 rounded-full text-white">
                    <Bell size={16} />
                </div>
                <span className="text-sm font-bold text-amber-900">
                    ともだち申請が <strong className="text-lg text-amber-600">{count}件</strong> 届いています
                </span>
            </div>
            <span className="text-xs font-black text-amber-500 uppercase tracking-widest">
                Check Now →
            </span>
        </div>
    );
};

export default PendingFriendBanner;