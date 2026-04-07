const CACHE_NAME = 'osidou-v3';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

// キャッシュしない、全部ネットワークから取得
self.addEventListener('fetch', (event) => {
  event.respondWith(fetch(event.request));
});