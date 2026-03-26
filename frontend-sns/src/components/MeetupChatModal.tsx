import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { authApi } from '../api';
import { Send, X, MessageCircle, AlertTriangle } from 'lucide-react';

const BACKEND_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// ==========================================
// 💡 スタンプ定義
// ==========================================
const STAMP_CATEGORIES = [
  { label: 'お返事', stamps: ['✅', '👀', '🙋'] },
  { label: 'お食事', stamps: ['🥩', '🐟', '🥗'] },
  { label: '飲み物', stamps: ['🍷', '🍺', '☕'] },
  { label: 'その他', stamps: ['❓', '🆘', '✨'] },
];
const ALL_STAMPS = STAMP_CATEGORIES.flatMap((c) => c.stamps);

// ==========================================
// 💡 型定義
// ==========================================
interface ReactionSummary {
  reaction: string;
  count: number;
  reacted_by_me: boolean;
}

interface Message {
  id: number;
  content: string;
  created_at: string;
  user_id: number;
  post_id: number;
  author_nickname?: string;
  reactions: ReactionSummary[];
}

interface MeetupChatModalProps {
  postId: number;
  onClose: () => void;
  meetupTitle: string;
  currentUserId: number;
  isOrganizer: boolean;
}

// ==========================================
// 💡 スタンプピッカー（モーダル中央固定）
// ==========================================
const StampPicker: React.FC<{
  onSelect: (stamp: string) => void;
  onClose: () => void;
}> = ({ onSelect, onClose }) => {
  return (
    // モーダル内オーバーレイ（z-20 でメッセージ一覧の上に重ねる）
    <div
      className="absolute inset-0 z-20 flex items-end justify-center pb-20"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-3xl shadow-2xl border border-orange-100 p-4 w-[90%] max-w-sm"
        onClick={e => e.stopPropagation()}
      >
        <p className="text-[10px] font-black text-orange-400 uppercase tracking-widest mb-3 text-center">
          スタンプを選ぶ
        </p>
        {STAMP_CATEGORIES.map((cat) => (
          <div key={cat.label} className="mb-3 last:mb-0">
            <p className="text-[9px] font-bold text-gray-400 mb-1.5">{cat.label}</p>
            <div className="flex gap-2">
              {cat.stamps.map((s) => (
                <button
                  key={s}
                  onClick={() => { onSelect(s); onClose(); }}
                  className="text-2xl hover:scale-125 active:scale-95 transition-transform"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// ==========================================
// 💡 メインコンポーネント
// ==========================================
const MeetupChatModal: React.FC<MeetupChatModalProps> = ({
  postId, onClose, meetupTitle, currentUserId, isOrganizer
}) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [participants, setParticipants] = useState<any[]>([]);
  const [newMsg, setNewMsg] = useState('');
  // スタンプピッカーを開いているメッセージID（nullなら閉じ）
  const [stampPickerFor, setStampPickerFor] = useState<number | null>(null);
  // 新着メッセージ送信後にスクロールをトップへ戻すためのref
  const messagesTopRef = useRef<HTMLDivElement>(null);

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
      await fetchMessages();
      // 新着が上に来るので、送信後はスクロールをトップへ
      messagesTopRef.current?.scrollIntoView({ behavior: 'smooth' });
    } catch {
      alert("送信に失敗しました。");
    }
  };

  // ==========================================
  // 💡 リアクション送信（トグル）
  // ==========================================
  const handleReaction = async (messageId: number, stamp: string) => {
    try {
      const res = await authApi.post(
        `/meetup-chat/${postId}/messages/${messageId}/reaction`,
        { reaction: stamp }
      );
      // レスポンスの reactions で該当メッセージを楽観的更新
      setMessages(prev =>
        prev.map(m =>
          m.id === messageId ? { ...m, reactions: res.data.reactions } : m
        )
      );
    } catch {
      console.error("リアクション送信に失敗しました");
    }
  };

  // ==========================================
  // 💡 No Show 処理（変更なし）
  // ==========================================
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
    <div
      className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100] flex items-center justify-center p-4"
      onClick={() => setStampPickerFor(null)} // ピッカー外クリックで閉じる
    >
      <div
        className="relative bg-white w-full max-w-lg rounded-[32px] overflow-hidden shadow-2xl flex flex-col h-[80vh]"
        onClick={e => e.stopPropagation()}
      >
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

        {/* Messages（新しい順＝上から追加） */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50">
          {/* 送信後のスクロール先（最上部） */}
          <div ref={messagesTopRef} />
          {messages.map((m) => (
            <div key={m.id} className="flex flex-col group">
              {/* 投稿者名（react-router-dom の Link に修正済み） */}
              <Link
                to={`/profile/${m.user_id}`}
                className="text-[10px] font-bold text-gray-400 ml-2 hover:text-pink-500 hover:underline transition-colors"
              >
                {m.author_nickname}
              </Link>

              {/* メッセージ本体 + スタンプボタン */}
              <div className="flex items-end gap-1">
                <div className="bg-white p-3 rounded-2xl shadow-sm border border-orange-100 max-w-[80%]">
                  <p className="text-sm text-gray-700">{m.content}</p>
                </div>

                {/* スタンプボタン（常時表示・PC/モバイル共通） */}
                <button
                  onClick={() =>
                    setStampPickerFor(stampPickerFor === m.id ? null : m.id)
                  }
                  className="text-base opacity-40 hover:opacity-100 active:scale-95 transition-all leading-none shrink-0"
                  title="スタンプ"
                >
                  😊
                </button>
              </div>

              {/* リアクション表示 */}
              {m.reactions && m.reactions.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1 ml-1">
                  {m.reactions.map((r) => (
                    <button
                      key={r.reaction}
                      onClick={() => handleReaction(m.id, r.reaction)}
                      className={`
                        flex items-center gap-0.5 px-2 py-0.5 rounded-full text-xs font-bold
                        border transition-all active:scale-95
                        ${r.reacted_by_me
                          ? 'bg-orange-100 border-orange-300 text-orange-700'
                          : 'bg-white border-gray-200 text-gray-600 hover:border-orange-200'}
                      `}
                    >
                      <span>{r.reaction}</span>
                      <span className="text-[10px]">{r.count}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* スタンプピッカー（モーダル中央固定・PC/モバイル共通） */}
        {stampPickerFor !== null && (
          <StampPicker
            onSelect={(stamp) => handleReaction(stampPickerFor, stamp)}
            onClose={() => setStampPickerFor(null)}
          />
        )}

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
