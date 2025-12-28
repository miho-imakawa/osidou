import axios from 'axios';

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

// ----------------------------------------------------
// 📌 型定義
// ----------------------------------------------------

export interface UserProfileType {
    id: number;
    username: string;
    email: string;
    nickname: string | null;
    bio: string | null;
    prefecture: string | null;
    city: string | null;
    town: string | null;
    oshi_page_url: string | null;
    facebook_url: string | null;
    x_url: string | null;
    instagram_url: string | null;
    note_url: string | null;
    threads_url: string | null;
    is_member_count_visible: boolean;
    is_mood_visible: boolean;
    current_mood: string | null; 
    current_mood_comment: string | null;
}

export interface HobbyCategory {
    id: number;
    name: string;
    description: string | null;
    parent_id: number | null;
    depth: number;
    member_count: number;
    children: HobbyCategory[]; 
}

export interface MoodLog {
    id: number;
    user_id: number;
    user_nickname?: string;
    user_avatar_url?: string | null;
    mood_type: string;
    comment: string | null;
    is_visible: boolean;
    created_at: string;
}

export interface MoodPostPayload {
    mood_type: string;
    comment?: string | null;
    is_visible: boolean;
}

export interface UserProfile {
    id: number;
    username: string;
    nickname: string | null;
    bio: string | null;
    current_mood: string | null;
    current_mood_comment: string | null;
    mood_updated_at: string | null;
    is_mood_visible: boolean;
    is_member_count_visible: boolean;
    is_pref_visible?: boolean;
    is_city_visible?: boolean;
    is_town_visible?: boolean;
    oshi_page_url: string | null;
    facebook_url: string | null;
    x_url: string | null;
    instagram_url: string | null;
    note_url: string | null;
    threads_url: string | null;
    email: string;
    prefecture: string | null;
    city: string | null;
}

export interface Friendship {
    id: number;
    friend_note: string | null;
    is_muted: boolean;
    is_hidden: boolean;
    friend: {
        id: number;
        username: string;
        nickname: string | null;
    };
}

// ✅ 友達の気分ログ用の型定義
export interface UserMoodResponse {
    user_id: number;
    nickname: string | null;
    current_mood: string;
    current_mood_comment: string | null;
    mood_updated_at: string | null;
    is_mood_visible: boolean;
}

// ----------------------------------------------------
// 📌 API関数
// ----------------------------------------------------

/**
 * カテゴリ取得
 */
export const fetchMyCategories = async (): Promise<HobbyCategory[]> => {
    const response = await authApi.get<HobbyCategory[]>('/hobbies/my-categories');
    return response.data;
};

/**
 * 気分ログ取得（友達の気分）
 */
export const fetchFollowingMoods = async (): Promise<UserMoodResponse[]> => {
    const response = await authApi.get<UserMoodResponse[]>('/users/following/moods');
    return response.data;
};

/**
 * 自分の気分履歴取得
 */
export const fetchMyMoodHistory = async (): Promise<MoodLog[]> => {
    const response = await authApi.get<MoodLog[]>('/users/me/mood-history');
    return response.data;
};

/**
 * 気分ログ投稿
 */
export const postMoodLog = async (data: MoodPostPayload): Promise<void> => {
    await authApi.post('/users/moods', data); 
};

/**
 * ユーザー検索
 */
export const searchUsers = async (query: string): Promise<UserProfileType[]> => {
    const response = await authApi.get<UserProfileType[]>('/users/search', {
        params: { query }
    });
    return response.data;
};

/**
 * フォロー/アンフォロー
 */
export const followOrUnfollowUser = async (userId: number): Promise<{ message: string, status: 'followed' | 'unfollowed' }> => {
    const response = await authApi.post(`/users/${userId}/follow`);
    return response.data;
};

// ==========================================
// 📌 フレンド申請関連
// ==========================================

/**
 * フレンド申請送信
 */
export const sendFriendRequest = async (userId: number): Promise<void> => {
    await authApi.post(`/friends/${userId}/friend_request`); 
};

/**
 * フレンド申請一覧取得
 */
export const fetchFriendRequests = async (): Promise<FriendRequest[]> => {
    const response = await authApi.get<FriendRequest[]>('/friends/me/friend-requests');
    return response.data;
};

/**
 * フレンド申請承認
 */
export const acceptFriendRequest = async (requestId: number): Promise<void> => {
    await authApi.put(`/friends/friend_requests/${requestId}/status`, { 
        status: 'accepted' 
    });
};

/**
 * フレンド申請拒否
 */
export const rejectFriendRequest = async (requestId: number): Promise<void> => {
    await authApi.put(`/friends/friend_requests/${requestId}/status`, { 
        status: 'rejected' 
    });
};

/**
 * 友達リスト取得
 */
export const fetchMyFriends = async (): Promise<Friendship[]> => {
    // 戻り値の型を Friendship[] に変更します
    const response = await authApi.get<Friendship[]>('/friends/me/friends');
    return response.data;
};

