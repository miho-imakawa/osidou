import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { authApi } from '../api';

const ResetPasswordPage: React.FC = () => {
    const [searchParams] = useSearchParams();
    const token = searchParams.get('token') || '';

    const [password, setPassword] = useState('');
    const [confirm, setConfirm] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [loading, setLoading] = useState(false);
    const [done, setDone] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async () => {
        if (password.length < 8) { setError('パスワードは8文字以上で入力してください'); return; }
        if (password !== confirm) { setError('パスワードが一致しません'); return; }
        setLoading(true);
        setError(null);
        try {
            await authApi.post(
                `/auth/password-reset?token=${encodeURIComponent(token)}&new_password=${encodeURIComponent(password)}`
            );
            setDone(true);
        } catch (err: any) {
            setError(err?.response?.data?.detail || 'リンクが無効または期限切れです');
        } finally {
            setLoading(false);
        }
    };

    if (!token) {
        return (
            <div className="flex items-center justify-center min-h-[70vh] px-4">
                <p className="text-gray-400 text-sm">無効なリンクです。</p>
            </div>
        );
    }

    return (
        <div className="flex flex-col items-center justify-center min-h-[70vh] px-4">
            <div className="w-full max-w-sm bg-white rounded-[32px] shadow-sm border border-gray-100 p-8">
                <h2 className="text-lg font-black text-gray-900 mb-2">新しいパスワード</h2>

                {done ? (
                    <>
                        <p className="text-sm text-gray-500 mb-6">
                            パスワードを変更しました！新しいパスワードでログインしてください。
                        </p>
                        <a
                            href="/login"
                            className="block w-full bg-pink-500 text-white py-3 rounded-2xl font-black text-sm text-center hover:bg-pink-600 transition-colors"
                        >
                            ログインする
                        </a>
                    </>
                ) : (
                    <div className="space-y-4">
                        <div className="relative">
                            <input
                                type={showPassword ? 'text' : 'password'}
                                placeholder="新しいパスワード（8文字以上）"
                                value={password}
                                onChange={e => setPassword(e.target.value)}
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
                        <input
                            type={showPassword ? 'text' : 'password'}
                            placeholder="パスワードを再入力"
                            value={confirm}
                            onChange={e => setConfirm(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && handleSubmit()}
                            className="w-full border border-gray-200 rounded-2xl px-4 py-3 text-sm focus:outline-none focus:border-pink-300"
                        />
                        {error && <p className="text-red-500 text-xs font-bold">{error}</p>}
                        <button
                            onClick={handleSubmit}
                            disabled={loading}
                            className="w-full bg-pink-500 text-white py-3 rounded-2xl font-black text-sm hover:bg-pink-600 transition-colors disabled:opacity-50"
                        >
                            {loading ? '変更中...' : 'パスワードを変更する'}
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};

export default ResetPasswordPage;