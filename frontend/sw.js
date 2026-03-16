// Service Worker — Podcast 自動解説 PWA
const CACHE_NAME = 'podcast-summary-v1';
const STATIC_ASSETS = [
    '/',
    '/style.css',
    '/app.js',
    '/manifest.json',
];

// インストール時に静的アセットをキャッシュ
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(STATIC_ASSETS))
            .then(() => self.skipWaiting())
    );
});

// アクティベーション時に古いキャッシュを削除
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(
                keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
            )
        ).then(() => self.clients.claim())
    );
});

// ネットワークファースト戦略（APIはキャッシュしない）
self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);

    // API リクエストはネットワークのみ
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(fetch(event.request));
        return;
    }

    // 静的アセットはネットワークファースト + キャッシュフォールバック
    event.respondWith(
        fetch(event.request)
            .then(response => {
                const clone = response.clone();
                caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
                return response;
            })
            .catch(() => caches.match(event.request))
    );
});
