import React, { useState, useEffect } from 'react';
import { authApi, UserProfile as UserProfileType, fetchMyCategories, HobbyCategory, fetchMyMoodHistory, MoodLog } from '../api.ts';
import MoodInput from './MoodInput.tsx';
import { Mail, User, MapPin, Globe, Facebook, Twitter, Instagram, Bookmark, Edit, MessageSquare, AtSign, Clock, Heart } from 'lucide-react';
import { useParams } from 'react-router-dom';

interface UserProfileProps {
  profile: UserProfileType;
  fetchProfile: () => void;
}

const MOOD_TYPES = [
  { type: 'happy', label: 'ハッピー', emoji: '😊' },
  { type: 'excited', label: 'ワクワク', emoji: '🤩' },
  { type: 'calm', label: '落ち着き', emoji: '😌' },
  { type: 'tired', label: '疲労困憊', emoji: '😥' },
  { type: 'sad', label: '悲しい', emoji: '😭' },
  { type: 'anxious', label: '不安', emoji: '😟' },
  { type: 'angry', label: 'イライラ', emoji: '😠' },
  { type: 'neutral', label: '普通', emoji: '😐' },
  { type: 'grateful', label: '感謝', emoji: '🙏' },
  { type: 'motivated', label: 'やる気', emoji: '🔥' },
];

