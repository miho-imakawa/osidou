import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

export const authApi = axios.create({
    baseURL: API_BASE_URL,
    headers: { 'Content-Type': 'application/json' },
});

authApi.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('access_token'); 
        if (token) config.headers.Authorization = `Bearer ${token}`;
        return config;
    },
    (error) => Promise.reject(error)
);

export const publicApi = axios.create({
    baseURL: API_BASE_URL,
    headers: { 'Content-Type': 'application/json' },
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
    is_mood_comment_visible?: boolean;
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

export interface UserProfile extends UserProfileType {
    mood_updated_at: string | null;
    is_pref_visible?: boolean;
    is_city_visible?: boolean;
    is_town_visible?: boolean;
    birth_year_month: string | null; 
    gender: string | null;               
}

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
    is_mood_comment_visible?: boolean;
}

/** 💡 参加表明・レスポンスの詳細型 */
export interface PostResponse {
    id: number;
    content: string;
    is_participation: boolean;
    is_attended: boolean;
    user_id: number;
    post_id: number;
    author_nickname: string; // バックエンドから返される名前
    created_at: string;
    ad_start_date?: string; // ★追加
    like_count?: number;    // ★追加
    pin_count?: number;     // ★追加
}

/** 💡 投稿（Post）型：バックエンドの修正に合わせて responses を追加 */
export interface Post {
    id: number;
    content: string;
    user_id: number;
    hobby_category_id: number;
    author_nickname: string;
    public_code?: string;
    created_at: string;
    is_meetup: boolean;
    is_ad: boolean;
    ad_color?: string;
    meetup_date?: string;
    meetup_location?: string;
    meetup_fee_info?: string;
    meetup_status?: string;
    meetup_capacity?: number;
    ad_end_date?: string;
    ad_start_date?: string; // ★追加：掲載開始日
    like_count?: number;    // ★追加：いいね数
    pin_count?: number;     // ★追加：PIN数
    parent_id?: number | null;
    response_count?: number; 
    participation_count?: number;
    is_joined: boolean;
    region_tag_pref?: string; // 都道府県タグ
    region_tag_city?: string; // 市区町村タグ（これが足りない！）    
    responses: PostResponse[];
}

/** 💡 参加表明の作成用 */
export interface PostResponseCreate {
    content?: string;
    is_participation: boolean;
}

export interface PostCreate {
    content: string;
    hobby_category_id: number;
    parent_id?: number | null;
    is_meetup?: boolean;
    is_ad?: boolean;
    ad_color?: string;
    meetup_date?: string;
    ad_end_date?: string;
    meetup_location?: string;
    meetup_fee_info?: string;
    meetup_capacity?: number;
    is_system: boolean;
    ad_start_date?: string;
}

export interface JoinStatus {
    is_joined: boolean;
}

// ----------------------------------------------------
// 📌 API関数
// ----------------------------------------------------

export const fetchMyCommunities = async (): Promise<HobbyCategory[]> => {
    const response = await authApi.get<HobbyCategory[]>('/hobby-categories/my-communities');
    return response.data;
};

export const fetchFollowingMoods = async (): Promise<UserMoodResponse[]> => (await authApi.get('/users/following/moods')).data;
export const fetchMyMoodHistory = async (): Promise<MoodLog[]> => (await authApi.get('/users/me/mood-history')).data;
export const postMoodLog = async (data: MoodPostPayload): Promise<void> => await authApi.post('/users/moods', data);
export const searchUsers = async (query: string): Promise<UserProfileType[]> => (await authApi.get('/users/search', { params: { query } })).data;
export const sendFriendRequest = async (userId: number): Promise<void> => await authApi.post(`/friends/${userId}/friend_request`);
export const fetchFriendRequests = async (): Promise<FriendRequest[]> => (await authApi.get('/friends/me/friend-requests')).data;

export const acceptFriendRequest = async (requestId: number): Promise<void> => {
    await authApi.put(`/friends/friend_requests/${requestId}/status`, { status: 'accepted' });
};

export const rejectFriendRequest = async (requestId: number): Promise<void> => {
    await authApi.put(`/friends/friend_requests/${requestId}/status`, { status: 'rejected' });
};

export const fetchMyFriends = async (): Promise<Friendship[]> => (await authApi.get('/friends/me/friends')).data;

export const createPost = async (data: PostCreate): Promise<Post> => (await authApi.post('/posts', data)).data;
export const fetchPostsByCategory = async (categoryId: number): Promise<Post[]> => (await authApi.get(`/posts/category/${categoryId}`)).data;

/** 💡 参加表明（JOIN REQUEST）の作成 */
export const createPostResponse = async (postId: number, data: PostResponseCreate): Promise<PostResponse> => {
    return (await authApi.post(`/posts/${postId}/responses`, data)).data;
};

export const joinCommunity = async (categoryId: number): Promise<void> => await authApi.post(`/hobby-categories/join/${categoryId}`);
export const fetchJoinStatus = async (categoryId: number): Promise<JoinStatus> => (await authApi.get(`/hobby-categories/check-join/${categoryId}`)).data;
export const leaveCommunity = async (categoryId: number): Promise<void> => await authApi.delete(`/hobby-categories/leave/${categoryId}`);
export const reportPost = async (postId: number): Promise<{ message: string }> => (await authApi.post(`/posts/${postId}/report`)).data;

/** 💡 出席管理の切り替え（バックエンドのパスに合わせて修正） */
export const toggleAttendance = async (responseId: number) => {
    return (await authApi.put(`/responses/${responseId}/attendance`)).data;
};

// ----------------------------------------------------
// 📌 住所・地域
// ----------------------------------------------------

export interface Prefecture { id: number; name: string; }
export interface City { id: number; name: string; }

export const fetchPrefectures = async (): Promise<Prefecture[]> => (await authApi.get('/admin/address/prefectures')).data;
export const fetchCities = async (prefectureId: number): Promise<City[]> => (await authApi.get(`/admin/address/cities/${prefectureId}`)).data;

// 💡 広告の見積もりを取得するAPI
export const fetchAdQuote = async (categoryIds: number[]) => {
    // ✅ 正しい書き方
    const response = await authApi.post('/hobby-categories/ad-quote', { category_ids: categoryIds });
    return response.data;
};

// 広告をマイリスト（保存）に追加
export const pinAd = (postId: number) => authApi.post(`/posts/${postId}/pin`);
// 広告の「いいね」
export const likePost = (postId: number) => authApi.post(`/posts/${postId}/like`);

export const adInteraction = async (postId: number, action: 'like' | 'pin' | 'close') => {
    const response = await authApi.post(`/posts/${postId}/ad-interaction`, { action });
    return response.data;
};

export const fetchMyAdInteractions = async () => {
    const response = await authApi.get('/posts/my-ad-interactions');
    return response.data;
};