// ===== Main Application Bootstrap =====

function initApp() {
    if (window.__loadProgress) window.__loadProgress(30);

    // 1. Initialize card system
    initExperimentCards();

    // 1b. Initialize module selector (gallery-based navigation per subject page)
    if (typeof ModuleSelector !== 'undefined') ModuleSelector.init();

    // 1c. Initialize experiment guide system
    if (typeof ExperimentGuide !== 'undefined') ExperimentGuide.init();

    // 1d. Initialize experiment export system (E-03)
    if (typeof ExperimentExport !== 'undefined') ExperimentExport.init();

    // 1d2. Initialize quiz system (X-02)
    if (typeof ExperimentQuiz !== 'undefined') ExperimentQuiz.init();

    // 1d3. Initialize favorites system
    if (typeof ExperimentFavorites !== 'undefined') ExperimentFavorites.init();

    // 1d4. Initialize rating system
    if (typeof ExperimentRating !== 'undefined') ExperimentRating.init();

    // 1e. Initialize learning progress system (X-01)
    if (typeof LearningProgress !== 'undefined') LearningProgress.init();

    // 1f. Initialize theme switch (X-03)
    if (typeof ThemeSwitch !== 'undefined') ThemeSwitch.init();

    // 1g. Initialize global search (v4.5-α1)
    if (typeof GlobalSearch !== 'undefined') GlobalSearch.init();

    // 1h. Initialize keyboard shortcuts (v4.5-α2)
    if (typeof KeyboardShortcuts !== 'undefined') KeyboardShortcuts.init();

    // 2. Homepage init moved to Router.onPageEnter('home') for lazy loading

    // 3. All experiment module inits moved to Router.onPageEnter() for lazy loading
    //    Modules are initialized only when their page is navigated to,
    //    and destroyed via Router.onPageLeave() when navigating away.

    // 4. Initialize scroll animation system
    if (typeof initScrollAnimations === 'function') initScrollAnimations();

    // 5. Render Lucide icons — lucide is now served locally (shared/js/lucide.min.js)
    //    so this is synchronous and reliable. CDN fallback script in index.html handles
    //    the rare edge case where the local file fails.
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    } else {
        // lucide CDN fallback may still be loading — retry after a tick
        setTimeout(function() {
            if (typeof lucide !== 'undefined') lucide.createIcons();
        }, 500);
    }

    if (window.__loadProgress) window.__loadProgress(50);

    // 6. Initialize router (page transitions — triggers initHome for homepage)
    //    FIXED: Router.init() now always calls onPageEnter for the initial page,
    //    so initHome() runs on first load instead of requiring a re-navigation.
    Router.init();

    // 7. Speed slider for bucket sort
    const speedInput = document.getElementById('sort-speed');
    if (speedInput) {
        speedInput.addEventListener('input', (e) => {
            const newSpeed = parseInt(e.target.value);
            window.sortSpeed = newSpeed;
            if (typeof sortSpeed !== 'undefined') {
                sortSpeed = newSpeed;
            }
            const speedValueEl = document.getElementById('speed-value');
            if (speedValueEl) {
                speedValueEl.textContent = newSpeed + 'ms';
            }
        });
    }

    // 8. Nav indicator initial position
    requestAnimationFrame(() => {
        const activeNav = document.querySelector('.nav-item.active');
        if (activeNav && Router.moveIndicator) {
            Router.moveIndicator(activeNav);
        }
    });

    // 9. Window resize: update nav indicator
    window.addEventListener('resize', () => {
        const activeNav = document.querySelector('.nav-item.active');
        if (activeNav && Router.moveIndicator) {
            Router.moveIndicator(activeNav);
        }
    });

    // 10. Back to top button
    initBackToTop();

    // 11. Footer visibility based on current page
    updateFooterVisibility();

    // 11b. Register service worker in the background for repeat-visit acceleration
    registerServiceWorker();

    // 12. Dismiss loading screen
    //     FIXED: _coreReady() no longer requires lucide (it's now local/sync).
    //     We only require GSAP and Router to be initialized before dismissing.
    //     This prevents the loading bar from being "stuck" due to CDN delays.
    if (window.__loadProgress) window.__loadProgress(70);

    var _loadDismissed = false;
    function _dismissLoadingScreen() {
        if (_loadDismissed) return;
        _loadDismissed = true;
        if (window.__loadProgress) window.__loadProgress(100);
        requestAnimationFrame(function () {
            var ls = document.getElementById('loading-screen');
            if (ls) {
                ls.classList.add('hidden');
                ls.addEventListener('transitionend', function () { ls.remove(); }, { once: true });
                setTimeout(function () { if (ls.parentNode) ls.remove(); }, 800);
            }
            // Clean up inline loading-screen styles
            var lsStyles = document.getElementById('loading-screen-styles');
            if (lsStyles) setTimeout(function () { lsStyles.remove(); }, 1000);
            delete window.__loadProgress;
        });
    }

    // Core readiness check — GSAP and Router are the only hard dependencies.
    // lucide is now local so it's always available synchronously.
    // We do NOT block on lucide CDN fallback here.
    function _coreReady() {
        return typeof gsap !== 'undefined' &&
               typeof Router !== 'undefined' &&
               Router._initialEnterFired;
    }

    var _isReturningVisitor = !!(window.__englabCache && window.__englabCache.returnVisitor);
    var _pollLimit = _isReturningVisitor ? 5 : 10;
    var _pollDelay = _isReturningVisitor ? 60 : 90;
    var _fallbackDelay = _isReturningVisitor ? 900 : 1800;

    if (_coreReady()) {
        // Already initialized (e.g. cached resources) — dismiss after a single frame
        requestAnimationFrame(_dismissLoadingScreen);
    } else {
        // Poll briefly for core readiness (deferred scripts may still be executing)
        var _pollCount = 0;
        var _pollTimer = setInterval(function () {
            _pollCount++;
            if (window.__loadProgress) window.__loadProgress(Math.min((_isReturningVisitor ? 82 : 72) + _pollCount * 4, 95));
            if (_coreReady() || _pollCount >= _pollLimit) {
                clearInterval(_pollTimer);
                requestAnimationFrame(_dismissLoadingScreen);
            }
        }, _pollDelay);
    }

    // Hard safety fallback: repeat visits should dismiss much faster
    setTimeout(function () {
        if (!_loadDismissed) _dismissLoadingScreen();
    }, _fallbackDelay);
}

