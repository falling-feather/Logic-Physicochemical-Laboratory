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

    // 5. Render Lucide icons (before Router so satellite icons are ready)
    if (typeof lucide !== 'undefined') lucide.createIcons();

    if (window.__loadProgress) window.__loadProgress(50);

    // 6. Initialize router (page transitions — triggers initHome for homepage)
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

    // 12. Dismiss loading screen (page content is now ready)
    if (window.__loadProgress) window.__loadProgress(100);
    requestAnimationFrame(function () {
        var ls = document.getElementById('loading-screen');
        if (ls) {
            ls.classList.add('hidden');
            ls.addEventListener('transitionend', function () { ls.remove(); }, { once: true });
            // Fallback removal if transitionend doesn't fire
            setTimeout(function () { if (ls.parentNode) ls.remove(); }, 800);
        }
        // Clean up global helper
        delete window.__loadProgress;
    });
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

// Launch immediately — DOM is ready (sync script at bottom of body).
// Do NOT use DOMContentLoaded: deferred experiment scripts would delay it.
initApp();
