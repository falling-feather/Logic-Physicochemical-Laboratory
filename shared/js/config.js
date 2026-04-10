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
            desc: '通过交互式可视化探索数学的奥秘，从古代算筹到现代函数图像，感受数学之美。'
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
            { id: 'complex', title: '复数运算', description: '复平面上的运算', icon: 'calculator', variant: 'featured' }
        ],
        physics: [
            { id: 'mechanics', title: '力学模拟', description: '重力、碰撞、弹簧', icon: 'gauge', variant: 'featured' },
            { id: 'electromagnetism', title: '电磁场', description: '电场和磁场分布', icon: 'zap', variant: 'featured' },
            { id: 'waves', title: '波动演示', description: '声波、光波', icon: 'waves', variant: 'featured' },
            { id: 'relativity', title: '相对论', description: '时间膨胀、长度收缩', icon: 'orbit', variant: 'featured' }
        ],
        chemistry: [
            { id: 'periodic-table', title: '元素周期表', description: '交互式元素周期表', icon: 'table', variant: 'featured' },
            { id: 'molecular-structure', title: '分子结构', description: '3D可视化分子', icon: 'atom', variant: 'featured' },
            { id: 'reactions', title: '化学反应', description: '模拟原子重排', icon: 'test-tube', variant: 'featured' },
            { id: 'experiments', title: '虚拟实验', description: '安全环境化学实验', icon: 'beaker', variant: 'upcoming' }
        ],
        algorithms: [
            { id: 'sorting', title: '排序算法', description: '冒泡、快排、归并', icon: 'arrow-up-down', variant: 'featured' },
            { id: 'searching', title: '搜索算法', description: '二分查找、DFS/BFS', icon: 'search', variant: 'featured' },
            { id: 'graph', title: '图算法', description: '最短路径、生成树', icon: 'network', variant: 'featured' },
            { id: 'data-structures', title: '数据结构', description: '栈、队列、树', icon: 'layers', variant: 'featured' }
        ],
        biology: [
            { id: 'cell-structure', title: '细胞结构', description: '动植物细胞的结构与功能', icon: 'microscope', variant: 'featured' },
            { id: 'dna', title: 'DNA结构', description: '双螺旋结构与复制过程', icon: 'dna', variant: 'featured' },
            { id: 'photosynthesis', title: '光合作用', description: '光反应与暗反应可视化', icon: 'sun', variant: 'featured' },
            { id: 'genetics', title: '遗传学', description: '孟德尔定律与遗传图谱', icon: 'git-branch', variant: 'featured' }
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
