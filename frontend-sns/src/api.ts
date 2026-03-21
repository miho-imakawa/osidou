import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const OFFLINE_POSTS_KEY = 'osidou_offline_posts';
const OFFLINE_MOODS_KEY = 'osidou_offline_moods'; 

export const authApi = axios.create({
    baseURL: API_BASE_URL,
    headers: { 'Content-Type': 'application/json' },
});

// ✅ リクエストインターセプター：全リクエストにトークンを付ける
authApi.interceptors.request.use((config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// レスポンスインターセプター（401時のリダイレクト）は意図的にコメントアウト中
// authApi.interceptors.response.use(
//     (response) => response,
//     (error) => {
//         if (error?.response?.status === 401) {
//             const url = error.config?.url || '';
//             const isAuthEndpoint = url.includes('/auth/');
//             const isMeEndpoint = url.includes('/users/me');
//             const isAlreadyOnLogin = window.location.pathname === '/login';
//             if (!isAuthEndpoint && !isMeEndpoint && !isAlreadyOnLogin) {
//                 localStorage.removeItem('access_token');
//                 window.location.href = '/login';
//             }
//         }
//         return Promise.reject(error);
//     }
// );

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
    is_public?: boolean;
}

const saveToOfflineQueue = (data: PostCreate) => {
    const queue = JSON.parse(localStorage.getItem(OFFLINE_POSTS_KEY) || '[]');
    const offlineData = { 
        ...data, 
        created_at: new Date().toISOString(),
        is_offline_original: true 
    };
    queue.push(offlineData);
    localStorage.setItem(OFFLINE_POSTS_KEY, JSON.stringify(queue));
};

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
    is_muted?: boolean; 
}

export interface PostResponse {
    id: number;
    content: string;
    is_participation: boolean;
    is_attended: boolean;
    user_id: number;
    post_id: number;
    author_nickname: string;
    created_at: string;
    ad_start_date?: string;
    like_count?: number;
    pin_count?: number;
}

export interface Post {
    id: number;
    content: string;
    user_id: number;
    hobby_category_id: number;
    author_nickname: string;
    is_system: boolean;
    public_code?: string;
    created_at: string;
    is_meetup: boolean;
    is_ad: boolean;
    ad_color?: string;
    meetup_date?: string;
    meetup_location?: string;
    meetup_fee_info?: string;
    meetup_status?: string;
    meetup_confirmed_at?: string | null;
    meetup_organizer_showed?: boolean | null;
    meetup_capacity?: number;
    ad_end_date?: string;
    ad_start_date?: string;
    like_count?: number;
    pin_count?: number;
    parent_id?: number | null;
    response_count?: number; 
    participation_count?: number;
    is_joined: boolean;
    region_tag_pref?: string;
    region_tag_city?: string;
    responses: PostResponse[];
}

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

export const fetchMyMoodHistory = async (): Promise<MoodLog[]> => {
    const res = await authApi.get('/users/moods/my-logs');
    return res.data;
};

export const postMoodLog = async (data: MoodPostPayload): Promise<void | { isOfflineSaved: true }> => {
    if (!navigator.onLine) {
        console.warn("オフライン検知。ローカルに保存します...");
        const queue = JSON.parse(localStorage.getItem(OFFLINE_MOODS_KEY) || '[]');
        queue.push({ ...data, created_at: new Date().toISOString() });
        localStorage.setItem(OFFLINE_MOODS_KEY, JSON.stringify(queue));
        return { isOfflineSaved: true };
    }
    try {
        await authApi.post('users/moods', data);
    } catch (error) {
        console.warn("送信失敗。ローカルに保存します...");
        const queue = JSON.parse(localStorage.getItem(OFFLINE_MOODS_KEY) || '[]');
        queue.push({ ...data, created_at: new Date().toISOString() });
        localStorage.setItem(OFFLINE_MOODS_KEY, JSON.stringify(queue));
        return { isOfflineSaved: true };
    }
};

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

export const createPost = async (data: PostCreate): Promise<Post | { isOfflineSaved: true }> => {
    try {
        const response = await authApi.post<Post>('/posts', data);
        return response.data;
    } catch (error) {
        if (!navigator.onLine || axios.isAxiosError(error)) {
            console.warn("Offline detected. Saving post to local storage...");
            saveToOfflineQueue(data);
            return { isOfflineSaved: true };
        }
        throw error;
    }
};

export const syncOfflinePosts = async () => {
    const queue: (PostCreate & { created_at: string })[] = JSON.parse(localStorage.getItem(OFFLINE_POSTS_KEY) || '[]');
    if (queue.length === 0) return;

    let successCount = 0;
    for (const post of [...queue]) {
        try {
            await authApi.post('/posts', post);
            successCount++;
            queue.shift(); 
            localStorage.setItem(OFFLINE_POSTS_KEY, JSON.stringify(queue));
        } catch (e) {
            console.error("Sync failed for a post. Stopping sync to retry later.", e);
            break;
        }
    }
    if (successCount > 0) console.log(`${successCount} posts synced successfully!`);
};

export const syncOfflineData = async () => {
    const moodQueue = JSON.parse(localStorage.getItem(OFFLINE_MOODS_KEY) || '[]');
    if (moodQueue.length === 0) return;

    const remainingQueue = [...moodQueue];
    for (const mood of moodQueue) {
        try {
            await authApi.post('/users/moods', mood);
            remainingQueue.shift();
            localStorage.setItem(OFFLINE_MOODS_KEY, JSON.stringify(remainingQueue));
        } catch (e) {
            console.error("同期に失敗しました。次回の復帰を待ちます。", e);
            break; 
        }
    }
    if (remainingQueue.length === 0) console.log("✅ すべての気分ログが同期されました！");
};

