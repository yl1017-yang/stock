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
            filterData('All'); // 초기 로딩 시 국내 테마 필터 즉시 적용
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
        let keyword = '국내 테마';
        if (filter === 'Pass') keyword = '수익';
        if (filter === 'Value') keyword = '국내 저평가';
        if (filter === 'US_SP') keyword = '미국 S&P500';
        if (filter === 'US_NDQ') keyword = '미국 나스닥';
        if (filter === 'US_RSL') keyword = '미국 Russell 1000';
        btn.classList.toggle('active', btn.textContent.trim() === keyword);
    });

    if (filter === 'All') {
        // 국내 주도 테마만 표시
        const filtered = allData.filter(item => item.category === 'domestic_theme');
        render(filtered);
    } else if (filter === 'Pass') {
        const filtered = allData.filter(item => item.is_profitable.includes('Pass') && item.category === 'domestic_theme');
        render(filtered);
    } else if (filter === 'Value') {
        // 국내 저평가 카테고리 필터링
        const filtered = allData.filter(item => item.category === 'domestic_value');
        render(filtered);
    } else if (filter === 'US_SP') {
        // S&P 500 관련 필터링
        const filtered = allData.filter(item => item.category === 'us_sp');
        render(filtered);
    } else if (filter === 'US_NDQ') {
        // NASDAQ 관련 필터링
        const filtered = allData.filter(item => item.category === 'us_ndq');
        render(filtered);
    } else if (filter === 'US_RSL') {
        // Russell 1000 관련 필터링
        const filtered = allData.filter(item => item.category === 'us_rsl');
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

            const isUp = s.change_1m && s.change_1m.includes('+');
            const isDown = s.change_1m && s.change_1m.includes('-');
            const changeClass = isUp ? 'up' : (isDown ? 'down' : '');
            const changeHtml = s.change_1m ? `<span class="change-val ${changeClass}">${s.change_1m}</span>` : '';

            // 프리미엄 지표 HTML 생성
            let premiumHtml = '';
            if (s.upside && s.upside !== "N/A") {
                const fairValue = s.fair_value && s.fair_value !== "N/A" ? Number(s.fair_value).toLocaleString() : "분석중";
                const currentPrice = s.current_price ? Number(s.current_price).toLocaleString() : "N/A";
                premiumHtml = `
                    <div class="upside-row">
                        <span class="fair-value">적정가 ${fairValue} <span style="margin-left: 8px; opacity: 0.6;">현재가 ${currentPrice}</span></span>
                        <span class="upside-badge">${s.upside} 여력</span>
                    </div>
                `;
            }

            // 등급 배지 HTML 생성
            let gradesHtml = '';
            if (s.grades) {
                const getGradeClass = (g) => {
                    if (g === '최고') return 'excellent';
                    if (g === '우수') return 'good';
                    if (g === '보통') return 'fair';
                    if (g === '주의') return 'poor';
                    return '';
                };
                gradesHtml = `
                    <div class="grade-container">
                        <span class="grade-badge ${getGradeClass(s.grades.profit)}">수익:${s.grades.profit}</span>
                        <span class="grade-badge ${getGradeClass(s.grades.health)}">재무:${s.grades.health}</span>
                        <span class="grade-badge ${getGradeClass(s.grades.growth)}">성장:${s.grades.growth}</span>
                        ${s.opinion && s.opinion !== 'N/A' ? `<span class="opinion-badge">${s.opinion}</span>` : ''}
                    </div>
                `;
            }

            // 지표 HTML 생성
            let indicatorsHtml = `
                <span class="indicator">PER <b>${s.per}</b></span>
                <span class="separator">|</span>
                <span class="indicator">PBR <b>${s.pbr}</b></span>
            `;
            
            if (s.eps && s.eps !== "N/A") {
                indicatorsHtml += `
                    <span class="separator">|</span>
                    <span class="indicator">EPS <b>${s.eps}</b></span>
                `;
            }

            indicatorsHtml += `
                <span class="separator">|</span>
                <span class="indicator">DIV <b>${s.dividend === 'N/A' || s.dividend.includes('%') ? s.dividend : s.dividend + '%'}</b></span>
            `;

            stocksHtml += `
                <div class="stock-item-wrapper">
                    <div class="stock-item">
                        <span class="stock-name"><span class="rank">#${idx + 1}</span> ${s.name} ${changeHtml}</span>
                        <span class="profit-status ${statusClass}">${s.is_profitable}</span>
                    </div>
                    <div class="stock-indicators">
                        ${indicatorsHtml}
                    </div>
                    ${premiumHtml}
                    ${gradesHtml}
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
