import React, { useState, useEffect } from 'react';
import { authApi } from '../api';
import { Send, X, MessageCircle } from 'lucide-react';

interface MeetupChatModalProps {
  postId: number;
  onClose: () => void;
  meetupTitle: string;
}

const MeetupChatModal: React.FC<MeetupChatModalProps> = ({ postId, onClose, meetupTitle }) => {
  const [messages, setMessages] = useState<any[]>([]);
  const [newMsg, setNewMsg] = useState('');

  // 💡 修正：バックエンドのURL /meetup-chat/${postId} に合わせる
  const fetchMessages = async () => {
    try {
      const res = await authApi.get(`/meetup-chat/${postId}`);
      setMessages(res.data);
    } catch (err) {
      console.error("Failed to fetch meetup messages");
    }
  };

  useEffect(() => {
    fetchMessages();
    const interval = setInterval(fetchMessages, 3000); // 3秒おきに更新
    return () => clearInterval(interval);
  }, [postId]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newMsg.trim()) return;
    try {
      // 💡 修正：送信先URLも /meetup-chat/${postId} に合わせる
      await authApi.post(`/meetup-chat/${postId}`, { content: newMsg });
      setNewMsg('');
      fetchMessages();
    } catch (err) {
      alert("送信に失敗しました。サーバーのログを確認してください。");
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
      <div className="bg-white w-full max-w-lg rounded-[32px] overflow-hidden shadow-2xl flex flex-col h-[80vh]">
        <div className="p-4 border-b flex justify-between items-center bg-orange-50">
          <div className="flex items-center gap-2">
            <MessageCircle className="text-orange-600" size={20} />
            <h2 className="font-bold text-orange-900 truncate max-w-[200px]">{meetupTitle}</h2>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-white/50 rounded-full"><X size={20} /></button>
        </div>
        
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

        <form onSubmit={handleSend} className="p-4 border-t flex gap-2">
          <input 
            value={newMsg} 
            onChange={(e) => setNewMsg(e.target.value)}
            placeholder="参加者限定メッセージ..."
            className="flex-1 px-4 py-2 bg-gray-100 rounded-full text-sm outline-none focus:ring-2 focus:ring-orange-200"
          />
          <button type="submit" className="p-2 bg-orange-600 text-white rounded-full"><Send size={18} /></button>
        </form>
      </div>
    </div>
  );
};

export default MeetupChatModal;