const CACHE_NAME = 'englab-static-v20260422y';
const APP_SHELL = [
  './',
  './index.html',
  './shared/js/lucide.min.js?v=20260417c',
  './shared/js/config.js?v=20260418q',
  './shared/js/learning-progress.js?v=20260422a',
  './shared/js/theme-switch.js?v=20260418c',
  './shared/js/touch-gestures.js?v=20260418a',
  './shared/js/experiment-export.js?v=20260418f',
  './shared/js/quiz-data.js?v=20260418e',
  './shared/js/experiment-quiz.js?v=20260418e',
  './shared/js/experiment-favorites.js?v=20260418f',
  './shared/js/experiment-rating.js?v=20260418g',
  './shared/js/module-selector.js?v=20260418q',
  './shared/js/router.js?v=20260418q',
  './shared/js/scroll-animations.js?v=20260417c',
  './shared/js/cards.js?v=20260417c',
  './shared/js/common.js?v=20260417c',
  './shared/js/main.js?v=20260417c',
  './pages/home/home.js?v=20260418f',
  './shared/workers/particle-worker.js?v=20260422y',
  './shared/css/tokens.css?v=20260417c',
  './shared/css/base.css?v=20260417c',
  './shared/css/typography.css?v=20260417c',
  './shared/css/navbar.css?v=20260417c',
  './shared/css/page-layout.css?v=20260417c',
  './shared/css/cards.css?v=20260417c',
  './shared/css/module-selector.css?v=20260417c',
  './shared/css/experiment-export.css?v=20260418f',
  './shared/css/experiment-favorites.css?v=20260418f',
  './shared/css/experiment-rating.css?v=20260418g',
  './shared/css/responsive.css?v=20260417c',
  './pages/home/home.css?v=20260422d'
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
