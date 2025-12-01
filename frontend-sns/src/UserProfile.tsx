import React, { useState, useEffect } from 'react';
import { authApi, UserProfile } from './api.ts'; // 💡 拡張子を明示
import { Mail, User, MapPin, Globe, Facebook, Twitter, Instagram, Bookmark, Edit } from 'lucide-react';

// 初期データとして空のオブジェクトを定義
const initialProfile: UserProfile = {
    id: 0,
    username: 'loading',
    email: '',
    nickname: '読み込み中...',
    bio: null,
    prefecture: null,
    city: null,
    town: null,
    oshi_page_url: null,
    facebook_url: null,
    x_url: null,
    instagram_url: null,
    note_url: null,
    is_member_count_visible: true,
    is_mood_visible: true,
    current_mood: 'neutral', 
    current_mood_comment: null,
};

const UserProfileComponent: React.FC = () => {
    const [profile, setProfile] = useState<UserProfile>(initialProfile);
    const [isEditing, setIsEditing] = useState(false);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // ユーザー情報のフェッチ
    const fetchProfile = async () => {
        setLoading(true);
        try {
            // FastAPIの /users/me エンドポイントを呼び出す
            const response = await authApi.get<UserProfile>('/users/me');
            setProfile(response.data);
            setError(null);
        } catch (err) {
            console.error(err);
            setError('プロフィールの読み込みに失敗しました。認証状態を確認してください。');
        } finally {
            setLoading(false);
        }
    };

    // プロフィール情報の更新
    const handleUpdate = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            // 更新データからNull値を除外
            const updateData = Object.fromEntries(
                Object.entries(profile)
                .filter(([key, v]) => v !== null && v !== undefined)
                .filter(([key, v]) => key !== 'id' && key !== 'username' && key !== 'email') // IDやusernameなどは更新しない
            );

            // FastAPIの /users/me エンドポイントを呼び出す (PUT/UPDATE)
            await authApi.put('/users/me', updateData);
            setIsEditing(false);
            fetchProfile(); // 更新後に再フェッチ
        } catch (err) {
            console.error(err);
            setError('プロフィールの更新に失敗しました。');
        }
    };

    useEffect(() => {
    // 仮のトークンを設置 (認証が完了している前提)
    if (!localStorage.getItem('access_token')) {
        // 🚨 修正: ここに最新の有効なJWTトークンを貼り付けてください
        localStorage.setItem('access_token', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMjZAc3RyaW5nLmNvbSIsImV4cCI6MTc2NDYxMTg1MX0.u2tkDj_tUQFZrPY7A3F1EImqKnBrz5yc273yBOd3FJc'); 
    }
    fetchProfile();
    }, []);

    if (loading) return <div className="p-8 text-center text-gray-500">読み込み中...</div>;
    if (error) return <div className="p-8 text-center text-red-500">{error}</div>;

    const SNS_FIELDS: { key: keyof UserProfile; icon: React.FC<any>; color: string; label: string }[] = [
        { key: 'x_url', icon: Twitter, color: 'text-gray-900', label: 'X (Twitter)' },
        { key: 'instagram_url', icon: Instagram, color: 'text-pink-600', label: 'Instagram' },
        { key: 'facebook_url', icon: Facebook, color: 'text-blue-600', label: 'Facebook' },
        { key: 'note_url', icon: Globe, color: 'text-green-600', label: 'note' },
    ];

    const toggleEdit = () => setIsEditing(!isEditing);

    return (
        <div className="max-w-4xl mx-auto p-4 md:p-8 bg-white shadow-xl rounded-2xl my-8">
            <div className="flex justify-between items-center border-b pb-4 mb-6">
                <h1 className="text-3xl font-bold text-gray-800 flex items-center">
                    <User className="w-8 h-8 mr-3 text-pink-500" />
                    {profile.nickname || profile.username} のページ
                </h1>
                <button onClick={toggleEdit} className="flex items-center px-4 py-2 bg-pink-500 text-white rounded-lg hover:bg-pink-600 transition duration-150 shadow-md">
                    <Edit className="w-4 h-4 mr-2" />
                    {isEditing ? '編集を終了' : 'プロフィール編集'}
                </button>
            </div>

            {/* 編集モード */}
            {isEditing ? (
                <form onSubmit={handleUpdate} className="space-y-6">
                    <h2 className="text-xl font-semibold border-l-4 border-pink-500 pl-3">基本情報</h2>
                    
                    {/* ニックネーム */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700">ニックネーム</label>
                        <input
                            type="text"
                            value={profile.nickname || ''}
                            onChange={(e) => setProfile({ ...profile, nickname: e.target.value })}
                            className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2"
                        />
                    </div>

                    {/* 自己紹介 */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700">自己紹介</label>
                        <textarea
                            value={profile.bio || ''}
                            onChange={(e) => setProfile({ ...profile, bio: e.target.value })}
                            rows={4}
                            className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2"
                        ></textarea>
                    </div>

                    <h2 className="text-xl font-semibold border-l-4 border-pink-500 pl-3 pt-4">SNSリンク</h2>
                    
                    {SNS_FIELDS.map(({ key, label }) => (
                        <div key={key} className="flex items-center">
                            <label className="block text-sm font-medium text-gray-700 w-32 shrink-0">{label} URL</label>
                            <input
                                type="url"
                                // 💡 修正: profile[key]が文字列またはnullであることを保証
                                value={(profile[key] as string) || ''}
                                onChange={(e) => setProfile({ ...profile, [key]: e.target.value })}
                                className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 ml-4"
                            />
                        </div>
                    ))}

                    <h2 className="text-xl font-semibold border-l-4 border-pink-500 pl-3 pt-4">公開設定</h2>
                    <div className="space-y-3">
                        <label className="flex items-center text-gray-700 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={profile.is_mood_visible}
                                onChange={(e) => setProfile({ ...profile, is_mood_visible: e.target.checked })}
                                className="h-4 w-4 text-pink-600 border-gray-300 rounded"
                            />
                            <span className="ml-2">今日の気分ログを他のユーザーに公開する</span>
                        </label>
                        <label className="flex items-center text-gray-700 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={profile.is_member_count_visible}
                                onChange={(e) => setProfile({ ...profile, is_member_count_visible: e.target.checked })}
                                className="h-4 w-4 text-pink-600 border-gray-300 rounded"
                            />
                            <span className="ml-2">参加カテゴリの人数情報（地域人数など）を公開する</span>
                        </label>
                    </div>

                    <div className="flex justify-end pt-4">
                        <button type="submit" className="px-6 py-2 bg-green-500 text-white font-semibold rounded-lg hover:bg-green-600 transition duration-150 shadow-lg">
                            変更を保存
                        </button>
                    </div>
                </form>

            ) : (
                // 表示モード
                <div className="space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        {/* 左：基本情報 */}
                        <div className="md:col-span-2 space-y-4">
                            <h2 className="text-xl font-semibold text-gray-800">自己紹介</h2>
                            <p className="text-gray-600 bg-gray-50 p-4 rounded-lg min-h-[100px] whitespace-pre-wrap">
                                {profile.bio || 'まだ自己紹介がありません。編集画面から追記しましょう！'}
                            </p>
                        </div>
                        
                        {/* 右：連絡先・地域情報 */}
                        <div className="md:col-span-1 space-y-3 bg-pink-50 p-4 rounded-lg">
                            <h2 className="text-xl font-semibold text-pink-800">所在地情報</h2>
                            <div className="text-sm flex items-center text-pink-700">
                                <Mail className="w-4 h-4 mr-2" /> {profile.email}
                            </div>
                            <div className="text-sm flex items-center text-pink-700">
                                <MapPin className="w-4 h-4 mr-2" />
                                {profile.prefecture && profile.city 
                                    ? `${profile.prefecture} ${profile.city}`
                                    : '地域未設定'}
                            </div>
                            <div className="text-sm pt-2">
                                <span className={`font-semibold ${profile.is_mood_visible ? 'text-green-600' : 'text-red-500'}`}>
                                    気分ログ: {profile.is_mood_visible ? '公開中' : '非公開'}
                                </span>
                            </div>
                        </div>
                    </div>
                    
                    {/* SNS & 入推しリンク */}
                    <div className="pt-4 border-t">
                        <h2 className="text-xl font-semibold text-gray-800 mb-4">推し活リンク ({profile.nickname}の入推し)</h2>
                        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
                            {SNS_FIELDS.map(({ key, icon: Icon, color, label }) => {
                                // 💡 修正: profile[key]が文字列またはnullであることを保証
                                const url = profile[key] as string | null | undefined;
                                if (!url) return null;
                                return (
                                    <a 
                                        key={key} 
                                        href={url as string} 
                                        target="_blank" 
                                        rel="noopener noreferrer"
                                        className={`flex items-center justify-center p-3 border rounded-lg shadow-sm hover:shadow-lg transition duration-150 ${color} bg-white`}
                                    >
                                        <Icon className="w-5 h-5 mr-2" />
                                        <span className="font-medium text-sm">{label}</span>
                                    </a>
                                );
                            })}
                        </div>
                        {/* SNSリンクが一つもない場合にメッセージを表示 */}
                        {!SNS_FIELDS.some(f => profile[f.key]) && (
                            <p className="text-gray-500 italic">公開されている推し活リンクはありません。</p>
                        )}
                    </div>
                    
                    {/* 今日の気分（ダミーデータ、API実装後に置き換え） */}
                    <div className="pt-4 border-t">
                        <h2 className="text-xl font-semibold text-gray-800 mb-3">今日の気分（最新の感情ログ）</h2>
                        <div className="p-4 bg-yellow-50 rounded-lg border border-yellow-200">
                            <p className="text-lg font-bold text-yellow-800 flex items-center">
                                {profile.current_mood === 'motivated' ? '💪 やる気' : '😐 普通'} 
                            </p>
                            <p className="text-sm text-yellow-700 mt-1">
                                {profile.current_mood_comment || '特にコメントはありません。'}
                            </p>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default UserProfileComponent;