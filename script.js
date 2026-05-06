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
        if (filter === 'US_THEME') keyword = '미국 테마';
        if (filter === 'US_SP') keyword = 'S&P500';
        if (filter === 'US_NDQ') keyword = '나스닥';
        if (filter === 'US_RSL') keyword = 'Russell 1000';
        if (filter === 'HEATMAP') keyword = '히트맵';
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
    } else if (filter === 'US_THEME') {
        // 미국 주요 성장 테마 바스켓에서 최근 강한 종목만 표시한다.
        const filtered = allData.filter(item => item.category === 'us_theme');
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
    } else if (filter === 'HEATMAP') {
        renderHeatmap();
    }
}

function parsePercent(value) {
    if (!value || value === 'N/A') return 0;
    return Number(String(value).replace('%', '').replace('+', '')) || 0;
}

function getHeatColor(change) {
    const intensity = Math.min(Math.abs(change) / 30, 1);
    if (change >= 0) {
        const light = 52 - intensity * 18;
        return `hsl(0, 86%, ${light}%)`;
    }
    const light = 50 - intensity * 12;
    return `hsl(220, 74%, ${light}%)`;
}

function getSizeMetric(item) {
    const marketCap = Number(item.market_cap) || 0;
    if (marketCap > 0) return marketCap;
    return (Number(item.current_price) || 0) * (Number(item.volume) || 0);
}

function getHeatSpanByRank(index) {
    if (index === 0) return { col: 4, row: 3 };
    if (index <= 2) return { col: 4, row: 2 };
    if (index <= 5) return { col: 3, row: 2 };
    if (index <= 11) return { col: 2, row: 2 };
    return { col: 2, row: 1 };
}

function createHeatmapSection(title, data) {
    const section = document.createElement('section');
    section.className = 'heatmap-section';

    const items = [...data]
        .sort((a, b) => getSizeMetric(b) - getSizeMetric(a))
        .slice(0, 36);

    const tiles = items.map((item, index) => {
        const change = parsePercent(item.change_1m);
        const span = getHeatSpanByRank(index);
        const flags = Array.isArray(item.risk_flags) ? item.risk_flags : [];
        const peakLabel = flags.includes('고점주의') ? '고점주의' : '고점아님';
        const sizeLabel = item.market_cap ? '시총 기준' : '거래대금 기준';
        return `
            <div class="heatmap-tile" title="${sizeLabel}" style="--tile-color:${getHeatColor(change)}; grid-column: span ${span.col}; grid-row: span ${span.row};">
                <div class="heatmap-stock">${item.name}</div>
                <div class="heatmap-theme">${item.theme}</div>
                <div class="heatmap-change">${item.change_1m || 'N/A'}</div>
                <span class="heatmap-flag">${peakLabel}</span>
            </div>
        `;
    }).join('');

    section.innerHTML = `
        <div class="heatmap-title">${title}</div>
        <div class="heatmap-grid">${tiles}</div>
    `;
    return section;
}

function renderHeatmap() {
    const container = document.getElementById('dashboard-items');
    container.innerHTML = '';
    container.classList.add('heatmap-mode');

    const domesticTheme = allData.filter(item => item.category === 'domestic_theme');
    const usTheme = allData.filter(item => item.category === 'us_theme');

    if (domesticTheme.length === 0 && usTheme.length === 0) {
        container.innerHTML = '<div style="text-align: center; color: #888; padding: 2rem; font-size: 1.2rem; grid-column: 1 / -1;">히트맵에 표시할 테마 데이터가 없습니다.</div>';
        return;
    }

    container.appendChild(createHeatmapSection('국내 테마 히트맵 (크기: 시가총액 / 색상: 1개월 수익률)', domesticTheme));
    container.appendChild(createHeatmapSection('미국 테마 히트맵 (크기: 시가총액 / 색상: 1개월 수익률)', usTheme));
}

function render(data) {
    const container = document.getElementById('dashboard-items');
    container.classList.remove('heatmap-mode');
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

            const getChangeBadge = (label, value) => {
                if (!value) return '';
                const changeClass = value.includes('+') ? 'up' : (value.includes('-') ? 'down' : '');
                return `<span class="change-val ${changeClass}">${label} ${value}</span>`;
            };
            const changeHtml = `${getChangeBadge('1M', s.change_1m)}${getChangeBadge('3M', s.change_3m)}`;
            const interestHtml = s.interest_level && s.interest_level !== 'N/A'
                ? `<span class="interest-badge interest-${s.interest_level}">관심도:${s.interest_level}</span>`
                : '';
            const rsiHtml = s.rsi && s.rsi !== 'N/A' ? `<span class="risk-badge rsi">RSI ${s.rsi}</span>` : '';
            const riskFlags = Array.isArray(s.risk_flags) ? s.risk_flags : [];
            const peakStatusHtml = riskFlags.includes('고점주의')
                ? '<span class="risk-badge high">고점주의</span>'
                : '<span class="risk-badge safe">고점아님</span>';
            const riskHtml = riskFlags
                .filter(flag => flag !== '고점주의')
                .map(flag => `<span class="risk-badge ${flag === '과열강함' ? 'high' : ''}">${flag}</span>`)
                .join('');

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
                        ${interestHtml}
                        ${rsiHtml}
                        ${peakStatusHtml}
                        ${riskHtml}
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
