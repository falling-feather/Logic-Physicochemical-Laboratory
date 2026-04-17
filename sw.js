const CACHE_NAME = 'englab-static-v20260416b';
const APP_SHELL = [
  './',
  './index.html',
  './shared/js/lucide.min.js',
  './shared/js/config.js',
  './shared/js/module-selector.js?v=20260416b',
  './shared/js/router.js?v=20260416b',
  './shared/js/scroll-animations.js?v=20260416b',
  './shared/js/cards.js',
  './shared/js/common.js',
  './shared/js/main.js?v=20260416b',
  './pages/home/home.js?v=20260416b',
  './shared/css/tokens.css',
  './shared/css/base.css',
  './shared/css/typography.css',
  './shared/css/navbar.css',
  './shared/css/page-layout.css',
  './shared/css/cards.css',
  './shared/css/module-selector.css',
  './shared/css/responsive.css',
  './pages/home/home.css'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL.map((url) => new Request(url, { cache: 'reload' }))))
      .then(() => self.skipWaiting())
      .catch(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // SPA navigation: network first, cache fallback
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put('./index.html', clone));
          return response;
        })
        .catch(() => caches.match('./index.html'))
    );
    return;
  }

  const isStaticAsset = /\.(?:js|css|png|jpg|jpeg|svg|webp|gif|ico|woff2?)$/i.test(url.pathname);
  if (!isStaticAsset) return;

  // Stale-while-revalidate for same-origin static assets
  event.respondWith(
    caches.match(request).then((cached) => {
      const fetchPromise = fetch(request)
        .then((response) => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        })
        .catch(() => cached);

      return cached || fetchPromise;
    })
  );
});
