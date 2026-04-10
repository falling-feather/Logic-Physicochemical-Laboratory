// ===== Photosynthesis Visualization =====

function initPhotosynthesis() {
    const canvas = document.getElementById('photosynthesis-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const info = document.getElementById('photo-info');

    let lightIntensity = 50;
    let running = false;
    let animId = null;
    let particles = [];
    let oxygenBubbles = [];
    let time = 0;

    const slider = document.getElementById('bio-light-intensity');

    function createParticle(type) {
        const w = canvas.width, h = canvas.height;
        if (type === 'co2') {
            return { type: 'co2', x: Math.random() * w * 0.3, y: h * 0.3 + Math.random() * h * 0.4, vx: 0.5 + Math.random() * 0.5, vy: (Math.random() - 0.5) * 0.3, r: 6, alpha: 0.8 };
        } else if (type === 'h2o') {
            return { type: 'h2o', x: w * 0.3 + Math.random() * w * 0.1, y: h * 0.85 + Math.random() * 20, vx: (Math.random() - 0.5) * 0.2, vy: -0.3 - Math.random() * 0.3, r: 5, alpha: 0.7 };
        }
    }

    function draw() {
        const w = canvas.width, h = canvas.height;
        ctx.clearRect(0, 0, w, h);

        // Sun (light source)
        const sunBrightness = lightIntensity / 100;
        ctx.beginPath();
        const gradient = ctx.createRadialGradient(w * 0.8, h * 0.1, 5, w * 0.8, h * 0.1, 60);
        gradient.addColorStop(0, `rgba(255,220,50,${sunBrightness})`);
        gradient.addColorStop(1, 'transparent');
        ctx.fillStyle = gradient;
        ctx.arc(w * 0.8, h * 0.1, 60, 0, Math.PI * 2);
        ctx.fill();

        // Light rays
        if (lightIntensity > 10) {
            ctx.strokeStyle = `rgba(255,220,100,${sunBrightness * 0.15})`;
            ctx.lineWidth = 2;
            for (let i = 0; i < 5; i++) {
                ctx.beginPath();
                const angle = -Math.PI * 0.7 + i * 0.15;
                ctx.moveTo(w * 0.8, h * 0.1);
                ctx.lineTo(w * 0.8 + Math.cos(angle) * 300, h * 0.1 + Math.sin(angle) * 300);
                ctx.stroke();
            }
        }

        // Chloroplast (leaf cross-section)
        ctx.beginPath();
        ctx.ellipse(w * 0.5, h * 0.5, w * 0.28, h * 0.25, 0, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(58,158,143,0.12)';
        ctx.fill();
        ctx.strokeStyle = 'rgba(58,158,143,0.4)';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Thylakoid stacks
        for (let i = 0; i < 4; i++) {
            const tx = w * 0.38 + i * w * 0.07;
            const ty = h * 0.45;
            for (let j = 0; j < 3; j++) {
                ctx.beginPath();
                ctx.ellipse(tx, ty + j * 12, 18, 5, 0, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(58,158,143,${0.3 + sunBrightness * 0.3})`;
                ctx.fill();
                ctx.strokeStyle = 'rgba(58,158,143,0.6)';
                ctx.lineWidth = 1;
                ctx.stroke();
            }
        }

        // Labels
        ctx.fillStyle = 'rgba(255,255,255,0.6)';
        ctx.font = '11px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('叶绿体', w * 0.5, h * 0.22);
        ctx.fillText('类囊体', w * 0.5, h * 0.4);

        // Draw particles
        particles.forEach(p => {
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            ctx.globalAlpha = p.alpha;
            if (p.type === 'co2') {
                ctx.fillStyle = '#888';
                ctx.fill();
                ctx.fillStyle = '#bbb';
                ctx.font = 'bold 8px JetBrains Mono';
                ctx.textAlign = 'center';
                ctx.fillText('CO₂', p.x, p.y + 3);
            } else {
                ctx.fillStyle = '#6090e0';
                ctx.fill();
                ctx.fillStyle = '#aaccff';
                ctx.font = 'bold 7px JetBrains Mono';
                ctx.textAlign = 'center';
                ctx.fillText('H₂O', p.x, p.y + 3);
            }
            ctx.globalAlpha = 1;
        });

        // Oxygen bubbles
        oxygenBubbles.forEach(b => {
            ctx.beginPath();
            ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(100,200,255,${b.alpha})`;
            ctx.fill();
            ctx.fillStyle = `rgba(200,240,255,${b.alpha})`;
            ctx.font = 'bold 7px JetBrains Mono';
            ctx.textAlign = 'center';
            ctx.fillText('O₂', b.x, b.y + 3);
        });

        // Equation
        ctx.fillStyle = 'rgba(255,255,255,0.5)';
        ctx.font = '12px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('6CO₂ + 6H₂O  →  C₆H₁₂O₆ + 6O₂', w * 0.5, h - 16);

        // Rate indicator
        const rate = Math.round(lightIntensity * 0.8);
        ctx.fillStyle = 'var(--accent-teal)';
        ctx.fillText(`光合速率: ${rate}%`, w * 0.15, h - 16);
    }

    function animate() {
        if (!running) return;
        time++;

        // Spawn particles based on light intensity
        if (time % Math.max(2, 20 - Math.floor(lightIntensity / 7)) === 0) {
            if (particles.length < 30) particles.push(createParticle('co2'));
            if (particles.length < 30) particles.push(createParticle('h2o'));
        }

        // Move particles
        particles.forEach(p => {
            p.x += p.vx;
            p.y += p.vy;
        });

        // Remove particles that enter chloroplast, spawn O2
        const cx = canvas.width * 0.5, cy = canvas.height * 0.5;
        const rxSq = (canvas.width * 0.28) ** 2, rySq = (canvas.height * 0.25) ** 2;
        particles = particles.filter(p => {
            const dx = (p.x - cx), dy = (p.y - cy);
            if ((dx * dx / rxSq + dy * dy / rySq) < 0.8) {
                if (Math.random() < 0.5) {
                    oxygenBubbles.push({ x: cx + (Math.random() - 0.5) * 60, y: cy - 20, vy: -0.5 - Math.random(), r: 4 + Math.random() * 3, alpha: 0.8 });
                }
                return false;
            }
            return p.x < canvas.width && p.y > 0;
        });

        // Move oxygen bubbles
        oxygenBubbles.forEach(b => { b.y += b.vy; b.alpha -= 0.003; });
        oxygenBubbles = oxygenBubbles.filter(b => b.alpha > 0 && b.y > -20);

        draw();
        animId = requestAnimationFrame(animate);
    }

    if (slider) slider.addEventListener('input', (e) => {
        lightIntensity = parseInt(e.target.value);
        if (!running) draw();
    });

    const startBtn = document.getElementById('bio-photo-start');
    if (startBtn) startBtn.addEventListener('click', () => {
        if (running) {
            running = false;
            startBtn.textContent = '开始模拟';
            if (info) info.textContent = '模拟已暂停';
        } else {
            running = true;
            startBtn.textContent = '暂停';
            if (info) info.textContent = '光合作用进行中...';
            animate();
        }
    });

    const resetBtn = document.getElementById('bio-photo-reset');
    if (resetBtn) resetBtn.addEventListener('click', () => {
        running = false;
        particles = [];
        oxygenBubbles = [];
        time = 0;
        if (startBtn) startBtn.textContent = '开始模拟';
        if (slider) { slider.value = 50; lightIntensity = 50; }
        if (info) info.textContent = '调节光照强度，观察光合作用速率变化';
        draw();
    });

    draw();
}
