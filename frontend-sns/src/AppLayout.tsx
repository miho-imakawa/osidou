import React, { useState, useEffect } from 'react';
import { Routes, Route, Link, useLocation } from 'react-router-dom';
import UserProfile from './components/UserProfile';
import HomeFeed from './components/HomeFeed';
import FriendManager from './components/FriendManager';
import CommunityList from './components/CommunityList';
import CommunityDetail from './components/CommunityDetail';
import { authApi, UserProfile as UserProfileType, syncOfflinePosts, syncOfflineData  } from './api';
import CategoryDetailPage from './components/CategoryDetailPage';
import { Menu, X } from 'lucide-react';
import LoginPage from './components/LoginPage';
import TokuteiPage from './components/TokuteiPage';
import FeelingLogDownload from './components/FeelingLogDownload';
import ForgotPasswordPage from './components/ForgotPasswordPage';
import ResetPasswordPage from './components/ResetPasswordPage';

// 💡 初期値の設定
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
    birth_year_month: null,
    gender: null
};

// --- サブコンポーネント (Header / Footer) ---

const Header: React.FC = () => {
    const [isOpen, setIsOpen] = useState(false);
    const location = useLocation();
    
    // 💡 ログイン状態の判定（トークンがあれば true）
    const isLoggedIn = !!localStorage.getItem('access_token');

    const isActive = (path: string) => location.pathname === path;

    const navItems = [
        { path: '/', label: 'HOME' },
        { path: '/community', label: 'コミュニティ' },
        { path: '/friends', label: 'ともだち' },
        { path: '/mypage', label: 'MY PAGE' },
    ];

    // 💡 ログアウト処理
    const handleLogout = () => {
        localStorage.removeItem('access_token');
        setIsOpen(false);
        window.location.href = '/'; // トップへリダイレクトして状態をリセット
    };

    return (
        <header className="bg-white shadow-md fixed top-0 w-full z-20">
            <div className="max-w-7xl mx-auto py-4 px-4 sm:px-6 lg:px-8 flex justify-between items-center">
                <Link to="/" className="text-xl sm:text-2xl font-extrabold text-pink-600 tracking-wider">
                    推し道 (Osidou.com)
                </Link>

                {/* PC版：ログイン/ログアウトを右端に追加 */}
                <nav className="hidden md:flex items-center space-x-6">
                    {navItems.map((item) => (
                        <Link key={item.path} to={item.path} className={`text-gray-600 hover:text-pink-600 ${isActive(item.path) ? 'font-bold border-b-2 border-pink-600' : ''}`}>
                            {item.label}
                        </Link>
                    ))}
                    {isLoggedIn ? (
                        <button onClick={handleLogout} className="text-gray-500 hover:text-red-500 text-sm border px-3 py-1 rounded">ログアウト</button>
                    ) : (
                        <Link to="/login" className="text-pink-600 font-bold text-sm">ログイン</Link>
                    )}
                </nav>

                <div className="md:hidden">
                    <button onClick={() => setIsOpen(!isOpen)} className="text-gray-600 p-2">
                        {isOpen ? <X size={28} /> : <Menu size={28} />}
                    </button>
                </div>
            </div>

            {/* スマホ版メニュー */}
            {isOpen && (
                <div className="md:hidden bg-white border-t border-gray-100 shadow-lg">
                    <nav className="flex flex-col p-4 space-y-4">
                        {navItems.map((item) => (
                            <Link key={item.path} to={item.path} onClick={() => setIsOpen(false)} className={`text-base py-2 px-4 rounded-lg ${isActive(item.path) ? 'bg-pink-50 text-pink-600 font-bold' : 'text-gray-600'}`}>
                                {item.label}
                            </Link>
                        ))}
                        
                        <hr className="border-gray-100" />
                        
                        {/* 💡 ここで出し分け */}
                        {isLoggedIn ? (
                            <button 
                                onClick={handleLogout}
                                className="text-left py-2 px-4 text-red-500 font-bold"
                            >
                                ログアウト
                            </button>
                        ) : (
                            <Link 
                                to="/login" 
                                onClick={() => setIsOpen(false)}
                                className="py-2 px-4 text-pink-600 font-bold bg-pink-50 rounded-lg text-center"
                            >
                                ログイン / 新規登録
                            </Link>
                        )}
                    </nav>
                </div>
            )}
        </header>
    );
};

const Footer: React.FC = () => (
    <footer className="bg-gray-800 text-white mt-12">
        <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8 text-center text-sm">
            <p>&copy; {new Date().getFullYear()} 推集炉 (Suishuro) 運営事務局</p>
            <p className="mt-1">推し道を行く人のための推集炉</p>
            <p className="mt-3">
                <Link to="/tokutei" className="text-gray-400 hover:text-white underline">
                    特定商取引法に基づく表記
                </Link>
            </p>
        </div>
    </footer>
);

