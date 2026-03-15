import React, { useState } from 'react';
import { authApi } from '../api';

const LoginPage: React.FC = () => {
    const [mode, setMode] = useState<'login' | 'signup'>('login');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [username, setUsername] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [showPassword, setShowPassword] = useState(false);

    const handleLogin = async () => {
        setLoading(true);
        setError(null);
        try {
            const params = new URLSearchParams();
            params.append('username', email);
            params.append('password', password);
            const res = await authApi.post('/auth/token', params, {
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
            });
            const token = res.data.access_token;
            if (!token) { setError('トークンが取得できませんでした'); return; }
            localStorage.setItem('access_token', token);
            await new Promise(resolve => setTimeout(resolve, 200));
            window.location.href = '/';
        } catch (err: any) {
            const status = err?.response?.status;
            const msg = err?.response?.data?.detail || err?.message || 'ネットワークエラー';
            setError(`エラー(${status}): ${msg}`);
        } finally {
            setLoading(false);
        }
    };

    const handleSignup = async () => {
        setError(null);
        if (password.length < 8) {
            setError('パスワードは8文字以上で入力してください');
            return;
        }
        setLoading(true);
        // 以下はそのまま
        try {
            await authApi.post('/auth/register', {
                username,
                email,
                password,
            });
            // 登録成功後、自動ログイン
            const params = new URLSearchParams();
            params.append('username', email);
            params.append('password', password);
            const res = await authApi.post('/auth/token', params, {
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
            });
            localStorage.setItem('access_token', res.data.access_token);
            await new Promise(resolve => setTimeout(resolve, 200));
            window.location.href = '/';
        } catch (err: any) {
            const msg = err?.response?.data?.detail || err?.message || 'ネットワークエラー';
            setError(msg);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col items-center justify-center min-h-[70vh] px-4">
            <div className="w-full max-w-sm bg-white rounded-[32px] shadow-sm border border-gray-100 p-8">
                
                {/* タブ切り替え */}
                <div className="flex mb-8 bg-gray-50 rounded-2xl p-1">
                    <button
                        onClick={() => { setMode('login'); setError(null); }}
                        className={`flex-1 py-2 rounded-xl text-sm font-black transition-all ${mode === 'login' ? 'bg-white shadow-sm text-gray-900' : 'text-gray-400'}`}
                    >
                        Log-in
                    </button>
                    <button
                        onClick={() => { setMode('signup'); setError(null); }}
                        className={`flex-1 py-2 rounded-xl text-sm font-black transition-all ${mode === 'signup' ? 'bg-white shadow-sm text-gray-900' : 'text-gray-400'}`}
                    >
                        Sign-up
                    </button>
                </div>

                <div className="space-y-4">
                    {mode === 'signup' && (
                        <input
                            type="text"
                            placeholder="USER ID（🔤 A-z 🔢 0-9）"
                            value={username}
                            onChange={e => setUsername(e.target.value)}
                            className="w-full border border-gray-200 rounded-2xl px-4 py-3 text-sm focus:outline-none focus:border-pink-300"
                        />
                    )}
                    <input
                        type="email"
                        placeholder="E-Msil Address"
                        value={email}
                        onChange={e => setEmail(e.target.value)}
                        className="w-full border border-gray-200 rounded-2xl px-4 py-3 text-sm focus:outline-none focus:border-pink-300"
                    />
                    <div className="relative">
                        <input
                            type={showPassword ? 'text' : 'password'}
                            placeholder="PASSWORD（8+ A-z 0-9）"
                            value={password}
                            onChange={e => setPassword(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && (mode === 'login' ? handleLogin() : handleSignup())}
                            className="w-full border border-gray-200 rounded-2xl px-4 py-3 text-sm focus:outline-none focus:border-pink-300"
                        />
                        <button
                            onClick={() => setShowPassword(!showPassword)}
                            className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400"
                            type="button"
                        >
                            {showPassword ? '🙈' : '👁️'}
                        </button>
                    </div>

                    {error && <p className="text-red-500 text-xs font-bold">{error}</p>}

                    <button
                        onClick={mode === 'login' ? handleLogin : handleSignup}
                        disabled={loading}
                        className="w-full bg-pink-500 text-white py-3 rounded-2xl font-black text-sm hover:bg-pink-600 transition-colors disabled:opacity-50"
                    >
                        {loading ? '処理中...' : mode === 'login' ? 'ログイン' : '登録する'}
                    </button>

                    {mode === 'login' && (
                        <p className="text-center text-[11px] text-gray-400">
                            パスワードをお忘れの方は{' '}
                            <a href="mailto:mihou.imakawa@machistrategist.com" className="text-pink-500 underline font-bold">
                                推集炉管理者にメールでお問い合わせ
                            </a>
                            {' '}からご連絡ください。
                        </p>
                    )}
                </div>
            </div>
        </div>
    );
};

export default LoginPage;