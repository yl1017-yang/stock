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
        let keyword = '국내테마';
        if (filter === 'Pass') keyword = '수익';
        if (filter === 'Value') keyword = '국내 저평가';
        if (filter === 'US') keyword = '미국 저평가';
        btn.classList.toggle('active', btn.textContent.trim() === keyword);
    });

    if (filter === 'All') {
        // 국내 저평가 및 미국 저평가 테마를 제외한 일반 국내 테마만 표시
        const filtered = allData.filter(item => 
            !item.theme.startsWith('국내 저평가') && 
            !item.theme.startsWith('미국 저평가') &&
            item.theme !== '가치투자(저평가 턴어라운드)'
        );
        render(filtered);
    } else if (filter === 'Pass') {
        // 'Pass' 글자가 포함된 종목만 필터링 (가치투자 테마 제외)
        const filtered = allData.filter(item => item.is_profitable.includes('Pass') && !item.theme.startsWith('국내 저평가') && !item.theme.includes('턴어라운드)'));
        render(filtered);
    } else if (filter === 'Value') {
        // '국내 저평가'로 시작하는 모든 테마 필터링
        const filtered = allData.filter(item => item.theme.startsWith('국내 저평가'));
        render(filtered);
    } else if (filter === 'US') {
        // '미국 저평가'로 시작하는 모든 테마 필터링
        const filtered = allData.filter(item => item.theme.startsWith('미국 저평가'));
        render(filtered);
    }
}

function render(data) {
    const container = document.getElementById('dashboard-items');
    container.innerHTML = '';

    if (data.length === 0) {
        container.innerHTML = '<div style="text-align: center; color: #888; padding: 2rem; font-size: 1.2rem; grid-column: 1 / -1;">해당 조건에 맞는 종목이 없습니다.<br><small style="font-size: 0.9rem; color: #555;">(현재 데이터가 없거나, 거래소 데이터 수집이 잠시 차단되었을 수 있습니다.)</small></div>';
        return;
    }

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