// --- メインコンポーネント ---

const AppLayout: React.FC = () => {
    const [profile, setProfile] = useState<UserProfileType>(initialProfile);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    
    const fetchProfile = async () => {
        setLoading(true);
        
        // ✅ トークンがなければ即終了
        const token = localStorage.getItem('access_token');
        if (!token) {
            setLoading(false);
            return;
        }
        
        try {
            const response = await authApi.get<UserProfileType>('/users/me');
            setProfile(response.data);
            localStorage.setItem('cached_profile', JSON.stringify(response.data));
            setError(null);
        } catch (err) {
            console.warn("Offline: Using cached profile");
            const cached = localStorage.getItem('cached_profile');
            if (cached) {
                setProfile(JSON.parse(cached));
                setError(null);
            } else {
                setError('オフラインです。一度オンラインでログインしてください。');
            }
        } finally {
            setLoading(false);
        }
    };

useEffect(() => {
    const initializeApp = async () => {
        // オフライン同期が失敗しても、メインの読み込みを止めないようにする
        try {
            await syncOfflinePosts().catch(e => console.error("Sync error ignored", e));
        } catch (e) {}

        // プロファイル取得を確実に実行
        await fetchProfile();
    };
    initializeApp();

        // ✅ 一度だけ取得、失敗してもsetGuideIdを1回だけ呼ぶ
    // fetch(`${import.meta.env.VITE_API_BASE_URL}/community/guide`)
    //     .then(res => {
    //         if (!res.ok) throw new Error('failed');
    //         return res.json();
    //     })
    //     .then(data => setGuideId(data.id ?? 1))
    //     .catch(() => setGuideId(prev => prev ?? 1));

    const handleOnline = () => {
        syncOfflinePosts();
        syncOfflineData();
    };
    window.addEventListener('online', handleOnline);
    return () => window.removeEventListener('online', handleOnline);
}, []); // ← [] が空であることを確認！

    const renderContent = () => {
        if (loading) return <div className="p-8 text-center text-gray-500">全体を読み込み中...</div>;

        const token = localStorage.getItem('access_token');

        const welcomeScreen = (
            <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6">
                <h2 className="text-2xl font-black text-gray-900">推し道へようこそ</h2>
                <p className="text-sm text-gray-500">ログインして始めましょう</p>
                <a href="/login" className="bg-pink-500 text-white px-8 py-3 rounded-full font-bold">
                    ログイン / サインアップ
                </a>
            </div>
        );

        // 初回ログイン判定
        const hasSeenGuide = localStorage.getItem('has_seen_guide');
        if (token && !hasSeenGuide) {
            return (
                <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6 text-center px-4">
                    <h2 className="text-2xl font-bold text-gray-900">ようこそ、推し道へ！🌸</h2>
                    <p className="text-sm text-gray-500">はじめに使い方をご確認ください</p>
                    <Link
                        to="/community/1"
                        onClick={() => localStorage.setItem('has_seen_guide', 'true')}
                        className="bg-pink-500 text-white px-8 py-3 rounded-full font-bold hover:bg-pink-600 transition-colors"
                    >
                        📖 SEE THE GUIDE
                    </Link>
                    <button
                        onClick={() => localStorage.setItem('has_seen_guide', 'true')}
                        className="text-gray-400 text-sm underline"
                    >
                        スキップ
                    </button>
                </div>
            );
        }

        return (
            <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route path="/tokutei" element={<TokuteiPage />} /> 
                <Route path="/forgot-password" element={<ForgotPasswordPage />} />
                <Route path="/reset-password" element={<ResetPasswordPage />} />
                {!token || error ? (
                    <Route path="*" element={welcomeScreen} />
                ) : (
                    <>
                        <Route path="/" element={<HomeFeed profile={profile} />} />
                        <Route path="/friends" element={<FriendManager />} />
                        <Route path="/download/feeling-log" element={<FeelingLogDownload />} />
                        <Route path="/mypage" element={<UserProfile profile={profile} fetchProfile={fetchProfile} />} />
                        <Route path="/profile/:userId" element={<UserProfile profile={profile} fetchProfile={fetchProfile} />} />
                        <Route path="/community" element={<CommunityList />} />
                        <Route path="/community/:categoryId" element={<CommunityDetail currentUserId={profile.id} />} />
                        <Route path="/community/:categoryId/detail" element={<CategoryDetailPage />} />
                        <Route path="*" element={<HomeFeed profile={profile} />} />
                        <Route path="/tokutei" element={<TokuteiPage />} />
                        <Route path="/login" element={<LoginPage />} />
                    </>
                )}
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