const CACHE_NAME = 'osidou-v2';  // v1→v2に変更
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/icons/icon-192x192.png',
  '/icons/icon-512x512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  // APIと認証関連は絶対にキャッシュしない
  if (
    event.request.url.includes('/api/') ||
    event.request.url.includes('/auth/') ||
    event.request.url.includes('/users/') ||
    event.request.url.includes('/friends/') ||
    event.request.url.includes('/posts/') ||
    event.request.url.includes('/notifications/') ||
    event.request.method !== 'GET'
  ) {
    return fetch(event.request);
  }

  // 静的ファイルのみキャッシュ
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => {
          cache.put(event.request, clone);
        });
        return response;
      })
      .catch(() => {
        return caches.match(event.request).then((cached) => {
          return cached || caches.match('/index.html');
        });
      })
  );
});