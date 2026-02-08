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
    master_id?: number | null;
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
    birth_year_month: string | null; 
    gender: string | null;           
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
    // 💡 エンドポイントを /hobby-categories/my-communities に合わせる
    const response = await authApi.get<HobbyCategory[]>('/hobby-categories/my-communities');
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

// frontend-sns/src/api.ts

export interface Post {
    is_system: any;
    id: number;
    content: string;
    user_id: number;
    hobby_category_id: number;
    author_nickname: string;
    public_code?: string;
    created_at: string;
    is_meetup: boolean;
    is_ad: boolean;
    meetup_date?: string;
    meetup_location?: string;  // 追加
    meetup_fee_info?: string;     // 💡 これを追記！
    meetup_status?: string;       // 💡 ついでにステータスも追記しておくと安心です
    meetup_capacity?: number;  // 追加
    author_id?: number;          // 投稿者のID（CommunityChatの非表示機能で必要）
    ad_end_date?: string;
    parent_id?: number | null; // 💡 これを追加
    response_count?: number;   // 追加
    participation_count?: number; // 追加
    region_tag_pref?: string;  // 追加
    region_tag_city?: string;  // 追加
}

export interface PostCreate {
    content: string;
    hobby_category_id: number;
    parent_id?: number | null;
    is_meetup?: boolean;
    is_ad?: boolean;      // 💡 追加
    meetup_date?: string;
    ad_end_date?: string; // 💡 追加
    is_system: boolean;
}

// --- 💡 参加状態用の型を新規追加 ---
export interface JoinStatus {
    is_joined: boolean;
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

// コミュニティに参加する
export const joinCommunity = async (categoryId: number): Promise<void> => {
    await authApi.post(`/hobby-categories/join/${categoryId}`);
};

// 参加状態を確認する
export const fetchJoinStatus = async (categoryId: number): Promise<JoinStatus> => {
    const response = await authApi.get<JoinStatus>(`/hobby-categories/check-join/${categoryId}`);
    return response.data;
};

// 自分が参加しているコミュニティ一覧を取得する
export const fetchMyCommunities = async (): Promise<HobbyCategory[]> => {
    const response = await authApi.get<HobbyCategory[]>('/hobby-categories/my-communities');
    return response.data;
};

// 投稿を通報する
export const reportPost = async (postId: number): Promise<{ message: string }> => {
    const response = await authApi.post(`/posts/${postId}/report`);
    return response.data;
};

// コミュニティを退会する
export const leaveCommunity = async (categoryId: number): Promise<void> => {
    await authApi.delete(`/hobby-categories/leave/${categoryId}`);
};

// ----------------------------------------------------
// 📌 住所・地域統計関連
// ----------------------------------------------------

export interface Prefecture {
    id: number;
    name: string;
}

export interface City {
    id: number;
    name: string;
}

export interface MemberCountResponse {
    count: number;
}

// 都道府県一覧を取得
export const fetchPrefectures = async (): Promise<Prefecture[]> => {
    // 認証不要な場合は publicApi、必要な場合は authApi を使用
    const response = await authApi.get<Prefecture[]>('/admin/address/prefectures');
    return response.data;
};

// 市区町村一覧を取得
export const fetchCities = async (prefectureId: number): Promise<City[]> => {
    const response = await authApi.get<City[]>(`/admin/address/cities/${prefectureId}`);
    return response.data;
};

// 地域メンバー数を取得
export const fetchMemberCount = async (prefecture: string, city: string): Promise<MemberCountResponse> => {
    const response = await authApi.get<MemberCountResponse>('/admin/address/member-count', {
        params: { prefecture, city }
    });
    return response.data;
};