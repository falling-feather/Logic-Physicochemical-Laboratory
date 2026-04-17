// ===== Router: GSAP Page Transitions =====
const Router = {
    overlay: null,
    currentPage: 'home',
    isTransitioning: false,
    _initialEnterFired: false,
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
                    if (page === this.currentPage && document.querySelector('.page.active')) {
                        if (page !== 'home' && typeof ModuleSelector !== 'undefined' && ModuleSelector.activeModule[page]) {
                            ModuleSelector.closeModule(page);
                        }
                        window.scrollTo({ top: 0, behavior: 'smooth' });
                        return;
                    }
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
        const initialPage = window.location.hash.slice(1) || 'home';
        this.currentPage = initialPage;

        // Ensure the correct page has 'active' class (HTML defaults to home)
        if (initialPage !== 'home') {
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
        this.onPageEnter(initialPage);

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
        this.isTransitioning = true; // Set immediately to prevent race conditions

        const currentEl = document.querySelector('.page.active');
        const targetEl = document.getElementById(`page-${page}`);
        if (!targetEl) { this.isTransitioning = false; return; }

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

        // Cleanup previous page modules
        this.onPageLeave(prevPage);

        // Respect prefers-reduced-motion
        const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        if (!animate || !currentEl || typeof gsap === 'undefined' || prefersReduced) {
            // No animation (initial load, no GSAP, or reduced motion)
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            targetEl.classList.add('active');
            window.scrollTo({ top: 0 });
            this.isTransitioning = false;
            this.onPageEnter(page);
            return;
        }

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
            // Pre-hide hero children so they never flash visible during the page fade-in.
            // animatePageContent will animate them in individually afterwards.
            if (page !== 'home') {
                const heroKids = targetEl.querySelectorAll(
                    '.page-hero__eyebrow, .page-hero__title, .page-hero__desc, .page-hero__actions, .page-hero__visual'
                );
                if (heroKids.length) gsap.set(heroKids, { y: 15, opacity: 0 });
            }
            // Start hero canvas rendering immediately in the background.
            // The canvas is invisible (opacity 0) but already drawing, so when
            // it fades in with the hero animation there is no blank-canvas flash.
            if (page !== 'home' && typeof initHeroVisual === 'function') {
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
        const activeNav = document.querySelector(`.nav-item[data-page="${page}"]`);
        if (activeNav) {
            activeNav.classList.add('active');
            activeNav.setAttribute('aria-current', 'page');
        }

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
        document.body.classList.toggle('home-scroll-locked', page === 'home');

        // === Page Initialization ===
        // Home page initializes directly; subject pages rely on ModuleSelector
        // for lazy per-experiment initialization (triggered when user opens an experiment).
        if (page === 'home') {
            if (typeof initHome === 'function') initHome();
        }
        // Subject pages: show sidebar toggle if an experiment was previously open,
        // but don't eagerly initialize any experiments (ModuleSelector handles it).

        // Refresh ScrollTrigger on content pages
        if (typeof ScrollTrigger !== 'undefined') {
            ScrollTrigger.refresh();
        }

        // Trigger scroll animations for the new page
        if (page !== 'home' && typeof initPageScrollAnimations === 'function') {
            initPageScrollAnimations(page);
        }

        // Initialize hero canvas if present

        // Initialize hero canvas (also serves as fallback for non-animated path).
        // canvas.dataset.initialized prevents double-init on the animated path.
        if (page !== 'home' && typeof initHeroVisual === 'function') {
            initHeroVisual(page);
        }
    },

    onPageLeave(page) {
        if (page === 'home') {
            document.body.classList.remove('home-scroll-locked');
        }

        if (page === 'home') {
            if (typeof ParticleNetwork !== 'undefined' && ParticleNetwork.destroy) ParticleNetwork.destroy();
            if (typeof SatelliteSystem !== 'undefined') SatelliteSystem.isRunning = false;
        } else {
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
    }
};

// Global navigate function (backward compatible)
function navigate(page) {
    Router.navigateTo(page, true);
}

window.navigate = navigate;
window.Router = Router;
