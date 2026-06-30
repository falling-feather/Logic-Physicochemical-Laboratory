const CACHE_NAME = 'astra-static-v20260630mainV64';
const APP_SHELL = [
  './',
  './index.html',
  './shared/js/lucide.min.js?v=20260417d',
  './shared/js/config.js?v=20260630mainV64',
  './shared/js/router.js?v=20260630mainV64',
  './shared/js/main.js?v=20260630mainV64',
  './shared/css/tokens.css?v=20260424ss',
  './shared/css/base.css?v=20260630mainV64',
  './shared/css/typography.css?v=20260526v61c',
  './shared/css/navbar.css?v=20260630mainV64',
  './shared/css/page-layout.css?v=20260606v62e',
  './shared/css/responsive.css?v=20260630mainV64',
  './pages/planets/planets.css?v=20260630mainV64',
  './pages/planets/planets.js?v=20260630mainV64',
  './UI/future-galaxy/future-galaxy-hero-sky.png',
  './UI/future-galaxy/future-galaxy-hero-nebula.png',
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

  if (/^\/(?:(?:doc|muban|server|tools)(?:\/|$)|(?:.*\/)?README\.md$|\.(?:git|github|vscode|agents|codex)(?:\/|$))/i.test(url.pathname)) {
    event.respondWith(new Response('Not Found', {
      status: 404,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' }
    }));
    return;
  }

  // SPA navigation: network first, cache fallback.
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

  // Versioned local/dev assets stay network-first to avoid stale JS after edits.
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

  // Stale-while-revalidate for unversioned production static assets.
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
