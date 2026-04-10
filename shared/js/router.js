// ===== Router: GSAP Page Transitions =====
const Router = {
    overlay: null,
    currentPage: 'home',
    isTransitioning: false,
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

        // Initial state
        this.handleHash();
        window.addEventListener('hashchange', () => this.handleHash());

        // Handle popstate (back/forward)
        window.addEventListener('popstate', () => this.handleHash());
    },

    handleHash() {
        const page = window.location.hash.slice(1) || 'home';
        if (page === this.currentPage && document.querySelector('.page.active')) return;
        this.navigateTo(page, false);
    },

    navigateTo(page, animate = true) {
        if (this.isTransitioning) return;
        if (page === this.currentPage && document.querySelector('.page.active')) return;

        const currentEl = document.querySelector('.page.active');
        const targetEl = document.getElementById(`page-${page}`);
        if (!targetEl) return;

        // Update hash without triggering hashchange
        if (window.location.hash.slice(1) !== page) {
            history.pushState(null, '', `#${page}`);
        }

        // Update nav
        this.updateNav(page);

        // Update navbar transparency
        const navbar = document.getElementById('navbar');
        if (navbar) {
            if (page === 'home') {
                navbar.classList.add('navbar--transparent');
            } else {
                navbar.classList.remove('navbar--transparent');
            }
        }

        const prevPage = this.currentPage;
        this.currentPage = page;

        // Respect prefers-reduced-motion
        const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        if (!animate || !currentEl || typeof gsap === 'undefined' || prefersReduced) {
            // No animation (initial load, no GSAP, or reduced motion)
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            targetEl.classList.add('active');
            window.scrollTo({ top: 0 });
            this.onPageEnter(page);
            return;
        }

        this.isTransitioning = true;

        // Determine accent color for overlay
        const colors = {
            mathematics: 'rgba(91,141,206,0.12)',
            physics: 'rgba(139,111,192,0.12)',
            chemistry: 'rgba(77,158,126,0.12)',
            algorithms: 'rgba(196,121,58,0.12)',
            biology: 'rgba(58,158,143,0.12)',
            home: 'rgba(91,141,206,0.08)'
        };
        this.overlay.style.background = `linear-gradient(135deg, ${colors[page] || colors.home}, var(--surface-0))`;

        const ox = this.transitionOrigin.x;
        const oy = this.transitionOrigin.y;

        const tl = gsap.timeline({
            onComplete: () => {
                this.isTransitioning = false;
                // Reset origin to center for next transition
                this.transitionOrigin = { x: 50, y: 50 };
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

    // Staggered entry for page sub-elements
    animatePageContent(page, pageEl) {
        if (typeof gsap === 'undefined') {
            this.onPageEnter(page);
            return;
        }

        if (page === 'home') {
            this.onPageEnter(page);
            return;
        }

        // Animate hero elements with stagger
        const hero = pageEl.querySelector('.page-hero');
        if (hero) {
            const heroChildren = hero.querySelectorAll('.page-hero__eyebrow, .page-hero__title, .page-hero__desc, .page-hero__actions, .page-hero__visual');
            if (heroChildren.length) {
                gsap.fromTo(heroChildren,
                    { y: 15, opacity: 0 },
                    {
                        y: 0, opacity: 1,
                        duration: 0.3,
                        ease: 'power3.out',
                        stagger: 0.05,
                        onComplete: () => this.onPageEnter(page)
                    }
                );
                return;
            }
        }

        this.onPageEnter(page);
    },

    updateNav(page) {
        document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
        const activeNav = document.querySelector(`.nav-item[data-page="${page}"]`);
        if (activeNav) activeNav.classList.add('active');

        // Animate indicator
        this.moveIndicator(activeNav);
    },

    moveIndicator(activeItem) {
        const indicator = document.querySelector('.nav-indicator');
        if (!indicator || !activeItem) {
            if (indicator) indicator.style.opacity = '0';
            return;
        }

        const menu = activeItem.parentElement;
        const menuRect = menu.getBoundingClientRect();
        const itemRect = activeItem.getBoundingClientRect();

        indicator.style.opacity = '1';
        indicator.style.width = itemRect.width + 'px';
        indicator.style.left = (itemRect.left - menuRect.left) + 'px';
    },

    onPageEnter(page) {
        // Refresh ScrollTrigger on content pages
        if (typeof ScrollTrigger !== 'undefined') {
            ScrollTrigger.refresh();
        }

        // Trigger scroll animations for the new page
        if (page !== 'home' && typeof initPageScrollAnimations === 'function') {
            initPageScrollAnimations(page);
        }

        // Initialize hero canvas if present
        if (typeof initHeroVisual === 'function') {
            initHeroVisual(page);
        }
    }
};

// Global navigate function (backward compatible)
function navigate(page) {
    Router.navigateTo(page, true);
}

window.navigate = navigate;
window.Router = Router;