const UserProfile: React.FC<UserProfileProps> = ({ profile: myProfile, fetchProfile: fetchMyProfile }) => {
  const { userId } = useParams<{ userId: string }>();
  
  // 表示するプロフィール情報
  const [displayProfile, setDisplayProfile] = useState<UserProfileType | null>(null);
  const [isMe, setIsMe] = useState(true);
  const [loading, setLoading] = useState(true);
  
  // 編集モード
  const [isEditing, setIsEditing] = useState(false);
  const [tempProfile, setTempProfile] = useState<UserProfileType | null>(null);
  
  // コミュニティ・履歴
  const [myCategories, setMyCategories] = useState<HobbyCategory[]>([]);
  const [moodHistory, setMoodHistory] = useState<MoodLog[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  
  // フォロー状態
  const [isFollowing, setIsFollowing] = useState(false);
  
  // 💡 追加: フレンド申請状態
  const [incomingRequest, setIncomingRequest] = useState<any>(null);
  const [friendStatus, setFriendStatus] = useState<'none' | 'friend' | 'muted' | 'hidden'>('none');

  // 特定ユーザーのプロフィール取得
  const fetchTargetUserProfile = async (id: string) => {
    try {
      setLoading(true);
      const response = await authApi.get(`/users/${id}`);
      setDisplayProfile(response.data);
      setIsMe(false);
      
      // フォロー状態の確認（必要に応じてAPIを追加）
      try {
        const followResponse = await authApi.get(`/users/${id}/follow-status`);
        setIsFollowing(followResponse.data.is_following || false);
      } catch (err) {
        console.log("フォロー状態の取得をスキップ");
      }
    } catch (err) {
      console.error("ユーザー情報の取得に失敗しました", err);
      setDisplayProfile(null);
    } finally {
      setLoading(false);
    }
  };

  // 初期ロード: URLパラメータに応じて自分 or 他人のプロフィールを表示
  useEffect(() => {
    if (userId) {
      // 他人のページ
      fetchTargetUserProfile(userId);
    } else {
      // 自分のページ
      setDisplayProfile(myProfile);
      setTempProfile({
        ...myProfile,
        is_mood_visible: myProfile.is_mood_visible ?? true,
        is_member_count_visible: myProfile.is_member_count_visible ?? true
      });
      setIsMe(true);
      setLoading(false);
    }
  }, [userId, myProfile]);

  // コミュニティとログ履歴の取得
  useEffect(() => {
    if (!displayProfile?.id) return;
    
    const loadData = async () => {
      // コミュニティ取得（自分の場合のみ）
      if (isMe) {
        try {
          const categories = await fetchMyCategories();
          setMyCategories(categories);
        } catch (err) {
          console.error("Failed to fetch user categories:", err);
        }
      }
      
      // 気分ログ履歴取得
      setHistoryLoading(true);
      try {
        if (isMe) {
          // 自分のログは全件取得
          const history = await fetchMyMoodHistory();
          const sortedHistory = history.sort((a, b) => 
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
          );
          setMoodHistory(sortedHistory);
        } else {
          // 他人のログは公開分のみ取得（APIで制御されている前提）
          try {
            const response = await authApi.get(`/users/${displayProfile.id}/mood-history`);
            const sortedHistory = response.data.sort((a: MoodLog, b: MoodLog) => 
              new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
            );
            setMoodHistory(sortedHistory);
          } catch (err) {
            console.log("他人のログ履歴を取得できませんでした");
            setMoodHistory([]);
          }
        }
      } catch (err) {
        console.error("Failed to fetch mood history:", err);
      } finally {
        setHistoryLoading(false);
      }
    };
    
    loadData();
  }, [displayProfile?.id, isMe]);

  // 編集モードの変更を検知してログをリロード
  useEffect(() => {
    if (!isEditing && displayProfile?.id) {
      const reloadHistory = async () => {
        setHistoryLoading(true);
        try {
          const history = await fetchMyMoodHistory();
          const sortedHistory = history.sort((a, b) => 
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
          );
          setMoodHistory(sortedHistory);
        } catch (err) {
          console.error("Failed to reload mood history:", err);
        } finally {
          setHistoryLoading(false);
        }
      };
      reloadHistory();
    }
  }, [isEditing, displayProfile?.id]);

  // フォロー/アンフォロー
  const handleFollowToggle = async () => {
    if (!displayProfile?.id) return;
    
    try {
      const response = await authApi.post(`/users/${displayProfile.id}/follow`);
      const status = response.data.status;
      setIsFollowing(status === 'followed');
      fetchMyProfile();
    } catch (error) {
      console.error("フォロー操作に失敗しました:", error);
    }
  };
  
  // 💡 追加: フレンド申請の承認
  const handleAcceptRequest = async () => {
    if (!incomingRequest) return;
    
    try {
      await authApi.put(`/friend_requests/${incomingRequest.id}/status`, {
        status: 'accepted'
      });
      alert('フレンド申請を承認しました！');
      setIncomingRequest(null);
      setFriendStatus('friend');
      fetchMyProfile();
    } catch (error) {
      console.error("承認に失敗しました:", error);
      alert('承認に失敗しました');
    }
  };
  
  // 💡 追加: フレンド申請の拒否
  const handleRejectRequest = async () => {
    if (!incomingRequest) return;
    
    try {
      await authApi.put(`/friend_requests/${incomingRequest.id}/status`, {
        status: 'rejected'
      });
      alert('フレンド申請を拒否しました');
      setIncomingRequest(null);
    } catch (error) {
      console.error("拒否に失敗しました:", error);
      alert('拒否に失敗しました');
    }
  };
  
  // 💡 追加: 友達の非表示（友達解除）
  const handleHideFriend = async () => {
    if (!displayProfile?.id) return;
    if (!confirm('この友達を非表示にしますか？（ホームから気分ログが消えます）')) return;
    
    try {
      await authApi.put(`/users/${displayProfile.id}/friend-status`, {
        action: 'hide'
      });
      setFriendStatus('hidden');
      alert('友達を非表示にしました');
      fetchMyProfile();
    } catch (error) {
      console.error("非表示に失敗しました:", error);
      alert('非表示に失敗しました');
    }
  };
  
  // 💡 追加: 友達の更新停止（ミュート）
  const handleMuteFriend = async () => {
    if (!displayProfile?.id) return;
    if (!confirm('この友達をミュートしますか？（気分ログの更新が停止します）')) return;
    
    try {
      await authApi.put(`/users/${displayProfile.id}/friend-status`, {
        action: 'mute'
      });
      setFriendStatus('muted');
      alert('友達をミュートしました');
      fetchMyProfile();
    } catch (error) {
      console.error("ミュートに失敗しました:", error);
      alert('ミュートに失敗しました');
    }
  };
  
  // 💡 追加: 友達の通常状態に戻す
  const handleUnmuteFriend = async () => {
    if (!displayProfile?.id) return;
    
    try {
      await authApi.put(`/users/${displayProfile.id}/friend-status`, {
        action: 'unmute'
      });
      setFriendStatus('friend');
      alert('ミュートを解除しました');
      fetchMyProfile();
    } catch (error) {
      console.error("ミュート解除に失敗しました:", error);
      alert('ミュート解除に失敗しました');
    }
  };

  // プロフィール更新
  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tempProfile) return;
    
    try {
      const updateData = Object.fromEntries(
        Object.entries(tempProfile)
          .filter(([key, v]) => v !== null && v !== undefined)
          .filter(([key]) => !['id', 'username', 'email', 'prefecture', 'city'].includes(key))
      );
      await authApi.put('/users/me', updateData);
      setIsEditing(false);
      fetchMyProfile();
      console.log('プロフィールを更新しました！');
    } catch (err) {
      console.error('プロフィールの更新に失敗しました:', err);
    }
  };

  const SNS_FIELDS = [
    { key: 'x_url' as keyof UserProfileType, icon: Twitter, color: 'text-gray-900', label: 'X (Twitter)' },
    { key: 'instagram_url' as keyof UserProfileType, icon: Instagram, color: 'text-pink-600', label: 'Instagram' },
    { key: 'facebook_url' as keyof UserProfileType, icon: Facebook, color: 'text-blue-600', label: 'Facebook' },
    { key: 'note_url' as keyof UserProfileType, icon: Globe, color: 'text-green-600', label: 'note' },
    { key: 'threads_url' as keyof UserProfileType, icon: AtSign, color: 'text-gray-600', label: 'Threads' },
  ];

  const toggleEdit = () => setIsEditing(!isEditing);

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const options: Intl.DateTimeFormatOptions = { 
      year: 'numeric', 
      month: 'numeric', 
      day: 'numeric', 
      hour: '2-digit', 
      minute: '2-digit' 
    };
    return date.toLocaleString('ja-JP', options);
  };

  if (loading) return <div className="text-center py-10">読み込み中...</div>;
  if (!displayProfile) return <div className="text-center py-10">ユーザーが見つかりません。</div>;

  return (
    <div className="max-w-4xl mx-auto p-6">
      {/* ヘッダー */}
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-gray-800 flex items-center gap-2">
          <User className="text-pink-600" />
          {displayProfile.nickname || displayProfile.username} のページ
        </h1>
        
        <div className="flex space-x-2">
          {!isMe ? (
            <>
              {/* 💡 フレンド申請が届いている場合 */}
              {incomingRequest && (
                <div className="flex gap-2">
                  <button
                    onClick={handleAcceptRequest}
                    className="px-4 py-2 bg-green-500 hover:bg-green-600 text-white rounded-lg flex items-center gap-2 font-semibold"
                  >
                    承認
                  </button>
                  <button
                    onClick={handleRejectRequest}
                    className="px-4 py-2 bg-gray-400 hover:bg-gray-500 text-white rounded-lg flex items-center gap-2 font-semibold"
                  >
                    拒否
                  </button>
                </div>
              )}
              
              {/* 💡 友達の場合：管理ボタン */}
              {friendStatus === 'friend' && !incomingRequest && (
                <div className="flex gap-2">
                  <button
                    onClick={handleMuteFriend}
                    className="px-3 py-2 bg-orange-500 hover:bg-orange-600 text-white rounded-lg text-sm"
                  >
                    ミュート
                  </button>
                  <button
                    onClick={handleHideFriend}
                    className="px-3 py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg text-sm"
                  >
                    非表示
                  </button>
                </div>
              )}
              
              {/* 💡 ミュート中の場合 */}
              {friendStatus === 'muted' && (
                <button
                  onClick={handleUnmuteFriend}
                  className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-semibold"
                >
                  ミュート解除
                </button>
              )}
              
              {/* 💡 非表示中の場合 */}
              {friendStatus === 'hidden' && (
                <span className="px-4 py-2 bg-gray-200 text-gray-600 rounded-lg font-semibold">
                  非表示中
                </span>
              )}
              
              {/* 💡 通常のフォローボタン（友達でない場合） */}
              {friendStatus === 'none' && !incomingRequest && (
                <button
                  onClick={handleFollowToggle}
                  className={`px-4 py-2 rounded-lg transition duration-150 flex items-center gap-2 text-white font-semibold ${
                    isFollowing ? 'bg-gray-500 hover:bg-gray-600' : 'bg-red-500 hover:bg-red-600'
                  }`}
                >
                  <Heart size={20} className={isFollowing ? 'text-white' : 'text-white fill-current'} />
                  {isFollowing ? 'フォロー中' : 'フォローする'}
                </button>
              )}
            </>
          ) : (
            <button
              onClick={toggleEdit}
              className="px-4 py-2 bg-pink-600 text-white rounded-lg hover:bg-pink-700 flex items-center gap-2"
            >
              <Edit size={20} />
              {isEditing ? '編集を終了' : 'プロフィール編集'}
            </button>
          )}
        </div>
      </div>

      {/* 編集モード */}
      {isEditing && isMe && tempProfile ? (
        <form onSubmit={handleUpdate} className="space-y-6 bg-white p-6 rounded-lg shadow">
          <div className="border-b pb-4">
            <h2 className="text-xl font-bold text-gray-800 mb-4">基本情報</h2>
            
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700">
                登録メールアドレス（変更不可）
              </label>
              <div className="mt-1 block w-full border border-gray-300 bg-gray-100 rounded-md shadow-sm p-2 text-gray-600">
                {displayProfile.email}
              </div>
            </div>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700">ニックネーム</label>
              <input
                type="text"
                value={tempProfile.nickname || ''}
                onChange={(e) => setTempProfile({ ...tempProfile, nickname: e.target.value })}
                className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">自己紹介</label>
              <textarea
                value={tempProfile.bio || ''}
                onChange={(e) => setTempProfile({ ...tempProfile, bio: e.target.value })}
                rows={4}
                className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2"
              ></textarea>
            </div>
          </div>
          
          <div className="border-b pb-4">
            <h2 className="text-xl font-bold text-gray-800 mb-4">SNSリンク</h2>
            {SNS_FIELDS.map(({ key, label }) => (
              <div key={key} className="mb-4">
                <label className="block text-sm font-medium text-gray-700">{label} URL</label>
                <input
                  type="url"
                  value={(tempProfile[key] as string) || ''}
                  onChange={(e) => setTempProfile({ ...tempProfile, [key]: e.target.value })}
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2"
                />
              </div>
            ))}
          </div>

          <div>
            <h2 className="text-xl font-bold text-gray-800 mb-4">公開設定</h2>
            <div className="space-y-2">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={tempProfile.is_mood_visible || false}
                  onChange={(e) => setTempProfile({ ...tempProfile, is_mood_visible: e.target.checked })}
                  className="h-4 w-4 text-pink-600 border-gray-300 rounded"
                />
                <span className="text-sm text-gray-700">今日の気分ログを他のユーザーに公開する</span>
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={tempProfile.is_member_count_visible || false}
                  onChange={(e) => setTempProfile({ ...tempProfile, is_member_count_visible: e.target.checked })}
                  className="h-4 w-4 text-pink-600 border-gray-300 rounded"
                />
                <span className="text-sm text-gray-700">参加カテゴリの人数情報（地域人数など）を公開する</span>
              </label>
            </div>
          </div>

          <button
            type="submit"
            className="w-full bg-pink-600 text-white py-2 rounded-lg hover:bg-pink-700 font-semibold"
          >
            変更を保存
          </button>
        </form>
      ) : (
        // 表示モード
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="md:col-span-2 bg-white p-6 rounded-lg shadow">
              <h2 className="text-xl font-bold text-gray-800 mb-4">自己紹介</h2>
              <p className="text-gray-700 whitespace-pre-wrap">
                {displayProfile.bio || 'まだ自己紹介がありません。'}
              </p>
            </div>

            <div className="md:col-span-1 bg-pink-50 p-6 rounded-lg shadow">
              <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center gap-2">
                <Bookmark className="text-pink-600" />
                公開設定
              </h2>
              <div className="space-y-2 text-sm text-gray-700">
                <p className="flex items-center gap-2">
                  <span className="font-semibold">気分ログ:</span>
                  <span className={displayProfile.is_mood_visible ? 'text-green-600' : 'text-gray-500'}>
                    {displayProfile.is_mood_visible ? '公開中' : '非公開'}
                  </span>
                </p>
              </div>
              {isMe && (
                <p className="text-xs text-gray-500 mt-4">
                  メールアドレスや所在地情報はプロフィール編集画面でのみ確認できます。
                </p>
              )}
            </div>
          </div>

          {isMe && (
            <div className="bg-white p-6 rounded-lg shadow">
              <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center gap-2">
                <MessageSquare className="text-pink-600" />
                参加コミュニティ (Chat/掲示板)
              </h2>
              {myCategories.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {myCategories.map(cat => (
                    <span key={cat.id} className="px-3 py-1 bg-pink-100 text-pink-700 rounded-full text-sm">
                      {cat.name}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 text-sm">
                  まだ参加しているコミュニティはありません。
                </p>
              )}
            </div>
          )}

          <div className="bg-white p-6 rounded-lg shadow">
            <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center gap-2">
              <Globe className="text-pink-600" />
              SNSリンク
            </h2>
            <div className="space-y-2">
              {SNS_FIELDS.map(({ key, icon: Icon, color, label }) => {
                const url = displayProfile[key] as string | null | undefined;
                if (!url) return null;
                return (
                  <a
                    key={key}
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 text-blue-600 hover:underline"
                  >
                    <Icon size={20} className={color} />
                    {label}
                  </a>
                );
              })}
            </div>
          </div>

          <div className="pt-4 border-t">
            {isMe && !displayProfile.is_mood_visible && (
              <div className="mb-4 text-sm text-center text-red-500 bg-red-50 p-4 rounded-lg">
                現在、気分ログ履歴は非公開設定です。他のユーザーには表示されません。
              </div>
            )}

            <h2 className="text-xl font-semibold text-gray-800 mb-4 flex items-center">
              <Clock className="w-5 h-5 mr-2 text-pink-500" /> 
              {isMe ? '自分の気分ログ履歴' : `${displayProfile.nickname || displayProfile.username}の気分ログ履歴`}
            </h2>
            
            {historyLoading && <p className="text-gray-500">履歴を読み込み中...</p>}
            
            {!historyLoading && moodHistory.length === 0 && (
              <p className="text-gray-500 italic">
                {isMe ? 'まだ気分ログの投稿履歴がありません。' : '公開されている気分ログがありません。'}
              </p>
            )}

            <div className="space-y-2">
              {moodHistory.map(log => {
                const moodDetail = MOOD_TYPES.find(m => m.type === log.mood_type) || 
                  { type: 'neutral', label: '普通', emoji: '😐' };

                return (
                  <div 
                    key={log.id} 
                    className="flex items-center justify-between p-3 bg-white rounded-lg border border-gray-200 hover:bg-gray-50 transition duration-150"
                  >
                    <div className="flex items-center overflow-hidden flex-1">
                      <span className="text-xs text-gray-500 mr-4 shrink-0">
                        {formatDate(log.created_at)}
                      </span>
                      <p className="text-sm font-medium text-gray-800 flex items-center">
                        <span className="text-lg mr-2 shrink-0">{moodDetail.emoji}</span>
                        <span className="shrink-0">{moodDetail.label}</span>
                        {log.comment && (
                          <span className="text-sm text-gray-600 ml-2 truncate">
                            : {log.comment}
                          </span>
                        )}
                      </p>
                    </div>
                    {isMe && !displayProfile.is_mood_visible && (
                      <span className="text-xs font-semibold text-red-500 shrink-0 border border-red-300 px-2 py-0.5 rounded-full ml-2">
                        非公開
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserProfile;