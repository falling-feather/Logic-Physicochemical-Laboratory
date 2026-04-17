// ===== Application Configuration =====
const CONFIG = {
    // Page metadata
    pages: {
        mathematics: {
            label: '数学',
            accent: 'blue',
            icon: 'calculator',
            title: '数学可视化',
            subtitle: '可视化探索',
            desc: '通过交互式可视化探索数学的奥秘，从函数图像到微积分、几何变换，感受数学之美。'
        },
        physics: {
            label: '物理',
            accent: 'purple',
            icon: 'atom',
            title: '物理演示',
            subtitle: '动态模拟',
            desc: '通过动态模拟理解物理世界的运行规律，从力学到电磁场，沉浸式体验物理法则。'
        },
        chemistry: {
            label: '化学',
            accent: 'green',
            icon: 'flask-conical',
            title: '化学实验',
            subtitle: '微观探索',
            desc: '探索化学元素和反应的奥秘，从原子结构到化学平衡，理解物质的本质。'
        },
        algorithms: {
            label: '算法',
            accent: 'orange',
            icon: 'code',
            title: '算法可视化',
            subtitle: '逻辑之美',
            desc: '通过动画理解算法的工作原理，从排序到图论，用代码解构复杂问题。'
        },
        biology: {
            label: '生物',
            accent: 'teal',
            icon: 'leaf',
            title: '生物实验',
            subtitle: '生命科学',
            desc: '探索生命的奥秘，从细胞结构到遗传规律，可视化理解生物学核心概念。'
        }
    },

    // Experiment cards
    experiments: {
        mathematics: [
            { id: 'function-graph', title: '函数图像', description: '可视化各种数学函数', icon: 'function-square', variant: 'featured', anchor: 'func-graph-section' },
            { id: 'calculus', title: '微积分', description: '理解导数、积分和极限', icon: 'trending-up', variant: 'featured' },
            { id: 'geometry', title: '几何变换', description: '探索平移、旋转、缩放', icon: 'shapes', variant: 'featured' },
            { id: 'complex', title: '复数运算', description: '复平面上的运算', icon: 'calculator', variant: 'featured' },
            { id: 'trigonometry', title: '三角函数', description: '单位圆与sin/cos/tan联动', icon: 'circle-dot', variant: 'featured' },
            { id: 'set-operations', title: '集合运算', description: 'Venn图与集合操作可视化', icon: 'combine', variant: 'featured' },
            { id: 'probability', title: '概率统计', description: '抛硬币/掷骰子频率收敛与直方图', icon: 'bar-chart-2', variant: 'featured' },
            { id: 'vector-ops', title: '向量运算', description: '向量加减/数量积/投影可视化', icon: 'move', variant: 'featured' },
            { id: 'inequality', title: '不等式', description: '线性规划可行域与最优解', icon: 'maximize-2', variant: 'featured' },
            { id: 'conic-sections', title: '圆锥曲线', description: '椭圆/双曲线/抛物线焦点轨迹', icon: 'circle', variant: 'featured' },
            { id: 'solid-geometry', title: '立体几何', description: '三维多面体旋转与截面', icon: 'box', variant: 'featured' },
            { id: 'permutation-combination', title: '排列组合', description: '树状图/计数公式/杨辉三角', icon: 'layers', variant: 'featured' },
            { id: 'sequences', title: '数列可视化', description: '等差/等比数列图形化与前n项和', icon: 'bar-chart', variant: 'featured' },
            { id: 'function-properties', title: '函数性质探究', description: '单调性/奇偶性/周期性交互分析', icon: 'scan-line', variant: 'featured' },
            { id: 'exp-log', title: '指数与对数', description: '底数a对图像影响与互为反函数', icon: 'trending-up', variant: 'featured' }
        ],
        physics: [
            { id: 'mechanics', title: '力学模拟', description: '重力、碰撞、弹簧', icon: 'gauge', variant: 'featured' },
            { id: 'electromagnetism', title: '电磁场', description: '电场和磁场分布', icon: 'zap', variant: 'featured' },
            { id: 'waves', title: '波动演示', description: '声波、光波', icon: 'waves', variant: 'featured' },
            { id: 'relativity', title: '相对论', description: '时间膨胀、长度收缩', icon: 'orbit', variant: 'featured' },
            { id: 'kinematics', title: '匀变速运动', description: 'v-t图与s-t图联动', icon: 'move-right', variant: 'featured' },
            { id: 'projectile', title: '抛体运动', description: '轨迹、速度分解、射程', icon: 'rocket', variant: 'featured' },
            { id: 'circular-motion', title: '圆周运动', description: '向心加速度/向心力/线速度', icon: 'rotate-ccw', variant: 'featured' },
            { id: 'energy-conservation', title: '机械能守恒', description: '过山车PE/KE能量条', icon: 'activity', variant: 'featured' },
            { id: 'circuit-analysis', title: '电路分析', description: '串并联电路与欧姆定律', icon: 'cpu', variant: 'featured' },
            { id: 'em-induction', title: '电磁感应', description: '法拉第定律与感应电动力', icon: 'zap', variant: 'featured' },
            { id: 'alternating-current', title: '交变电流', description: 'AC波形、RMS与变压器', icon: 'radio', variant: 'featured' },
            { id: 'fluid-dynamics', title: '流体力学', description: '势流叠加、圆柱绕流与伯努利方程', icon: 'wind', variant: 'featured' },
            { id: 'optics', title: '光学', description: '透镜成像/双缝干涉/折射/色散/偏振', icon: 'eye', variant: 'featured' },
            { id: 'gravitation', title: '万有引力', description: '卫星轨道模拟与引力场', icon: 'orbit', variant: 'featured' }
        ],
        chemistry: [
            { id: 'periodic-table', title: '元素周期表', description: '交互式元素周期表', icon: 'table', variant: 'featured' },
            { id: 'molecular-structure', title: '分子结构', description: '3D可视化分子', icon: 'atom', variant: 'featured' },
            { id: 'reactions', title: '化学反应', description: '模拟原子重排', icon: 'test-tube', variant: 'featured' },
            { id: 'chemical-equilibrium', title: '化学平衡', description: '勒夏特列原理与平衡移动', icon: 'scale', variant: 'featured' },
            { id: 'electrochemistry', title: '电化学', description: '原电池/电解池电子流动', icon: 'battery-charging', variant: 'featured' },
            { id: 'chemical-bond', title: '化学键', description: '离子键/共价键/金属键微观结构', icon: 'link', variant: 'featured' },
            { id: 'organic-chemistry', title: '有机化学', description: '碳链结构与常见有机分子', icon: 'hexagon', variant: 'featured' },
            { id: 'reaction-rate', title: '反应速率', description: '碰撞理论与温度/浓度/催化剂影响', icon: 'trending-up', variant: 'featured' },
            { id: 'solution-ionization', title: '溶液与电离', description: 'pH指示与强弱电解质', icon: 'droplet', variant: 'featured' },
            { id: 'ionic-reaction', title: '离子反应', description: '离子方程式拆分与旁观离子', icon: 'split', variant: 'featured' },
            { id: 'redox', title: '氧化还原', description: '电子转移可视化与双线桥法', icon: 'arrow-right-left', variant: 'featured' },
            { id: 'experiments', title: '虚拟实验', description: '安全环境化学实验', icon: 'beaker', variant: 'upcoming' }
        ],
        algorithms: [
            { id: 'sorting', title: '排序算法', description: '冒泡、快排、归并', icon: 'arrow-up-down', variant: 'featured' },
            { id: 'searching', title: '搜索算法', description: '二分查找、DFS/BFS', icon: 'search', variant: 'featured' },
            { id: 'graph', title: '图算法', description: '最短路径、生成树', icon: 'network', variant: 'featured' },
            { id: 'data-structures', title: '数据结构', description: '栈、队列、树', icon: 'layers', variant: 'featured' },
            { id: 'sorting-compare', title: '排序对比', description: '5种排序算法动画对比', icon: 'bar-chart', variant: 'featured' },
            { id: 'recursion-vis', title: '递归可视化', description: 'Fibonacci树/汉诺塔动画', icon: 'git-branch', variant: 'featured' },
            { id: 'dynamic-programming', title: '动态规划', description: '0/1背包问题DP表填充', icon: 'grid', variant: 'featured' },
            { id: 'string-matching', title: '字符串匹配', description: 'KMP算法逐步动画', icon: 'search', variant: 'featured' }
        ],
        biology: [
            { id: 'cell-structure', title: '细胞结构', description: '动植物细胞的结构与功能', icon: 'microscope', variant: 'featured' },
            { id: 'dna', title: 'DNA结构', description: '双螺旋结构与复制过程', icon: 'dna', variant: 'featured' },
            { id: 'photosynthesis', title: '光合作用', description: '光反应与暗反应可视化', icon: 'sun', variant: 'featured' },
            { id: 'genetics', title: '遗传学', description: '孟德尔定律与遗传图谱', icon: 'git-branch', variant: 'featured' },
            { id: 'mitosis', title: '有丝分裂', description: '细胞分裂各时期动画演示', icon: 'split', variant: 'featured' },
            { id: 'neural-regulation', title: '神经调节', description: '突触传递与动作电位可视化', icon: 'zap', variant: 'featured' },
            { id: 'immune-system', title: '免疫系统', description: '巨噬细胞/抗体/T细胞免疫模拟', icon: 'shield', variant: 'featured' },
            { id: 'ecosystem', title: '生态系统', description: '食物链能量流动与种群动态模拟', icon: 'trees', variant: 'featured' },
            { id: 'meiosis', title: '减数分裂', description: '同源染色体联会与分裂全过程', icon: 'git-merge', variant: 'featured' },
            { id: 'gene-expression', title: '基因表达', description: '转录(DNA→mRNA)与翻译(mRNA→蛋白质)', icon: 'dna', variant: 'featured' },
            { id: 'cellular-respiration', title: '细胞呼吸', description: '糖酵解/柠檬酸循环/电子传递链', icon: 'flame', variant: 'featured' },
            { id: 'substance-transport', title: '物质运输', description: '自由扩散/协助扩散/主动运输/胞吞胞吐', icon: 'arrow-left-right', variant: 'featured' },
            { id: 'gene-mutation', title: '基因突变', description: '碱基替换/插入/缺失对蛋白质的影响', icon: 'alert-triangle', variant: 'featured' }
        ]
    },

    // Color mapping
    accentColors: {
        mathematics: 'blue',
        physics: 'purple',
        chemistry: 'green',
        algorithms: 'orange',
        biology: 'teal'
    }
};
