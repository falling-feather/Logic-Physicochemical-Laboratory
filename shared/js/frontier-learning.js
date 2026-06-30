// ===== Frontier Galaxy Learning Frame =====
const FrontierLearning = {
    pages: ['cosmos', 'engineering', 'datascience', 'infotech', 'materials', 'humanities'],
    sectionPlans: {
        cosmos: [
            { key: 'lab', selector: '.cosmos-lab', label: '实验台', note: '拖动日期和纬度，观察赤纬、昼长与太阳高度。', evidence: 'NOAA：太阳计算近似', protocol: { adjust: '日期与纬度', observe: '赤纬、昼长、太阳高度', boundary: '按 NOAA 近似理解趋势' }, legend: [
                { tone: 'input', label: '日期/纬度', note: '调参入口' },
                { tone: 'signal', label: '太阳高度', note: '曲线观察' },
                { tone: 'boundary', label: '昼长趋势', note: '近似判读' }
            ] },
            { key: 'read', selector: '.cosmos-interpretation', label: '判读', note: '把季节图读成地轴、赤纬、纬度和近似边界。', evidence: 'NASA/JPL：季节图像' },
            { key: 'reference', selector: '.cosmos-reference', label: '资料', note: '回到 NASA 与 NOAA 资料确认模型边界。', evidence: '来源索引：3 条' }
        ],
        engineering: [
            { key: 'chain', selector: '.engineering-model-chain', label: '判断链', note: '按模型假设、整体反力、节点杆力和设计边界推进。', evidence: '静力平衡：受力图' },
            { key: 'lab', selector: '.engineering-lab', label: '实验台', note: '调整荷载位置，观察支座反力和杆件拉压。', evidence: '节点法：杆力符号', protocol: { adjust: '荷载位置', observe: '支座反力、杆件拉压', boundary: '只作二维静定桁架入门' }, legend: [
                { tone: 'load', label: '荷载', note: '外力输入' },
                { tone: 'reaction', label: '支座反力', note: '整体平衡' },
                { tone: 'signal', label: '杆件拉压', note: '节点判读' }
            ] },
            { key: 'read', selector: '.engineering-interpretation', label: '判读', note: '区分整体平衡、节点平衡、拉压符号和真实验算。', evidence: 'OpenStax：静态平衡' },
            { key: 'reference', selector: '.engineering-reference', label: '资料', note: '核对静力学教材中的桁架和节点法依据。', evidence: '来源索引：5 条' }
        ],
        datascience: [
            { key: 'map', selector: '.datascience-model-map', label: '模型链', note: '把数据、参数、损失和解释边界串起来。', evidence: 'Google ML：线性回归' },
            { key: 'lab', selector: '.datascience-lab', label: '实验台', note: '调节斜率、截距和学习率，观察损失变化。', evidence: 'Google ML：损失函数', protocol: { adjust: '斜率、截距、学习率', observe: '损失、残差、预测线', boundary: '不作样本外保证' }, legend: [
                { tone: 'input', label: '样本点', note: '训练数据' },
                { tone: 'signal', label: '预测线', note: '当前模型' },
                { tone: 'boundary', label: '残差/损失', note: '只在样本范围判读' }
            ] },
            { key: 'read', selector: '.datascience-interpretation', label: '判读', note: '用残差、样本范围和异常点检查模型。', evidence: 'scikit-learn：模型 API 边界' },
            { key: 'reference', selector: '.datascience-reference', label: '资料', note: '对照开放统计教材与机器学习资料。', evidence: '来源索引：4 条' }
        ],
        infotech: [
            { key: 'protocols', selector: '.infotech-protocols', label: '协议层', note: '建立 DNS、HTTP/2、TCP 与 IPv6 的角色边界。', evidence: 'RFC 1034 / 9113 / 9293 / 8200' },
            { key: 'lab', selector: '.infotech-lab', label: '实验台', note: '切换请求阶段，观察封装和逐跳转发。', evidence: 'RFC：封装角色', protocol: { adjust: '请求阶段', observe: '封装层、逐跳转发', boundary: '真实抓包受 TLS/MTU 等影响' }, legend: [
                { tone: 'model', label: '封装层', note: '应用到链路' },
                { tone: 'signal', label: '路径节点', note: '逐跳转发' },
                { tone: 'boundary', label: '教学近似', note: 'TLS/MTU 另行影响' }
            ] },
            { key: 'read', selector: '.infotech-interpretation', label: '判读', note: '区分教学包头模型和真实抓包开销。', evidence: 'TCP/IPv6：真实边界' },
            { key: 'reference', selector: '.infotech-reference', label: '资料', note: '回到 IETF RFC 原文确认协议定义。', evidence: '来源索引：4 条' }
        ],
        materials: [
            { key: 'topics', selector: '.materials-topic-map', label: '专题地图', note: '把材料样板拆成晶体结构、晶粒尺度、性能趋势和来源附录。', evidence: '四分支导通' },
            { key: 'pages', selector: '.materials-topic-pages', label: '专题页骨架', note: '把四个专题整理成可迁移为真实路由的页面蓝图。', evidence: '四条可寻址专题页路径' },
            { key: 'modules', selector: '.materials-topic-modules', label: '专题模块', note: '把四个专题拆成学习看点、操作动作和来源边界。', evidence: '四张任务卡' },
            { key: 'deep', selector: '.materials-deep-panels', label: '深层面板', note: '用折叠面板呈现准独立专题页的讲解脚本和拆页方向。', evidence: '四个专题面板' },
            { key: 'visuals', selector: '.materials-visual-atlas', label: '视觉图谱', note: '用三张自制教学示意连接晶格、晶界和趋势曲线。', evidence: '自制 SVG 素材：3 组' },
            { key: 'trust', selector: '.materials-trust-ledger', label: '可信审查', note: '前置事实依据、教学近似、不可外推和回查动作。', evidence: '模型边界前置' },
            { key: 'scale', selector: '.materials-scales', label: '尺度桥', note: '区分理想晶胞、位错、晶界和加工历史。', evidence: '尺度边界：晶胞到晶粒' },
            { key: 'judge', selector: '.materials-judgement', label: '判断链', note: '把显微图像转成有边界的材料判断。', evidence: 'Hall-Petch：统计边界' },
            { key: 'lab', selector: '.materials-lab', label: '实验台', note: '切换晶体结构与晶粒尺寸，观察相对趋势。', evidence: '晶体结构 + 晶粒趋势', protocol: { adjust: '晶体结构、晶粒尺寸', observe: '配位、堆积、相对强度趋势', boundary: 'Hall-Petch 不无限外推' }, legend: [
                { tone: 'model', label: '晶胞模型', note: '理想结构' },
                { tone: 'signal', label: '晶界密度', note: '相对趋势' },
                { tone: 'boundary', label: '强度指数', note: '不可无限外推' }
            ] },
            { key: 'read', selector: '.materials-interpretation', label: '判读', note: '限定 Hall-Petch 趋势和不可外推场景。', evidence: 'Hall-Petch：破裂场景' },
            { key: 'reference', selector: '.materials-reference', label: '资料', note: '核对晶体结构和晶粒强化参考资料。', evidence: '来源索引：3 条' }
        ],
        humanities: [
            { key: 'chain', selector: '.humanities-evidence-chain', label: '证据链', note: '按清理文本、观察分布、回读和继续求证推进。', evidence: 'LOC：原始资料回读' },
            { key: 'lab', selector: '.humanities-lab', label: '实验台', note: '切换文本和视角，观察图表如何提出问题。', evidence: 'Voyant：视图解释', protocol: { adjust: '文本与分析视角', observe: '词频、上下文、共现', boundary: '回到原文和语境解释' }, legend: [
                { tone: 'input', label: '文本样本', note: '材料范围' },
                { tone: 'signal', label: '词频/共现', note: '提出问题' },
                { tone: 'boundary', label: '原文回读', note: '语境解释' }
            ] },
            { key: 'read', selector: '.humanities-interpretation', label: '判读', note: '回到原文、出处和语境中解释数量线索。', evidence: 'TEI / IR：标注与词频' },
            { key: 'reference', selector: '.humanities-reference', label: '资料', note: '对照 Voyant、国会图书馆和信息检索教材。', evidence: '来源索引：4 条' }
        ]
    },

    labDecorators: {
        cosmos: {
            workbench: '.cosmos-workbench',
            controls: '.cosmos-controls',
            canvas: '.cosmos-canvas-wrap',
            readout: '.cosmos-info'
        },
        engineering: {
            workbench: '.truss-workbench',
            controls: '.truss-controls',
            canvas: '.truss-canvas-wrap',
            readout: '.truss-info'
        },
        datascience: {
            workbench: '.regression-workbench',
            controls: '.regression-controls',
            canvas: '.regression-canvas-wrap',
            readout: '.regression-info'
        },
        infotech: {
            workbench: '.network-workbench',
            controls: '.network-controls',
            canvas: '.network-canvas-wrap',
            readout: '.network-info'
        },
        materials: {
            workbench: '.materials-workbench',
            controls: '.materials-controls',
            canvas: '.materials-canvas-wrap',
            readout: '.materials-info'
        },
        humanities: {
            workbench: '.humanities-workbench',
            controls: '.humanities-controls',
            canvas: '.humanities-canvas-wrap',
            readout: '.humanities-info'
        }
    },

    subjectModules: {
        cosmos: [
            { label: '太阳路径模型', href: '#frontier-cosmos-lab', icon: 'sun', note: '调节日期和纬度，观察太阳高度、昼长和赤纬变化。' },
            { label: '季节判读', href: '#frontier-cosmos-read', icon: 'orbit', note: '把地轴倾角、直射点和纬度差异连成解释链。' },
            { label: '极区与低纬', href: '#frontier-cosmos-lab', icon: 'globe-2', note: '用预设纬度快速比较不同地区的日照节奏。' },
            { label: '资料回查', href: '#frontier-cosmos-reference', icon: 'book-open-check', note: '回到公开资料确认模型近似和适用边界。' }
        ],
        engineering: [
            { label: '结构模型', href: '#frontier-engineering-chain', icon: 'construction', note: '先确认支座、节点和杆件的二维静定假设。' },
            { label: '荷载路径', href: '#frontier-engineering-lab', icon: 'weight', note: '移动荷载位置，观察支座反力和杆件拉压变化。' },
            { label: '节点判读', href: '#frontier-engineering-read', icon: 'git-fork', note: '区分整体平衡、节点平衡和拉压符号。' },
            { label: '设计边界', href: '#frontier-engineering-reference', icon: 'shield-check', note: '把教学桁架和真实工程验算明确分层。' }
        ],
        datascience: [
            { label: '样本与特征', href: '#frontier-datascience-map', icon: 'scatter-chart', note: '从数据点、参数和预测线建立模型坐标。' },
            { label: '损失函数', href: '#frontier-datascience-lab', icon: 'line-chart', note: '调节斜率、截距和学习率，观察损失变化。' },
            { label: '残差判读', href: '#frontier-datascience-read', icon: 'scan-line', note: '用残差、样本范围和异常点检查模型解释。' },
            { label: '模型边界', href: '#frontier-datascience-reference', icon: 'book-marked', note: '回到资料说明训练样本与样本外预测边界。' }
        ],
        infotech: [
            { label: '协议分层', href: '#frontier-infotech-protocols', icon: 'layers-3', note: '建立 DNS、HTTP、TCP、IPv6 的角色边界。' },
            { label: '请求旅程', href: '#frontier-infotech-lab', icon: 'network', note: '切换请求阶段，观察封装和逐跳转发。' },
            { label: '包头判读', href: '#frontier-infotech-read', icon: 'binary', note: '区分教学包头模型和真实抓包开销。' },
            { label: '标准回查', href: '#frontier-infotech-reference', icon: 'file-search', note: '对照 RFC 原文确认协议定义和省略内容。' }
        ],
        materials: [
            { label: '晶体结构', href: '#frontier-materials-topic-page-crystal', icon: 'box', note: '比较 SC、BCC、FCC、HCP 的几何读数。' },
            { label: '晶粒尺度', href: '#frontier-materials-topic-page-grain', icon: 'grip', note: '理解晶界、位错和加工历史如何影响趋势。' },
            { label: '性能趋势', href: '#frontier-materials-topic-page-performance', icon: 'activity', note: '用相对曲线练习趋势判断和不可外推边界。' },
            { label: '来源回查', href: '#frontier-materials-trust', icon: 'book-open-check', note: '查看资料用途、模型边界和本地来源附录。' }
        ],
        humanities: [
            { label: '文本清理', href: '#frontier-humanities-chain', icon: 'text-cursor-input', note: '先确认语料、分词和停用词的处理边界。' },
            { label: '词频上下文', href: '#frontier-humanities-lab', icon: 'list-filter', note: '切换文本视角，观察词项如何提出回读问题。' },
            { label: '共现网络', href: '#frontier-humanities-read', icon: 'network', note: '把数量线索放回原文和语境解释。' },
            { label: '资料回读', href: '#frontier-humanities-reference', icon: 'book-open-text', note: '回到来源、标注规则和阅读方法确认解释边界。' }
        ]
    },

    _runtimes: Object.create(null),
    _activeRuntimePage: null,

    init(page) {
        if (typeof CONFIG === 'undefined' || !CONFIG.learningDesign) return;
        const targetPage = page || (window.Router && Router.currentPage) || (location.hash || '').slice(1).split('/')[0];
        if (this.pages.includes(targetPage)) {
            this._activateRuntime(targetPage);
            this.renderPage(targetPage);
            this.bindHashDetailsTarget();
        } else if (targetPage === 'all') {
            this.pages.forEach((item) => {
                this._activateRuntime(item);
                this.renderPage(item);
            });
            this._activeRuntimePage = null;
        }
    },

    destroy(page) {
        const targets = page && page !== 'all' ? [page] : Object.keys(this._runtimes);
        targets.forEach((item) => this._destroyRuntime(item));
    },

    _activateRuntime(page) {
        this._destroyRuntime(page);
        this._activeRuntimePage = page;
        this._runtimes[page] = { cleanups: [] };
    },

    _destroyRuntime(page) {
        const runtime = this._runtimes[page];
        if (runtime && Array.isArray(runtime.cleanups)) {
            runtime.cleanups.splice(0).reverse().forEach((cleanup) => {
                try { cleanup(); } catch (e) { /* noop */ }
            });
        }
        delete this._runtimes[page];
        if (this._activeRuntimePage === page) this._activeRuntimePage = null;
        this._clearRuntimeFlags(page);
    },

    _trackCleanup(cleanup) {
        const runtime = this._activeRuntimePage ? this._runtimes[this._activeRuntimePage] : null;
        if (runtime && typeof cleanup === 'function') runtime.cleanups.push(cleanup);
    },

    _listen(target, type, handler, options) {
        if (!target || !target.addEventListener || !target.removeEventListener) return;
        target.addEventListener(type, handler, options);
        const capture = typeof options === 'boolean' ? options : Boolean(options && options.capture);
        this._trackCleanup(() => target.removeEventListener(type, handler, capture));
    },

    _observe(observer, target, options) {
        if (!observer || !target || !observer.observe) return;
        observer.observe(target, options);
        this._trackCleanup(() => observer.disconnect());
    },

    _setTimeout(handler, delay) {
        const id = window.setTimeout(handler, delay);
        this._trackCleanup(() => window.clearTimeout(id));
        return id;
    },

    _requestFrame(handler) {
        const id = window.requestAnimationFrame(handler);
        this._trackCleanup(() => window.cancelAnimationFrame(id));
        return id;
    },

    _clearRuntimeFlags(page) {
        const pageEl = document.getElementById(`page-${page}`);
        if (!pageEl) return;
        pageEl.querySelectorAll('[data-frontier-lab-control-element-observer]').forEach((node) => {
            delete node.dataset.frontierLabControlElementObserver;
        });
        pageEl.querySelectorAll('[data-frontier-lab-status-observer]').forEach((node) => {
            delete node.dataset.frontierLabStatusObserver;
            delete node.dataset.frontierLabStatusPending;
        });
        pageEl.querySelectorAll('[data-frontier-lab-status-source-preview]').forEach((node) => {
            delete node.dataset.frontierLabStatusSourcePreview;
        });
        pageEl.querySelectorAll('[data-frontier-lab-panel-observer]').forEach((node) => {
            delete node.dataset.frontierLabPanelObserver;
        });
        pageEl.querySelectorAll('.frontier-section-rail[data-bound]').forEach((node) => {
            delete node.dataset.bound;
        });
        pageEl.querySelectorAll('[data-frontier-lab-source-active="status"]').forEach((node) => {
            delete node.dataset.frontierLabSourceActive;
        });
        pageEl.querySelectorAll('[data-frontier-lab-source-arrival="status"]').forEach((node) => {
            delete node.dataset.frontierLabSourceArrival;
        });
        pageEl.querySelectorAll('.frontier-lab-status__item[data-frontier-lab-status-active="true"]').forEach((node) => {
            delete node.dataset.frontierLabStatusActive;
            node.setAttribute('aria-pressed', 'false');
        });
    },

    renderPage(page) {
        const pageEl = document.getElementById(`page-${page}`);
        const shell = pageEl ? pageEl.querySelector(`.${page}-shell`) : null;
        const learning = CONFIG.learningDesign.subjects && CONFIG.learningDesign.subjects[page];
        const meta = CONFIG.pages && CONFIG.pages[page];
        if (!pageEl || !shell || !learning || !meta) return;
        this.hideLegacyOverview(page, shell);
        shell.classList.add('frontier-study-shell');
        if (!shell.querySelector('.frontier-brief')) {

        const subjectLinks = [
            '<a href="#frontier">未来星系总览</a>',
            ...this.pages.map((id) => {
            const item = CONFIG.pages[id] || {};
            const label = this.escape(item.label || id);
            const active = id === page ? ' aria-current="page"' : '';
            return `<a href="#${this.escapeAttr(id)}"${active}>${label}</a>`;
            })
        ].join('');

        const sourceItems = this.getSourceItems(learning, page);
        const sourceLinks = sourceItems.map((source) => this.renderSourceItem(source)).join('');
        const sourceSummary = sourceItems.length
            ? `本页列出 ${sourceItems.length} 条资料，用于回查概念定义、模型边界和拓展阅读。`
            : '本页会在学习框架中列出可回查的公开资料。';

        const title = `${this.escape(meta.title || meta.label || '学习主题')} · 二级总览`;
        const overview = this.escape(learning.overview || '本页围绕一个跨学科主题建立观察路径。');
        const teachingNote = this.escape(learning.teachingNote || '先确认模型假设，再解释可视化结果。');
        const guardrail = this.escape(learning.guardrail || '不要只看图形结果；先回到模型假设、样本范围和来源资料。');
        const sourceNote = this.escape(CONFIG.learningDesign.sourceNote || '学习内容参考开放教材与权威资料。');

        const frame = document.createElement('section');
        frame.className = 'frontier-brief';
        frame.setAttribute('aria-label', `${meta.label || meta.title}学习框架`);
        frame.innerHTML = `
            <div class="frontier-brief__head">
                <span class="frontier-brief__mark"><i data-lucide="sparkles"></i>未来星系二级目录</span>
                <h2>${title}</h2>
                <p>${sourceNote}</p>
            </div>
            <nav class="frontier-brief__nav" aria-label="未来星系二级目录">
                ${subjectLinks}
            </nav>
            <div class="frontier-brief__grid">
                <article class="frontier-brief__card">
                    <span><i data-lucide="target"></i>学习任务</span>
                    <p>${overview}</p>
                </article>
                <article class="frontier-brief__card">
                    <span><i data-lucide="sliders-horizontal"></i>模型边界</span>
                    <p>${teachingNote}</p>
                </article>
                <article class="frontier-brief__card frontier-brief__card--guardrail">
                    <span><i data-lucide="shield-check"></i>误解防护</span>
                    <p>${guardrail}</p>
                </article>
                <article class="frontier-brief__card frontier-brief__card--sources">
                    <span><i data-lucide="book-open-check"></i>来源索引</span>
                    <p class="frontier-brief__source-summary">${this.escape(sourceSummary)}</p>
                    <div class="frontier-brief__sources">${sourceLinks}</div>
                </article>
            </div>
        `;

        shell.insertBefore(frame, shell.firstElementChild);
        }
        this.renderSubjectOverview(page, shell, learning, meta);
        this.renderPathway(page, shell, learning, meta);
    },

    hideLegacyOverview(page, shell) {
        const selector = `.${page}-overview`;
        const overview = shell ? shell.querySelector(selector) : null;
        if (!overview) return;
        overview.hidden = true;
        overview.dataset.frontierLegacyOverview = 'hidden';
    },

    renderSubjectOverview(page, shell, learning, meta) {
        if (!shell || shell.querySelector('.frontier-subject-overview')) return;
        const modules = this.subjectModules[page] || [];
        if (!modules.length) return;

        const cards = modules.map((item, index) => `
            <a class="frontier-subject-module" href="${this.escapeAttr(item.href || '#')}" data-frontier-subject-module="${this.escapeAttr(page)}-${index + 1}">
                <span class="frontier-subject-module__index">${String(index + 1).padStart(2, '0')}</span>
                <i data-lucide="${this.escapeAttr(item.icon || 'sparkles')}"></i>
                <strong>${this.escape(item.label)}</strong>
                <p>${this.escape(item.note)}</p>
            </a>
        `).join('');

        const overview = document.createElement('section');
        overview.className = 'frontier-subject-overview';
        overview.setAttribute('aria-label', `${meta.label || meta.title}学科总览`);
        overview.innerHTML = `
            <div class="frontier-subject-overview__head">
                <span><i data-lucide="layout-dashboard"></i>学科总览</span>
                <h2>${this.escape(meta.label || meta.title || '学习主题')} · 先选模块再进入细节</h2>
                <p>${this.escape(learning.overview || '先建立主题坐标，再进入实验、判读和资料回查。')}</p>
            </div>
            <div class="frontier-subject-overview__grid">
                ${cards}
            </div>
        `;

        const brief = shell.querySelector('.frontier-brief');
        if (brief) {
            brief.insertAdjacentElement('afterend', overview);
        } else {
            shell.insertBefore(overview, shell.firstElementChild);
        }
    },

    renderPathway(page, shell, learning, meta) {
        if (!shell) return;
        const sections = this.collectSections(page, shell);
        if (!sections.length) return;

        if (!shell.querySelector('.frontier-pathway')) {
            const links = sections.map((item) => {
                const evidence = item.evidence
                    ? `<em class="frontier-pathway__evidence"><i data-lucide="book-marked"></i>${this.escape(item.evidence)}</em>`
                    : '';
                return `
                    <a class="frontier-pathway__step" href="#${this.escapeAttr(item.id)}" data-frontier-target="${this.escapeAttr(item.id)}">
                        <span>${item.index}</span>
                        <strong>${this.escape(item.label)}</strong>
                        <p>${this.escape(item.note)}</p>
                        ${evidence}
                    </a>
                `;
            }).join('');

            const sourceCount = this.getSourceItems(learning, page).length;
            const pathway = document.createElement('section');
            pathway.className = 'frontier-pathway';
            pathway.setAttribute('aria-label', `${meta.label || meta.title}页内学习路径`);
            pathway.innerHTML = `
                <div class="frontier-pathway__head">
                    <span><i data-lucide="route"></i>页内学习路径</span>
                    <h2>${this.escape(meta.label || meta.title || '学习主题')} · 从问题到证据</h2>
                    <p>按顺序完成概览、模型、实验台、判读和资料核对，避免只看动画而跳过模型边界。</p>
                </div>
                <div class="frontier-pathway__meta" aria-label="本页结构摘要">
                    <div><span>路径节点</span><strong>${sections.length}</strong></div>
                    <div><span>资料来源</span><strong>${sourceCount}</strong></div>
                </div>
                <nav class="frontier-pathway__steps" aria-label="${meta.label || meta.title}页内目录">
                    ${links}
                </nav>
            `;

            const brief = shell.querySelector('.frontier-brief');
            if (brief) {
                brief.insertAdjacentElement('afterend', pathway);
            } else {
                shell.insertBefore(pathway, shell.firstElementChild);
            }
        }

        this.renderSectionRail(page, shell, sections, meta);
        this.bindSectionRail(page, shell, sections);
        this.refreshIcons();
    },

    collectSections(page, shell) {
        const plan = this.sectionPlans[page] || [];
        return plan.map((item, index) => {
            const target = shell.querySelector(item.selector);
            if (!target) return null;
            const id = target.id || `frontier-${page}-${item.key}`;
            const stepIndex = String(index + 1).padStart(2, '0');
            target.id = id;
            target.classList.add('frontier-anchor-section');
            target.classList.toggle('frontier-anchor-section--overview', item.key === 'overview');
            target.classList.toggle('frontier-anchor-section--body', item.key !== 'overview');
            target.classList.toggle('frontier-anchor-section--lab', item.key === 'lab');
            if (item.key === 'lab') {
                this.decorateLabSection(page, target, item);
            }
            target.dataset.frontierIndex = stepIndex;
            target.dataset.frontierLabel = item.label;
            target.dataset.frontierNote = item.note;
            if (item.key !== 'overview') {
                this.ensureSectionContext(target, item, stepIndex, id);
            }
            return {
                id,
                index: stepIndex,
                label: item.label,
                note: item.note,
                evidence: item.evidence || '',
                protocol: item.protocol || null
            };
        }).filter(Boolean);
    },

    decorateLabSection(page, target, item) {
        if (!target) return;
        const selectors = this.labDecorators[page] || {};
        const roleNodes = {};
        target.classList.add('frontier-lab-stage');
        target.dataset.frontierLab = page;
        this.decorateLabShell(page, target, item);
        this.decorateLabHeader(page, target, item);

        [
            ['workbench', selectors.workbench, 'frontier-lab-workbench'],
            ['controls', selectors.controls, 'frontier-lab-controls'],
            ['canvas', selectors.canvas, 'frontier-lab-canvas'],
            ['readout', selectors.readout, 'frontier-lab-readout']
        ].forEach(([role, selector, className]) => {
            const node = selector ? target.querySelector(selector) : null;
            if (!node) return;
            roleNodes[role] = node;
            node.classList.add(className);
            node.dataset.frontierLabRole = role;
            this.decorateLabZone(node, role, page);
            if (role === 'controls') {
                this.decorateLabControlPanels(node);
            }
            if (role === 'canvas') {
                this.decorateLabCanvas(node, page, item);
            }
            if (role === 'readout') {
                this.decorateLabReadoutPanels(node);
            }
        });
        this.decorateLabLayout(target, roleNodes);
        const labContainer = roleNodes.workbench || target;
        this.renderLabInstrumentHeader(labContainer, item);
        this.renderLabEvidence(labContainer, item);
        this.renderLabFlow(labContainer, item);
        this.renderLabStatus(labContainer, item, roleNodes);
    },

    decorateLabShell(page, target, item) {
        if (!target) return;
        target.classList.add('frontier-lab-shell');
        target.dataset.frontierLabShell = 'active';
        target.dataset.frontierLabShellPage = page || 'frontier';
        if (!target.getAttribute('aria-label') && !target.getAttribute('aria-labelledby')) {
            target.setAttribute('aria-label', `${this.escapeAttr(item.label || '实验台')}学习舱体`);
        }
    },

    decorateLabHeader(page, target, item) {
        if (!target) return;
        const header = Array.from(target.children || [])
            .find((child) => child.nodeType === 1 && /(^|\s)[\w-]+-lab__header(\s|$)/.test(child.className || ''));
        if (!header) return;

        header.classList.add('frontier-lab-header');
        header.dataset.frontierLabHeader = page || 'frontier';
        header.setAttribute('aria-label', `${this.escapeAttr(item.label || '实验台')}标题区`);

        const copy = header.querySelector('div');
        if (copy) copy.classList.add('frontier-lab-header__copy');

        const eyebrow = Array.from(header.querySelectorAll('span'))
            .find((node) => /(^|\s)[\w-]+-lab__eyebrow(\s|$)/.test(node.className || ''));
        if (eyebrow) {
            eyebrow.classList.add('frontier-lab-header__eyebrow');
            eyebrow.dataset.frontierLabHeaderRole = 'eyebrow';
        }

        const title = header.querySelector('h2');
        if (title) title.classList.add('frontier-lab-header__title');

        const description = copy ? copy.querySelector('p') : header.querySelector('p');
        if (description) description.classList.add('frontier-lab-header__desc');

        const badge = Array.from(header.children || [])
            .find((node) => node.tagName === 'SPAN' && /(^|\s)[\w-]+-lab__badge(\s|$)/.test(node.className || ''));
        if (badge) {
            badge.classList.add('frontier-lab-header__badge');
            badge.dataset.frontierLabHeaderRole = 'badge';
        }
    },

    decorateLabZone(node, role, page) {
        const zones = {
            controls: ['input', '调参区', '调整变量与操作入口'],
            canvas: ['visual', '可视区', '承载模型画布与读图标记'],
            readout: ['feedback', '读数区', '汇总观察量与边界反馈']
        };
        const zone = zones[role];
        if (!node || !zone) return;
        node.classList.add('frontier-lab-zone');
        node.dataset.frontierLabZone = zone[0];
        node.dataset.frontierLabZoneLabel = zone[1];
        node.dataset.frontierLabZoneNote = zone[2];
        node.dataset.frontierLabZonePage = page || 'frontier';
        this.renderLabZoneHeader(node, zone[0], zone[1], zone[2]);
        this.ensureLabSourceId(node, page, role);
    },

    renderLabZoneHeader(node, key, label, note) {
        if (!node) return;
        const existing = Array.from(node.children || [])
            .find((child) => child.nodeType === 1 && child.classList.contains('frontier-lab-zone-head'));
        const header = existing || document.createElement('div');
        const signature = `${key || 'zone'}|${label || '分区'}|${note || ''}`;
        header.className = 'frontier-lab-zone-head';
        header.dataset.frontierLabZoneHead = key || 'zone';
        if (header.dataset.frontierLabZoneSignature !== signature) {
            header.dataset.frontierLabZoneSignature = signature;
            header.innerHTML = `
                <span class="frontier-lab-zone-head__mark">${this.escape((key || 'zone').toUpperCase())}</span>
                <strong>${this.escape(label || '分区')}</strong>
                <em>${this.escape(note || '')}</em>
            `;
        }
        if (!existing) {
            node.insertBefore(header, node.firstElementChild);
        }
    },

    decorateLabLayout(target, roleNodes) {
        const workbench = roleNodes && roleNodes.workbench ? roleNodes.workbench : target;
        if (!workbench) return;
        workbench.dataset.frontierLabLayout = 'instrument';
        workbench.dataset.frontierLabLayoutRoles = ['controls', 'canvas', 'readout']
            .filter((role) => roleNodes && roleNodes[role])
            .join(' ');
        if (target) target.dataset.frontierLabLayout = 'instrument';
    },

    decorateLabControlPanels(controls) {
        if (!controls) return;
        controls.dataset.frontierLabControls = 'true';

        Array.from(controls.children || []).forEach((child) => {
            child.classList.add('frontier-lab-control-panel');
            child.dataset.frontierLabControl = this.getLabControlKind(child);
        });
        this.decorateLabControlElements(controls);
        this.bindLabControlElementObserver(controls);
    },

    decorateLabControlElements(controls) {
        if (!controls) return;
        Array.from(controls.querySelectorAll('button')).forEach((button) => {
            button.classList.add('frontier-lab-control-button');
            button.dataset.frontierLabControlElement = 'button';
        });
        Array.from(controls.querySelectorAll('input[type="range"]')).forEach((input) => {
            input.classList.add('frontier-lab-range');
            input.dataset.frontierLabControlElement = 'range';
        });
    },

    bindLabControlElementObserver(controls) {
        if (!controls || controls.dataset.frontierLabControlElementObserver === 'true' || typeof MutationObserver === 'undefined') return;
        controls.dataset.frontierLabControlElementObserver = 'true';
        const observer = new MutationObserver((mutations) => {
            const hasControlElement = mutations.some((mutation) => Array.from(mutation.addedNodes || []).some((node) => {
                if (node.nodeType !== 1) return false;
                if (node.matches && node.matches('button, input[type="range"]')) return true;
                return Boolean(node.querySelector && node.querySelector('button, input[type="range"]'));
            }));
            if (hasControlElement) this.decorateLabControlElements(controls);
        });
        this._observe(observer, controls, { childList: true, subtree: true });
    },

    getLabControlKind(child) {
        const className = child && child.className ? child.className : '';
        if (/note/.test(className)) return 'boundary-note';
        if (/actions/.test(className)) return 'action-group';
        const buttons = child ? child.querySelectorAll('button').length : 0;
        const ranges = child ? child.querySelectorAll('input[type="range"]').length : 0;
        const actionButton = child && child.querySelector('button[id$="step"], button[id$="fit"], button[id$="reset"]');
        if (actionButton) return 'action-group';
        if (/presets|samples|modes|buttons|processes|focus-list/.test(className) || (buttons > 1 && ranges === 0)) return 'option-group';
        return 'parameter';
    },

    decorateLabCanvas(canvasFrame, page, item) {
        if (!canvasFrame) return;
        canvasFrame.dataset.frontierLabCanvas = page || 'visual-stage';
        canvasFrame.setAttribute('aria-label', canvasFrame.getAttribute('aria-label') || '实验台可视化画布');

        Array.from(canvasFrame.querySelectorAll('canvas, svg')).forEach((surface) => {
            surface.classList.add('frontier-lab-canvas-surface');
            surface.dataset.frontierLabSurface = surface.tagName.toLowerCase();
        });

        Array.from(canvasFrame.children || []).forEach((child) => {
            if (/^(CANVAS|SVG)$/.test(child.tagName)) return;
            child.classList.add('frontier-lab-canvas-layer');
        });

        this.renderLabLegend(canvasFrame, item);
        this.renderLabCanvasAnnotations(canvasFrame, item);
    },

    renderLabLegend(canvasFrame, item) {
        const legend = item && Array.isArray(item.legend) ? item.legend : [];
        if (!canvasFrame || !legend.length) return;
        const existing = canvasFrame.querySelector('.frontier-lab-legend');
        const panel = existing || document.createElement('div');
        const rows = legend.map((entry) => `
            <span class="frontier-lab-legend__item" data-frontier-legend-tone="${this.escapeAttr(entry.tone || 'signal')}">
                <i aria-hidden="true"></i>
                <b>${this.escape(entry.label || '')}</b>
                <em>${this.escape(entry.note || '')}</em>
            </span>
        `).join('');
        panel.className = 'frontier-lab-legend frontier-lab-canvas-layer';
        panel.setAttribute('aria-label', `${this.escapeAttr(item.label || '实验台')}图例`);
        panel.innerHTML = `
            <span class="frontier-lab-legend__title">图例</span>
            <span class="frontier-lab-legend__items">${rows}</span>
        `;
        canvasFrame.dataset.frontierLabLegend = String(legend.length);
        if (!existing) canvasFrame.insertBefore(panel, canvasFrame.firstElementChild);
    },

    renderLabCanvasAnnotations(canvasFrame, item) {
        const legend = item && Array.isArray(item.legend) ? item.legend : [];
        if (!canvasFrame || !legend.length) return;

        const existing = canvasFrame.querySelector('.frontier-lab-annotations');
        const panel = existing || document.createElement('div');
        const rows = legend.slice(0, 3).map((entry, index) => `
            <span class="frontier-lab-annotations__item" data-frontier-annotation-tone="${this.escapeAttr(entry.tone || 'signal')}">
                <b>${String(index + 1).padStart(2, '0')}</b>
                <em>${this.escape(entry.label || '')}</em>
                <i>${this.escape(entry.note || '')}</i>
            </span>
        `).join('');

        panel.className = 'frontier-lab-annotations frontier-lab-canvas-layer';
        panel.setAttribute('aria-label', `${this.escapeAttr(item.label || '实验台')}画布标注`);
        panel.innerHTML = `
            <span class="frontier-lab-annotations__title">读图层</span>
            <span class="frontier-lab-annotations__list">${rows}</span>
        `;
        canvasFrame.dataset.frontierLabAnnotations = String(Math.min(legend.length, 3));
        if (!existing) canvasFrame.appendChild(panel);
    },

    renderLabInstrumentHeader(container, item) {
        const note = item && item.note ? item.note : '';
        const evidence = item && item.evidence ? item.evidence : '';
        if (!container || (!note && !evidence)) return;

        const existing = container.querySelector('.frontier-lab-instrument');
        const panel = existing || document.createElement('div');
        const headline = item && item.label && item.label !== '实验台' ? item.label : '当前任务';
        panel.className = 'frontier-lab-instrument';
        panel.setAttribute('aria-label', `${this.escapeAttr(item.label || '实验台')}仪器栏`);
        panel.innerHTML = `
            <span class="frontier-lab-instrument__mark">实验台</span>
            <span class="frontier-lab-instrument__body">
                <strong>${this.escape(headline)}</strong>
                <em>${this.escape(note)}</em>
            </span>
            ${evidence ? `<span class="frontier-lab-instrument__source">回查 ${this.escape(evidence)}</span>` : ''}
        `;
        container.dataset.frontierLabInstrument = 'true';
        if (!existing) container.insertBefore(panel, container.firstElementChild);
    },

    renderLabEvidence(container, item) {
        const evidence = item && item.evidence ? item.evidence : '';
        const boundary = item && item.protocol && item.protocol.boundary ? item.protocol.boundary : '';
        if (!container || (!evidence && !boundary)) return;

        const existing = container.querySelector('.frontier-lab-evidence');
        const panel = existing || document.createElement('div');
        const chips = [
            ['证据回查', evidence, 'book-marked'],
            ['模型边界', boundary, 'shield-check']
        ].filter((entry) => entry[1]).map(([label, value, icon]) => `
            <span class="frontier-lab-evidence__chip">
                <i data-lucide="${this.escapeAttr(icon)}" aria-hidden="true"></i>
                <b>${this.escape(label)}</b>
                <em>${this.escape(value)}</em>
            </span>
        `).join('');

        panel.className = 'frontier-lab-evidence';
        this.ensureLabSourceId(panel, this.getLabPageFromNode(container), 'boundary');
        panel.setAttribute('aria-label', `${this.escapeAttr(item.label || '实验台')}证据边界`);
        panel.innerHTML = `
            <span class="frontier-lab-evidence__title">证据边界</span>
            <span class="frontier-lab-evidence__chips">${chips}</span>
        `;
        container.dataset.frontierLabEvidence = 'true';
        if (!existing) {
            const instrument = container.querySelector('.frontier-lab-instrument');
            if (instrument) {
                instrument.insertAdjacentElement('afterend', panel);
            } else {
                container.insertBefore(panel, container.firstElementChild);
            }
        }
    },

    renderLabFlow(container, item) {
        const protocol = item && item.protocol ? item.protocol : null;
        const evidence = item && item.evidence ? item.evidence : '';
        if (!container || !protocol) return;

        const entries = [
            ['调参', protocol.adjust, 'sliders-horizontal'],
            ['观察', protocol.observe, 'scan-line'],
            ['回查', evidence || protocol.boundary, 'book-open-check']
        ].filter((entry) => entry[1]);
        if (!entries.length) return;

        const existing = container.querySelector('.frontier-lab-flow');
        const panel = existing || document.createElement('div');
        const rows = entries.map(([label, value, icon], index) => `
            <span class="frontier-lab-flow__step" data-frontier-lab-flow-step="${index + 1}">
                <i data-lucide="${this.escapeAttr(icon)}" aria-hidden="true"></i>
                <b>${this.escape(label)}</b>
                <em>${this.escape(value)}</em>
            </span>
        `).join('');

        panel.className = 'frontier-lab-flow';
        panel.setAttribute('aria-label', `${this.escapeAttr(item.label || '实验台')}操作流`);
        panel.innerHTML = `
            <span class="frontier-lab-flow__title">操作流</span>
            <span class="frontier-lab-flow__steps">${rows}</span>
        `;
        container.dataset.frontierLabFlow = String(entries.length);

        if (!existing) {
            const evidencePanel = container.querySelector('.frontier-lab-evidence');
            if (evidencePanel) {
                evidencePanel.insertAdjacentElement('afterend', panel);
            } else {
                container.insertBefore(panel, container.firstElementChild);
            }
        }
    },

    renderLabStatus(container, item, roleNodes) {
        roleNodes = roleNodes || {};
        if (!container || (!roleNodes.controls && !roleNodes.readout)) return;

        const existing = container.querySelector('.frontier-lab-status');
        const panel = existing || document.createElement('div');
        panel.className = 'frontier-lab-status';
        panel.setAttribute('aria-label', `${this.escapeAttr(item.label || '实验台')}状态读数`);
        panel.innerHTML = `
            <span class="frontier-lab-status__title">状态读数</span>
            <span class="frontier-lab-status__items" aria-live="polite"></span>
        `;
        container.dataset.frontierLabStatus = 'true';
        if (!existing) {
            const flow = container.querySelector('.frontier-lab-flow');
            if (flow) {
                flow.insertAdjacentElement('afterend', panel);
            } else {
                container.insertBefore(panel, container.firstElementChild);
            }
        }

        const update = () => this.refreshLabStatus(panel, item, roleNodes);
        update();
        this.bindLabStatusUpdates(panel, roleNodes, update);
        this.bindLabStatusSourcePreview(panel);
    },

    refreshLabStatus(panel, item, roleNodes) {
        if (!panel) return;
        const items = panel.querySelector('.frontier-lab-status__items');
        if (!items) return;
        const entries = this.getLabStatusEntries(item, roleNodes);
        panel.dataset.frontierLabStatusItems = String(entries.length);
        items.innerHTML = entries.map(([key, label, value], index) => {
            const itemId = this.getLabStatusItemId(panel, key, index);
            const labelId = `${itemId}-label`;
            const valueId = `${itemId}-value`;
            const source = this.getLabStatusSource(panel, roleNodes, key);
            const sourceAttr = source.ids.length ? ` aria-details="${this.escapeAttr(source.ids.join(' '))}"` : '';
            const controlsAttr = source.ids.length ? ` aria-controls="${this.escapeAttr(source.ids.join(' '))}"` : '';
            return `
            <button type="button" class="frontier-lab-status__item" id="${this.escapeAttr(itemId)}" data-frontier-lab-status-key="${this.escapeAttr(key)}" data-frontier-lab-status-index="${String(index + 1).padStart(2, '0')}" data-frontier-lab-status-source="${this.escapeAttr(source.type)}" data-frontier-lab-status-source-ids="${this.escapeAttr(source.ids.join(' '))}" data-frontier-lab-status-source-label="${this.escapeAttr(source.label)}" aria-labelledby="${this.escapeAttr(labelId)}" aria-describedby="${this.escapeAttr(valueId)}" aria-pressed="false"${sourceAttr}${controlsAttr}>
                <b id="${this.escapeAttr(labelId)}" data-frontier-lab-status-part="label">${this.escape(label)}</b>
                <em id="${this.escapeAttr(valueId)}" data-frontier-lab-status-part="value">${this.escape(value)}</em>
            </button>
        `;
        }).join('');
    },

    getLabStatusEntries(item, roleNodes) {
        const controlSummary = this.getLabControlSummary(roleNodes.controls);
        const readoutSummary = this.getLabReadoutSummary(roleNodes.readout);
        const boundary = item && item.protocol && item.protocol.boundary ? item.protocol.boundary : '';

        return [
            ['control', '当前调参', controlSummary],
            ['readout', '观测读数', readoutSummary],
            ['boundary', '模型边界', boundary]
        ].filter((entry) => entry[2]);
    },

    getLabStatusItemId(panel, key, index) {
        const lab = panel && panel.closest ? panel.closest('.frontier-lab-stage') : null;
        const page = lab && lab.dataset.frontierLab ? lab.dataset.frontierLab : 'frontier';
        return `frontier-lab-status-${this.normalizeLabReadoutId(page)}-${this.normalizeLabReadoutId(key)}-${String((index || 0) + 1).padStart(2, '0')}`;
    },

    getLabStatusSource(panel, roleNodes, key) {
        const page = this.getLabPageFromNode(panel);
        const map = {
            control: {
                type: 'controls',
                label: '控件区',
                nodes: [roleNodes && roleNodes.controls]
            },
            readout: {
                type: 'readout',
                label: '读数区',
                nodes: [roleNodes && roleNodes.readout]
            },
            boundary: {
                type: 'boundary',
                label: '边界条',
                nodes: [panel && panel.parentElement ? panel.parentElement.querySelector('.frontier-lab-evidence') : null]
            }
        };
        const source = map[key] || { type: 'unknown', label: '来源', nodes: [] };
        const ids = source.nodes
            .filter(Boolean)
            .map((node, index) => this.ensureLabSourceId(node, page, source.type || key, index))
            .filter(Boolean);
        return {
            type: source.type,
            label: source.label,
            ids
        };
    },

    ensureLabSourceId(node, page, role, index) {
        if (!node) return '';
        const suffix = index ? `-${String(index + 1).padStart(2, '0')}` : '';
        const id = node.id || `frontier-lab-source-${this.normalizeLabReadoutId(page || this.getLabPageFromNode(node))}-${this.normalizeLabReadoutId(role || 'source')}${suffix}`;
        node.id = id;
        node.dataset.frontierLabSource = role || 'source';
        if (!node.hasAttribute('tabindex')) {
            node.setAttribute('tabindex', '-1');
        }
        return id;
    },

    getLabPageFromNode(node) {
        const lab = node && node.closest ? node.closest('.frontier-lab-stage') : null;
        return lab && lab.dataset.frontierLab ? lab.dataset.frontierLab : 'frontier';
    },

    getLabControlSummary(controls) {
        if (!controls) return '';
        const activeButtons = Array.from(controls.querySelectorAll('button[aria-pressed="true"], button.is-active, button.active'))
            .map((node) => this.getCompactText(node))
            .filter(Boolean);

        const rangeValues = Array.from(controls.querySelectorAll('input[type="range"]'))
            .map((input) => this.getRangeStatusText(controls, input))
            .filter(Boolean);

        return this.compactStatusValue(this.uniqueStatusParts([...activeButtons, ...rangeValues]).slice(0, 4).join(' / '), 72);
    },

    getRangeStatusText(controls, input) {
        if (!input) return '';
        const labels = Array.from(controls.querySelectorAll('label'));
        const linked = input.id ? labels.find((label) => label.getAttribute('for') === input.id) : null;
        const label = linked || input.closest('label') || (input.closest('.frontier-lab-control-panel') || input.parentElement || controls).querySelector('label');
        const name = label ? this.getCompactText(label.querySelector('span')) : '';
        const value = label ? this.getCompactText(label.querySelector('strong')) : '';
        const fallback = input.value ? this.getCompactText(input) || input.value : '';
        return [name, value || fallback].filter(Boolean).join(' ');
    },

    getLabReadoutSummary(readout) {
        if (!readout) return '';
        const panels = this.getLabReadoutPanels(readout)
            .slice(0, 3);
        const parts = panels.map((panel) => {
            if (panel.dataset.frontierLabReadoutSummary) return panel.dataset.frontierLabReadoutSummary;
            const label = this.getCompactText(panel.querySelector('[class$="__label"], [class*="__label"]'));
            const value = this.getCompactText(panel.querySelector('strong'));
            return [label, value].filter(Boolean).join(' ');
        }).filter(Boolean);
        return this.compactStatusValue(this.uniqueStatusParts(parts).join(' / '), 84);
    },

    bindLabStatusUpdates(panel, roleNodes, update) {
        if (!panel || panel.dataset.frontierLabStatusObserver === 'true') return;
        panel.dataset.frontierLabStatusObserver = 'true';

        const schedule = () => {
            if (panel.dataset.frontierLabStatusPending === 'true') return;
            panel.dataset.frontierLabStatusPending = 'true';
            this._requestFrame(() => {
                panel.dataset.frontierLabStatusPending = 'false';
                update();
            });
        };

        ['click', 'input', 'change'].forEach((eventName) => {
            if (roleNodes.controls) this._listen(roleNodes.controls, eventName, schedule, true);
            if (roleNodes.readout) this._listen(roleNodes.readout, eventName, schedule, true);
        });

        if (typeof MutationObserver === 'undefined') return;
        const observer = new MutationObserver(schedule);
        if (roleNodes.controls) {
            this._observe(observer, roleNodes.controls, {
                subtree: true,
                attributes: true,
                attributeFilter: ['aria-pressed', 'class', 'value']
            });
        }
        if (roleNodes.readout) {
            this._observe(observer, roleNodes.readout, {
                subtree: true,
                childList: true,
                characterData: true
            });
        }
    },

    bindLabStatusSourcePreview(panel) {
        if (!panel || panel.dataset.frontierLabStatusSourcePreview === 'true') return;
        panel.dataset.frontierLabStatusSourcePreview = 'true';
        const clear = () => {
            const lab = panel.closest ? panel.closest('.frontier-lab-stage') : null;
            if (!lab) return;
            lab.querySelectorAll('[data-frontier-lab-source-active="status"]').forEach((node) => {
                delete node.dataset.frontierLabSourceActive;
            });
            lab.querySelectorAll('[data-frontier-lab-source-arrival="status"]').forEach((node) => {
                delete node.dataset.frontierLabSourceArrival;
            });
            lab.querySelectorAll('.frontier-lab-status__item[data-frontier-lab-status-active="true"]').forEach((node) => {
                delete node.dataset.frontierLabStatusActive;
                node.setAttribute('aria-pressed', 'false');
            });
        };
        const isActiveSource = (node) => Boolean(node && node.closest && node.closest('[data-frontier-lab-source-active="status"]'));
        const shouldKeepActive = (node) => panel.contains(node) || isActiveSource(node) || isActiveSource(document.activeElement);
        const arrivalTimers = new WeakMap();
        const focusSource = (source) => {
            if (!source || !source.focus) return;
            try {
                source.focus({ preventScroll: true });
            } catch (error) {
                source.focus();
            }
        };
        const showArrival = (source) => {
            if (!source) return;
            const previousTimer = arrivalTimers.get(source);
            if (previousTimer) {
                window.clearTimeout(previousTimer);
            }
            delete source.dataset.frontierLabSourceArrival;
            void source.offsetWidth;
            source.dataset.frontierLabSourceArrival = 'status';
            const timer = this._setTimeout(() => {
                if (source.dataset.frontierLabSourceArrival === 'status') {
                    delete source.dataset.frontierLabSourceArrival;
                }
                arrivalTimers.delete(source);
            }, 900);
            arrivalTimers.set(source, timer);
        };
        const activate = (target, options) => {
            const item = target && target.closest ? target.closest('.frontier-lab-status__item') : null;
            if (!item) return;
            clear();
            const ids = (item.dataset.frontierLabStatusSourceIds || '').split(/\s+/).filter(Boolean);
            const sources = ids.map((id) => document.getElementById(id)).filter(Boolean);
            item.dataset.frontierLabStatusActive = 'true';
            item.setAttribute('aria-pressed', 'true');
            sources.forEach((source) => {
                source.dataset.frontierLabSourceActive = 'status';
            });
            if (options && options.locate && sources[0] && sources[0].scrollIntoView) {
                sources[0].scrollIntoView({ block: 'nearest', inline: 'nearest' });
                showArrival(sources[0]);
                this._requestFrame(() => focusSource(sources[0]));
            }
        };
        this._listen(panel, 'pointerover', (event) => activate(event.target));
        this._listen(panel, 'mouseover', (event) => activate(event.target));
        this._listen(panel, 'click', (event) => activate(event.target, { locate: true }));
        this._listen(panel, 'focusin', (event) => activate(event.target));
        this._listen(panel, 'keydown', (event) => {
            if (event.key !== 'Enter' && event.key !== ' ' && event.key !== 'Spacebar') return;
            event.preventDefault();
            activate(event.target, { locate: true });
        });
        this._listen(panel, 'pointerout', (event) => {
            if (!shouldKeepActive(event.relatedTarget)) clear();
        });
        this._listen(panel, 'mouseout', (event) => {
            if (!shouldKeepActive(event.relatedTarget)) clear();
        });
        this._listen(panel, 'focusout', (event) => {
            if (!shouldKeepActive(event.relatedTarget)) clear();
        });
        this._trackCleanup(clear);
    },

    uniqueStatusParts(parts) {
        const seen = new Set();
        return parts.filter((part) => {
            const value = this.compactStatusValue(part, 96);
            if (!value || seen.has(value)) return false;
            seen.add(value);
            return true;
        });
    },

    getCompactText(node) {
        return node && node.textContent ? node.textContent.trim().replace(/\s+/g, ' ') : '';
    },

    compactStatusValue(value, limit) {
        const text = value ? String(value).trim().replace(/\s+/g, ' ') : '';
        if (!text || !limit || text.length <= limit) return text;
        return `${text.slice(0, Math.max(0, limit - 1))}…`;
    },

    decorateLabReadoutPanels(readout) {
        if (!readout) return;
        readout.setAttribute('aria-label', readout.getAttribute('aria-label') || '实验台读数反馈');

        const decorate = (root) => {
            this.renderLabZoneHeader(root, 'feedback', '读数区', '汇总观察量与边界反馈');
            const panels = this.getLabReadoutPanels(root);
            panels.forEach((child, index) => {
                child.classList.add('frontier-lab-readout-panel');
                child.dataset.frontierLabRole = 'feedback-panel';
                child.dataset.frontierLabReadoutIndex = String(index + 1).padStart(2, '0');
                this.decorateLabReadoutPanelParts(child, index);
            });
            readout.dataset.frontierLabReadoutCount = String(panels.length);
            this.renderLabReadoutHeader(root, panels);
        };

        decorate(readout);
        if (readout.dataset.frontierLabPanelObserver === 'true' || typeof MutationObserver === 'undefined') return;
        readout.dataset.frontierLabPanelObserver = 'true';

        const observer = new MutationObserver((mutations) => {
            const changed = mutations.some((mutation) => (
                mutation.type === 'characterData' ||
                ((mutation.addedNodes || []).length > 0) ||
                ((mutation.removedNodes || []).length > 0)
            ));
            if (changed) decorate(readout);
        });
        this._observe(observer, readout, { childList: true, subtree: true, characterData: true });
    },

    getLabReadoutPanels(readout) {
        return Array.from((readout && readout.children) || [])
            .filter((child) => child.nodeType === 1
                && !child.classList.contains('frontier-lab-zone-head')
                && !child.classList.contains('frontier-lab-readout-head'));
    },

    renderLabReadoutHeader(readout, panels) {
        if (!readout) return;
        const panelList = panels || this.getLabReadoutPanels(readout);
        const labels = panelList.map((panel) => this.getLabReadoutLabel(panel)).filter(Boolean);
        const summary = labels.slice(0, 4).join(' / ');
        const title = panelList.length ? `${panelList.length} 项` : '待刷新';
        const signature = `${title}|${summary}`;
        let header = Array.from(readout.children || [])
            .find((child) => child.nodeType === 1 && child.classList.contains('frontier-lab-readout-head'));
        if (!header) {
            header = document.createElement('div');
            header.className = 'frontier-lab-readout-head';
            header.dataset.frontierLabReadoutHead = 'true';
            readout.insertBefore(header, panelList[0] || null);
        }
        if (header.dataset.frontierLabReadoutSignature === signature) return;
        header.dataset.frontierLabReadoutSignature = signature;
        header.setAttribute('aria-label', `读数反馈：${title}`);
        header.innerHTML = `
            <span class="frontier-lab-readout-head__mark">读数反馈</span>
            <strong>${this.escape(title)}</strong>
            ${summary ? `<em>${this.escape(summary)}</em>` : ''}
        `;
    },

    decorateLabReadoutPanelParts(panel, index) {
        if (!panel) return;
        const label = panel.querySelector('.frontier-lab-readout-label, [class$="panel__label"]');
        if (label) {
            label.classList.add('frontier-lab-readout-label');
            label.dataset.frontierLabReadoutPart = 'label';
        }
        const valueNodes = Array.from(panel.querySelectorAll('strong'));
        valueNodes.forEach((node) => {
            node.classList.add('frontier-lab-readout-value');
            node.dataset.frontierLabReadoutPart = 'value';
        });
        const noteNodes = Array.from(panel.querySelectorAll('p'));
        noteNodes.forEach((node) => {
            node.classList.add('frontier-lab-readout-note');
            node.dataset.frontierLabReadoutPart = 'note';
        });

        const labelText = this.getLabReadoutLabel(panel);
        const valueText = this.getLabReadoutValue(panel);
        const readoutKey = this.getLabReadoutKey(labelText, index);
        const panelId = this.getLabReadoutPanelId(panel, readoutKey, index);
        const labelId = label ? this.assignLabReadoutPartId(label, panelId, 'label', 0) : '';
        const valueIds = valueNodes.map((node, nodeIndex) => this.assignLabReadoutPartId(node, panelId, 'value', nodeIndex));
        const noteIds = noteNodes.map((node, nodeIndex) => this.assignLabReadoutPartId(node, panelId, 'note', nodeIndex));
        const labelledBy = [labelId, valueIds[0]].filter(Boolean).join(' ');
        const describedBy = noteIds.filter(Boolean).join(' ');
        panel.dataset.frontierLabReadoutKey = readoutKey;
        panel.dataset.frontierLabReadoutLabel = labelText || '';
        panel.dataset.frontierLabReadoutTone = this.getLabReadoutTone(readoutKey, labelText);
        panel.dataset.frontierLabReadoutId = panelId;
        panel.dataset.frontierLabReadoutSummary = this.getLabReadoutAria(labelText, valueText, index);
        panel.id = panelId;
        panel.setAttribute('role', 'group');
        panel.setAttribute('aria-label', this.getLabReadoutAria(labelText, valueText, index));
        if (labelledBy) {
            panel.setAttribute('aria-labelledby', labelledBy);
        } else {
            panel.removeAttribute('aria-labelledby');
        }
        if (describedBy) {
            panel.setAttribute('aria-describedby', describedBy);
        } else {
            panel.removeAttribute('aria-describedby');
        }
    },

    getLabReadoutLabel(panel) {
        const label = panel ? panel.querySelector('.frontier-lab-readout-label, [class$="panel__label"]') : null;
        return this.getCompactText(label);
    },

    getLabReadoutValue(panel) {
        const value = panel ? panel.querySelector('.frontier-lab-readout-value, strong') : null;
        return this.compactStatusValue(this.getCompactText(value), 72);
    },

    getLabReadoutKey(label, index) {
        const map = {
            '太阳赤纬': 'solar-declination',
            '正午太阳高度': 'solar-noon-altitude',
            '理论昼长': 'daylight-duration',
            '季节判断': 'season-reading',
            '支座反力': 'support-reaction',
            '最大杆力': 'maximum-member-force',
            '当前荷载': 'active-load',
            '近零杆件': 'near-zero-member',
            '当前模型': 'current-model',
            '损失与解释度': 'loss-fit',
            '最小二乘线': 'least-squares-line',
            '读图边界': 'reading-boundary',
            'DNS': 'dns-resolution',
            'TCP': 'tcp-transfer',
            'IPv6': 'ipv6-network',
            '逐跳转发': 'hop-forwarding',
            '晶体结构': 'crystal-structure',
            '晶胞数据': 'unit-cell',
            '晶粒尺度': 'grain-size',
            '性能趋势': 'property-trend',
            '适用范围': 'model-scope',
            '词项分布': 'term-distribution',
            '回读位置': 'close-reading-position',
            '共现线索': 'cooccurrence-clue',
            '方法边界': 'method-boundary'
        };
        if (label && map[label]) return map[label];
        return `metric-${String((index || 0) + 1).padStart(2, '0')}`;
    },

    getLabReadoutPanelId(panel, key, index) {
        const lab = panel && panel.closest ? panel.closest('.frontier-lab-stage') : null;
        const page = lab && lab.dataset.frontierLab ? lab.dataset.frontierLab : 'frontier';
        return `frontier-lab-readout-${this.normalizeLabReadoutId(page)}-${this.normalizeLabReadoutId(key)}-${String((index || 0) + 1).padStart(2, '0')}`;
    },

    assignLabReadoutPartId(node, panelId, part, index) {
        if (!node || !panelId || !part) return '';
        const suffix = index ? `-${index + 1}` : '';
        const id = `${panelId}-${part}${suffix}`;
        node.id = id;
        return id;
    },

    normalizeLabReadoutId(value) {
        const slug = String(value || '')
            .trim()
            .toLowerCase()
            .replace(/[^a-z0-9_-]+/g, '-')
            .replace(/^-+|-+$/g, '');
        return slug || 'metric';
    },

    getLabReadoutTone(key, label) {
        const text = `${key || ''} ${label || ''}`;
        if (/boundary|scope|边界|范围/.test(text)) return 'boundary';
        if (/model|structure|unit-cell|dns|tcp|ipv6|模型|结构|数据/.test(text)) return 'model';
        if (/load|grain-size|active|荷载|尺度/.test(text)) return 'input';
        return 'signal';
    },

    getLabReadoutAria(label, value, index) {
        const fallback = `读数 ${String((index || 0) + 1).padStart(2, '0')}`;
        const name = label || fallback;
        return value ? `${name}：${value}` : name;
    },

    ensureSectionContext(target, item, stepIndex, targetId) {
        const parent = target && target.parentElement;
        if (!parent) return;
        const existing = Array.from(parent.querySelectorAll('.frontier-section-context'))
            .find((node) => node.dataset.frontierFor === targetId);
        const context = existing || document.createElement('div');
        const labProtocol = this.renderLabProtocol(item);
        context.className = 'frontier-section-context';
        context.dataset.frontierFor = targetId;
        context.setAttribute('aria-label', `${item.label}本节坐标`);
        context.innerHTML = `
            <span class="frontier-section-context__index">${this.escape(stepIndex)}</span>
            <span class="frontier-section-context__label">本节坐标</span>
            <strong>${this.escape(item.label)}</strong>
            <p>${this.escape(item.note)}</p>
            ${labProtocol}
            ${item.evidence ? `<span class="frontier-section-context__evidence"><i data-lucide="book-marked"></i>证据回查：${this.escape(item.evidence)}</span>` : ''}
        `;
        if (!existing) parent.insertBefore(context, target);
    },

    renderLabProtocol(item) {
        if (!item || !item.protocol) return '';
        const entries = [
            ['调参', item.protocol.adjust],
            ['观察', item.protocol.observe],
            ['边界', item.protocol.boundary]
        ].filter((entry) => entry[1]);
        if (!entries.length) return '';
        const rows = entries.map(([label, value]) => `
            <span><b>${this.escape(label)}</b>${this.escape(value)}</span>
        `).join('');
        return `<div class="frontier-lab-protocol" aria-label="${this.escapeAttr(item.label)}实验台协议">${rows}</div>`;
    },

    renderSectionRail(page, shell, sections, meta) {
        if (!shell || shell.querySelector('.frontier-section-rail')) return;
        const links = sections.map((item, index) => {
            const current = index === 0 ? ' aria-current="location"' : '';
            return `
                <a href="#${this.escapeAttr(item.id)}" data-frontier-target="${this.escapeAttr(item.id)}"${current}>
                    <span>${item.index}</span>${this.escape(item.label)}
                </a>
            `;
        }).join('');
        const rail = document.createElement('nav');
        rail.className = 'frontier-section-rail';
        rail.setAttribute('aria-label', `${meta.label || meta.title}章节航线`);
        rail.innerHTML = `
            <div class="frontier-section-rail__inner">
                <span class="frontier-section-rail__label"><i data-lucide="compass"></i>学习航线</span>
                <div class="frontier-section-rail__links">
                    ${links}
                </div>
            </div>
        `;
        const brief = shell.querySelector('.frontier-brief');
        const pathway = shell.querySelector('.frontier-pathway');
        if (pathway) {
            pathway.insertAdjacentElement('afterend', rail);
        } else if (brief) {
            brief.insertAdjacentElement('afterend', rail);
        } else {
            shell.insertBefore(rail, shell.firstElementChild);
        }
    },

    renderSourceItem(source) {
        return `
            <a class="frontier-brief__source" href="${source.url}" target="_blank" rel="noopener">${source.label}</a>
        `;
    },

    getSourceItems(learning) {
        const sources = Array.isArray(learning && learning.sources) ? learning.sources : [];
        return sources.map((source) => {
            const rawLabel = source && source.label ? String(source.label) : '';
            const rawUrl = source && source.url ? String(source.url) : '';
            const label = rawLabel ? this.escape(rawLabel) : '';
            const url = this.safeUrl(rawUrl);
            if (!label || url === '#') return null;
            return { label, url };
        }).filter(Boolean);
    },

    bindHashDetailsTarget() {
        this._listen(window, 'hashchange', () => {
            this._setTimeout(() => this.openTargetDetailsFromHash(), 0);
        });
        this._requestFrame(() => this.openTargetDetailsFromHash());
        this._setTimeout(() => this.openTargetDetailsFromHash(), 120);
    },

    openTargetDetailsFromHash() {
        const rawHash = (window.location.hash || '').slice(1);
        if (!rawHash) return;
        let target = null;
        try {
            target = document.getElementById(decodeURIComponent(rawHash));
        } catch (e) {
            target = document.getElementById(rawHash);
        }
        if (!target) return;
        const details = target.tagName && target.tagName.toLowerCase() === 'details'
            ? target
            : target.closest && target.closest('details');
        if (details && !details.open) details.open = true;
    },


    bindSectionRail(page, shell, sections) {
        const rail = shell ? shell.querySelector('.frontier-section-rail') : null;
        if (!rail || rail.dataset.bound === 'true') return;
        rail.dataset.bound = 'true';
        const update = () => {
            const pageEl = document.getElementById(`page-${page}`);
            if (!pageEl || !pageEl.classList.contains('active')) return;
            let currentId = sections[0] && sections[0].id;
            sections.forEach((item) => {
                const target = document.getElementById(item.id);
                if (!target) return;
                if (target.getBoundingClientRect().top <= 144) currentId = item.id;
            });
            rail.querySelectorAll('a[data-frontier-target]').forEach((link) => {
                const active = link.dataset.frontierTarget === currentId;
                if (active) {
                    link.setAttribute('aria-current', 'location');
                } else {
                    link.removeAttribute('aria-current');
                }
            });
        };
        this._listen(window, 'scroll', update, { passive: true });
        this._listen(window, 'hashchange', () => this._setTimeout(update, 80));
        this._requestFrame(update);
        this._setTimeout(update, 300);
    },

    refreshIcons() {
        if (typeof lucide !== 'undefined' && typeof lucide.createIcons === 'function') {
            lucide.createIcons();
        }
    },

    escape(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    },

    escapeAttr(value) {
        return this.escape(value).replace(/`/g, '&#96;');
    },

    safeUrl(value) {
        const raw = String(value || '#');
        if (/^https?:\/\//i.test(raw)) return this.escapeAttr(raw);
        return '#';
    }
};

window.FrontierLearning = FrontierLearning;
