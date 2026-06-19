// ===== Router: GSAP Page Transitions =====
const Router = {
    overlay: null,
    currentPage: 'planets',
    isTransitioning: false,
    _initialEnterFired: false,
    _queuedNavigation: null,
    _pageEnterComplete: true,
    _runningTimeId: null,
    _hashReconcileId: null,
    _pendingModule: null,
    _pendingAnchor: null,
    _lastAppliedAnchor: null,
    _pageScriptPromises: {},
    _galaxySupportPromises: {},
    frontierPages: ['frontier', 'cosmos', 'engineering', 'datascience', 'infotech', 'materials', 'humanities'],
    coursePages: ['mathematics', 'physics', 'chemistry', 'algorithms', 'biology'],
    _activeGalaxy: null,
    _galaxyCacheKey: 'astra-galaxy-cache-meta',
    _galaxyCacheVersion: '20260619v63FrontierLifecycleP1',
    _galaxyPageMap: {
        planets: 'astra',
        home: 'englab',
        mathematics: 'englab',
        physics: 'englab',
        chemistry: 'englab',
        algorithms: 'englab',
        biology: 'englab',
        frontier: 'frontier',
        cosmos: 'frontier',
        engineering: 'frontier',
        datascience: 'frontier',
        infotech: 'frontier',
        materials: 'frontier',
        humanities: 'frontier',
        license: 'englab',
        changelog: 'englab'
    },
    courseSupportScripts: [
        'shared/js/lucide.min.js?v=20260417d',
        'shared/js/module-selector.js?v=20260619v63StartupLazyP1'
    ],
    galaxySupportScripts: {
        astra: [
            'shared/js/lucide.min.js?v=20260417d'
        ],
        englab: [
            'shared/js/learning-progress.js?v=20260422a',
            'shared/js/back-to-top.js?v=20260424rr',
            'shared/js/fab-trigger.js?v=20260528v61g',
            'shared/js/touch-gestures.js?v=20260418a',
            'shared/js/experiment-guide.js?v=20260619v63FrontierLifecycleP1',
            'shared/js/experiment-export.js?v=20260528v61f',
            'shared/js/quiz-data.js?v=20260618refsP1',
            'shared/js/experiment-quiz.js?v=20260606fix1',
            'shared/js/experiment-favorites.js?v=20260423q',
            'shared/js/experiment-rating.js?v=20260418g',
            'shared/js/global-search.js?v=20260424v45a',
            'shared/js/keyboard-shortcuts.js?v=20260424v45b',
            'shared/js/related-experiments.js?v=20260424v45c'
        ],
        frontier: [
            'shared/js/lucide.min.js?v=20260417d',
            'shared/js/frontier-learning.js?v=20260619v63FrontierLifecycleP1',
            'shared/js/scroll-animations.js?v=20260619v63FrontierLifecycleP1'
        ]
    },
    pageScripts: {
        home: 'pages/home/home.js?v=20260619v63StartupLazyP1',
        planets: 'pages/planets/planets.js?v=20260619v63AsyncGsapP1',
        cosmos: 'pages/cosmos/earth-sun.js?v=20260619v63FrontierLifecycleP1',
        datascience: 'pages/datascience/linear-regression.js?v=20260619v63FrontierLifecycleP1',
        infotech: 'pages/infotech/network-layers.js?v=20260619v63FrontierLifecycleP1',
        materials: 'pages/materials/materials-lab.js?v=20260619v63AsyncGsapP1',
        humanities: 'pages/humanities/text-lab.js?v=20260618humanP3',
        engineering: 'pages/engineering/bridge-truss.js?v=20260619v63FrontierLifecycleP1',
        license: 'pages/about/about.js?v=20260619v63FrontierLifecycleP1',
        changelog: 'pages/about/about.js?v=20260619v63FrontierLifecycleP1'
    },
    pageReadyChecks: {
        home: () => typeof window.initHome === 'function',
        planets: () => typeof window.initPlanets === 'function',
        cosmos: () => typeof window.initCosmosSeasons === 'function',
        datascience: () => typeof window.initLinearRegressionLab === 'function',
        infotech: () => typeof window.initNetworkLayersLab === 'function',
        materials: () => typeof window.initMaterialsLab === 'function',
        humanities: () => typeof window.initHumanitiesLab === 'function',
        engineering: () => typeof window.initBridgeTruss === 'function',
        license: () => typeof window.initLicense === 'function',
        changelog: () => typeof window.initChangelog === 'function'
    },
    // Store origin point for radial wipe (set by selectModule or default center)
    transitionOrigin: { x: 50, y: 50 },

    init() {
        // Create transition overlay
        this.overlay = document.createElement('div');
        this.overlay.className = 'page-transition-overlay';
        document.body.appendChild(this.overlay);

        // Nav click delegation (intercept for animated transitions)
        document.querySelectorAll('.nav-item[data-page], .nav-logo[data-page]').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const page = item.dataset.page;
                if (page) {
                    // If already on this page, reset to gallery view (back to experiment list)
                    if (page === this.currentPage && this._isActivePage(page)) {
                        this._pendingModule = null;
                        this._pendingAnchor = null;
                        this._lastAppliedAnchor = null;
                        if (page !== 'home' && typeof ModuleSelector !== 'undefined' && ModuleSelector.activeModule[page]) {
                            ModuleSelector.closeModule(page);
                        }
                        if (window.location.hash.slice(1) !== page) {
                            history.pushState(null, '', `#${page}`);
                        }
                        window.scrollTo({ top: 0, behavior: 'smooth' });
                        return;
                    }
                    this._pendingModule = null;
                    this._pendingAnchor = null;
                    this._lastAppliedAnchor = null;
                    // Use nav item center as transition origin
                    const rect = item.getBoundingClientRect();
                    this.transitionOrigin = {
                        x: ((rect.left + rect.width / 2) / window.innerWidth) * 100,
                        y: ((rect.top + rect.height / 2) / window.innerHeight) * 100
                    };
                    this.navigateTo(page, true);
                }
            });
        });

        // Initial state — determine page from hash
        const parsedInit = this._parseHash();
        const initialPage = parsedInit.page;
        this.currentPage = initialPage;
        this._pendingModule = parsedInit.moduleId;
        this._pendingAnchor = parsedInit.anchorId || null;

        // Ensure the correct page has 'active' class (HTML defaults to planets v6.1.0-alpha5)
        if (initialPage !== 'planets') {
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            const initEl = document.getElementById(`page-${initialPage}`);
            if (initEl) initEl.classList.add('active');
        }
        this.updateNav(initialPage);

        // CRITICAL FIX: Always fire onPageEnter for the initial page.
        // Previously, handleHash() returned early when page-home already had .active
        // in HTML, so initHome() was never called on first load — causing the
        // satellite animation to never start until a re-navigation.
        this._initialEnterFired = true;
        // v5.0：初次加载（特别是直接进入 #planets）也需要同步导航栏可见性，
        //       否则 HTML 默认的 .navbar--transparent 不会被替换为 .navbar--hidden。
        const initNavbar = document.getElementById('navbar');
        if (initNavbar) {
            const isFrontier = this._isFrontierPage(initialPage);
            initNavbar.classList.toggle('navbar--transparent', initialPage === 'home');
            initNavbar.classList.toggle('navbar--hidden', initialPage === 'planets');
            initNavbar.classList.toggle('navbar--frontier', isFrontier);
        }
        this._toggleGalaxyFooters(initialPage);
        this._syncGalaxyRuntime(initialPage);
        this.onPageEnter(initialPage);

        // Show running time footer for non-home pages
        this._toggleRunningTime(this._usesEnglabFooter(initialPage));

        window.addEventListener('hashchange', () => this.handleHash());

        // Handle popstate (back/forward)
        window.addEventListener('popstate', () => this.handleHash());

        this._startHashReconcile();
    },

    /**
     * 解析 hash，支持 "subject/experiment" 深链接与未来星系页内锚点。
     * 返回 { page, moduleId, anchorId }，moduleId 与 anchorId 均可为空。
     */
    _parseHash() {
        const raw = (window.location.hash || '').slice(1);
        if (!raw) return { page: 'planets', moduleId: null, anchorId: null };
        const anchorPage = this._pageForFrontierAnchor(raw);
        if (anchorPage) return { page: anchorPage, moduleId: null, anchorId: raw };
        const idx = raw.indexOf('/');
        if (idx === -1) return { page: raw, moduleId: null, anchorId: null };
        return { page: raw.slice(0, idx), moduleId: raw.slice(idx + 1) || null, anchorId: null };
    },

    _pageForFrontierAnchor(anchorId) {
        if (!anchorId || !anchorId.startsWith('frontier-')) return null;
        return this.frontierPages.find((page) => anchorId.startsWith(`frontier-${page}-`)) || null;
    },

    _galaxyForPage(page) {
        return this._galaxyPageMap[page] || 'englab';
    },

    getActiveGalaxy() {
        return this._activeGalaxy || this._galaxyForPage(this.currentPage);
    },

    _readCookieValue(name) {
        try {
            const prefix = `${encodeURIComponent(name)}=`;
            const item = document.cookie.split('; ').find((entry) => entry.startsWith(prefix));
            return item ? decodeURIComponent(item.slice(prefix.length)) : null;
        } catch (e) {
            return null;
        }
    },

    _writeCookieValue(name, value) {
        try {
            const maxAge = 60 * 60 * 24 * 180;
            document.cookie = `${encodeURIComponent(name)}=${encodeURIComponent(value)}; Max-Age=${maxAge}; Path=/; SameSite=Lax`;
        } catch (e) {}
    },

    _readGalaxyCacheMeta() {
        const fallback = {
            version: this._galaxyCacheVersion,
            loadedGalaxies: {},
            visits: {}
        };
        try {
            const stored = window.localStorage && window.localStorage.getItem(this._galaxyCacheKey);
            const raw = JSON.parse(stored || this._readCookieValue(this._galaxyCacheKey) || '{}');
            if (raw.version !== this._galaxyCacheVersion) {
                return fallback;
            }
            raw.loadedGalaxies = raw.loadedGalaxies || {};
            raw.visits = raw.visits || {};
            return raw;
        } catch (e) {
            return fallback;
        }
    },

    _writeGalaxyCacheMeta(meta) {
        try {
            const value = JSON.stringify(meta);
            if (window.localStorage) {
                window.localStorage.setItem(this._galaxyCacheKey, value);
            }
            this._writeCookieValue(this._galaxyCacheKey, value);
        } catch (e) {}
    },

    _markGalaxyLoaded(galaxy, page) {
        const meta = this._readGalaxyCacheMeta();
        const now = Date.now();
        meta.lastGalaxy = galaxy;
        meta.lastPage = page;
        meta.updatedAt = now;
        meta.loadedGalaxies[galaxy] = {
            firstLoadedAt: meta.loadedGalaxies[galaxy] && meta.loadedGalaxies[galaxy].firstLoadedAt || now,
            lastLoadedAt: now
        };
        meta.visits[galaxy] = (meta.visits[galaxy] || 0) + 1;
        this._writeGalaxyCacheMeta(meta);
        window.__astraGalaxyCache = meta;
        if (typeof window.warmGalaxyCache === 'function') {
            window.warmGalaxyCache(galaxy);
        }
    },

    loadActiveGalaxySupport() {
        return this._loadGalaxySupport(this.getActiveGalaxy(), this.currentPage);
    },

    _loadGalaxySupport(galaxy, page) {
        try {
            if (new URLSearchParams(location.search).get('noDeferred') === '1') {
                return Promise.resolve();
            }
        } catch (e) {}

        const scripts = this.galaxySupportScripts[galaxy] || [];
        if (!scripts.length) {
            this._bootGalaxySupport(galaxy, page);
            return Promise.resolve();
        }

        if (!this._galaxySupportPromises[galaxy]) {
            this._galaxySupportPromises[galaxy] = scripts.reduce(
                (chain, src) => chain.then(() => this._loadScriptOnce(src, 'routerGalaxyScript', galaxy)),
                Promise.resolve()
            ).catch((error) => {
                delete this._galaxySupportPromises[galaxy];
                throw error;
            });
        }

        return this._galaxySupportPromises[galaxy].then(() => {
            this._bootGalaxySupport(galaxy, page);
        });
    },

    _bootGalaxySupport(galaxy) {
        const current = this.currentPage;
        if (this._galaxyForPage(current) !== galaxy) return;

        if (typeof lucide !== 'undefined') {
            try { lucide.createIcons(); } catch (e) {}
        }

        if (galaxy === 'englab') {
            if (typeof ExperimentGuide !== 'undefined') ExperimentGuide.init();
            if (typeof ExperimentExport !== 'undefined') ExperimentExport.init();
            if (typeof ExperimentQuiz !== 'undefined') ExperimentQuiz.init();
            if (typeof ExperimentFavorites !== 'undefined') ExperimentFavorites.init();
            if (typeof ExperimentRating !== 'undefined') ExperimentRating.init();
            if (typeof LearningProgress !== 'undefined') LearningProgress.init();
            if (typeof GlobalSearch !== 'undefined') GlobalSearch.init();
            if (typeof KeyboardShortcuts !== 'undefined') KeyboardShortcuts.init();

            const isCoursePage = this.coursePages.includes(current);
            if (typeof BackToTop !== 'undefined') {
                if (isCoursePage) BackToTop.show(); else BackToTop.hide();
            }
            if (typeof FabTrigger !== 'undefined') {
                if (isCoursePage) FabTrigger.show(); else FabTrigger.hide();
            }
            return;
        }

        if (galaxy === 'frontier') {
            if (typeof FrontierLearning !== 'undefined') FrontierLearning.init(current);
            if (typeof window.initScrollAnimations === 'function') window.initScrollAnimations();
            if (current !== 'home' && current !== 'planets' && typeof window.initPageScrollAnimations === 'function') {
                window.initPageScrollAnimations(current);
            }
            if (current !== 'home' && current !== 'planets' && typeof window.initHeroVisual === 'function') {
                window.initHeroVisual(current);
            }
        }
    },

    _syncGalaxyRuntime(page) {
        const nextGalaxy = this._galaxyForPage(page);
        const previousGalaxy = this._activeGalaxy;
        if (previousGalaxy && previousGalaxy !== nextGalaxy) {
            this._unloadGalaxyRuntime(previousGalaxy, nextGalaxy);
        }
        this._activeGalaxy = nextGalaxy;
        document.documentElement.dataset.activeGalaxy = nextGalaxy;
        document.body.dataset.activeGalaxy = nextGalaxy;
        this._markGalaxyLoaded(nextGalaxy, page);
        this._loadGalaxySupport(nextGalaxy, page).catch((error) => {
            console.warn('[Router] galaxy support load failed:', nextGalaxy, error);
        });
    },

    _unloadGalaxyRuntime(previousGalaxy, nextGalaxy) {
        try {
            window.dispatchEvent(new CustomEvent('astra:galaxy-unload', {
                detail: { previousGalaxy, nextGalaxy }
            }));
        } catch (e) {}

        if (previousGalaxy === 'englab' && typeof ModuleSelector !== 'undefined' && ModuleSelector.activeModule) {
            this.coursePages.forEach((subject) => {
                if (ModuleSelector.activeModule[subject] && typeof ModuleSelector.closeModule === 'function') {
                    try { ModuleSelector.closeModule(subject); } catch (e) {}
                }
            });
            try {
                if (typeof BackToTop !== 'undefined') BackToTop.hide();
                if (typeof FabTrigger !== 'undefined') FabTrigger.hide();
            } catch (e) {}
        }

        if (previousGalaxy === 'frontier') {
            if (typeof FrontierLearning !== 'undefined' && typeof FrontierLearning.destroy === 'function') {
                try { FrontierLearning.destroy(); } catch (e) {}
            }
            if (typeof destroyAllHeroVisuals === 'function') {
                try { destroyAllHeroVisuals(); } catch (e) {}
            }
        }
    },

    handleHash() {
        const parsed = this._parseHash();
        const page = parsed.page;
        this._pendingModule = parsed.moduleId;
        this._pendingAnchor = parsed.anchorId || null;
        if (!this._pendingAnchor) this._lastAppliedAnchor = null;
        // 同 page 但深链接或页内锚点变化：直接处理，不重走转场
        if (page === this.currentPage && this._isActivePage(page)) {
            if (this._pendingAnchor) {
                this._applyPendingAnchor();
                return;
            }
            this._applyPendingModule(page);
            return;
        }
        this.navigateTo(page, false);
    },

    navigateTo(page, animate = true) {
        if (this.isTransitioning) {
            this._queueNavigation(page, animate);
            return;
        }
        if (page === this.currentPage && this._isActivePage(page)) {
            if (this._pendingAnchor) this._applyPendingAnchor();
            return;
        }
        this.isTransitioning = true; // Set immediately to prevent race conditions

        const currentEl = document.querySelector('.page.active');
        const targetEl = document.getElementById(`page-${page}`);
        if (!targetEl) {
            this.isTransitioning = false;
            this._pageEnterComplete = true;
            this._flushQueuedNavigation();
            return;
        }
        this._pageEnterComplete = false;

        // Update hash without triggering hashchange
        // 保留可能存在的深链接模块后缀（如 #physics/momentum-conservation）
        const desiredHash = this._pendingAnchor || (this._pendingModule ? `${page}/${this._pendingModule}` : page);
        if (window.location.hash.slice(1) !== desiredHash) {
            history.pushState(null, '', `#${desiredHash}`);
        }

        // Update nav
        this.updateNav(page);

        // Update navbar visibility/transparency
        // v4.3：home 透明化；v4.4：planets 大屏完全隐藏顶栏（作为目录承载更沉浸）
        const navbar = document.getElementById('navbar');
        if (navbar) {
            const isFrontier = this._isFrontierPage(page);
            navbar.classList.toggle('navbar--transparent', page === 'home');
            navbar.classList.toggle('navbar--hidden', page === 'planets');
            navbar.classList.toggle('navbar--frontier', isFrontier);
        }
        this._toggleGalaxyFooters(page);

        // Toggle running time footer
        this._toggleRunningTime(this._usesEnglabFooter(page));

        const prevPage = currentEl && currentEl.id
            ? currentEl.id.replace(/^page-/, '')
            : this.currentPage;
        this.currentPage = page;

        // Cleanup previous page modules
        this.onPageLeave(prevPage);
        this._syncGalaxyRuntime(page);

        // Respect prefers-reduced-motion
        const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        const isDirectoryTransition = page === 'planets' || prevPage === 'planets';
        if (!animate || isDirectoryTransition || !currentEl || typeof gsap === 'undefined' || prefersReduced) {
            // No animation (initial load, no GSAP, or reduced motion)
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            targetEl.classList.add('active');
            window.scrollTo({ top: 0 });
            this.onPageEnter(page);
            this._finishTransition();
            return;
        }

        // Determine accent color for overlay
        const colors = {
            mathematics: 'rgba(91,141,206,0.12)',
            physics: 'rgba(139,111,192,0.12)',
            chemistry: 'rgba(77,158,126,0.12)',
            algorithms: 'rgba(196,121,58,0.12)',
            biology: 'rgba(58,158,143,0.12)',
            cosmos: 'rgba(116,185,255,0.12)',
            datascience: 'rgba(138,167,255,0.12)',
            infotech: 'rgba(94,224,216,0.12)',
            materials: 'rgba(224,181,106,0.12)',
            humanities: 'rgba(126,215,193,0.12)',
            engineering: 'rgba(216,163,72,0.12)',
            frontier: 'rgba(242,200,107,0.12)',
            home: 'rgba(91,141,206,0.08)',
            planets: 'rgba(0,255,213,0.10)'
        };
        this.overlay.style.background = `linear-gradient(135deg, ${colors[page] || colors.home}, var(--surface-0))`;

        const ox = this.transitionOrigin.x;
        const oy = this.transitionOrigin.y;

        const tl = gsap.timeline({
            onComplete: () => {
                this._finishTransition();
            }
        });

        // Phase 1: Current page exit
        tl.to(currentEl, {
            opacity: 0,
            scale: 0.97,
            filter: 'blur(6px)',
            duration: 0.18,
            ease: 'power2.in',
            onComplete: () => {
                currentEl.classList.remove('active');
                gsap.set(currentEl, { clearProps: 'all' });
            }
        });

        // Phase 2: Radial clip-path wipe in from origin point
        tl.set(this.overlay, {
            opacity: 1,
            clipPath: `circle(0% at ${ox}% ${oy}%)`
        }, '-=0.1');

        tl.to(this.overlay, {
            clipPath: `circle(150% at ${ox}% ${oy}%)`,
            duration: 0.3,
            ease: 'power3.inOut'
        });

        // Phase 3: Switch content and start reveal
        tl.add(() => {
            targetEl.classList.add('active');
            window.scrollTo({ top: 0 });
            gsap.set(targetEl, { opacity: 0, y: 20 });
            // Pre-hide hero children so they never flash visible during the page fade-in.
            // animatePageContent will animate them in individually afterwards.
            if (page !== 'home' && page !== 'planets') {
                const heroKids = targetEl.querySelectorAll(
                    '.page-hero__eyebrow, .page-hero__label, .page-hero__title, .page-hero__desc, .page-hero__actions, .page-hero__visual, .frontier-hero__label, .frontier-hero__title, .frontier-hero__desc, .frontier-hero__visual'
                );
                if (heroKids.length) gsap.set(heroKids, { y: 15, opacity: 0 });
            }
            // Start hero canvas rendering immediately in the background.
            // The canvas is invisible (opacity 0) but already drawing, so when
            // it fades in with the hero animation there is no blank-canvas flash.
            if (page !== 'home' && page !== 'planets' && typeof initHeroVisual === 'function') {
                initHeroVisual(page);
            }
        }, '-=0.1');

        // Phase 4: Fade out overlay while fading in target
        tl.to(this.overlay, {
            opacity: 0,
            duration: 0.2,
            ease: 'power2.out',
            onComplete: () => {
                gsap.set(this.overlay, { clipPath: 'circle(0% at 50% 50%)', opacity: 0 });
            }
        });

        tl.to(targetEl, {
            opacity: 1,
            y: 0,
            duration: 0.3,
            ease: 'power3.out',
            onComplete: () => this.animatePageContent(page, targetEl)
        }, '-=0.18');
    },

    _queueNavigation(page, animate) {
        this._queuedNavigation = {
            page,
            moduleId: this._pendingModule,
            anchorId: this._pendingAnchor,
            animate
        };
    },

    _finishTransition() {
        this.isTransitioning = false;
        this.transitionOrigin = { x: 50, y: 50 };
        this._flushQueuedNavigation();
    },

    _flushQueuedNavigation() {
        if (!this._queuedNavigation || this.isTransitioning || !this._pageEnterComplete) return;
        const next = this._queuedNavigation;
        this._queuedNavigation = null;
        this._pendingModule = next.moduleId;
        this._pendingAnchor = next.anchorId || null;

        if (next.page === this.currentPage && this._isActivePage(next.page)) {
            if (this._pendingAnchor) {
                this._applyPendingAnchor();
                return;
            }
            this._applyPendingModule(next.page);
            return;
        }

        setTimeout(() => this.navigateTo(next.page, next.animate), 0);
    },

    _startHashReconcile() {
        if (this._hashReconcileId) return;
        this._hashReconcileId = setInterval(() => {
            if (this.isTransitioning) return;
            const parsed = this._parseHash();
            const page = parsed.page;
            if (!document.getElementById(`page-${page}`)) return;
            if (page === this.currentPage && this._isActivePage(page)) {
                if (parsed.anchorId && parsed.anchorId !== this._lastAppliedAnchor) {
                    this._pendingAnchor = parsed.anchorId;
                    this._applyPendingAnchor();
                }
                return;
            }

            this._pendingModule = parsed.moduleId;
            this._pendingAnchor = parsed.anchorId || null;
            this.navigateTo(page, false);
        }, 250);
    },

    // Staggered entry for page sub-elements
    animatePageContent(page, pageEl) {
        if (typeof gsap === 'undefined') {
            this.onPageEnter(page);
            return;
        }

        if (page === 'home' || page === 'planets') {
            this.onPageEnter(page);
            return;
        }

        // Animate hero elements with stagger
        const hero = pageEl.querySelector('.page-hero, .frontier-hero');
        if (hero) {
            const heroChildren = hero.querySelectorAll('.page-hero__eyebrow, .page-hero__label, .page-hero__title, .page-hero__desc, .page-hero__actions, .page-hero__visual, .frontier-hero__label, .frontier-hero__title, .frontier-hero__desc, .frontier-hero__visual');
            if (heroChildren.length) {
                // Hero children are already pre-hidden (y:15, opacity:0) in Phase 3.
                // Use gsap.to() to avoid re-setting the start state which would cause a flash.
                gsap.to(heroChildren, {
                    y: 0, opacity: 1,
                    duration: 0.35,
                    ease: 'power3.out',
                    stagger: 0.06,
                    onComplete: () => this.onPageEnter(page)
                });
                return;
            }
        }

        this.onPageEnter(page);
    },

    updateNav(page) {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
            item.removeAttribute('aria-current');
        });
        document.querySelectorAll('.nav-indicator').forEach(indicator => {
            indicator.style.opacity = '0';
        });
        const activeNav = document.querySelector(`.nav-item[data-page="${page}"]`);
        if (activeNav) {
            activeNav.classList.add('active');
            activeNav.setAttribute('aria-current', 'page');
        }

        // Animate indicator
        this.moveIndicator(activeNav);
    },

    moveIndicator(activeItem) {
        const indicator = activeItem && activeItem.parentElement
            ? activeItem.parentElement.querySelector('.nav-indicator')
            : null;
        if (!indicator || !activeItem) {
            return;
        }

        const menu = activeItem.parentElement;
        const menuRect = menu.getBoundingClientRect();
        const itemRect = activeItem.getBoundingClientRect();

        indicator.style.opacity = '1';
        indicator.style.width = itemRect.width + 'px';
        indicator.style.left = (itemRect.left - menuRect.left) + 'px';
    },

    _isPageScriptReady(page) {
        const check = this.pageReadyChecks[page];
        return !check || check();
    },

    _loadScriptOnce(src, markerName, markerValue) {
        if (!src) return Promise.resolve();
        const key = markerName + ':' + src;
        if (this._pageScriptPromises[key]) return this._pageScriptPromises[key];

        this._pageScriptPromises[key] = new Promise((resolve, reject) => {
            const plainSrc = src.split('?')[0];
            const existing = Array.from(document.scripts).find(script => {
                const current = script.getAttribute('src') || '';
                return current === src || current.split('?')[0] === plainSrc;
            });

            if (existing && !existing.dataset[markerName]) {
                resolve();
                return;
            }

            const script = existing || document.createElement('script');
            if (!existing) {
                script.src = src;
                script.async = true;
                script.dataset[markerName] = markerValue || 'true';
                document.body.appendChild(script);
            }

            script.addEventListener('load', () => resolve(), { once: true });
            script.addEventListener('error', () => {
                delete this._pageScriptPromises[key];
                reject(new Error(`Failed to load script: ${src}`));
            }, { once: true });
        });

        return this._pageScriptPromises[key];
    },

    _loadPageScript(page) {
        const src = this.pageScripts[page];
        if (!src || this._isPageScriptReady(page)) return Promise.resolve();
        if (this._pageScriptPromises[src]) return this._pageScriptPromises[src];

        this._pageScriptPromises[src] = new Promise((resolve, reject) => {
            const plainSrc = src.split('?')[0];
            const existing = Array.from(document.scripts).find(script => {
                const current = script.getAttribute('src') || '';
                return current === src || current.split('?')[0] === plainSrc;
            });

            if (existing && !existing.dataset.routerPageScript) {
                resolve();
                return;
            }

            const script = existing || document.createElement('script');
            if (!existing) {
                script.src = src;
                script.async = true;
                script.dataset.routerPageScript = page;
                document.body.appendChild(script);
            }

            script.addEventListener('load', () => resolve(), { once: true });
            script.addEventListener('error', () => {
                delete this._pageScriptPromises[src];
                reject(new Error(`Failed to load page script: ${src}`));
            }, { once: true });
        });

        return this._pageScriptPromises[src];
    },

    _needsCourseSupport(page) {
        return this.coursePages.includes(page) && typeof ModuleSelector === 'undefined';
    },

    _loadCourseSupport(page) {
        if (!this.coursePages.includes(page)) return Promise.resolve();
        return this.courseSupportScripts.reduce(
            (chain, src) => chain.then(() => this._loadScriptOnce(src, 'routerSupportScript', page)),
            Promise.resolve()
        ).then(() => {
            if (typeof ModuleSelector !== 'undefined' && !ModuleSelector.__routerSupportBooted) {
                ModuleSelector.__routerSupportBooted = true;
                ModuleSelector.__bootedAfterMinimalStart = true;
                ModuleSelector.init();
            }
            if (typeof lucide !== 'undefined') {
                try { lucide.createIcons(); } catch (e) {}
            }
        });
    },

    _ensurePageScript(page) {
        const pageScriptReady = this._isPageScriptReady(page);
        const needsCourseSupport = this._needsCourseSupport(page);
        if (pageScriptReady && !needsCourseSupport) {
            if (this.coursePages.includes(page)) this._loadCourseSupport(page);
            return true;
        }
        try {
            if (new URLSearchParams(location.search).get('noPageScript') === '1') return true;
        } catch (e) {}
        setTimeout(() => {
            this._loadCourseSupport(page)
                .then(() => this._loadPageScript(page))
                .then(() => {
                    if (this.currentPage === page && this._isActivePage(page)) {
                        this.onPageEnter(page);
                    }
                })
                .catch(error => {
                    console.warn('[Router] page script load failed:', page, error);
                });
        }, 120);
        return false;
    },

    onPageEnter(page) {
        if (!this._ensurePageScript(page)) {
            this._pageEnterComplete = true;
            this._flushQueuedNavigation();
            return;
        }

        // v6.1.0-alpha6 修复：home / planets 是「单屏锁定式」展示页，若沿用前一页的 scrollTop，
        // 加上 home-scroll-locked 后 body 高度被钉死在 100vh，旧滚动偏移会让首页卡在下方留黑框。
        // 用双阶段重置：同步置 0 + rAF 再置 0（覆盖 GSAP 转场结束后浏览器恢复滚动的边缘场景）。
        if (page === 'home' || page === 'planets') {
            const resetScroll = () => {
                try {
                    window.scrollTo(0, 0);
                    document.documentElement.scrollTop = 0;
                    document.body.scrollTop = 0;
                } catch (e) { /* noop */ }
            };
            resetScroll();
            requestAnimationFrame(resetScroll);
        }
        document.body.classList.toggle('home-scroll-locked', page === 'home');

        // v5.0：移除亮色主题，全站固定 dark
        document.documentElement.setAttribute('data-theme', 'dark');

        // v5.0：FAB 仅在学科课程页显示，首页/多星系大屏等展示页面不显示
        const isCoursePage = ['mathematics', 'physics', 'chemistry', 'algorithms', 'biology'].includes(page);
        if (typeof BackToTop !== 'undefined') {
            if (isCoursePage) BackToTop.show(); else BackToTop.hide();
        }
        if (typeof FabTrigger !== 'undefined') {
            if (isCoursePage) FabTrigger.show(); else FabTrigger.hide();
        }

        // === Page Initialization ===
        // Home page initializes directly; subject pages rely on ModuleSelector
        // for lazy per-experiment initialization (triggered when user opens an experiment).
        if (page === 'home') {
            if (typeof initHome === 'function') initHome();
        } else if (page === 'planets') {
            if (typeof initPlanets === 'function') initPlanets();
        } else if (page === 'cosmos') {
            if (typeof initCosmosSeasons === 'function') initCosmosSeasons();
        } else if (page === 'datascience') {
            if (typeof initLinearRegressionLab === 'function') initLinearRegressionLab();
        } else if (page === 'infotech') {
            if (typeof initNetworkLayersLab === 'function') initNetworkLayersLab();
        } else if (page === 'materials') {
            if (typeof initMaterialsLab === 'function') initMaterialsLab();
        } else if (page === 'humanities') {
            if (typeof initHumanitiesLab === 'function') initHumanitiesLab();
        } else if (page === 'engineering') {
            if (typeof initBridgeTruss === 'function') initBridgeTruss();
        } else if (page === 'license') {
            if (typeof initLicense === 'function') initLicense();
        } else if (page === 'changelog') {
            if (typeof initChangelog === 'function') initChangelog();
        }
        // Subject pages: show sidebar toggle if an experiment was previously open,
        // but don't eagerly initialize any experiments (ModuleSelector handles it).

        // Refresh ScrollTrigger on content pages
        if (typeof ScrollTrigger !== 'undefined') {
            ScrollTrigger.refresh();
        }

        // Trigger scroll animations for the new page
        if (page !== 'home' && page !== 'planets' && typeof initPageScrollAnimations === 'function') {
            initPageScrollAnimations(page);
        }

        // Initialize hero canvas if present

        // Initialize hero canvas (also serves as fallback for non-animated path).
        // canvas.dataset.initialized prevents double-init on the animated path.
        if (page !== 'home' && page !== 'planets' && typeof initHeroVisual === 'function') {
            initHeroVisual(page);
        }

        // 深链接：URL 形如 #physics/momentum-conservation 时，自动打开对应实验
        this._applyPendingModule(page);
        this._applyPendingAnchor();
        this._pageEnterComplete = true;
        this._flushQueuedNavigation();
    },

    /**
     * 若 _pendingModule 与当前 page（课程页）匹配，则尝试调用 ModuleSelector.openModule。
     * 等待 ModuleSelector 渲染好侧栏后再调用，以处理首屏即直达的场景。
     */
    _applyPendingModule(page) {
        const moduleId = this._pendingModule;
        if (!moduleId) return;
        const isCoursePage = ['mathematics', 'physics', 'chemistry', 'algorithms', 'biology'].includes(page);
        if (!isCoursePage) { this._pendingModule = null; return; }
        const tryOpen = (retries) => {
            if (typeof ModuleSelector !== 'undefined' && typeof ModuleSelector.openModule === 'function') {
                try { ModuleSelector.openModule(page, moduleId); } catch (e) {}
                this._pendingModule = null;
                return;
            }
            if (retries > 0) setTimeout(() => tryOpen(retries - 1), 60);
        };
        // 等一个 microtask + 一次 60ms 重试，覆盖 ModuleSelector 尚未初始化的边缘场景
        setTimeout(() => tryOpen(5), 0);
    },

    _applyPendingAnchor() {
        const anchorId = this._pendingAnchor;
        if (!anchorId) return;
        const target = document.getElementById(anchorId);
        if (!target) return;
        const context = target.previousElementSibling && target.previousElementSibling.classList.contains('frontier-section-context')
            ? target.previousElementSibling
            : null;
        const scrollTarget = context || target;
        this._lastAppliedAnchor = anchorId;
        this._pendingAnchor = null;
        setTimeout(() => {
            try {
                const offset = 88;
                const rootStyle = document.documentElement.style;
                const bodyStyle = document.body.style;
                const previousRootBehavior = rootStyle.scrollBehavior;
                const previousBodyBehavior = bodyStyle.scrollBehavior;
                const align = () => {
                    const top = Math.max(0, scrollTarget.getBoundingClientRect().top + window.pageYOffset - offset);
                    const scroller = document.scrollingElement || document.documentElement;
                    rootStyle.scrollBehavior = 'auto';
                    bodyStyle.scrollBehavior = 'auto';
                    window.scrollTo(0, top);
                    if (scroller) scroller.scrollTop = top;
                    document.documentElement.scrollTop = top;
                    document.body.scrollTop = top;
                };
                requestAnimationFrame(align);
                setTimeout(align, 80);
                setTimeout(align, 220);
                setTimeout(() => {
                    rootStyle.scrollBehavior = previousRootBehavior;
                    bodyStyle.scrollBehavior = previousBodyBehavior;
                }, 260);
                target.setAttribute('tabindex', '-1');
                target.focus({ preventScroll: true });
            } catch (e) { /* noop */ }
        }, 0);
    },

    onPageLeave(page) {
        if (page === 'home') {
            document.body.classList.remove('home-scroll-locked');
        }

        if (page !== 'home' && page !== 'planets' && typeof destroyHeroVisual === 'function') {
            try { destroyHeroVisual(page); } catch (e) { /* ignore */ }
        }

        if (this._galaxyForPage(page) === 'frontier'
            && typeof FrontierLearning !== 'undefined'
            && typeof FrontierLearning.destroy === 'function') {
            try { FrontierLearning.destroy(page); } catch (e) { /* ignore */ }
        }

        if (page === 'home') {
            if (typeof ParticleNetwork !== 'undefined' && ParticleNetwork.destroy) ParticleNetwork.destroy();
            if (typeof SatelliteSystem !== 'undefined') SatelliteSystem.isRunning = false;
        } else if (page === 'planets') {
            if (typeof destroyPlanets === 'function') destroyPlanets();
        } else if (page === 'cosmos') {
            if (typeof destroyCosmosSeasons === 'function') destroyCosmosSeasons();
        } else if (page === 'datascience') {
            if (typeof destroyLinearRegressionLab === 'function') destroyLinearRegressionLab();
        } else if (page === 'infotech') {
            if (typeof destroyNetworkLayersLab === 'function') destroyNetworkLayersLab();
        } else if (page === 'materials') {
            if (typeof destroyMaterialsLab === 'function') destroyMaterialsLab();
        } else if (page === 'humanities') {
            if (typeof destroyHumanitiesLab === 'function') destroyHumanitiesLab();
        } else if (page === 'engineering') {
            if (typeof destroyBridgeTruss === 'function') destroyBridgeTruss();
        } else {
            // v4.2.3 Bug3 修复：先调用 closeModule 隐藏全部浮动控件
            // （ExperimentExport / ExperimentQuiz / ExperimentFavorites / ExperimentRating /
            //   ExperimentGuide），避免离开学科页面后控件仍残留在首页/星系大屏。
            if (typeof ModuleSelector !== 'undefined' && ModuleSelector.activeModule
                && ModuleSelector.activeModule[page]
                && typeof ModuleSelector.closeModule === 'function') {
                try { ModuleSelector.closeModule(page); } catch (e) { /* ignore */ }
            }
            // 兜底：即便 ModuleSelector 未记录 active module，也强制隐藏全部浮动控件
            try {
                const guide = window.ExperimentGuide || (typeof ExperimentGuide !== 'undefined' ? ExperimentGuide : null);
                if (guide) guide.hideHelpButton();
            } catch(e){}
            try { if (window.ExperimentExport) ExperimentExport.hide(); } catch(e){}
            try { if (window.ExperimentQuiz) ExperimentQuiz.hide(); } catch(e){}
            try { if (window.ExperimentFavorites) ExperimentFavorites.hide(); } catch(e){}
            try { if (window.ExperimentRating) ExperimentRating.hide(); } catch(e){}

            // Destroy all modules that were initialized for this page
            const destroyMap = {
                mathematics: [
                    () => { if (typeof destroyFunctionGraph === 'function') destroyFunctionGraph(); },
                    () => { if (typeof Calculus !== 'undefined' && Calculus.destroy) Calculus.destroy(); },
                    () => { if (typeof GeoTransform !== 'undefined' && GeoTransform.destroy) GeoTransform.destroy(); },
                    () => { if (typeof ComplexVis !== 'undefined' && ComplexVis.destroy) ComplexVis.destroy(); },
                    () => { if (typeof TrigVis !== 'undefined' && TrigVis.destroy) TrigVis.destroy(); },
                    () => { if (typeof SetOps !== 'undefined' && SetOps.destroy) SetOps.destroy(); },
                    () => { if (typeof Probability !== 'undefined' && Probability.destroy) Probability.destroy(); },
                    () => { if (typeof VectorOps !== 'undefined' && VectorOps.destroy) VectorOps.destroy(); },
                    () => { if (typeof Inequality !== 'undefined' && Inequality.destroy) Inequality.destroy(); },
                    () => { if (typeof ConicSections !== 'undefined' && ConicSections.destroy) ConicSections.destroy(); },
                    () => { if (typeof SolidGeom !== 'undefined' && SolidGeom.destroy) SolidGeom.destroy(); },
                    () => { if (typeof PermComb !== 'undefined' && PermComb.destroy) PermComb.destroy(); },
                    () => { if (typeof Sequences !== 'undefined' && Sequences.destroy) Sequences.destroy(); },
                    () => { if (typeof FuncProps !== 'undefined' && FuncProps.destroy) FuncProps.destroy(); },
                    () => { if (typeof ExpLog !== 'undefined' && ExpLog.destroy) ExpLog.destroy(); },
                    () => { if (typeof Binomial !== 'undefined' && Binomial.destroy) Binomial.destroy(); },
                    () => { if (typeof StatReg !== 'undefined' && StatReg.destroy) StatReg.destroy(); },
                    () => { if (typeof SpatialVec !== 'undefined' && SpatialVec.destroy) SpatialVec.destroy(); },
                    () => { if (typeof DerivApp !== 'undefined' && DerivApp.destroy) DerivApp.destroy(); },
                ],
                physics: [
                    () => { if (typeof destroyPhysics === 'function') destroyPhysics(); },
                    () => { if (typeof EMField !== 'undefined' && EMField.destroy) EMField.destroy(); },
                    () => { if (typeof WaveDemo !== 'undefined' && WaveDemo.destroy) WaveDemo.destroy(); },
                    () => { if (typeof RelativityDemo !== 'undefined' && RelativityDemo.destroy) RelativityDemo.destroy(); },
                    () => { if (typeof FluidSim !== 'undefined' && FluidSim.destroy) FluidSim.destroy(); },
                    () => { if (typeof OpticsLab !== 'undefined' && OpticsLab.destroy) OpticsLab.destroy(); },
                    () => { if (typeof Kinematics !== 'undefined' && Kinematics.destroy) Kinematics.destroy(); },
                    () => { if (typeof Projectile !== 'undefined' && Projectile.destroy) Projectile.destroy(); },
                    () => { if (typeof CircularMotion !== 'undefined' && CircularMotion.destroy) CircularMotion.destroy(); },
                    () => { if (typeof EnergyConservation !== 'undefined' && EnergyConservation.destroy) EnergyConservation.destroy(); },
                    () => { if (typeof CircuitAnalysis !== 'undefined' && CircuitAnalysis.destroy) CircuitAnalysis.destroy(); },
                    () => { if (typeof EMInduction !== 'undefined' && EMInduction.destroy) EMInduction.destroy(); },
                    () => { if (typeof ACCircuit !== 'undefined' && ACCircuit.destroy) ACCircuit.destroy(); },
                    () => { if (typeof Gravitation !== 'undefined' && Gravitation.destroy) Gravitation.destroy(); },
                    () => { if (typeof ForceComposition !== 'undefined' && ForceComposition.destroy) ForceComposition.destroy(); },
                    () => { if (typeof MomentumConservation !== 'undefined' && MomentumConservation.destroy) MomentumConservation.destroy(); },
                    () => { if (typeof ChargedParticle !== 'undefined' && ChargedParticle.destroy) ChargedParticle.destroy(); },
                ],
                chemistry: [
                    () => { if (typeof PeriodicTable !== 'undefined' && PeriodicTable.destroy) PeriodicTable.destroy(); },
                    () => { if (typeof MoleculeVis !== 'undefined' && MoleculeVis.destroy) MoleculeVis.destroy(); },
                    () => { if (typeof ChemReaction !== 'undefined' && ChemReaction.destroy) ChemReaction.destroy(); },
                    () => { if (typeof ChemEquilibrium !== 'undefined' && ChemEquilibrium.destroy) ChemEquilibrium.destroy(); },
                    () => { if (typeof Electrochemistry !== 'undefined' && Electrochemistry.destroy) Electrochemistry.destroy(); },
                    () => { if (typeof ChemBond !== 'undefined' && ChemBond.destroy) ChemBond.destroy(); },
                    () => { if (typeof OrganicChem !== 'undefined' && OrganicChem.destroy) OrganicChem.destroy(); },
                    () => { if (typeof ReactionRate !== 'undefined' && ReactionRate.destroy) ReactionRate.destroy(); },
                    () => { if (typeof SolutionIon !== 'undefined' && SolutionIon.destroy) SolutionIon.destroy(); },
                    () => { if (typeof IonicReaction !== 'undefined' && IonicReaction.destroy) IonicReaction.destroy(); },
                    () => { if (typeof Redox !== 'undefined' && Redox.destroy) Redox.destroy(); },
                    () => { if (typeof AtomicStructure !== 'undefined' && AtomicStructure.destroy) AtomicStructure.destroy(); },
                    () => { if (typeof ElementCompounds !== 'undefined' && ElementCompounds.destroy) ElementCompounds.destroy(); },
                    () => { if (typeof Intermolecular !== 'undefined' && Intermolecular.destroy) Intermolecular.destroy(); },
                ],
                algorithms: [
                    () => { if (typeof SearchComparison !== 'undefined' && SearchComparison.destroy) SearchComparison.destroy(); },
                    () => { if (typeof TreeTraversal !== 'undefined' && TreeTraversal.destroy) TreeTraversal.destroy(); },
                    () => { if (typeof HashSearch !== 'undefined' && HashSearch.destroy) HashSearch.destroy(); },
                    () => { if (typeof GraphAlgo !== 'undefined' && GraphAlgo.destroy) GraphAlgo.destroy(); },
                    () => { if (typeof DataStructVis !== 'undefined' && DataStructVis.destroy) DataStructVis.destroy(); },
                    () => { if (typeof SortCompare !== 'undefined' && SortCompare.destroy) SortCompare.destroy(); },
                    () => { if (typeof RecursionVis !== 'undefined' && RecursionVis.destroy) RecursionVis.destroy(); },
                    () => { if (typeof DPVis !== 'undefined' && DPVis.destroy) DPVis.destroy(); },
                    () => { if (typeof StringMatch !== 'undefined' && StringMatch.destroy) StringMatch.destroy(); },
                ],
                biology: [
                    () => { if (typeof Biology !== 'undefined' && Biology.destroy) Biology.destroy(); },
                    () => { if (typeof Mitosis !== 'undefined' && Mitosis.destroy) Mitosis.destroy(); },
                    () => { if (typeof NeuralReg !== 'undefined' && NeuralReg.destroy) NeuralReg.destroy(); },
                    () => { if (typeof ImmuneSystem !== 'undefined' && ImmuneSystem.destroy) ImmuneSystem.destroy(); },
                    () => { if (typeof Ecosystem !== 'undefined' && Ecosystem.destroy) Ecosystem.destroy(); },
                    () => { if (typeof Meiosis !== 'undefined' && Meiosis.destroy) Meiosis.destroy(); },
                    () => { if (typeof GeneExpression !== 'undefined' && GeneExpression.destroy) GeneExpression.destroy(); },
                    () => { if (typeof CellularResp !== 'undefined' && CellularResp.destroy) CellularResp.destroy(); },
                    () => { if (typeof SubstanceTransport !== 'undefined' && SubstanceTransport.destroy) SubstanceTransport.destroy(); },
                    () => { if (typeof GeneMutation !== 'undefined' && GeneMutation.destroy) GeneMutation.destroy(); },
                ]
            };

            const fns = destroyMap[page];
            if (fns) fns.forEach(fn => { try { fn(); } catch(e) { /* ignore */ } });

            // Reset ModuleSelector state for this page
            if (typeof ModuleSelector !== 'undefined' && ModuleSelector.resetPage) {
                ModuleSelector.resetPage(page);
            }
        }
    },

    // ── Running Time Footer ──
    _toggleRunningTime(show) {
        const el = document.getElementById('running-time-footer');
        if (!el) return;
        if (show) {
            el.classList.add('visible');
            if (!this._runningTimeId) {
                const START = new Date('2026-04-14T00:00:00').getTime();
                const dEl = document.getElementById('rt-days');
                const hEl = document.getElementById('rt-hours');
                const mEl = document.getElementById('rt-minutes');
                const sEl = document.getElementById('rt-seconds');
                const tick = () => {
                    const diff = Math.max(0, Date.now() - START);
                    const d = Math.floor(diff / 86400000);
                    const h = Math.floor((diff % 86400000) / 3600000);
                    const m = Math.floor((diff % 3600000) / 60000);
                    const s = Math.floor((diff % 60000) / 1000);
                    if (dEl) dEl.textContent = d;
                    if (hEl) hEl.textContent = h;
                    if (mEl) mEl.textContent = m;
                    if (sEl) sEl.textContent = s;
                };
                tick();
                this._runningTimeId = setInterval(tick, 1000);
            }
        } else {
            el.classList.remove('visible');
            if (this._runningTimeId) {
                clearInterval(this._runningTimeId);
                this._runningTimeId = null;
            }
        }
    },

    _isFrontierPage(page) {
        return this.frontierPages.includes(page);
    },

    _isActivePage(page) {
        const active = document.querySelector('.page.active');
        return !!active && active.id === `page-${page}`;
    },

    _usesEnglabFooter(page) {
        return page !== 'home' && page !== 'planets' && !this._isFrontierPage(page);
    },

    _toggleGalaxyFooters(page) {
        const englabFooter = document.getElementById('site-footer');
        const frontierFooter = document.getElementById('frontier-footer');
        const showFrontier = this._isFrontierPage(page);
        const showEnglab = this._usesEnglabFooter(page);

        if (englabFooter) englabFooter.style.display = showEnglab ? '' : 'none';
        if (frontierFooter) {
            frontierFooter.hidden = !showFrontier;
            frontierFooter.classList.toggle('is-visible', showFrontier);
        }
    }
};

// Global navigate function (backward compatible)
function navigate(page) {
    Router.navigateTo(page, true);
}

window.navigate = navigate;
window.Router = Router;
