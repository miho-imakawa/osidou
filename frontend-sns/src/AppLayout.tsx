// frontend-sns/src/AppLayout.tsx (全体を置き換え)

import React, { useState, useEffect } from 'react';
import UserProfile from './components/UserProfile.tsx';
import HomeFeed from './components/HomeFeed.tsx';
// 💡 api.tsから必要なものをインポート
import { authApi, UserProfile as UserProfileType } from './api.ts';
import FriendManager from './components/FriendManager.tsx'; // 💡 新しく追加
import { Routes, Route, useNavigate } from 'react-router-dom';

// --- 定数定義
const PAGE = {
    HOME: 'home',
    COMMUNITY: 'community',
    MYPAGE: 'mypage',
    FRIEND_MANAGER: 'friend_manager', // 💡 新しく追加
};

// 💡 UserProfileの型とinitialProfileはapi.tsからインポート/流用を想定
const initialProfile: UserProfileType = {
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
    threads_url: null, // 💡 Threads URL用のプロパティを追加
    is_member_count_visible: true,
    is_mood_visible: true,
    current_mood: 'neutral', 
    current_mood_comment: null,
};

// AppLayout.tsx の Header 部分を修正
import { Link, useLocation } from 'react-router-dom'; // 💡 useLocationを追加

const Header: React.FC = () => {
    const location = useLocation(); // 💡 現在のURLを取得
    
    // 現在のパスが一致しているか判定する関数
    const isActive = (path: string) => location.pathname === path;

    return (
        <header className="bg-white shadow-md fixed top-0 w-full z-10">
            <div className="max-w-7xl mx-auto py-4 px-4 sm:px-6 lg:px-8 flex justify-between items-center">
                <Link to="/" className="text-2xl font-extrabold text-pink-600 tracking-wider">
                    推し道 (Osidou.com)
                </Link>
                <nav className="space-x-4">
                    {/* 💡 setPageの代わりに Link to="..." を使う */}
                    <Link
                        to="/"
                        className={`text-gray-600 hover:text-pink-600 ${isActive('/') ? 'font-bold border-b-2 border-pink-600' : ''}`}
                    >
                        ホーム
                    </Link>
                    <Link
                        to="/community"
                        className={`text-gray-600 hover:text-pink-600 ${isActive('/community') ? 'font-bold border-b-2 border-pink-600' : ''}`}
                    >
                        コミュニティ
                    </Link>
                    <Link
                        to="/friends"
                        className={`text-gray-600 hover:text-pink-600 ${isActive('/friends') ? 'font-bold border-b-2 border-pink-600' : ''}`}
                    >
                        ともだち
                    </Link>
                    <Link
                        to="/mypage"
                        className={`text-gray-600 hover:text-pink-600 ${isActive('/mypage') ? 'font-bold border-b-2 border-pink-600' : ''}`}
                    >
                        マイページ
                    </Link>
                </nav>
            </div>
        </header>
    );
};

// --- フッターコンポーネント (変更なし)
const Footer: React.FC = () => (
    <footer className="bg-gray-800 text-white mt-12">
        <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8 text-center text-sm">
            <p>&copy; {new Date().getFullYear()} 推集炉 (Suishuro) 運営事務局</p>
            <p className="mt-1">推し道を行く人のための推集炉</p>
        </div>
    </footer>
);

// --- AppLayoutのメインコンポーネント
const AppLayout: React.FC = () => {
    // 💡 Profile Stateを AppLayout に移動
    const [profile, setProfile] = useState<UserProfileType>(initialProfile);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    
    // 💡 Profile Fetching Logicを AppLayout に移動
    const fetchProfile = async () => {
        setLoading(true);
        try {
            // ユーザー情報とカテゴリ情報はここで一括で取得せず、プロフィール情報のみを取得
            const response = await authApi.get<UserProfileType>('/users/me');
            setProfile(response.data);
            setError(null);
        } catch (err) {
            console.error(err);
            setError('プロフィールの読み込みに失敗しました。認証状態を確認してください。');
        } finally {
            setLoading(false);
        }
    };

    // 💡 useEffectも AppLayout に移動
useEffect(() => {
        // 🚨 ここに最新の有効なトークンを挿入します
        // このトークンは、AppLayoutが子コンポーネントにデータを渡す前に設定されます。
        localStorage.setItem('access_token', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjExQHN0cmluZy5jb20iLCJleHAiOjE3NjY5OTU3Mzl9.8IH7-eQzDxDbBQRC3t5Uoj1PtYalmDLnhEcIk2OxW8c'); 
        
        fetchProfile();
    }, []);


    // 現在のページに応じて表示するコンポーネントを切り替える関数
    const renderContent = () => {
        if (loading) return <div className="p-8 text-center text-gray-500">全体を読み込み中...</div>;
        if (error) return <div className="p-8 text-center text-red-500">{error}</div>;

        return (
            <Routes>
                {/* 💡 URL: / (ホーム) */}
                <Route path="/" element={<HomeFeed profile={profile} />} />

                {/* 💡 URL: /friends (友達管理) */}
                <Route path="/friends" element={<FriendManager />} />

                {/* 💡 URL: /mypage (自分自身のプロフィール) */}
                <Route path="/mypage" element={
                    <UserProfile 
                        profile={profile} 
                        fetchProfile={fetchProfile} 
                    />
                } />

                {/* 💡 URL: /profile/4 (相手のプロフィール) */}
                <Route path="/profile/:userId" element={<UserProfile />} />

                {/* 💡 URL: /community (コミュニティ作成・カテゴリ選択) */}
                <Route path="/community" element={
                    <div className="py-12 px-4 sm:px-6 lg:px-8">
                        <h2 className="text-3xl font-extrabold text-gray-900">コミュニティ（カテゴリ選択）画面</h2>
                        <p className="mt-4 text-lg text-gray-600">
                            現在、カテゴリ機能の実装準備中です。
                        </p>
                    </div>
                } />

                {/* 💡 どこにも当てはまらないURLの場合はホームへ */}
                <Route path="*" element={<HomeFeed profile={profile} />} />
            </Routes>
        );
    };

    return (
    <div className="min-h-screen bg-gray-100 font-sans pt-20">
        {/* 💡 引数を消してシンプルに */}
        <Header /> 
        
        <main className="container mx-auto">
            {renderContent()}
        </main>

        <Footer />
    </div>
    );
};

export default AppLayout;