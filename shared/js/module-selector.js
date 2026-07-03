// ===== Module Selector (Sidebar Navigation + Lazy Init) =====
// Provides sidebar navigation for experiments within each subject page.
// Experiments are only initialized when opened (fixing canvas-in-hidden-container issues).

const ModuleSelector = {
    activeModule: {},   // { pageName: 'module-id' | null }
    _initialized: {},   // { 'module-id': true } — tracks which modules have been initialized
    _sidebars: {},      // { pageName: sidebar DOM element }
    _sidebarOpen: {},   // { pageName: bool }
    _swipeBackCtrls: {}, // { pageName: SwipeBack controller }
    _scriptPromises: {},
    _moduleScripts: {
        // Mathematics
        'function-graph': 'pages/mathematics/mathematics.js',
        'calculus': 'pages/mathematics/calculus.js',
        'geometry': 'pages/mathematics/geometry.js',
        'complex': 'pages/mathematics/complex-numbers.js',
        'trigonometry': 'pages/mathematics/trigonometry.js',
        'set-operations': 'pages/mathematics/set-operations.js',
        'probability': 'pages/mathematics/probability.js',
        'vector-ops': 'pages/mathematics/vector-ops.js',
        'inequality': 'pages/mathematics/inequality.js',
        'conic-sections': 'pages/mathematics/conic-sections.js',
        'solid-geometry': 'pages/mathematics/solid-geometry.js',
        'permutation-combination': 'pages/mathematics/permutation-combination.js',
        'sequences': 'pages/mathematics/sequences.js',
        'function-properties': 'pages/mathematics/function-properties.js',
        'exp-log': 'pages/mathematics/exp-log.js',
        'binomial-theorem': 'pages/mathematics/binomial-theorem.js',
        'statistics-regression': 'pages/mathematics/statistics-regression.js',
        'modeling-numerical': 'pages/mathematics/modeling-numerical.js?v=20260618mathModelP1',
        'spatial-vector': 'pages/mathematics/spatial-vector.js',
        'derivative-application': 'pages/mathematics/derivative-application.js?v=20260606fix1',

        // Physics
        'mechanics': 'pages/physics/physics.js',
        'gas-laws': 'pages/physics/gas-laws.js?v=20260618publicClean1',
        'thermodynamics': 'pages/physics/thermodynamics.js?v=20260618thermoP1',
        'electromagnetism': 'pages/physics/electromagnetic.js',
        'waves': 'pages/physics/waves.js',
        'relativity': 'pages/physics/relativity.js',
        'fluid-dynamics': 'pages/physics/fluid-dynamics.js?v=20260424v46e',
        'optics': 'pages/physics/optics.js',
        'kinematics': 'pages/physics/kinematics.js',
        'projectile': 'pages/physics/projectile.js',
        'circular-motion': 'pages/physics/circular-motion.js',
        'energy-conservation': 'pages/physics/energy-conservation.js?v=20260424v46b',
        'circuit-analysis': 'pages/physics/circuit-analysis.js',
        'em-induction': 'pages/physics/electromagnetic-induction.js',
        'alternating-current': 'pages/physics/alternating-current.js',
        'gravitation': 'pages/physics/gravitation.js?v=20260424v46d',
        'force-composition': 'pages/physics/force-composition.js?v=20260424v46a',
        'momentum-conservation': 'pages/physics/momentum-conservation.js?v=20260424v46c',
        'charged-particle': 'pages/physics/charged-particle.js',
        'atomic-physics': 'pages/physics/atomic-physics.js?v=20260618publicClean1',

        // Chemistry
        'periodic-table': 'pages/chemistry/periodic-table.js?v=20260618ptNames1',
        'molecular-structure': 'pages/chemistry/molecular-structure.js?v=20260424v45e',
        'hybrid-orbitals': 'pages/chemistry/hybrid-orbitals.js?v=20260618hybFix1',
        'crystal-structures': 'pages/chemistry/crystal-structures.js?v=20260617crystalP2',
        'reactions': 'pages/chemistry/chemical-reactions.js?v=20260424v45g',
        'chemical-equilibrium': 'pages/chemistry/chemical-equilibrium.js?v=20260606chem1',
        'electrochemistry': 'pages/chemistry/electrochemistry.js?v=20260606chem1',
        'chemical-bond': 'pages/chemistry/chemical-bond.js?v=20260424v45h',
        'organic-chemistry': 'pages/chemistry/organic-chemistry.js?v=20260424v45i',
        'reaction-rate': 'pages/chemistry/reaction-rate.js?v=20260618rateP1',
        'solution-ionization': 'pages/chemistry/solution-ionization.js?v=20260618ionP1',
        'ionic-reaction': 'pages/chemistry/ionic-reaction.js',
        'redox': 'pages/chemistry/redox.js?v=20260618redoxP1',
        'atomic-structure': 'pages/chemistry/atomic-structure.js',
        'element-compounds': 'pages/chemistry/element-compounds.js?v=20260530v62a',
        'intermolecular-forces': 'pages/chemistry/intermolecular-forces.js?v=20260617gasP1b',
        'experiments': 'pages/chemistry/virtual-experiments.js?v=20260618refsP1',

        // Algorithms
        'sorting': 'pages/algorithms/algorithms.js',
        'searching': 'pages/algorithms/search-algorithms.js',
        'hash-tables': 'pages/algorithms/hash-tables.js?v=20260617bstP1b',
        'bst-avl': 'pages/algorithms/bst-avl.js?v=20260617bstP1b',
        'graph': 'pages/algorithms/graph-algo.js',
        'mst-compare': 'pages/algorithms/mst-compare.js?v=20260618mstP1',
        'greedy-scheduling': 'pages/algorithms/greedy-scheduling.js?v=20260618refsP1',
        'data-structures': 'pages/algorithms/data-structures.js',
        'sorting-compare': 'pages/algorithms/sorting-compare.js',
        'recursion-vis': 'pages/algorithms/recursion-vis.js',
        'dynamic-programming': 'pages/algorithms/dynamic-programming.js?v=20260618algoTextP1',
        'string-matching': 'pages/algorithms/string-matching.js?v=20260618algoTextP1',

        // Biology
        'cell-structure': 'pages/biology/cell-structure.js?v=20260617gasP1b',
        'dna': 'pages/biology/dna-helix.js?v=20260416b',
        'photosynthesis': 'pages/biology/photosynthesis.js?v=20260618photoSourceP1d',
        'enzyme-properties': 'pages/biology/enzyme-properties.js?v=20260618enzymeSourceP1b',
        'homeostasis': 'pages/biology/homeostasis.js?v=20260618homeostasisP1',
        'humoral-regulation': 'pages/biology/humoral-regulation.js?v=20260618humoralP2',
        'genetics': 'pages/biology/genetics.js?v=20260416b',
        'mitosis': 'pages/biology/mitosis.js?v=20260617gasP1b',
        'meiosis': 'pages/biology/meiosis.js?v=20260617gasP1b',
        'gene-expression': 'pages/biology/gene-expression.js?v=20260618genexpP1',
        'gene-engineering': 'pages/biology/gene-engineering.js?v=20260618gengP1',
        'cellular-respiration': 'pages/biology/cellular-respiration.js?v=20260618cellRespSourceP1',
        'substance-transport': 'pages/biology/substance-transport.js?v=20260618transportSourceP1',
        'gene-mutation': 'pages/biology/gene-mutation.js?v=20260618gmutP3',
        'neural-regulation': 'pages/biology/neural-regulation.js?v=20260618neuralP1',
        'immune-system': 'pages/biology/immune-system.js?v=20260618immuneP2',
        'population-community': 'pages/biology/population-community.js?v=20260618popcommP1',
        'material-cycles': 'pages/biology/material-cycles.js?v=20260618cyclesP1',
        'ecosystem': 'pages/biology/ecosystem.js?v=20260423a'
    },
    _pageEnhancementScripts: {
        physics: ['pages/physics/physics-zoom.js'],
        biology: ['pages/biology/biology.js?v=20260416b', 'pages/biology/biology-zoom.js?v=20260416b']
    },

    _getExperimentGuide() {
        if (window.ExperimentGuide) return window.ExperimentGuide;
        if (globalThis.ExperimentGuide) return globalThis.ExperimentGuide;
        return typeof ExperimentGuide !== 'undefined' ? ExperimentGuide : null;
    },

    init() {
        const pages = ['mathematics', 'physics', 'chemistry', 'algorithms', 'biology'];
        pages.forEach(page => {
            const pageEl = document.getElementById(`page-${page}`);
            if (!pageEl) return;

            pageEl.classList.add(`page-${page}`);
            this.activeModule[page] = null;
            this._sidebarOpen[page] = false;

            this.createSidebar(page, pageEl);
            this.createLearningOverview(page, pageEl);
            this.createGallery(page, pageEl);
        });

        // Create global backdrop for mobile
        const backdrop = document.createElement('div');
        backdrop.className = 'module-sidebar-backdrop';
        backdrop.id = 'module-sidebar-backdrop';
        backdrop.addEventListener('click', () => this._closeSidebarForCurrentPage());
        document.body.appendChild(backdrop);

        // ── E-04: Global keyboard navigation ──
        this._initKeyboardNav();
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
            item.title = exp.description || exp.title;

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

    createLearningOverview(page, pageEl) {
        const experiments = CONFIG.experiments[page];
        const hero = pageEl.querySelector('.page-hero');
        const learning = CONFIG.learningDesign;
        const subject = learning && learning.subjects ? learning.subjects[page] : null;
        if (!experiments || !hero || !subject) return;

        const activeCount = experiments.filter(exp => exp.variant !== 'upcoming').length;
        const label = this._escapeHtml(CONFIG.pages[page]?.label || page);
        const methodText = subject.teachingNote || '建议先完成基础实验，再进入带有模型近似或跨学科背景的主题。每个实验都配有观察任务、可调参数和小测验。';
        const featured = experiments.filter(exp => exp.variant !== 'upcoming').slice(0, 3).map((exp, idx) => `
            <div class="learning-path__item">
                <span class="learning-path__index">${String(idx + 1).padStart(2, '0')}</span>
                <strong>${this._escapeHtml(exp.title)}</strong>
                <p>${this._escapeHtml(exp.description || '')}</p>
            </div>
        `).join('');
        const sourceLinks = (subject.sources || []).slice(0, 6).map(source => {
            const item = this._normalizeLearningSource(source);
            if (!item.label) return '';
            if (item.url) {
                return `<a href="${this._escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">${this._escapeHtml(item.label)}</a>`;
            }
            return `<span>${this._escapeHtml(item.label)}</span>`;
        }).join('');
        const sourceBlock = sourceLinks ? `
            <div class="learning-overview__sources" aria-label="${label}参考资料">
                <span>参考资料</span>
                ${sourceLinks}
            </div>
        ` : '';
        const sourceNote = learning.sourceNote ? `
            <div class="learning-overview__note" aria-label="${label}学习说明">
                <i data-lucide="book-open"></i>
                <p>${this._escapeHtml(learning.sourceNote)}</p>
            </div>
        ` : '';

        const overview = document.createElement('section');
        overview.className = 'learning-overview';
        overview.id = `learning-overview-${page}`;
        overview.setAttribute('aria-label', `${label}学习地图`);
        overview.innerHTML = `
            <div class="learning-overview__copy">
                <span class="learning-overview__eyebrow">${label} · 学习地图</span>
                <h2>${this._escapeHtml(CONFIG.pages[page]?.title || label)}</h2>
                <p>${this._escapeHtml(subject.overview || CONFIG.pages[page]?.desc || '')}</p>
            </div>
            <div class="learning-overview__ledger" aria-label="学习概览">
                <div><span>实验数</span><strong>${activeCount}</strong></div>
                <div><span>学习方式</span><strong>互动观察</strong></div>
                <div><span>练习入口</span><strong>小测验</strong></div>
            </div>
            <div class="learning-overview__method">
                <i data-lucide="route"></i>
                <p>${this._escapeHtml(methodText)}</p>
            </div>
            ${sourceNote}
            ${sourceBlock}
            <div class="learning-path" aria-label="${label}推荐学习起点">
                ${featured}
            </div>
        `;

        hero.insertAdjacentElement('afterend', overview);
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
            const meta = this.getLearningMeta(page, exp);

            const card = document.createElement('div');
            card.className = 'module-card';
            card.dataset.moduleTarget = exp.id;
            card.setAttribute('role', 'button');
            card.setAttribute('tabindex', '0');
            card.setAttribute('aria-label', exp.title);
            card.title = exp.description || exp.title;

            card.innerHTML = `
                <div class="module-card__topline">
                    <div class="module-card__icon"><i data-lucide="${this._escapeHtml(exp.icon || 'box')}"></i></div>
                </div>
                <div class="module-card__title">${this._escapeHtml(exp.title)}</div>
                <div class="module-card__desc">${this._escapeHtml(exp.description)}</div>
                <div class="module-card__learning">
                    <div>
                        <span>学习目标</span>
                        <p>${this._escapeHtml(meta.task)}</p>
                    </div>
                </div>
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

        const overview = document.getElementById(`learning-overview-${page}`);
        (overview || hero).insertAdjacentElement('afterend', gallery);
        pageEl.classList.add('module-gallery-active');

        if (typeof lucide !== 'undefined') lucide.createIcons();

        // Show favorite indicators on gallery cards
        if (window.ExperimentFavorites) ExperimentFavorites.updateGalleryCards();
    },

    getLearningMeta(page, exp) {
        const learning = CONFIG.learningDesign || {};
        const focus = learning.focus ? learning.focus[exp.id] : null;
        return {
            task: focus?.task || `观察 ${exp.title} 中参数变化与结论的对应关系。`
        };
    },

    _normalizeLearningSource(source) {
        if (!source) return { label: '', url: '' };
        if (typeof source === 'string') return { label: source, url: '' };
        return {
            label: source.label || source.title || source.url || '',
            url: /^https?:\/\//i.test(source.url || '') ? source.url : ''
        };
    },

    _escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
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

        // v6.1：同步深链接到 URL hash（#subject/experiment），便于分享 / 刷新保持现场
        try {
            const newHash = '#' + page + '/' + moduleId;
            if (window.location.hash !== newHash) {
                history.replaceState(null, '', newHash);
            }
        } catch (e) {}

        // X-01: Track learning progress
        if (typeof LearningProgress !== 'undefined') {
            LearningProgress.markVisited(moduleId);
        }

        // Lazy-initialize this specific module
        this._initModule(page, moduleId);
        this._applyBackendSchema(page, moduleId);

        // Scroll to top
        window.scrollTo({ top: 0, behavior: 'smooth' });

        // 默认关闭侧边栏，避免改变实验区域尺寸
        this._closeSidebar(page);

        // Trigger resize for canvas elements
        setTimeout(() => window.dispatchEvent(new Event('resize')), 150);

        // E-04: Focus first interactive control for keyboard users
        this._focusExperiment(page, moduleId);

        // v4.5-α3: Render related experiments panel at the bottom
        if (typeof RelatedExperiments !== 'undefined') {
            // 等模块 DOM 渲染完毕（_initModule 是同步的，但部分模块在 microtask 内才挂 DOM）
            setTimeout(() => RelatedExperiments.show(page, moduleId), 80);
        }

        // Enable swipe-back from left edge (touch devices)
        if (typeof TouchGestures !== 'undefined' && !this._swipeBackCtrls[page]) {
            this._swipeBackCtrls[page] = TouchGestures.enableSwipeBack(
                pageEl, () => this.closeModule(page)
            );
        }
    },

    closeModule(page) {
        const pageEl = document.getElementById(`page-${page}`);
        if (!pageEl) return;

        // Hide experiment guide help button
        const guide = this._getExperimentGuide();
        if (guide) guide.hideHelpButton();

        // Hide export button (E-03)
        if (window.ExperimentExport) ExperimentExport.hide();

        // Hide quiz FAB (X-02)
        if (window.ExperimentQuiz) ExperimentQuiz.hide();

        // Hide favorites button
        if (window.ExperimentFavorites) ExperimentFavorites.hide();

        // Hide rating card
        if (window.ExperimentRating) ExperimentRating.hide();

        // Hide all module sections
        pageEl.querySelectorAll('[data-module].module-active').forEach(s => {
            s.classList.remove('module-active');
        });

        // v4.5-α3: 移除相关实验推荐面板
        pageEl.querySelectorAll('.related-experiments').forEach(el => el.remove());

        // Show gallery
        const gallery = document.getElementById(`gallery-${page}`);
        if (gallery) gallery.style.display = '';

        // Update favorite indicators on gallery cards
        if (window.ExperimentFavorites) ExperimentFavorites.updateGalleryCards();

        // Restore gallery-active state
        pageEl.classList.add('module-gallery-active');

        // Hide sidebar and toggle
        this._closeSidebar(page);
        const toggle = document.getElementById(`sidebar-toggle-${page}`);
        if (toggle) toggle.style.display = 'none';

        this.activeModule[page] = null;

        // v6.1：清理深链接，把 #subject/experiment 还原成 #subject
        try {
            const newHash = '#' + page;
            if (window.location.hash !== newHash) {
                history.replaceState(null, '', newHash);
            }
        } catch (e) {}

        // Clear sidebar active states
        const sidebar = this._sidebars[page];
        if (sidebar) {
            sidebar.querySelectorAll('.module-sidebar__item.active').forEach(i => i.classList.remove('active'));
        }

        window.scrollTo({ top: 0, behavior: 'smooth' });

        // Destroy swipe-back gesture for this page
        if (this._swipeBackCtrls[page]) {
            this._swipeBackCtrls[page].destroy();
            this._swipeBackCtrls[page] = null;
        }
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
    _loadScript(src) {
        if (!src) return Promise.resolve();
        if (this._scriptPromises[src]) return this._scriptPromises[src];

        this._scriptPromises[src] = new Promise((resolve, reject) => {
            const plainSrc = src.split('?')[0];
            const existing = Array.from(document.scripts).find(script => {
                const current = script.getAttribute('src') || '';
                return current === src || current.split('?')[0] === plainSrc;
            });

            if (existing && existing.dataset.moduleLoaderLoaded === 'true') {
                resolve();
                return;
            }
            if (existing && !existing.dataset.moduleLoaderSrc) {
                resolve();
                return;
            }

            const script = existing || document.createElement('script');
            if (!existing) {
                script.src = src;
                script.async = true;
                script.dataset.moduleLoaderSrc = src;
                document.body.appendChild(script);
            }

            script.addEventListener('load', () => {
                script.dataset.moduleLoaderLoaded = 'true';
                resolve();
            }, { once: true });

            script.addEventListener('error', () => {
                delete this._scriptPromises[src];
                reject(new Error(`Failed to load ${src}`));
            }, { once: true });
        });

        return this._scriptPromises[src];
    },

    _loadModuleAssets(page, moduleId) {
        const scripts = [];
        if (this._moduleScripts[moduleId]) scripts.push(this._moduleScripts[moduleId]);
        if (this._pageEnhancementScripts[page]) scripts.push(...this._pageEnhancementScripts[page]);

        return scripts.reduce(
            (chain, src) => chain.then(() => this._loadScript(src)),
            Promise.resolve()
        );
    },

    _initModule(page, moduleId) {
        const key = `${page}:${moduleId}`;
        if (this._initialized[key]) {
            this._showModuleTools(page, moduleId);
            return;
        }

        // Map moduleId to init function
        const retryInit = (fnName) => {
            const fn = window[fnName];
            if (typeof fn !== 'function') return false;
            fn();
            return true;
        };
        const initMap = {
            // Mathematics
            'function-graph': () => retryInit('initFunctionGraph'),
            'calculus': () => retryInit('initCalculus'),
            'geometry': () => retryInit('initGeoTransform'),
            'complex': () => retryInit('initComplexVis'),
            'trigonometry': () => retryInit('initTrigVis'),
            'set-operations': () => retryInit('initSetOps'),
            'probability': () => retryInit('initProbability'),
            'vector-ops': () => retryInit('initVectorOps'),
            'inequality': () => retryInit('initInequality'),
            'conic-sections': () => retryInit('initConicSections'),
            'solid-geometry': () => retryInit('initSolidGeom'),
            'permutation-combination': () => retryInit('initPermComb'),
            'sequences': () => retryInit('initSequences'),
            'function-properties': () => retryInit('initFuncProps'),
            'exp-log': () => retryInit('initExpLog'),
            'binomial-theorem': () => retryInit('initBinomial'),
            'statistics-regression': () => retryInit('initStatReg'),
            'modeling-numerical': () => retryInit('initModelingNumerical'),
            'spatial-vector': () => retryInit('initSpatialVec'),
            'derivative-application': () => retryInit('initDerivApp'),

            // Physics
            'mechanics': () => retryInit('initPhysics'),
            'gas-laws': () => retryInit('initGasLaws'),
            'thermodynamics': () => retryInit('initThermodynamics'),
            'electromagnetism': () => retryInit('initElectromagnetic'),
            'waves': () => retryInit('initWaves'),
            'relativity': () => retryInit('initRelativity'),
            'fluid-dynamics': () => retryInit('initFluidDynamics'),
            'optics': () => retryInit('initOptics'),
            'kinematics': () => retryInit('initKinematics'),
            'projectile': () => retryInit('initProjectile'),
            'circular-motion': () => retryInit('initCircularMotion'),
            'energy-conservation': () => retryInit('initEnergyConservation'),
            'circuit-analysis': () => retryInit('initCircuitAnalysis'),
            'em-induction': () => retryInit('initEMInduction'),
            'alternating-current': () => retryInit('initACCircuit'),
            'gravitation': () => retryInit('initGravitation'),
            'force-composition': () => retryInit('initForceComposition'),
            'momentum-conservation': () => retryInit('initMomentumConservation'),
            'charged-particle': () => retryInit('initChargedParticle'),
            'atomic-physics': () => retryInit('initAtomicPhysics'),

            // Chemistry
            'periodic-table': () => retryInit('initPeriodicTable'),
            'molecular-structure': () => retryInit('initMoleculeVis'),
            'hybrid-orbitals': () => retryInit('initHybridOrbitals'),
            'crystal-structures': () => retryInit('initCrystalStructures'),
            'reactions': () => retryInit('initChemReaction'),
            'chemical-equilibrium': () => retryInit('initChemEquilibrium'),
            'electrochemistry': () => retryInit('initElectrochemistry'),
            'chemical-bond': () => retryInit('initChemBond'),
            'organic-chemistry': () => retryInit('initOrganicChem'),
            'reaction-rate': () => retryInit('initReactionRate'),
            'solution-ionization': () => retryInit('initSolutionIon'),
            'ionic-reaction': () => retryInit('initIonicReaction'),
            'redox': () => retryInit('initRedox'),
            'atomic-structure': () => retryInit('initAtomicStructure'),
            'element-compounds': () => retryInit('initElementCompounds'),
            'intermolecular-forces': () => retryInit('initIntermolecular'),
            'experiments': () => retryInit('initChemVirtualExperiments'),

            // Algorithms
            'sorting': () => true, // algorithms.js self-inits
            'searching': () => retryInit('initSearchAlgorithms'),
            'hash-tables': () => retryInit('initHashTablesLab'),
            'bst-avl': () => retryInit('initBSTAVL'),
            'graph': () => retryInit('initGraphAlgo'),
            'mst-compare': () => retryInit('initMSTCompare'),
            'greedy-scheduling': () => retryInit('initGreedyScheduling'),
            'data-structures': () => retryInit('initDataStructVis'),
            'sorting-compare': () => retryInit('initSortCompare'),
            'recursion-vis': () => retryInit('initRecursionVis'),
            'dynamic-programming': () => retryInit('initDPVis'),
            'string-matching': () => retryInit('initStringMatch'),

            // Biology
            'cell-structure': () => retryInit('initCellStructure'),
            'dna': () => retryInit('initDNAHelix'),
            'photosynthesis': () => retryInit('initPhotosynthesis'),
            'enzyme-properties': () => retryInit('initEnzymeProperties'),
            'homeostasis': () => retryInit('initHomeostasis'),
            'humoral-regulation': () => retryInit('initHumoralRegulation'),
            'genetics': () => retryInit('initGenetics'),
            'mitosis': () => retryInit('initMitosis'),
            'meiosis': () => retryInit('initMeiosis'),
            'gene-expression': () => retryInit('initGeneExpression'),
            'gene-engineering': () => retryInit('initGeneEngineering'),
            'cellular-respiration': () => retryInit('initCellularResp'),
            'substance-transport': () => retryInit('initSubstanceTransport'),
            'gene-mutation': () => retryInit('initGeneMutation'),
            'neural-regulation': () => retryInit('initNeuralReg'),
            'immune-system': () => retryInit('initImmuneSystem'),
            'population-community': () => retryInit('initPopulationCommunity'),
            'material-cycles': () => retryInit('initMaterialCycles'),
            'ecosystem': () => retryInit('initEcosystem'),
        };

        const initFn = initMap[moduleId];
        if (initFn) {
            const runInit = (attempt = 0) => {
                if (this.activeModule[page] !== moduleId) return;
                const initialized = initFn();
                if (initialized === false && attempt < 20) {
                    setTimeout(() => runInit(attempt + 1), 100);
                    return;
                }
                if (initialized === false) {
                    console.warn('[ModuleSelector] init function unavailable after script load:', moduleId);
                    return;
                }
                this._initialized[key] = true;
                if (page === 'physics' && window.PhysicsZoom && typeof window.PhysicsZoom.init === 'function') {
                    window.PhysicsZoom.init();
                }
                if (page === 'biology' && window.BiologyZoom && typeof window.BiologyZoom.init === 'function') {
                    window.BiologyZoom.init();
                }
                this._showModuleTools(page, moduleId);
            };
            this._loadModuleAssets(page, moduleId)
                .then(() => setTimeout(() => runInit(), 50))
                .catch(error => {
                    console.warn('[ModuleSelector] failed to load module assets:', moduleId, error);
                });
        }
    },

    _showModuleTools(page, moduleId) {
        // Show experiment guide on first visit
        const guide = this._getExperimentGuide();
        if (guide) {
            guide.showIfFirstTime(page, moduleId);
            guide.showHelpButton(page, moduleId);
        }
        // Show export button (E-03)
        if (window.ExperimentExport) {
            ExperimentExport.show(page, moduleId);
        }
        // Show quiz FAB (X-02)
        if (window.ExperimentQuiz) {
            ExperimentQuiz.show(moduleId);
        }
        // Show favorites button
        if (window.ExperimentFavorites) {
            ExperimentFavorites.show(moduleId);
        }
        // Show rating card after delay
        if (window.ExperimentRating) {
            ExperimentRating.show(moduleId);
        }
        if (window.BackendContent && typeof BackendContent.applyExperimentSchema === 'function') {
            this._applyBackendSchema(page, moduleId);
        }
    },

    _applyBackendSchema(page, moduleId) {
        if (!window.BackendContent || typeof BackendContent.applyExperimentSchema !== 'function') return;
        try {
            BackendContent.applyExperimentSchema(page, moduleId);
        } catch (e) {
            console.warn('[ModuleSelector] backend schema apply failed:', moduleId, e);
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

    // ── E-04: Keyboard Navigation ──

    _initKeyboardNav() {
        document.addEventListener('keydown', (e) => {
            // Skip if user is typing in an input/textarea/select
            const tag = (e.target.tagName || '').toLowerCase();
            if (tag === 'input' || tag === 'textarea' || tag === 'select') return;

            const page = typeof Router !== 'undefined' ? Router.currentPage : null;
            if (!page) return;

            if (e.key === 'Escape') {
                // Priority chain: zoom modal → guide overlay → export menu → sidebar → experiment
                const zoomModal = document.querySelector('.physics-zoom-modal.open, .biology-zoom-modal.open');
                if (zoomModal) return; // Let zoom modal handle its own Esc

                const guideOverlay = document.getElementById('experiment-guide-overlay');
                if (guideOverlay && guideOverlay.classList.contains('active')) return; // Guide handles Esc

                // Close export menu if open
                if (window.ExperimentExport && ExperimentExport._menuOpen) {
                    ExperimentExport._closeMenu();
                    e.preventDefault();
                    return;
                }

                // Close sidebar if open
                if (this._sidebarOpen[page]) {
                    this._closeSidebar(page);
                    e.preventDefault();
                    return;
                }

                // Close experiment → back to gallery
                if (this.activeModule[page]) {
                    this.closeModule(page);
                    e.preventDefault();
                    return;
                }
            }

            // Arrow keys in sidebar
            if (this._sidebarOpen[page] && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
                this._sidebarArrowNav(page, e.key === 'ArrowDown' ? 1 : -1);
                e.preventDefault();
            }
        });
    },

    _sidebarArrowNav(page, direction) {
        const sidebar = this._sidebars[page];
        if (!sidebar) return;
        const items = Array.from(sidebar.querySelectorAll('.module-sidebar__item[data-module-target]'));
        if (items.length === 0) return;

        const focused = document.activeElement;
        let idx = items.indexOf(focused);
        if (idx < 0) {
            // Find currently active item
            idx = items.findIndex(i => i.classList.contains('active'));
        }
        idx = Math.max(0, Math.min(items.length - 1, idx + direction));
        items[idx].focus();
    },

    // Focus the first interactive control inside the experiment when it opens
    _focusExperiment(page, moduleId) {
        const pageEl = document.getElementById(`page-${page}`);
        if (!pageEl) return;
        const section = pageEl.querySelector(`[data-module="${moduleId}"].module-active`);
        if (!section) return;

        // Find first focusable element (button, input, select, [tabindex])
        const focusable = section.querySelector(
            'button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        if (focusable) {
            setTimeout(() => focusable.focus(), 200);
        }
    }
};
