import React from 'react';
import UserProfileComponent from './UserProfile.tsx'; 
// 💡 Tailwind CSSはPostCSSで処理されます

const Header: React.FC = () => (
    <header className="bg-white shadow-md">
        <div className="max-w-7xl mx-auto py-4 px-4 sm:px-6 lg:px-8 flex justify-between items-center">
            <h1 className="text-2xl font-extrabold text-pink-600 tracking-wider">
                推し道 (Osidou.com)
            </h1>
            <nav className="space-x-4">
                <a href="#" className="text-gray-600 hover:text-pink-600">ホーム</a>
                <a href="#" className="text-gray-600 hover:text-pink-600">コミュニティ</a>
                <a href="#" className="text-gray-600 hover:text-pink-600 font-bold border-b-2 border-pink-600">マイページ</a>
            </nav>
        </div>
    </header>
);

const Footer: React.FC = () => (
    <footer className="bg-gray-800 text-white mt-12">
        <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8 text-center text-sm">
            <p>&copy; {new Date().getFullYear()} 推集炉 (Suishuro) 運営事務局</p>
            <p className="mt-1">推し道を行く人のための推集炉</p>
        </div>
    </footer>
);

// 💡 エントリポイントである main.tsx から呼び出されるメインコンポーネント
const AppLayout: React.FC = () => {
    return (
        <div className="min-h-screen bg-gray-100 font-sans">
            <Header />
            <main className="container mx-auto">
                {/* UserProfileComponent がここで呼び出されます */}
                <UserProfileComponent />
            </main>
            <Footer />
        </div>
    );
};

export default AppLayout;