export const fetchPostsByCategory = async (categoryId: number): Promise<Post[]> => (await authApi.get(`/posts/category/${categoryId}`)).data;

export const createPostResponse = async (postId: number, data: PostResponseCreate): Promise<PostResponse> => {
    return (await authApi.post(`/posts/${postId}/responses`, data)).data;
};

export const joinCommunity = async (categoryId: number): Promise<void> => await authApi.post(`/hobby-categories/join/${categoryId}`);
export const fetchJoinStatus = async (categoryId: number): Promise<JoinStatus> => (await authApi.get(`/hobby-categories/check-join/${categoryId}`)).data;
export const leaveCommunity = async (categoryId: number): Promise<void> => await authApi.delete(`/hobby-categories/leave/${categoryId}`);
export const reportPost = async (postId: number): Promise<{ message: string }> => (await authApi.post(`/posts/${postId}/report`)).data;

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

export const fetchAdQuote = async (categoryIds: number[]) => {
    const response = await authApi.post('/hobby-categories/ad-quote', { category_ids: categoryIds });
    return response.data;
};

export const pinAd = (postId: number) => authApi.post(`/posts/${postId}/pin`);
export const likePost = (postId: number) => authApi.post(`/posts/${postId}/like`);

export const adInteraction = async (postId: number, action: 'like' | 'pin' | 'close') => {
    const response = await authApi.post(`/posts/${postId}/ad-interaction`, { action });
    return response.data;
};

export const fetchMyAdInteractions = async () => {
    const response = await authApi.get('/posts/my-ad-interactions');
    return response.data;
};

export const createSubCategory = async (data: {
    name: string;
    parent_id: number;
    master_id?: number;
    role_type?: string;
}): Promise<{ id: number; name: string; parent_id: number; message: string }> => {
    const response = await authApi.post('/hobby-categories/create-sub', data);
    return response.data;
};

// ----------------------------------------------------
// 📌 Stripe 課金API
// ----------------------------------------------------

const redirectToStripe = async (endpoint: string, body: object) => {
    const res = await authApi.post(endpoint, body);
    if (res.data.url) {
        window.location.href = res.data.url;
    } else {
        throw new Error("Stripe URLの取得に失敗しました");
    }
};

export const startFeelingLogCheckout = async (userId: string | number) => {
    await redirectToStripe("/api/stripe/feeling-log-checkout", {
        userId: String(userId),
        successUrl: `${window.location.origin}/download/feeling-log?session_id={CHECKOUT_SESSION_ID}`,
        cancelUrl: window.location.href,
    });
};

export const startFriendsLogCheckout = async (userId: string | number, targetUserId?: string | number) => {
    await redirectToStripe("/api/stripe/friends-log-checkout", {
        userId: String(userId),
        targetUserId: targetUserId ? String(targetUserId) : undefined,
        successUrl: targetUserId 
            ? `${window.location.origin}/profile/${targetUserId}?friends_log_session={CHECKOUT_SESSION_ID}`
            : undefined,
        cancelUrl: window.location.href,
    });
};

export const startMeetupCheckout = async (userId: string | number, postId?: number) => {
    await redirectToStripe("/api/stripe/meetup-checkout", {
        userId: String(userId),
        postId,
        successUrl: `${window.location.origin}/community?meetup_paid=true`,
        cancelUrl: window.location.href,
    });
};

export const startNoAffiliateCheckout = async (userId: string | number) => {
    await redirectToStripe("/api/stripe/no-affiliate-checkout", {
        userId: String(userId),
        successUrl: `${window.location.origin}/profile?no_affiliate_paid=true`,
        cancelUrl: window.location.href,
    });
};

export const startAdCheckout = async (
    userId: string | number,
    amount: number,
    adTitle: string,
    adContent: string,
    startDate: string,
    endDate: string,
    categoryIds: number[],
    adColor: string,
) => {
    await redirectToStripe("/api/stripe/ad-checkout", {
        userId: String(userId),
        amount,
        adTitle,
        adContent,
        startDate,
        endDate,
        categoryIds,
        adColor,
        successUrl: `${window.location.origin}${window.location.pathname}?ad_session_id={CHECKOUT_SESSION_ID}`,
        cancelUrl: window.location.href,
    });
};

export const fetchFriendsLogStatus = async (userId: number) => {
    const res = await authApi.get(`/api/stripe/friends-log-status?user_id=${userId}`);
    return res.data as {
        has_active_purchase: boolean;
        credits_remaining?: number;
        can_download?: boolean;
        next_available_at?: string;
    };
};

export const activateFriendsLog = async (sessionId: string) => {
    const res = await authApi.post('/api/stripe/friends-log-activate', { sessionId });
    return res.data as {
        status: string;
        credits_remaining?: number;
    };
};

export const verifyFriendsLogSession = async (sessionId: string): Promise<{
    valid: boolean;
    target_user_id?: string;
    expires_at?: string;
    reason?: string;
}> => {
    const res = await authApi.get(`/api/stripe/friends-log-verify?session_id=${sessionId}`);
    return res.data;
};