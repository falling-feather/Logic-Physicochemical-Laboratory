// ===== Router: GSAP Page Transitions =====
const Router = {
    overlay: null,
    currentPage: 'home',
    isTransitioning: false,
    _initialEnterFired: false,
    _runningTimeId: null,
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

        // Show running time footer for non-home pages
        this._toggleRunningTime(initialPage !== 'home' && initialPage !== 'planets');

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

        // Update navbar visibility/transparency
        // v4.3：home 透明化；v4.4：planets 大屏完全隐藏顶栏（作为目录承载更沉浸）
        const navbar = document.getElementById('navbar');
        if (navbar) {
            navbar.classList.toggle('navbar--transparent', page === 'home');
            navbar.classList.toggle('navbar--hidden', page === 'planets');
        }

        // Toggle running time footer
        this._toggleRunningTime(page !== 'home' && page !== 'planets');

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
            home: 'rgba(91,141,206,0.08)',
            planets: 'rgba(0,255,213,0.10)'
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
            if (page !== 'home' && page !== 'planets') {
                const heroKids = targetEl.querySelectorAll(
                    '.page-hero__eyebrow, .page-hero__title, .page-hero__desc, .page-hero__actions, .page-hero__visual'
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

        // v4.2.45：主题切换不再受路由强制干预；主页内容区由 CSS 锁定 dark token，
        // 仅顶栏（navbar）会响应主题切换；其它页面照常完整响应主题。
        const stored = localStorage.getItem('englab-theme');
        document.documentElement.setAttribute('data-theme', stored === 'light' ? 'light' : 'dark');

        // v4.2.4：非首页统一显示右下角主题切换 FAB；返回首页则隐藏
        if (typeof ThemeSwitch !== 'undefined') {
            if (page === 'home') ThemeSwitch.hide();
            else ThemeSwitch.show();
        }
        // v4.2.17：非首页显示返回顶部 FAB
        if (typeof BackToTop !== 'undefined') {
            if (page === 'home') BackToTop.hide();
            else BackToTop.show();
        }
        // v4.2.19：非首页显示 FAB 折叠主控按钮（默认折叠）
        if (typeof FabTrigger !== 'undefined') {
            if (page === 'home') FabTrigger.hide();
            else FabTrigger.show();
        }

        // === Page Initialization ===
        // Home page initializes directly; subject pages rely on ModuleSelector
        // for lazy per-experiment initialization (triggered when user opens an experiment).
        if (page === 'home') {
            if (typeof initHome === 'function') initHome();
        } else if (page === 'planets') {
            if (typeof initPlanets === 'function') initPlanets();
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
    },

    onPageLeave(page) {
        if (page === 'home') {
            document.body.classList.remove('home-scroll-locked');
        }

        if (page === 'home') {
            if (typeof ParticleNetwork !== 'undefined' && ParticleNetwork.destroy) ParticleNetwork.destroy();
            if (typeof SatelliteSystem !== 'undefined') SatelliteSystem.isRunning = false;
        } else if (page === 'planets') {
            if (typeof destroyPlanets === 'function') destroyPlanets();
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
            try { if (window.ExperimentGuide) ExperimentGuide.hideHelpButton(); } catch(e){}
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
    }
};

// Global navigate function (backward compatible)
function navigate(page) {
    Router.navigateTo(page, true);
}

window.navigate = navigate;
window.Router = Router;
