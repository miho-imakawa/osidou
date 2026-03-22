import React, { useState, useEffect } from 'react';
import { authApi } from '../api';
import { Send, X, MessageCircle, AlertTriangle } from 'lucide-react';

const BACKEND_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface MeetupChatModalProps {
  postId: number;
  onClose: () => void;
  meetupTitle: string;
  currentUserId: number;
  isOrganizer: boolean;
}

const MeetupChatModal: React.FC<MeetupChatModalProps> = ({
  postId, onClose, meetupTitle, currentUserId, isOrganizer
}) => {
  const [messages, setMessages] = useState<any[]>([]);
  const [participants, setParticipants] = useState<any[]>([]);
  const [newMsg, setNewMsg] = useState('');

  const fetchMessages = async () => {
    try {
      const res = await authApi.get(`/meetup-chat/${postId}`);
      setMessages(res.data);
    } catch (err) {
      console.error("Failed to fetch meetup messages");
    }
  };

  const fetchParticipants = async () => {
    try {
      const res = await authApi.get(`/posts/${postId}/responses`);
      setParticipants(res.data.filter((r: any) => r.is_participation));
    } catch {}
  };

  useEffect(() => {
      fetchMessages();
      fetchParticipants();
      let interval = setInterval(fetchMessages, 3000);
      let idleTimer: ReturnType<typeof setTimeout>;

      const resetIdleTimer = () => {
          clearTimeout(idleTimer);
          clearInterval(interval);
          interval = setInterval(fetchMessages, 3000);
          idleTimer = setTimeout(() => {
              clearInterval(interval);
          }, 10 * 60 * 1000);
      };

      const events = ['mousemove', 'keydown', 'click', 'scroll', 'touchstart'];
      events.forEach(e => document.addEventListener(e, resetIdleTimer));
      resetIdleTimer();

      const handleVisibilityChange = () => {
          if (document.hidden) {
              clearInterval(interval);
              clearTimeout(idleTimer);
          } else {
              resetIdleTimer();
          }
      };
      document.addEventListener('visibilitychange', handleVisibilityChange);

      return () => {
          clearInterval(interval);
          clearTimeout(idleTimer);
          events.forEach(e => document.removeEventListener(e, resetIdleTimer));
          document.removeEventListener('visibilitychange', handleVisibilityChange);
      };
  }, [postId]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newMsg.trim()) return;
    try {
      await authApi.post(`/meetup-chat/${postId}`, { content: newMsg });
      setNewMsg('');
      fetchMessages();
    } catch {
      alert("送信に失敗しました。");
    }
  };

  // 主催者：参加者をNo Showマーク
  const handleNoShow = async (targetUserId: number, nickname: string) => {
    if (!window.confirm(`${nickname} さんをNo Showとしてマークしますか？\n参加費100%が課金されます。`)) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/stripe/meetup-noshow`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          postId,
          userId: currentUserId,
          targetId: targetUserId,
          type: 'organizer',
        }),
      });
      const result = await res.json();
      if (result.status === 'noshow_charged') {
        alert(`¥${result.amount} を課金しました。`);
      } else {
        alert('カード未登録のためスキップしました。');
      }
      fetchParticipants();
    } catch {
      alert('No Show処理に失敗しました。');
    }
  };

  // 参加者：主催者No Showを報告
  const handleOrganizerNoShow = async () => {
    if (!window.confirm('主催者が来ていないことを報告しますか？\n課金済みの場合は返金されます。')) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/stripe/meetup-noshow`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          postId,
          userId: currentUserId,
          type: 'participant',
        }),
      });
      const result = await res.json();
      alert(`報告を受け付けました。${result.refunded > 0 ? ` ${result.refunded}名に返金しました。` : ''}`);
    } catch {
      alert('報告に失敗しました。');
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
      <div className="bg-white w-full max-w-lg rounded-[32px] overflow-hidden shadow-2xl flex flex-col h-[80vh]">

        {/* Header */}
        <div className="p-4 border-b flex justify-between items-center bg-orange-50 shrink-0">
          <div className="flex items-center gap-2">
            <MessageCircle className="text-orange-600" size={20} />
            <h2 className="font-bold text-orange-900 truncate max-w-[200px]">{meetupTitle}</h2>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-white/50 rounded-full">
            <X size={20} />
          </button>
        </div>

        {/* 主催者：参加者チェックリスト */}
        {isOrganizer && participants.length > 0 && (
          <div className="px-4 py-3 bg-orange-50/50 border-b shrink-0">
            <p className="text-[9px] font-black text-orange-400 uppercase tracking-widest mb-2">
              参加者チェック（No Show マーク）
            </p>
            <div className="flex flex-wrap gap-2">
              {participants.map((p) => (
                <div key={p.user_id}
                  className="flex items-center gap-1.5 bg-white border border-orange-100 px-2 py-1 rounded-full"
                >
                  <span className="text-[11px] font-bold text-gray-700">
                    {p.author_nickname || `User-${p.user_id}`}
                  </span>
                  <button
                    onClick={() => handleNoShow(p.user_id, p.author_nickname || `User-${p.user_id}`)}
                    className="text-[9px] font-black text-red-400 hover:text-red-600 transition-colors"
                    title="No Showマーク"
                  >
                    <AlertTriangle size={11} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 参加者：主催者No Show報告ボタン */}
        {!isOrganizer && (
          <div className="px-4 py-2 bg-red-50/50 border-b shrink-0">
            <button
              onClick={handleOrganizerNoShow}
              className="text-[10px] font-black text-red-400 hover:text-red-600 flex items-center gap-1 transition-colors"
            >
              <AlertTriangle size={12} />
              主催者が来ていない場合は報告する
            </button>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50">
          {messages.map((m) => (
            <div key={m.id} className="flex flex-col">
              <span className="text-[10px] font-bold text-gray-400 ml-2">{m.author_nickname}</span>
              <div className="bg-white p-3 rounded-2xl shadow-sm border border-orange-100 max-w-[85%]">
                <p className="text-sm text-gray-700">{m.content}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Input */}
        <form onSubmit={handleSend} className="p-4 border-t flex gap-2 shrink-0">
          <input
            value={newMsg}
            onChange={(e) => setNewMsg(e.target.value)}
            placeholder="参加者限定メッセージ..."
            className="flex-1 px-4 py-2 bg-gray-100 rounded-full text-sm outline-none focus:ring-2 focus:ring-orange-200"
          />
          <button type="submit" className="p-2 bg-orange-600 text-white rounded-full">
            <Send size={18} />
          </button>
        </form>
      </div>
    </div>
  );
};

export default MeetupChatModal;