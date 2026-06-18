const CACHE_NAME = 'englab-static-v20260618materialsP1';
const APP_SHELL = [
  './',
  './index.html',
  './shared/js/lucide.min.js?v=20260417c',
  './shared/js/config.js?v=20260618materialsP1',
  './shared/js/learning-progress.js?v=20260422a',
  './shared/js/back-to-top.js?v=20260424rr',
  './shared/js/fab-trigger.js?v=20260618publicCleanP1',
  './shared/js/touch-gestures.js?v=20260418a',
  './shared/js/experiment-export.js?v=20260528v61f',
  './shared/js/quiz-data.js?v=20260618refsP1',
  './shared/js/experiment-quiz.js?v=20260606fix1',
  './shared/js/experiment-favorites.js?v=20260423q',
  './shared/js/experiment-rating.js?v=20260418g',
  './shared/js/module-selector.js?v=20260618publicCleanP1',
  './shared/js/router.js?v=20260618fabLayerP1',
  './shared/js/scroll-animations.js?v=20260618crossCanvasP1',
  './shared/js/cards.js?v=20260618publicCleanP1',
  './shared/js/common.js?v=20260417c',
  './shared/js/main.js?v=20260618materialsP1',
  './shared/js/global-search.js?v=20260424v45a',
  './shared/js/keyboard-shortcuts.js?v=20260424v45b',
  './shared/js/related-experiments.js?v=20260424v45c',
  './shared/css/related-experiments.css?v=20260424v45c',
  './shared/css/global-search.css?v=20260606v62e',
  './pages/home/home.js?v=20260605v62f',
  './pages/planets/planets.js?v=20260618crossCanvasP1',
  './pages/cosmos/earth-sun.js?v=20260618publicCleanP1',
  './pages/datascience/linear-regression.js?v=20260618dataP2',
  './pages/infotech/network-layers.js?v=20260618publicCleanP1',
  './pages/materials/materials-lab.js?v=20260618materialsP1',
  './pages/humanities/text-lab.js?v=20260618humanP3',
  './pages/engineering/bridge-truss.js?v=20260618engP2',
  './shared/workers/particle-worker.js?v=20260422y',
  './shared/css/tokens.css?v=20260424ss',
  './shared/css/base.css?v=20260417c',
  './shared/css/typography.css?v=20260526v61c',
  './shared/css/navbar.css?v=20260423s',
  './shared/css/page-layout.css?v=20260606v62e',
  './shared/css/cards.css?v=20260618publicCleanP1',
  './shared/css/module-selector.css?v=20260618publicCleanP1',
  './shared/css/experiment-export.css?v=20260418f',
  './shared/css/experiment-favorites.css?v=20260423s',
  './shared/css/experiment-rating.css?v=20260422z',
  './shared/css/experiment-polish.css?v=20260526v61c',
  './shared/css/responsive.css?v=20260606v62e',
  './pages/home/home.css?v=20260605v62e',
  './pages/planets/planets.css?v=20260618crossCanvasP1',
  './pages/cosmos/cosmos.css?v=20260618publicCleanP1',
  './pages/datascience/datascience.css?v=20260618dataP2',
  './pages/infotech/infotech.css?v=20260618publicCleanP1',
  './pages/materials/materials.css?v=20260618materialsP1',
  './pages/humanities/humanities.css?v=20260618humanP3',
  './pages/engineering/engineering.css?v=20260618engP2',
  './pages/about/about.css?v=20260618publicCleanP1',
  './pages/about/about.js?v=20260618publicCleanP1',
  './codevis/',
  './codevis/index.html?v=20260618publicDocsP1',
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

  if (/^\/(?:(?:doc|muban|server)(?:\/|$)|(?:.*\/)?README\.md$|\.(?:git|github|vscode|agents|codex)(?:\/|$))/i.test(url.pathname)) {
    event.respondWith(new Response('Not Found', {
      status: 404,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' }
    }));
    return;
  }

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

  const isLocalhost = url.hostname === 'localhost' || url.hostname === '127.0.0.1' || url.hostname === '::1';
  const isVersionedAsset = url.searchParams.has('v');

  // During local development and for explicit versioned assets, prefer the network.
  // This prevents a previously installed worker from serving stale JS after edits.
  if (isLocalhost || isVersionedAsset) {
    event.respondWith(
      fetch(request, { cache: 'reload' })
        .then((response) => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  // Stale-while-revalidate for unversioned production static assets
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
