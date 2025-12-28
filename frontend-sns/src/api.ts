import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

export const authApi = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

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
    unique_code: string;
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
    town: string | null;
}

// ✅ FriendRequest 型を追加
export interface FriendRequest {
    id: number;
    requester_id: number;
    receiver_id: number;
    status: string;
    created_at: string;
    requester: {
        id: number;
        username: string;
        nickname: string | null;
    };
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

export interface UserMoodResponse {
    user_id: number;
    nickname: string | null;
    username: string;
    email: string | null;
    current_mood: string;
    current_mood_comment: string | null;
    mood_updated_at: string | null;
    friend_note: string | null;
}

// ----------------------------------------------------
// 📌 API関数
// ----------------------------------------------------

export const fetchMyCategories = async (): Promise<HobbyCategory[]> => {
    const response = await authApi.get<HobbyCategory[]>('/hobbies/my-categories');
    return response.data;
};

export const fetchFollowingMoods = async (): Promise<UserMoodResponse[]> => {
    const response = await authApi.get<UserMoodResponse[]>('/users/following/moods');
    return response.data;
};

export const fetchMyMoodHistory = async (): Promise<MoodLog[]> => {
    const response = await authApi.get<MoodLog[]>('/users/me/mood-history');
    return response.data;
};

export const postMoodLog = async (data: MoodPostPayload): Promise<void> => {
    await authApi.post('/users/moods', data); 
};

export const searchUsers = async (query: string): Promise<UserProfileType[]> => {
    const response = await authApi.get<UserProfileType[]>('/users/search', {
        params: { query }
    });
    return response.data;
};

export const followOrUnfollowUser = async (userId: number): Promise<{ message: string, status: 'followed' | 'unfollowed' }> => {
    const response = await authApi.post(`/users/${userId}/follow`);
    return response.data;
};

export const sendFriendRequest = async (userId: number): Promise<void> => {
    await authApi.post(`/friends/${userId}/friend_request`); 
};

export const fetchFriendRequests = async (): Promise<FriendRequest[]> => {
    const response = await authApi.get<FriendRequest[]>('/friends/me/friend-requests');
    return response.data;
};

export const acceptFriendRequest = async (requestId: number): Promise<void> => {
    await authApi.put(`/friends/friend_requests/${requestId}/status`, { 
        status: 'accepted' 
    });
};

export const rejectFriendRequest = async (requestId: number): Promise<void> => {
    await authApi.put(`/friends/friend_requests/${requestId}/status`, { 
        status: 'rejected' 
    });
};

export const fetchMyFriends = async (): Promise<Friendship[]> => {
    const response = await authApi.get<Friendship[]>('/friends/me/friends');
    return response.data;
};

// api.ts に追加

export interface Post {
    id: number;
    content: string;
    user_id: number;
    hobby_category_id: number;
    author_nickname: string;
    public_code?: string;
    created_at: string;
    response_count?: number;
    participation_count?: number;
}

export interface PostCreate {
    content: string;
    hobby_category_id: number;
    is_meetup?: boolean;
    meetup_date?: string;
    meetup_location?: string;
    meetup_capacity?: number;
}

// 投稿を作成する関数
export const createPost = async (data: PostCreate): Promise<Post> => {
    const response = await authApi.post<Post>('/posts', data);
    return response.data;
};

// カテゴリの投稿一覧を取得する関数
export const fetchPostsByCategory = async (categoryId: number): Promise<Post[]> => {
    const response = await authApi.get<Post[]>(`/posts/category/${categoryId}`);
    return response.data;
};