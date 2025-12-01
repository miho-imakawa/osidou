import axios from 'axios';

// 開発中は http://localhost:8000 など、FastAPIサーバーのURLを設定してください
const API_BASE_URL = 'http://localhost:8000';

/**
 * 認証を必要とするAPIリクエスト用のAxiosインスタンス
 */
export const authApi = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// リクエストインターセプター: 各リクエストにJWTトークンを自動で付与
authApi.interceptors.request.use(
    (config) => {
        // 本番ではlocalStorageの使用は避けてください。ここではデモとして使用します。
        const token = localStorage.getItem('access_token'); 
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

/**
 * 認証不要なAPIリクエスト用のAxiosインスタンス
 */
export const publicApi = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// 💡 修正: ユーザープロフィールの型定義に感情ログ関連のフィールドを追加
export interface UserProfile {
    id: number;
    username: string;
    email: string;
    nickname: string | null;
    bio: string | null;
    prefecture: string | null;
    city: string | null;
    town: string | null;

    // バックエンドで追加した新しいプロフィールフィールド
    oshi_page_url: string | null;
    facebook_url: string | null;
    x_url: string | null;
    instagram_url: string | null;
    note_url: string | null;
    
    // 💡 新規追加: 感情ログ関連のフィールド
    current_mood: string | null;
    current_mood_comment: string | null;

    // 公開設定フラグ
    is_member_count_visible: boolean;
    is_mood_visible: boolean;
    // ... 他の is_*_visible フラグ
}