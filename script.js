let allData = [];
let currentFilter = 'All';

async function init() {
    try {
        const response = await fetch('data.json');
        if (!response.ok) throw new Error('Not found');
        
        allData = await response.json();
        document.getElementById('loading').style.display = 'none';
        
        if (allData.length > 0) {
            document.getElementById('update-time-val').textContent = allData[0].time;
            render(allData);
        }
    } catch (err) {
        console.error(err);
        document.getElementById('loading').style.display = 'none';
        document.getElementById('error').style.display = 'block';
    }
}

function filterData(filter) {
    currentFilter = filter;
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.toggle('active', btn.textContent.includes(filter === 'All' ? '전체' : '수익'));
    });

    if (filter === 'All') {
        render(allData);
    } else {
        // 'Pass' 글자가 포함된 종목만 필터링
        const filtered = allData.filter(item => item.is_profitable.includes('Pass'));
        render(filtered);
    }
}

function render(data) {
    const container = document.getElementById('dashboard-items');
    container.innerHTML = '';

    // 테마별 그룹화
    const themes = [...new Set(data.map(item => item.theme))];

    themes.forEach((themeName, index) => {
        const themeStocks = data.filter(s => s.theme === themeName);
        
        const card = document.createElement('div');
        card.className = 'theme-card';
        card.style.animationDelay = `${index * 0.1}s`;

        let stocksHtml = '';
        themeStocks.forEach((s, idx) => {
            let statusClass = 'status-skip';
            if (s.is_profitable.includes('Pass')) statusClass = 'status-pass';
            else if (s.is_profitable.includes('Fail')) statusClass = 'status-fail';

            stocksHtml += `
                <div class="stock-item-wrapper">
                    <div class="stock-item">
                        <span class="stock-name"><span class="rank">#${idx + 1}</span> ${s.name}</span>
                        <span class="profit-status ${statusClass}">${s.is_profitable}</span>
                    </div>
                    <div class="stock-indicators">
                        <span class="indicator">PER <b>${s.per}</b></span>
                        <span class="separator">|</span>
                        <span class="indicator">PBR <b>${s.pbr}</b></span>
                        <span class="separator">|</span>
                        <span class="indicator">DIV <b>${s.dividend === 'N/A' ? 'N/A' : s.dividend + '%'}</b></span>
                    </div>
                </div>
            `;
        });

        card.innerHTML = `
            <div class="theme-header">
                <div class="theme-name">${themeName}</div>
            </div>
            <div class="stock-list">
                ${stocksHtml}
            </div>
        `;
        
        container.appendChild(card);
    });
}

// 초기화 실행
init();
