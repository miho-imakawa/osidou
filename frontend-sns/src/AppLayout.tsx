import React, { useState, useEffect } from 'react';
import { Routes, Route, Link, useLocation } from 'react-router-dom';
import UserProfile from './components/UserProfile';
import HomeFeed from './components/HomeFeed';
import FriendManager from './components/FriendManager';
import CommunityList from './components/CommunityList';
import CommunityDetail from './components/CommunityDetail';
import { authApi, UserProfile as UserProfileType } from './api';

// 💡 TypeScriptのエラー を防ぐための完全な初期値
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
    threads_url: null,
    is_member_count_visible: true,
    is_mood_visible: true,
    current_mood: 'neutral', 
    current_mood_comment: null,
    mood_updated_at: null,
    // 💡 以下の2行を追加することで api.ts との不整合を解消
    birth_year_month: null,
    gender: null
};

const Header: React.FC = () => {
    const location = useLocation();
    const isActive = (path: string) => location.pathname === path;

    return (
        <header className="bg-white shadow-md fixed top-0 w-full z-10">
            <div className="max-w-7xl mx-auto py-4 px-4 sm:px-6 lg:px-8 flex justify-between items-center">
                <Link to="/" className="text-2xl font-extrabold text-pink-600 tracking-wider">
                    推し道 (Osidou.com)
                </Link>
                <nav className="space-x-4 text-sm sm:text-base">
                    <Link to="/" className={`text-gray-600 hover:text-pink-600 ${isActive('/') ? 'font-bold border-b-2 border-pink-600' : ''}`}>HOME</Link>
                    <Link to="/community" className={`text-gray-600 hover:text-pink-600 ${isActive('/community') ? 'font-bold border-b-2 border-pink-600' : ''}`}>コミュニティ</Link>
                    <Link to="/friends" className={`text-gray-600 hover:text-pink-600 ${isActive('/friends') ? 'font-bold border-b-2 border-pink-600' : ''}`}>ともだち</Link>
                    <Link to="/mypage" className={`text-gray-600 hover:text-pink-600 ${isActive('/mypage') ? 'font-bold border-b-2 border-pink-600' : ''}`}>MY PAGE</Link>
                </nav>
            </div>
        </header>
    );
};

const Footer: React.FC = () => (
    <footer className="bg-gray-800 text-white mt-12">
        <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8 text-center text-sm">
            <p>&copy; {new Date().getFullYear()} 推集炉 (Suishuro) 運営事務局</p>
            <p className="mt-1">推し道を行く人のための推集炉</p>
        </div>
    </footer>
);

const AppLayout: React.FC = () => {
    const [profile, setProfile] = useState<UserProfileType>(initialProfile);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    
    const fetchProfile = async () => {
        setLoading(true);
        try {
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

// frontend-sns/src/AppLayout.tsx

    useEffect(() => {
        const initializeApp = async () => {
            // 💡 開発用の強制トークンセット
            // 先ほど取得した access_token をここに貼り付けます
            const devToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0QGV4YW1wbGUuY29tIiwiZXhwIjoxNzcwNjIxNjIxfQ.lBtJMm_Pn768ygbki8dlROysTkRD3E-vIKsk3VMKgp8";

            if (devToken) {
                // api.ts が見に行く 'access_token' というキー名で保存
                localStorage.setItem('access_token', devToken);
                console.log("🛠️ 開発用トークンをセットしました");
            }

            // トークンがセットされた後にプロフィールを取得
            await fetchProfile();
        };

        initializeApp();
    }, []);

    const renderContent = () => {
        if (loading) return <div className="p-8 text-center text-gray-500">全体を読み込み中...</div>;
        if (error) return <div className="p-8 text-center text-red-500">{error}</div>;

        return (
            <Routes>
                <Route path="/" element={<HomeFeed profile={profile} />} />
                <Route path="/friends" element={<FriendManager />} />
                <Route path="/mypage" element={<UserProfile profile={profile} fetchProfile={fetchProfile} />} />
                <Route path="/profile/:userId" element={<UserProfile profile={profile} fetchProfile={fetchProfile} />} />
                <Route path="/community" element={<CommunityList />} />
                <Route path="/community/:categoryId" element={<CommunityDetail />} />
                <Route path="*" element={<HomeFeed profile={profile} />} />
            </Routes>
        );
    };

    return (
        <div className="min-h-screen bg-gray-100 font-sans pt-20">
            <Header /> 
            <main className="container mx-auto px-4">
                {renderContent()}
            </main>
            <Footer />
        </div>
    );
};

export default AppLayout;