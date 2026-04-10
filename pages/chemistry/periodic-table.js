// ===== 交互式元素周期表 =====

const PeriodicTable = {
    // 元素分类 & 颜色
    categories: {
        'alkali':       { label: '碱金属',     color: '#ef4444' },
        'alkaline':     { label: '碱土金属',   color: '#f97316' },
        'transition':   { label: '过渡金属',   color: '#eab308' },
        'post-trans':   { label: '后过渡金属', color: '#22c55e' },
        'metalloid':    { label: '类金属',     color: '#14b8a6' },
        'nonmetal':     { label: '非金属',     color: '#3b82f6' },
        'halogen':      { label: '卤素',       color: '#8b5cf6' },
        'noble':        { label: '稀有气体',   color: '#ec4899' },
        'lanthanide':   { label: '镧系',       color: '#06b6d4' },
        'actinide':     { label: '锕系',       color: '#a855f7' },
    },

    // 前 56 + 72-88 + 104-118 + 镧系/锕系 = 118 个元素
    // 格式: [原子序数, 符号, 中文名, 原子量, 类别, 行(period), 列(group), 电子构型摘要]
    elements: [
        [1,'H','氢',1.008,'nonmetal',1,1,'1s¹'],
        [2,'He','氦',4.003,'noble',1,18,'1s²'],
        [3,'Li','锂',6.941,'alkali',2,1,'[He]2s¹'],
        [4,'Be','铍',9.012,'alkaline',2,2,'[He]2s²'],
        [5,'B','硼',10.81,'metalloid',2,13,'[He]2s²2p¹'],
        [6,'C','碳',12.01,'nonmetal',2,14,'[He]2s²2p²'],
        [7,'N','氮',14.01,'nonmetal',2,15,'[He]2s²2p³'],
        [8,'O','氧',16.00,'nonmetal',2,16,'[He]2s²2p⁴'],
        [9,'F','氟',19.00,'halogen',2,17,'[He]2s²2p⁵'],
        [10,'Ne','氖',20.18,'noble',2,18,'[He]2s²2p⁶'],
        [11,'Na','钠',22.99,'alkali',3,1,'[Ne]3s¹'],
        [12,'Mg','镁',24.31,'alkaline',3,2,'[Ne]3s²'],
        [13,'Al','铝',26.98,'post-trans',3,13,'[Ne]3s²3p¹'],
        [14,'Si','硅',28.09,'metalloid',3,14,'[Ne]3s²3p²'],
        [15,'P','磷',30.97,'nonmetal',3,15,'[Ne]3s²3p³'],
        [16,'S','硫',32.07,'nonmetal',3,16,'[Ne]3s²3p⁴'],
        [17,'Cl','氯',35.45,'halogen',3,17,'[Ne]3s²3p⁵'],
        [18,'Ar','氩',39.95,'noble',3,18,'[Ne]3s²3p⁶'],
        [19,'K','钾',39.10,'alkali',4,1,'[Ar]4s¹'],
        [20,'Ca','钙',40.08,'alkaline',4,2,'[Ar]4s²'],
        [21,'Sc','钪',44.96,'transition',4,3,'[Ar]3d¹4s²'],
        [22,'Ti','钛',47.87,'transition',4,4,'[Ar]3d²4s²'],
        [23,'V','钒',50.94,'transition',4,5,'[Ar]3d³4s²'],
        [24,'Cr','铬',52.00,'transition',4,6,'[Ar]3d⁵4s¹'],
        [25,'Mn','锰',54.94,'transition',4,7,'[Ar]3d⁵4s²'],
        [26,'Fe','铁',55.85,'transition',4,8,'[Ar]3d⁶4s²'],
        [27,'Co','钴',58.93,'transition',4,9,'[Ar]3d⁷4s²'],
        [28,'Ni','镍',58.69,'transition',4,10,'[Ar]3d⁸4s²'],
        [29,'Cu','铜',63.55,'transition',4,11,'[Ar]3d¹⁰4s¹'],
        [30,'Zn','锌',65.38,'transition',4,12,'[Ar]3d¹⁰4s²'],
        [31,'Ga','镓',69.72,'post-trans',4,13,'[Ar]3d¹⁰4s²4p¹'],
        [32,'Ge','锗',72.63,'metalloid',4,14,'[Ar]3d¹⁰4s²4p²'],
        [33,'As','砷',74.92,'metalloid',4,15,'[Ar]3d¹⁰4s²4p³'],
        [34,'Se','硒',78.97,'nonmetal',4,16,'[Ar]3d¹⁰4s²4p⁴'],
        [35,'Br','溴',79.90,'halogen',4,17,'[Ar]3d¹⁰4s²4p⁵'],
        [36,'Kr','氪',83.80,'noble',4,18,'[Ar]3d¹⁰4s²4p⁶'],
        [37,'Rb','铷',85.47,'alkali',5,1,'[Kr]5s¹'],
        [38,'Sr','锶',87.62,'alkaline',5,2,'[Kr]5s²'],
        [39,'Y','钇',88.91,'transition',5,3,'[Kr]4d¹5s²'],
        [40,'Zr','锆',91.22,'transition',5,4,'[Kr]4d²5s²'],
        [41,'Nb','铌',92.91,'transition',5,5,'[Kr]4d⁴5s¹'],
        [42,'Mo','钼',95.95,'transition',5,6,'[Kr]4d⁵5s¹'],
        [43,'Tc','锝',98,'transition',5,7,'[Kr]4d⁵5s²'],
        [44,'Ru','钌',101.1,'transition',5,8,'[Kr]4d⁷5s¹'],
        [45,'Rh','铑',102.9,'transition',5,9,'[Kr]4d⁸5s¹'],
        [46,'Pd','钯',106.4,'transition',5,10,'[Kr]4d¹⁰'],
        [47,'Ag','银',107.9,'transition',5,11,'[Kr]4d¹⁰5s¹'],
        [48,'Cd','镉',112.4,'transition',5,12,'[Kr]4d¹⁰5s²'],
        [49,'In','铟',114.8,'post-trans',5,13,'[Kr]4d¹⁰5s²5p¹'],
        [50,'Sn','锡',118.7,'post-trans',5,14,'[Kr]4d¹⁰5s²5p²'],
        [51,'Sb','锑',121.8,'metalloid',5,15,'[Kr]4d¹⁰5s²5p³'],
        [52,'Te','碲',127.6,'metalloid',5,16,'[Kr]4d¹⁰5s²5p⁴'],
        [53,'I','碘',126.9,'halogen',5,17,'[Kr]4d¹⁰5s²5p⁵'],
        [54,'Xe','氙',131.3,'noble',5,18,'[Kr]4d¹⁰5s²5p⁶'],
        [55,'Cs','铯',132.9,'alkali',6,1,'[Xe]6s¹'],
        [56,'Ba','钡',137.3,'alkaline',6,2,'[Xe]6s²'],
        // 镧系 57-71 放在第 9 行（视觉行）
        [57,'La','镧',138.9,'lanthanide',9,3,'[Xe]5d¹6s²'],
        [58,'Ce','铈',140.1,'lanthanide',9,4,'[Xe]4f¹5d¹6s²'],
        [59,'Pr','镨',140.9,'lanthanide',9,5,'[Xe]4f³6s²'],
        [60,'Nd','钕',144.2,'lanthanide',9,6,'[Xe]4f⁴6s²'],
        [61,'Pm','钷',145,'lanthanide',9,7,'[Xe]4f⁵6s²'],
        [62,'Sm','钐',150.4,'lanthanide',9,8,'[Xe]4f⁶6s²'],
        [63,'Eu','铕',152.0,'lanthanide',9,9,'[Xe]4f⁷6s²'],
        [64,'Gd','钆',157.3,'lanthanide',9,10,'[Xe]4f⁷5d¹6s²'],
        [65,'Tb','铽',158.9,'lanthanide',9,11,'[Xe]4f⁹6s²'],
        [66,'Dy','镝',162.5,'lanthanide',9,12,'[Xe]4f¹⁰6s²'],
        [67,'Ho','钬',164.9,'lanthanide',9,13,'[Xe]4f¹¹6s²'],
        [68,'Er','铒',167.3,'lanthanide',9,14,'[Xe]4f¹²6s²'],
        [69,'Tm','铥',168.9,'lanthanide',9,15,'[Xe]4f¹³6s²'],
        [70,'Yb','镱',173.0,'lanthanide',9,16,'[Xe]4f¹⁴6s²'],
        [71,'Lu','镥',175.0,'lanthanide',9,17,'[Xe]4f¹⁴5d¹6s²'],
        // 第 6 周期继续
        [72,'Hf','铪',178.5,'transition',6,4,'[Xe]4f¹⁴5d²6s²'],
        [73,'Ta','钽',180.9,'transition',6,5,'[Xe]4f¹⁴5d³6s²'],
        [74,'W','钨',183.8,'transition',6,6,'[Xe]4f¹⁴5d⁴6s²'],
        [75,'Re','铼',186.2,'transition',6,7,'[Xe]4f¹⁴5d⁵6s²'],
        [76,'Os','锇',190.2,'transition',6,8,'[Xe]4f¹⁴5d⁶6s²'],
        [77,'Ir','铱',192.2,'transition',6,9,'[Xe]4f¹⁴5d⁷6s²'],
        [78,'Pt','铂',195.1,'transition',6,10,'[Xe]4f¹⁴5d⁹6s¹'],
        [79,'Au','金',197.0,'transition',6,11,'[Xe]4f¹⁴5d¹⁰6s¹'],
        [80,'Hg','汞',200.6,'transition',6,12,'[Xe]4f¹⁴5d¹⁰6s²'],
        [81,'Tl','铊',204.4,'post-trans',6,13,'[Xe]4f¹⁴5d¹⁰6s²6p¹'],
        [82,'Pb','铅',207.2,'post-trans',6,14,'[Xe]4f¹⁴5d¹⁰6s²6p²'],
        [83,'Bi','铋',209.0,'post-trans',6,15,'[Xe]4f¹⁴5d¹⁰6s²6p³'],
        [84,'Po','钋',209,'post-trans',6,16,'[Xe]4f¹⁴5d¹⁰6s²6p⁴'],
        [85,'At','砹',210,'halogen',6,17,'[Xe]4f¹⁴5d¹⁰6s²6p⁵'],
        [86,'Rn','氡',222,'noble',6,18,'[Xe]4f¹⁴5d¹⁰6s²6p⁶'],
        [87,'Fr','钫',223,'alkali',7,1,'[Rn]7s¹'],
        [88,'Ra','镭',226,'alkaline',7,2,'[Rn]7s²'],
        // 锕系 89-103 放在第 10 行
        [89,'Ac','锕',227,'actinide',10,3,'[Rn]6d¹7s²'],
        [90,'Th','钍',232.0,'actinide',10,4,'[Rn]6d²7s²'],
        [91,'Pa','镤',231.0,'actinide',10,5,'[Rn]5f²6d¹7s²'],
        [92,'U','铀',238.0,'actinide',10,6,'[Rn]5f³6d¹7s²'],
        [93,'Np','镎',237,'actinide',10,7,'[Rn]5f⁴6d¹7s²'],
        [94,'Pu','钚',244,'actinide',10,8,'[Rn]5f⁶7s²'],
        [95,'Am','镅',243,'actinide',10,9,'[Rn]5f⁷7s²'],
        [96,'Cm','锔',247,'actinide',10,10,'[Rn]5f⁷6d¹7s²'],
        [97,'Bk','锫',247,'actinide',10,11,'[Rn]5f⁹7s²'],
        [98,'Cf','锎',251,'actinide',10,12,'[Rn]5f¹⁰7s²'],
        [99,'Es','锿',252,'actinide',10,13,'[Rn]5f¹¹7s²'],
        [100,'Fm','镄',257,'actinide',10,14,'[Rn]5f¹²7s²'],
        [101,'Md','钔',258,'actinide',10,15,'[Rn]5f¹³7s²'],
        [102,'No','锘',259,'actinide',10,16,'[Rn]5f¹⁴7s²'],
        [103,'Lr','铹',266,'actinide',10,17,'[Rn]5f¹⁴7s²7p¹'],
        // 第 7 周期继续
        [104,'Rf','𬬻',267,'transition',7,4,'[Rn]5f¹⁴6d²7s²'],
        [105,'Db','𬭊',268,'transition',7,5,'[Rn]5f¹⁴6d³7s²'],
        [106,'Sg','𬭳',269,'transition',7,6,'[Rn]5f¹⁴6d⁴7s²'],
        [107,'Bh','𬭛',270,'transition',7,7,'[Rn]5f¹⁴6d⁵7s²'],
        [108,'Hs','𬭶',269,'transition',7,8,'[Rn]5f¹⁴6d⁶7s²'],
        [109,'Mt','鿏',278,'transition',7,9,'[Rn]5f¹⁴6d⁷7s²'],
        [110,'Ds','𫟼',281,'transition',7,10,'[Rn]5f¹⁴6d⁸7s²'],
        [111,'Rg','𬬭',282,'transition',7,11,'[Rn]5f¹⁴6d⁹7s²'],
        [112,'Cn','鿔',285,'transition',7,12,'[Rn]5f¹⁴6d¹⁰7s²'],
        [113,'Nh','鿭',286,'post-trans',7,13,'[Rn]5f¹⁴6d¹⁰7s²7p¹'],
        [114,'Fl','𫓧',289,'post-trans',7,14,'[Rn]5f¹⁴6d¹⁰7s²7p²'],
        [115,'Mc','镆',290,'post-trans',7,15,'[Rn]5f¹⁴6d¹⁰7s²7p³'],
        [116,'Lv','𫟷',293,'post-trans',7,16,'[Rn]5f¹⁴6d¹⁰7s²7p⁴'],
        [117,'Ts','鿬',294,'halogen',7,17,'[Rn]5f¹⁴6d¹⁰7s²7p⁵'],
        [118,'Og','鿫',294,'noble',7,18,'[Rn]5f¹⁴6d¹⁰7s²7p⁶'],
    ],

    selectedElement: null,

    init() {
        const container = document.getElementById('periodic-table-grid');
        if (!container) return;
        this.buildTable(container);
        this.buildLegend();

        // 关闭详情面板
        const closeBtn = document.getElementById('pt-detail-close');
        if (closeBtn) closeBtn.addEventListener('click', () => this.closeDetail());
    },

    buildTable(container) {
        container.innerHTML = '';

        // 镧系/锕系占位 (6,3) 和 (7,3)
        const placeholders = new Map();
        placeholders.set('6-3', { label: '57-71', sub: '镧系' });
        placeholders.set('7-3', { label: '89-103', sub: '锕系' });

        // 构建所有普通位置的元素 map
        const posMap = new Map();
        for (const el of this.elements) {
            const row = el[5], col = el[6];
            posMap.set(`${row}-${col}`, el);
        }

        // 渲染 10 行 × 18 列
        for (let r = 1; r <= 10; r++) {
            // 在第 8 行插入分隔行
            if (r === 8) {
                const spacer = document.createElement('div');
                spacer.className = 'pt-spacer';
                spacer.style.gridColumn = '1 / -1';
                container.appendChild(spacer);
                continue;
            }

            for (let c = 1; c <= 18; c++) {
                const key = `${r}-${c}`;

                // 占位符
                if (placeholders.has(key)) {
                    const ph = placeholders.get(key);
                    const div = document.createElement('div');
                    div.className = 'pt-cell pt-placeholder';
                    div.innerHTML = `<span class="pt-symbol">${ph.label}</span><span class="pt-name">${ph.sub}</span>`;
                    container.appendChild(div);
                    continue;
                }

                const el = posMap.get(key);
                if (!el) {
                    // 空格
                    const empty = document.createElement('div');
                    empty.className = 'pt-cell pt-empty';
                    container.appendChild(empty);
                    continue;
                }

                const [num, sym, name, mass, cat] = el;
                const color = this.categories[cat]?.color || '#888';

                const cell = document.createElement('div');
                cell.className = `pt-cell pt-element`;
                cell.dataset.cat = cat;
                cell.style.setProperty('--el-color', color);
                cell.innerHTML = `
                    <span class="pt-number">${num}</span>
                    <span class="pt-symbol">${sym}</span>
                    <span class="pt-name">${name}</span>
                `;

                cell.addEventListener('click', () => this.showDetail(el));
                cell.addEventListener('mouseenter', () => this.highlightCategory(cat));
                cell.addEventListener('mouseleave', () => this.clearHighlight());

                container.appendChild(cell);
            }
        }
    },

    buildLegend() {
        const legend = document.getElementById('pt-legend');
        if (!legend) return;
        legend.innerHTML = '';
        for (const [key, val] of Object.entries(this.categories)) {
            const item = document.createElement('span');
            item.className = 'pt-legend-item';
            item.innerHTML = `<span class="pt-legend-dot" style="background:${val.color}"></span>${val.label}`;
            item.addEventListener('click', () => this.filterCategory(key));
            legend.appendChild(item);
        }
    },

    highlightCategory(cat) {
        const grid = document.getElementById('periodic-table-grid');
        if (!grid) return;
        grid.querySelectorAll('.pt-element').forEach(el => {
            el.classList.toggle('pt-dim', el.dataset.cat !== cat);
        });
    },

    clearHighlight() {
        const grid = document.getElementById('periodic-table-grid');
        if (!grid) return;
        grid.querySelectorAll('.pt-element').forEach(el => {
            el.classList.remove('pt-dim');
        });
    },

    filterCategory(cat) {
        // Toggle: 再次点击取消过滤
        const grid = document.getElementById('periodic-table-grid');
        if (!grid) return;
        const alreadyFiltered = grid.dataset.filter === cat;
        if (alreadyFiltered) {
            delete grid.dataset.filter;
            grid.querySelectorAll('.pt-element').forEach(el => el.classList.remove('pt-dim'));
        } else {
            grid.dataset.filter = cat;
            grid.querySelectorAll('.pt-element').forEach(el => {
                el.classList.toggle('pt-dim', el.dataset.cat !== cat);
            });
        }
    },

    showDetail(el) {
        const [num, sym, name, mass, cat, , , config] = el;
        const panel = document.getElementById('pt-detail');
        if (!panel) return;

        const catInfo = this.categories[cat] || { label: cat, color: '#888' };

        panel.querySelector('.pt-detail-number').textContent = num;
        panel.querySelector('.pt-detail-symbol').textContent = sym;
        panel.querySelector('.pt-detail-symbol').style.color = catInfo.color;
        panel.querySelector('.pt-detail-name').textContent = name;
        panel.querySelector('.pt-detail-mass').textContent = mass;
        panel.querySelector('.pt-detail-cat').textContent = catInfo.label;
        panel.querySelector('.pt-detail-cat').style.color = catInfo.color;
        panel.querySelector('.pt-detail-config').textContent = config;

        panel.classList.add('active');
        this.selectedElement = el;
    },

    closeDetail() {
        const panel = document.getElementById('pt-detail');
        if (panel) panel.classList.remove('active');
        this.selectedElement = null;
    }
};

function initPeriodicTable() {
    PeriodicTable.init();
}
