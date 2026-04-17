// ===== Module Selector (Sidebar Navigation + Lazy Init) =====
// Provides sidebar navigation for experiments within each subject page.
// Experiments are only initialized when opened (fixing canvas-in-hidden-container issues).

const ModuleSelector = {
    activeModule: {},   // { pageName: 'module-id' | null }
    _initialized: {},   // { 'module-id': true } — tracks which modules have been initialized
    _sidebars: {},      // { pageName: sidebar DOM element }
    _sidebarOpen: {},   // { pageName: bool }

    init() {
        const pages = ['mathematics', 'physics', 'chemistry', 'algorithms', 'biology'];
        pages.forEach(page => {
            const pageEl = document.getElementById(`page-${page}`);
            if (!pageEl) return;

            pageEl.classList.add(`page-${page}`);
            this.activeModule[page] = null;
            this._sidebarOpen[page] = false;

            this.createSidebar(page, pageEl);
            this.createGallery(page, pageEl);
        });

        // Create global backdrop for mobile
        const backdrop = document.createElement('div');
        backdrop.className = 'module-sidebar-backdrop';
        backdrop.id = 'module-sidebar-backdrop';
        backdrop.addEventListener('click', () => this._closeSidebarForCurrentPage());
        document.body.appendChild(backdrop);
    },

    createSidebar(page, pageEl) {
        const experiments = CONFIG.experiments[page];
        if (!experiments || experiments.length === 0) return;

        // Sidebar container
        const sidebar = document.createElement('nav');
        sidebar.className = 'module-sidebar';
        sidebar.id = `sidebar-${page}`;
        sidebar.setAttribute('aria-label', `${CONFIG.pages[page].label}实验导航`);

        // Header
        const header = document.createElement('div');
        header.className = 'module-sidebar__header';
        header.textContent = CONFIG.pages[page].label + ' 实验';
        sidebar.appendChild(header);

        // Back-to-gallery button
        const backItem = document.createElement('button');
        backItem.className = 'module-sidebar__item';
        backItem.innerHTML = `
            <span class="module-sidebar__item-icon"><i data-lucide="layout-grid"></i></span>
            <span class="module-sidebar__item-text">返回实验列表</span>
        `;
        backItem.addEventListener('click', () => this.closeModule(page));
        sidebar.appendChild(backItem);

        // Experiment items
        experiments.forEach((exp, idx) => {
            if (exp.variant === 'upcoming') return;

            const item = document.createElement('button');
            item.className = 'module-sidebar__item';
            item.dataset.moduleTarget = exp.id;
            item.setAttribute('aria-label', exp.title);

            item.innerHTML = `
                <span class="module-sidebar__item-icon"><i data-lucide="${exp.icon || 'box'}"></i></span>
                <span class="module-sidebar__item-text">${exp.title}</span>
                <span class="module-sidebar__item-badge">${String(idx + 1).padStart(2, '0')}</span>
            `;

            item.addEventListener('click', () => {
                this.openModule(page, exp.id);
            });
            sidebar.appendChild(item);
        });

        // Toggle button
        const toggle = document.createElement('button');
        toggle.className = 'module-sidebar-toggle';
        toggle.id = `sidebar-toggle-${page}`;
        toggle.setAttribute('aria-label', '切换实验导航');
        toggle.innerHTML = '<i data-lucide="panel-left"></i>';
        toggle.addEventListener('click', () => this.toggleSidebar(page));

        // Append sidebar & toggle to document.body so position:fixed works
        // (pageEl has will-change:transform which breaks fixed positioning)
        document.body.appendChild(sidebar);
        document.body.appendChild(toggle);
        this._sidebars[page] = sidebar;

        if (typeof lucide !== 'undefined') lucide.createIcons();
    },

    createGallery(page, pageEl) {
        const experiments = CONFIG.experiments[page];
        if (!experiments || experiments.length === 0) return;

        const hero = pageEl.querySelector('.page-hero');
        if (!hero) return;

        const gallery = document.createElement('div');
        gallery.className = 'module-gallery';
        gallery.id = `gallery-${page}`;

        experiments.forEach((exp, idx) => {
            if (exp.variant === 'upcoming') return;

            const card = document.createElement('div');
            card.className = 'module-card';
            card.dataset.moduleTarget = exp.id;
            card.setAttribute('role', 'button');
            card.setAttribute('tabindex', '0');
            card.setAttribute('aria-label', exp.title);

            card.innerHTML = `
                <div class="module-card__icon"><i data-lucide="${exp.icon || 'box'}"></i></div>
                <div class="module-card__title">${exp.title}</div>
                <div class="module-card__desc">${exp.description}</div>
                <div class="module-card__badge">${String(idx + 1).padStart(2, '0')}</div>
            `;

            card.addEventListener('click', () => this.openModule(page, exp.id));
            card.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.openModule(page, exp.id);
                }
            });
            gallery.appendChild(card);
        });

        hero.insertAdjacentElement('afterend', gallery);
        pageEl.classList.add('module-gallery-active');

        if (typeof lucide !== 'undefined') lucide.createIcons();
    },

    openModule(page, moduleId) {
        const pageEl = document.getElementById(`page-${page}`);
        if (!pageEl) return;

        // If same module, just close sidebar
        if (this.activeModule[page] === moduleId) {
            if (window.innerWidth <= 768) this._closeSidebar(page);
            return;
        }

        // Deactivate previous module
        const prevModule = this.activeModule[page];
        if (prevModule) {
            pageEl.querySelectorAll(`[data-module="${prevModule}"].module-active`).forEach(s => {
                s.classList.remove('module-active');
            });
        }

        // Hide gallery
        const gallery = document.getElementById(`gallery-${page}`);
        if (gallery) gallery.style.display = 'none';

        // Show target module sections
        const sections = pageEl.querySelectorAll(`[data-module="${moduleId}"]`);
        sections.forEach(s => s.classList.add('module-active'));

        // Update sidebar active state
        const sidebar = this._sidebars[page];
        if (sidebar) {
            sidebar.querySelectorAll('.module-sidebar__item').forEach(item => {
                item.classList.toggle('active', item.dataset.moduleTarget === moduleId);
            });
        }

        // Remove gallery-active state
        pageEl.classList.remove('module-gallery-active');

        // Show sidebar toggle button
        const toggle = document.getElementById(`sidebar-toggle-${page}`);
        if (toggle) toggle.style.display = 'flex';

        this.activeModule[page] = moduleId;

        // Lazy-initialize this specific module
        this._initModule(page, moduleId);

        // Scroll to top
        window.scrollTo({ top: 0, behavior: 'smooth' });

        // 默认关闭侧边栏，避免改变实验区域尺寸
        this._closeSidebar(page);

        // Trigger resize for canvas elements
        setTimeout(() => window.dispatchEvent(new Event('resize')), 150);
    },

    closeModule(page) {
        const pageEl = document.getElementById(`page-${page}`);
        if (!pageEl) return;

        // Hide all module sections
        pageEl.querySelectorAll('[data-module].module-active').forEach(s => {
            s.classList.remove('module-active');
        });

        // Show gallery
        const gallery = document.getElementById(`gallery-${page}`);
        if (gallery) gallery.style.display = '';

        // Restore gallery-active state
        pageEl.classList.add('module-gallery-active');

        // Hide sidebar and toggle
        this._closeSidebar(page);
        const toggle = document.getElementById(`sidebar-toggle-${page}`);
        if (toggle) toggle.style.display = 'none';

        this.activeModule[page] = null;

        // Clear sidebar active states
        const sidebar = this._sidebars[page];
        if (sidebar) {
            sidebar.querySelectorAll('.module-sidebar__item.active').forEach(i => i.classList.remove('active'));
        }

        window.scrollTo({ top: 0, behavior: 'smooth' });
    },

    toggleSidebar(page) {
        if (this._sidebarOpen[page]) {
            this._closeSidebar(page);
        } else {
            this._openSidebar(page);
        }
    },

    _openSidebar(page) {
        const sidebar = this._sidebars[page];
        const toggle = document.getElementById(`sidebar-toggle-${page}`);
        const backdrop = document.getElementById('module-sidebar-backdrop');

        if (sidebar) sidebar.classList.add('open');
        if (toggle) toggle.classList.add('shifted');
        this._sidebarOpen[page] = true;

        // 移动端显示遮罩，桌面端保持覆盖式侧栏
        if (window.innerWidth <= 768) {
            if (backdrop) backdrop.classList.add('visible');
        }
    },

    _closeSidebar(page) {
        const sidebar = this._sidebars[page];
        const toggle = document.getElementById(`sidebar-toggle-${page}`);
        const backdrop = document.getElementById('module-sidebar-backdrop');

        if (sidebar) sidebar.classList.remove('open');
        if (toggle) toggle.classList.remove('shifted');
        if (backdrop) backdrop.classList.remove('visible');
        this._sidebarOpen[page] = false;
    },

    _closeSidebarForCurrentPage() {
        const page = Router.currentPage;
        if (page && this._sidebars[page]) {
            this._closeSidebar(page);
        }
    },

    // ── Lazy Module Initialization ──
    // Only initialize a module when it is first opened.
    _initModule(page, moduleId) {
        const key = `${page}:${moduleId}`;
        if (this._initialized[key]) return;
        this._initialized[key] = true;

        // Map moduleId to init function
        const initMap = {
            // Mathematics
            'function-graph': () => { if (typeof initFunctionGraph === 'function') initFunctionGraph(); },
            'calculus': () => { if (typeof initCalculus === 'function') initCalculus(); },
            'geometry': () => { if (typeof initGeoTransform === 'function') initGeoTransform(); },
            'complex': () => { if (typeof initComplexVis === 'function') initComplexVis(); },
            'trigonometry': () => { if (typeof initTrigVis === 'function') initTrigVis(); },
            'set-operations': () => { if (typeof initSetOps === 'function') initSetOps(); },
            'probability': () => { if (typeof initProbability === 'function') initProbability(); },
            'vector-ops': () => { if (typeof initVectorOps === 'function') initVectorOps(); },
            'inequality': () => { if (typeof initInequality === 'function') initInequality(); },
            'conic-sections': () => { if (typeof initConicSections === 'function') initConicSections(); },
            'solid-geometry': () => { if (typeof initSolidGeom === 'function') initSolidGeom(); },
            'permutation-combination': () => { if (typeof initPermComb === 'function') initPermComb(); },
            'sequences': () => { if (typeof initSequences === 'function') initSequences(); },
            'function-properties': () => { if (typeof initFuncProps === 'function') initFuncProps(); },
            'exp-log': () => { if (typeof initExpLog === 'function') initExpLog(); },

            // Physics
            'mechanics': () => { if (typeof initPhysics === 'function') initPhysics(); },
            'electromagnetism': () => { if (typeof initElectromagnetic === 'function') initElectromagnetic(); },
            'waves': () => { if (typeof initWaves === 'function') initWaves(); },
            'relativity': () => { if (typeof initRelativity === 'function') initRelativity(); },
            'fluid-dynamics': () => { if (typeof initFluidDynamics === 'function') initFluidDynamics(); },
            'optics': () => { if (typeof initOptics === 'function') initOptics(); },
            'kinematics': () => { if (typeof initKinematics === 'function') initKinematics(); },
            'projectile': () => { if (typeof initProjectile === 'function') initProjectile(); },
            'circular-motion': () => { if (typeof initCircularMotion === 'function') initCircularMotion(); },
            'energy-conservation': () => { if (typeof initEnergyConservation === 'function') initEnergyConservation(); },
            'circuit-analysis': () => { if (typeof initCircuitAnalysis === 'function') initCircuitAnalysis(); },
            'em-induction': () => { if (typeof initEMInduction === 'function') initEMInduction(); },
            'alternating-current': () => { if (typeof initACCircuit === 'function') initACCircuit(); },
            'gravitation': () => { if (typeof initGravitation === 'function') initGravitation(); },

            // Chemistry
            'periodic-table': () => { if (typeof initPeriodicTable === 'function') initPeriodicTable(); },
            'molecular-structure': () => { if (typeof initMoleculeVis === 'function') initMoleculeVis(); },
            'reactions': () => { if (typeof initChemReaction === 'function') initChemReaction(); },
            'chemical-equilibrium': () => { if (typeof initChemEquilibrium === 'function') initChemEquilibrium(); },
            'electrochemistry': () => { if (typeof initElectrochemistry === 'function') initElectrochemistry(); },
            'chemical-bond': () => { if (typeof initChemBond === 'function') initChemBond(); },
            'organic-chemistry': () => { if (typeof initOrganicChem === 'function') initOrganicChem(); },
            'reaction-rate': () => { if (typeof initReactionRate === 'function') initReactionRate(); },
            'solution-ionization': () => { if (typeof initSolutionIon === 'function') initSolutionIon(); },
            'ionic-reaction': () => { if (typeof initIonicReaction === 'function') initIonicReaction(); },
            'redox': () => { if (typeof initRedox === 'function') initRedox(); },

            // Algorithms
            'sorting': () => { /* algorithms.js self-inits */ },
            'searching': () => { if (typeof initSearchAlgorithms === 'function') initSearchAlgorithms(); },
            'graph': () => { if (typeof initGraphAlgo === 'function') initGraphAlgo(); },
            'data-structures': () => { if (typeof initDataStructVis === 'function') initDataStructVis(); },
            'sorting-compare': () => { if (typeof initSortCompare === 'function') initSortCompare(); },
            'recursion-vis': () => { if (typeof initRecursionVis === 'function') initRecursionVis(); },
            'dynamic-programming': () => { if (typeof initDPVis === 'function') initDPVis(); },
            'string-matching': () => { if (typeof initStringMatch === 'function') initStringMatch(); },

            // Biology
            'cell-structure': () => { if (typeof initCellStructure === 'function') initCellStructure(); },
            'dna': () => { if (typeof initDNAHelix === 'function') initDNAHelix(); },
            'photosynthesis': () => { if (typeof initPhotosynthesis === 'function') initPhotosynthesis(); },
            'genetics': () => { if (typeof initGenetics === 'function') initGenetics(); },
            'mitosis': () => { if (typeof initMitosis === 'function') initMitosis(); },
            'meiosis': () => { if (typeof initMeiosis === 'function') initMeiosis(); },
            'gene-expression': () => { if (typeof initGeneExpression === 'function') initGeneExpression(); },
            'cellular-respiration': () => { if (typeof initCellularResp === 'function') initCellularResp(); },
            'substance-transport': () => { if (typeof initSubstanceTransport === 'function') initSubstanceTransport(); },
            'gene-mutation': () => { if (typeof initGeneMutation === 'function') initGeneMutation(); },
            'neural-regulation': () => { if (typeof initNeuralReg === 'function') initNeuralReg(); },
            'immune-system': () => { if (typeof initImmuneSystem === 'function') initImmuneSystem(); },
            'ecosystem': () => { if (typeof initEcosystem === 'function') initEcosystem(); },
        };

        const initFn = initMap[moduleId];
        if (initFn) {
            // Small delay to ensure DOM is visible and has layout before init
            setTimeout(() => {
                initFn();
                if (page === 'physics' && window.PhysicsZoom && typeof window.PhysicsZoom.init === 'function') {
                    window.PhysicsZoom.init();
                }
                if (page === 'biology' && window.BiologyZoom && typeof window.BiologyZoom.init === 'function') {
                    window.BiologyZoom.init();
                }
            }, 50);
        }
    },

    // Reset initialization state when leaving a page (so re-entering re-inits)
    resetPage(page) {
        const experiments = CONFIG.experiments[page];
        if (!experiments) return;
        experiments.forEach(exp => {
            delete this._initialized[`${page}:${exp.id}`];
        });
        this.activeModule[page] = null;

        // Reset sidebar
        this._closeSidebar(page);
        const toggle = document.getElementById(`sidebar-toggle-${page}`);
        if (toggle) toggle.style.display = 'none';

        // Show gallery
        const pageEl = document.getElementById(`page-${page}`);
        if (pageEl) {
            pageEl.querySelectorAll('[data-module].module-active').forEach(s => {
                s.classList.remove('module-active');
            });
            pageEl.classList.add('module-gallery-active');
            const gallery = document.getElementById(`gallery-${page}`);
            if (gallery) gallery.style.display = '';
        }

        // Clear sidebar active states
        const sidebar = this._sidebars[page];
        if (sidebar) {
            sidebar.querySelectorAll('.module-sidebar__item.active').forEach(i => i.classList.remove('active'));
        }
    },

    // Show back button (kept for backward compat, now no-op since sidebar handles it)
    showBackButton() {},
};