// ===== Back to Top =====
function initBackToTop() {
    const btn = document.getElementById('back-to-top');
    if (!btn) return;

    window.addEventListener('scroll', () => {
        if (window.scrollY > 400) {
            btn.classList.add('visible');
        } else {
            btn.classList.remove('visible');
        }
    }, { passive: true });

    btn.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
}

// ===== Footer Visibility =====
function updateFooterVisibility() {
    const footer = document.getElementById('site-footer');
    if (!footer) return;

    // Hide footer on home page, show on content pages
    const observer = new MutationObserver(() => {
        const homePage = document.getElementById('page-home');
        footer.style.display = homePage && homePage.classList.contains('active') ? 'none' : '';
    });

    observer.observe(document.querySelector('.main-content'), {
        childList: false,
        subtree: true,
        attributes: true,
        attributeFilter: ['class']
    });

    // Initial check
    const homePage = document.getElementById('page-home');
    footer.style.display = homePage && homePage.classList.contains('active') ? 'none' : '';
}

window.updateFooterVisibility = updateFooterVisibility;

const ENGLAB_ASSET_VERSION = '20260417c';
const HTTP_FALLBACK_ASSETS = [
    './',
    './index.html',
    './shared/css/tokens.css?v=' + ENGLAB_ASSET_VERSION,
    './shared/css/base.css?v=' + ENGLAB_ASSET_VERSION,
    './shared/css/typography.css?v=' + ENGLAB_ASSET_VERSION,
    './shared/css/navbar.css?v=' + ENGLAB_ASSET_VERSION,
    './shared/css/page-layout.css?v=' + ENGLAB_ASSET_VERSION,
    './shared/css/cards.css?v=' + ENGLAB_ASSET_VERSION,
    './shared/css/module-selector.css?v=' + ENGLAB_ASSET_VERSION,
    './shared/css/responsive.css?v=' + ENGLAB_ASSET_VERSION,
    './pages/home/home.css?v=' + ENGLAB_ASSET_VERSION,
    './shared/js/lucide.min.js?v=' + ENGLAB_ASSET_VERSION,
    './shared/js/config.js?v=' + ENGLAB_ASSET_VERSION,
    './shared/js/module-selector.js?v=' + ENGLAB_ASSET_VERSION,
    './shared/js/router.js?v=' + ENGLAB_ASSET_VERSION,
    './shared/js/scroll-animations.js?v=' + ENGLAB_ASSET_VERSION,
    './shared/js/cards.js?v=' + ENGLAB_ASSET_VERSION,
    './shared/js/common.js?v=' + ENGLAB_ASSET_VERSION,
    './shared/js/main.js?v=' + ENGLAB_ASSET_VERSION,
    './pages/home/home.js?v=' + ENGLAB_ASSET_VERSION
];

