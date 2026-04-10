// ===== Cell Structure Visualization =====

function initCellStructure() {
    const canvas = document.getElementById('cell-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const info = document.getElementById('cell-info');

    let isPlant = false;
    let showLabels = true;
    let hoveredOrganelle = null;

    const organelles = {
        animal: [
            { name: '细胞膜', x: 0.5, y: 0.5, rx: 0.42, ry: 0.4, color: 'rgba(91,141,206,0.3)', border: '#5b8dce', desc: '半透膜，控制物质进出，保护细胞' },
            { name: '细胞核', x: 0.5, y: 0.45, rx: 0.12, ry: 0.11, color: 'rgba(139,111,192,0.4)', border: '#8b6fc0', desc: '含有DNA，控制细胞的生命活动' },
            { name: '线粒体', x: 0.28, y: 0.35, rx: 0.06, ry: 0.035, color: 'rgba(196,121,58,0.5)', border: '#c4793a', desc: '有氧呼吸的主要场所，提供ATP能量' },
            { name: '线粒体', x: 0.72, y: 0.6, rx: 0.055, ry: 0.03, color: 'rgba(196,121,58,0.5)', border: '#c4793a', desc: '有氧呼吸的主要场所，提供ATP能量', label: false },
            { name: '内质网', x: 0.62, y: 0.35, rx: 0.08, ry: 0.06, color: 'rgba(77,158,126,0.2)', border: '#4d9e7e', desc: '蛋白质合成（粗面）和脂质合成（光面）' },
            { name: '高尔基体', x: 0.35, y: 0.6, rx: 0.06, ry: 0.04, color: 'rgba(184,84,80,0.4)', border: '#b85450', desc: '加工、分类和运输蛋白质' },
            { name: '核糖体', x: 0.55, y: 0.32, rx: 0.012, ry: 0.012, color: 'rgba(255,255,255,0.5)', border: '#aaa', desc: '蛋白质合成的场所' },
            { name: '中心体', x: 0.43, y: 0.65, rx: 0.02, ry: 0.02, color: 'rgba(79,168,163,0.5)', border: '#4fa8a3', desc: '与细胞分裂有关（动物细胞特有）' }
        ],
        plant: [
            { name: '细胞壁', x: 0.5, y: 0.5, rx: 0.46, ry: 0.44, color: 'rgba(77,158,126,0.15)', border: '#4d9e7e', desc: '纤维素组成，支持和保护细胞' },
            { name: '细胞膜', x: 0.5, y: 0.5, rx: 0.42, ry: 0.4, color: 'rgba(91,141,206,0.2)', border: '#5b8dce', desc: '半透膜，控制物质进出' },
            { name: '细胞核', x: 0.5, y: 0.35, rx: 0.1, ry: 0.09, color: 'rgba(139,111,192,0.4)', border: '#8b6fc0', desc: '含有DNA，控制细胞的生命活动' },
            { name: '液泡', x: 0.5, y: 0.58, rx: 0.2, ry: 0.18, color: 'rgba(91,141,206,0.15)', border: 'rgba(91,141,206,0.5)', desc: '储存水分和营养物质，维持细胞渗透压' },
            { name: '叶绿体', x: 0.28, y: 0.4, rx: 0.05, ry: 0.03, color: 'rgba(58,158,143,0.6)', border: '#3a9e8f', desc: '光合作用的场所（植物细胞特有）' },
            { name: '叶绿体', x: 0.7, y: 0.45, rx: 0.045, ry: 0.028, color: 'rgba(58,158,143,0.6)', border: '#3a9e8f', desc: '光合作用的场所（植物细胞特有）', label: false },
            { name: '线粒体', x: 0.32, y: 0.55, rx: 0.05, ry: 0.028, color: 'rgba(196,121,58,0.5)', border: '#c4793a', desc: '有氧呼吸的主要场所，提供ATP能量' },
            { name: '内质网', x: 0.65, y: 0.32, rx: 0.07, ry: 0.05, color: 'rgba(77,158,126,0.2)', border: '#4d9e7e', desc: '蛋白质和脂质的合成运输' }
        ]
    };

    function draw() {
        const w = canvas.width, h = canvas.height;
        ctx.clearRect(0, 0, w, h);

        const list = isPlant ? organelles.plant : organelles.animal;

        list.forEach(org => {
            ctx.beginPath();
            ctx.ellipse(org.x * w, org.y * h, org.rx * w, org.ry * h, 0, 0, Math.PI * 2);
            ctx.fillStyle = org.color;
            ctx.fill();
            ctx.strokeStyle = org.border;
            ctx.lineWidth = hoveredOrganelle === org ? 3 : 1.5;
            ctx.stroke();

            if (showLabels && org.label !== false) {
                ctx.fillStyle = org.border;
                ctx.font = '13px "Noto Sans SC", sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText(org.name, org.x * w, org.y * h - org.ry * h - 6);
            }
        });

        ctx.fillStyle = 'rgba(255,255,255,0.5)';
        ctx.font = '12px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(isPlant ? '植物细胞' : '动物细胞', w - 16, h - 12);
    }

    canvas.addEventListener('mousemove', (e) => {
        const rect = canvas.getBoundingClientRect();
        const mx = (e.clientX - rect.left) / rect.width;
        const my = (e.clientY - rect.top) / rect.height;
        const list = isPlant ? organelles.plant : organelles.animal;

        hoveredOrganelle = null;
        for (let i = list.length - 1; i >= 0; i--) {
            const org = list[i];
            const dx = (mx - org.x) / org.rx;
            const dy = (my - org.y) / org.ry;
            if (dx * dx + dy * dy <= 1) {
                hoveredOrganelle = org;
                break;
            }
        }
        canvas.style.cursor = hoveredOrganelle ? 'pointer' : 'default';
        draw();
    });

    canvas.addEventListener('click', () => {
        if (hoveredOrganelle && info) {
            info.textContent = `${hoveredOrganelle.name}：${hoveredOrganelle.desc}`;
        }
    });

    const toggleBtn = document.getElementById('bio-cell-toggle');
    if (toggleBtn) toggleBtn.addEventListener('click', () => { isPlant = !isPlant; hoveredOrganelle = null; draw(); if (info) info.textContent = isPlant ? '当前：植物细胞' : '当前：动物细胞'; });

    const labelBtn = document.getElementById('bio-cell-label-toggle');
    if (labelBtn) labelBtn.addEventListener('click', () => { showLabels = !showLabels; draw(); });

    draw();
}
