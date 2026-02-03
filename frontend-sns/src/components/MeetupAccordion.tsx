import React, { useState } from 'react';
import { 
  Calendar, MapPin, Users, ChevronDown, ChevronUp, 
  CircleDollarSign, ExternalLink 
} from 'lucide-react';
import { Post } from '../api';

interface MeetupAccordionProps {
  post: Post;
  onJoin?: (postId: number) => void;
}

export const MeetupAccordion: React.FC<MeetupAccordionProps> = ({ post, onJoin }) => {
  const [isOpen, setIsOpen] = useState(false);

  // 💡 追加: Googleマップを開く関数
  const handleMapClick = (e: React.MouseEvent) => {
    e.stopPropagation(); // 蛇腹が開閉するのを防ぐ
    if (!post.meetup_location) return;
    // 住所をURL用に変換してGoogleマップで開く
    const url = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(post.meetup_location)}`;
    window.open(url, '_blank');
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return "未設定";
    return new Date(dateStr).toLocaleString('ja-JP', {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
    });
  };

  return (
    <div className="border-2 border-pink-100 rounded-2xl overflow-hidden bg-white shadow-sm mb-4">
      {/* 概要部分 */}
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="w-full p-4 flex flex-col gap-2 hover:bg-pink-50 transition-colors text-left"
      >
        <div className="flex justify-between items-start">
          <span className="bg-pink-100 text-pink-700 text-[10px] font-bold px-2 py-0.5 rounded-full uppercase">Meet Up</span>
          {isOpen ? <ChevronUp className="text-gray-400" size={20} /> : <ChevronDown className="text-gray-400" size={20} />}
        </div>

        <div className="grid grid-cols-2 gap-y-2 text-sm">
          <div className="flex items-center gap-1.5 text-gray-700">
            <Calendar size={14} className="text-pink-500" />
            <span className="font-bold">{formatDate(post.meetup_date)}</span>
          </div>
          
          {/* 💡 修正: ここにマップボタンを追加 */}
          <div className="flex items-center gap-1.5 text-gray-700 overflow-hidden">
            <MapPin size={14} className="text-pink-500 shrink-0" />
            <span className="truncate">{post.region_tag_city || "場所未指定"}</span>
            {post.meetup_location && (
              <div
                onClick={handleMapClick}
                className="ml-1 p-1 hover:bg-pink-200 rounded text-pink-600 bg-pink-50 cursor-pointer flex items-center"
                title="地図を開く"
              >
                <ExternalLink size={12} />
              </div>
            )}
          </div>

          <div className="flex items-center gap-1.5 text-gray-700">
            <Users size={14} className="text-pink-500" />
            <span>{post.participation_count || 0} / {post.meetup_capacity || "--"} 人</span>
          </div>
        </div>
      </button>

      {/* 詳細部分 */}
      {isOpen && (
        <div className="px-4 pb-4 pt-2 border-t border-pink-50 bg-gray-50 bg-opacity-30">
          <div className="space-y-4">
            <div className="text-gray-800 text-sm whitespace-pre-wrap leading-relaxed">
              {post.content}
            </div>

            {/* 費用詳細 */}
            <div className="flex items-start gap-2 p-3 bg-blue-50 rounded-xl border border-blue-100">
              <CircleDollarSign size={18} className="text-blue-600 mt-0.5" />
              <div>
                <p className="text-[10px] font-bold text-blue-600 uppercase">費用・条件</p>
                <p className="text-sm text-blue-800">
                   {/* 💡 お茶代などの表記にも対応 */}
                   {post.meetup_fee_info || "お茶代各自など、詳細は主催者へ"}
                </p>
              </div>
            </div>

            <button 
              onClick={() => onJoin && onJoin(post.id)}
              className="w-full py-2.5 bg-pink-600 hover:bg-pink-700 text-white rounded-xl font-bold transition-all shadow-md active:scale-95"
            >
              このイベントに参加する
            </button>
          </div>
        </div>
      )}
    </div>
  );
};