// ===== 算法页面逻辑 =====

// ===== 桶排序 =====
let sortArray = [], isSorting = false;
let sortSpeed = 500; // 全局变量，供main.js使用

// 确保sortSpeed是全局的
window.sortSpeed = sortSpeed;

function sleep(ms) { 
    return new Promise(r => setTimeout(r, ms)); 
}

function updateSortInfo(t) { 
    const el = document.getElementById('sort-info'); 
    if(el) el.textContent = t; 
}

function clearBuckets() { 
    const el = document.getElementById('buckets-container'); 
    if(el) el.innerHTML = ''; 
}

function generateRandomArray() {
    if(isSorting) return;
    sortArray = Array.from({length:15}, () => Math.floor(Math.random()*100)+1);
    renderArray('original-array', sortArray);
    renderArray('sorted-array', []);
    clearBuckets();
    updateSortInfo('点击"开始排序"');
}

function renderArray(id, arr) {
    const c = document.getElementById(id);
    if(!c) return;
    c.innerHTML = '';
    const max = Math.max(...arr, 1);
    arr.forEach(v => {
        const b = document.createElement('div');
        b.className = 'array-bar';
        b.style.height = (v/max*180)+'px';
        b.textContent = v;
        c.appendChild(b);
    });
}

function renderBuckets(buckets) {
    const c = document.getElementById('buckets-container');
    if(!c) return;
    c.innerHTML = '';
    buckets.forEach((b, i) => {
        const el = document.createElement('div');
        el.className = 'bucket';
        el.innerHTML = `<div class="bucket-label">桶 ${i+1}</div><div class="bucket-items">${b.map((v,j)=>`<div class="bucket-item" style="animation-delay:${j*0.1}s">${v}</div>`).join('')}</div>`;
        c.appendChild(el);
    });
}

function highlightBar(id, idx, on) {
    const bars = document.querySelectorAll(`#${id} .array-bar`);
    if(bars[idx]) on ? bars[idx].classList.add('active') : bars[idx].classList.remove('active');
}

async function startBucketSort() {
    if(isSorting || !sortArray.length) { 
        if(!sortArray.length) { 
            generateRandomArray(); 
            await sleep(500); 
        } else return; 
    }
    isSorting = true;
    document.querySelectorAll('.sort-toolbar .btn').forEach(b => b.disabled = true);
    
    const arr = [...sortArray];
    const buckets = Array(10).fill(null).map(()=>[]);
    const max = Math.max(...arr);
    const currentSpeed = window.sortSpeed || sortSpeed; // 使用全局变量
    
    updateSortInfo('步骤1: 分配到桶...');
    for(let i=0; i<arr.length; i++) {
        const v = arr[i];
        const bi = Math.floor((v/(max+1))*10);
        buckets[bi].push(v);
        highlightBar('original-array', i, true);
        await sleep(currentSpeed);
        renderBuckets(buckets);
        updateSortInfo(`将 ${v} 放入桶 ${bi+1}`);
        await sleep(currentSpeed);
        highlightBar('original-array', i, false);
    }
    
    updateSortInfo('步骤2: 桶内排序...');
    for(let i=0; i<buckets.length; i++) {
        if(buckets[i].length) {
            buckets[i].sort((a,b)=>a-b);
            renderBuckets(buckets);
            updateSortInfo(`桶 ${i+1} 排序完成`);
            await sleep(currentSpeed);
        }
    }
    
    updateSortInfo('步骤3: 合并...');
    const sorted = [];
    for(let b of buckets) {
        for(let v of b) {
            sorted.push(v);
            renderArray('sorted-array', sorted);
            await sleep(currentSpeed/2);
        }
    }
    updateSortInfo('完成！');
    updateSortEdu(arr.length, buckets);
    document.querySelectorAll('#sorted-array .array-bar').forEach((b,i)=>setTimeout(()=>b.classList.add('sorted'), i*50));
    isSorting = false;
    document.querySelectorAll('.sort-toolbar .btn').forEach(b => b.disabled = false);
}

function updateSortEdu(n, buckets) {
    let eduEl = document.getElementById('sort-edu');
    if (!eduEl) {
        const parent = document.getElementById('sort-info');
        if (!parent || !parent.parentElement) return;
        eduEl = document.createElement('div');
        eduEl.id = 'sort-edu';
        eduEl.style.cssText = 'font-size:12px;color:#c4793a;margin-top:8px;line-height:1.6;opacity:0.85;';
        parent.parentElement.appendChild(eduEl);
    }
    const k = buckets.filter(b => b.length > 0).length;
    const maxBucket = Math.max(...buckets.map(b => b.length));
    eduEl.innerHTML =
        `<strong>桶排序 (Bucket Sort)</strong>` +
        `<br>时间复杂度：平均 O(n + k)，最坏 O(n²)（所有元素落入同一个桶）` +
        `<br>空间复杂度：O(n + k)，k = 桶数` +
        `<br>本次：n=${n} 个元素 → ${k} 个非空桶，最大桶含 ${maxBucket} 个元素` +
        `<br>💡 桶排序适合数据均匀分布的场景。数据越均匀，桶内排序越快。`;
}

function resetBucketSort() {
    if(isSorting) return;
    sortArray = [];
    renderArray('original-array', []); 
    renderArray('sorted-array', []); 
    clearBuckets();
    updateSortInfo('已重置');
}

// ===== 算法页面初始化 =====
function initAlgorithms() {
    const speedInput = document.getElementById('sort-speed');
    if (speedInput) {
        speedInput.addEventListener('input', (e) => {
            sortSpeed = parseInt(e.target.value);
            const speedValue = document.getElementById('speed-value');
            if(speedValue) speedValue.textContent = sortSpeed + 'ms';
        });
    }
}

// 导出全局
window.generateRandomArray = generateRandomArray;
window.startBucketSort = startBucketSort;
window.resetBucketSort = resetBucketSort;