function updateCacheDiagnostics(patch) {
    window.__englabCache = window.__englabCache || {};
    Object.assign(window.__englabCache, patch || {});
    try {
        const raw = JSON.parse(localStorage.getItem('englab-cache-diagnostics') || '{}');
        const next = Object.assign(raw, patch || {}, { updatedAt: Date.now() });
        localStorage.setItem('englab-cache-diagnostics', JSON.stringify(next));
    } catch (_) {}
}

function warmHttpCacheFallback() {
    updateCacheDiagnostics({
        cacheMode: 'http-fallback',
        transport: 'browser-http-cache',
        swRegistered: false
    });

    const runWarmup = function () {
        Promise.all(HTTP_FALLBACK_ASSETS.map(function (url) {
            return fetch(url, {
                credentials: 'same-origin',
                cache: 'force-cache'
            }).then(function (response) {
                return response && response.ok ? response.url : null;
            }).catch(function () {
                return null;
            });
        })).then(function (results) {
            const warmedUrls = results.filter(Boolean);
            updateCacheDiagnostics({
                warmedAssetCount: warmedUrls.length,
                warmedAssetUrls: warmedUrls.slice(0, 12),
                lastWarmupAt: Date.now()
            });
        });
    };

    if (window.requestIdleCallback) {
        window.requestIdleCallback(runWarmup, { timeout: 1500 });
    } else {
        setTimeout(runWarmup, 500);
    }
}

function registerServiceWorker() {
    if (location.protocol !== 'http:' && location.protocol !== 'https:') return;

    const hostname = location.hostname;
    const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1';
    let forcedMode = null;
    try {
        forcedMode = new URLSearchParams(location.search).get('cacheMode') || localStorage.getItem('englab-force-cache-mode');
    } catch (_) {}

    const supportsSW = 'serviceWorker' in navigator;
    const canUseSW = supportsSW && (window.isSecureContext || isLocalhost) && forcedMode !== 'fallback';

    updateCacheDiagnostics({
        origin: location.origin,
        protocol: location.protocol,
        secureContext: !!window.isSecureContext,
        supportsSW: supportsSW,
        cacheMode: canUseSW ? 'service-worker-pending' : 'http-fallback'
    });

    if (!canUseSW) {
        warmHttpCacheFallback();
        return;
    }

    const doRegister = function () {
        navigator.serviceWorker.register('./sw.js?v=' + ENGLAB_ASSET_VERSION)
            .then(function (registration) {
                updateCacheDiagnostics({
                    cacheMode: 'service-worker',
                    transport: 'cache-storage',
                    swRegistered: true,
                    swScope: registration.scope,
                    controller: !!navigator.serviceWorker.controller
                });
                if (navigator.serviceWorker.ready) {
                    navigator.serviceWorker.ready.then(function () {
                        updateCacheDiagnostics({
                            swReady: true,
                            controller: !!navigator.serviceWorker.controller
                        });
                    }).catch(function () {});
                }
            })
            .catch(function (error) {
                updateCacheDiagnostics({
                    cacheMode: 'http-fallback',
                    transport: 'browser-http-cache',
                    swRegistered: false,
                    swError: String(error && error.message ? error.message : error)
                });
                warmHttpCacheFallback();
            });
    };

    if (window.requestIdleCallback) {
        window.requestIdleCallback(doRegister, { timeout: 1200 });
    } else {
        setTimeout(doRegister, 400);
    }
}

// Launch immediately — DOM is ready (sync script at bottom of body).
// Do NOT use DOMContentLoaded: deferred experiment scripts would delay it.
initApp();
