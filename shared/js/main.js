// ===== Main Application Bootstrap =====

function initApp() {
    if (window.__loadProgress) window.__loadProgress(30);

    // 1. Initialize card system
    initExperimentCards();

    // 1b. Initialize module selector (gallery-based navigation per subject page)
    if (typeof ModuleSelector !== 'undefined') ModuleSelector.init();

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

function registerServiceWorker() {
    if (!('serviceWorker' in navigator)) return;
    if (location.protocol !== 'http:' && location.protocol !== 'https:') return;

    const doRegister = function () {
        navigator.serviceWorker.register('./sw.js?v=20260416b').catch(function () {
            // ignore registration failures in unsupported dev environments
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
