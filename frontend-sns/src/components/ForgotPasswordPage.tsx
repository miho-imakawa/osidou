import React, { useState } from 'react';
import { authApi } from '../api';
import { Link } from 'react-router-dom'; // 1. これを追加

const ForgotPasswordPage: React.FC = () => {
    const [email, setEmail] = useState('');
    const [loading, setLoading] = useState(false);
    const [sent, setSent] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async () => {
        if (!email) { setError('メールアドレスを入力してください'); return; }
        setLoading(true);
        setError(null);
        try {
            await authApi.post(`/auth/password-reset-request?email=${encodeURIComponent(email)}`);
            setSent(true);
        } catch (err: any) {
            setError(err?.response?.data?.detail || 'エラーが発生しました');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col items-center justify-center min-h-[70vh] px-4">
            <div className="w-full max-w-sm bg-white rounded-[32px] shadow-sm border border-gray-100 p-8">
                <h2 className="text-lg font-black text-gray-900 mb-2">パスワードの再設定</h2>

                {sent ? (
                    <>
                        <p className="text-sm text-gray-500 mb-6">
                            登録済みのメールアドレスであれば、再設定リンクを送信しました。メールをご確認ください。
                        </p>
                        <Link
                            to="/login"
                            className="block text-center text-pink-500 text-sm font-bold underline"
                        >
                            ログイン画面に戻る
                        </Link>
                    </>
                ) : (
                    <>
                        <p className="text-sm text-gray-500 mb-6">
                            登録したメールアドレスを入力してください。再設定リンクをお送りします。
                        </p>
                        <div className="space-y-4">
                            <input
                                type="email"
                                placeholder="E-MAIL ADDRESS"
                                value={email}
                                onChange={e => setEmail(e.target.value)}
                                onKeyDown={e => e.key === 'Enter' && handleSubmit()}
                                className="w-full border border-gray-200 rounded-2xl px-4 py-3 text-sm focus:outline-none focus:border-pink-300"
                            />
                            {error && <p className="text-red-500 text-xs font-bold">{error}</p>}
                            <button
                                onClick={handleSubmit}
                                disabled={loading}
                                className="w-full bg-pink-500 text-white py-3 rounded-2xl font-black text-sm hover:bg-pink-600 transition-colors disabled:opacity-50"
                            >
                                {loading ? '送信中...' : '再設定メールを送る'}
                            </button>
                            <Link
                                to="/login"
                                className="block text-center text-gray-400 text-[11px]"
                            >
                                ログイン画面に戻る
                            </Link>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};

export default ForgotPasswordPage;