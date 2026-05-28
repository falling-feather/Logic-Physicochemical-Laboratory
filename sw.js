const CACHE_NAME = 'englab-static-v20260528v61s';
const APP_SHELL = [
  './',
  './index.html',
  './shared/js/lucide.min.js?v=20260417c',
  './shared/js/config.js?v=20260418q',
  './shared/js/learning-progress.js?v=20260422a',
  './shared/js/back-to-top.js?v=20260424rr',
  './shared/js/fab-trigger.js?v=20260528v61g',
  './shared/js/touch-gestures.js?v=20260418a',
  './shared/js/experiment-export.js?v=20260528v61f',
  './shared/js/quiz-data.js?v=20260418e',
  './shared/js/experiment-quiz.js?v=20260418e',
  './shared/js/experiment-favorites.js?v=20260423q',
  './shared/js/experiment-rating.js?v=20260418g',
  './shared/js/module-selector.js?v=20260528v61f',
  './shared/js/router.js?v=20260528v61j',
  './shared/js/scroll-animations.js?v=20260417c',
  './shared/js/cards.js?v=20260417c',
  './shared/js/common.js?v=20260417c',
  './shared/js/main.js?v=20260424v45c',
  './shared/js/global-search.js?v=20260424v45a',
  './shared/js/keyboard-shortcuts.js?v=20260424v45b',
  './shared/js/related-experiments.js?v=20260424v45c',
  './shared/css/related-experiments.css?v=20260424v45c',
  './shared/css/global-search.css?v=20260424v45b',
  './pages/home/home.js?v=20260418f',
  './shared/workers/particle-worker.js?v=20260422y',
  './shared/css/tokens.css?v=20260424ss',
  './shared/css/base.css?v=20260417c',
  './shared/css/typography.css?v=20260526v61c',
  './shared/css/navbar.css?v=20260423s',
  './shared/css/page-layout.css?v=20260526v61c',
  './shared/css/cards.css?v=20260417c',
  './shared/css/module-selector.css?v=20260417c',
  './shared/css/experiment-export.css?v=20260418f',
  './shared/css/experiment-favorites.css?v=20260423s',
  './shared/css/experiment-rating.css?v=20260422z',
  './shared/css/experiment-polish.css?v=20260526v61c',
  './shared/css/responsive.css?v=20260417c',
  './pages/home/home.css?v=20260422e',
  './pages/about/about.css?v=20260528v61e',
  './pages/about/about.js?v=20260528v61d',
  './codevis/',
  './codevis/index.html',
  './codevis/shared/css/tokens.css?v=20260426b',
  './codevis/shared/css/base.css?v=20260526v61b',
  './codevis/shared/css/navbar.css?v=20260528v61r',
  './codevis/shared/css/layout.css?v=20260528v61s',
  './codevis/pages/home/home.css?v=20260528v61r',
  './codevis/pages/code-trace/code-trace.css?v=20260528v61o',
  './codevis/shared/js/router.js?v=20260526v61b',
  './codevis/shared/js/runtime.js?v=20260526v61b',
  './codevis/shared/js/runtimes/runtime-js.js?v=20260426h',
  './codevis/shared/js/runtimes/runtime-py.js?v=20260426h',
  './codevis/shared/js/runtimes/runtime-cpp.js?v=20260426h',
  './codevis/pages/home/home.js?v=20260526v61b',
  './codevis/pages/code-trace/code-trace.js?v=20260528v61p',
  './codevis/shared/js/main.js?v=20260426b',
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
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        })
        .catch(async () => {
          const isCodevisNav = /\/codevis\/(?:index\.html)?$/.test(url.pathname);
          const cache = await caches.open(CACHE_NAME);
          const fallbacks = isCodevisNav
            ? [request, './codevis/', './codevis/index.html', './index.html']
            : [request, './', './index.html'];

          for (const fallback of fallbacks) {
            const cached = await cache.match(fallback);
            if (cached) return cached;
          }

          return new Response('Offline', {
            status: 503,
            headers: { 'Content-Type': 'text/plain; charset=utf-8' }
          });
        })
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
