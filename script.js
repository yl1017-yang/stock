let allData = [];
let currentFilter = 'All';

async function init() {
    try {
        const response = await fetch('data.json');
        if (!response.ok) throw new Error('Not found');
        
        allData = await response.json();
        document.getElementById('loading').style.display = 'none';
        
        if (allData.length > 0) {
            const latestItem = allData.find(item => item.time);
            document.getElementById('update-time-val').textContent = latestItem ? latestItem.time : '-';
            renderMarketStatus();
            filterData('All'); // 초기 로딩 시 국내 테마 필터 즉시 적용
        }
    } catch (err) {
        console.error(err);
        document.getElementById('loading').style.display = 'none';
        document.getElementById('error').style.display = 'block';
    }
}


function renderMarketStatus() {
    const container = document.getElementById('market-status-line');
    if (!container) return;

    const statusItem = allData.find(item => item.category === 'market_status');
    const rows = statusItem && Array.isArray(statusItem.market_status) ? statusItem.market_status : [];
    if (rows.length === 0) {
        container.hidden = true;
        return;
    }

    container.hidden = false;
    container.innerHTML = rows.map(row => {
        const flags = Array.isArray(row.flags) ? row.flags : [];
        const level = row.level || 'N/A';
        const levelClass = level === '위험' ? 'danger' : (level === '주의' ? 'caution' : 'stable');
        const flagText = flags.length ? flags.join(', ') : '정상';
        const changeText = row.change_1m && row.change_1m !== 'N/A' ? `1M ${row.change_1m}` : '1M N/A';
        return `
            <span class="market-chip ${levelClass}" title="3M ${row.change_3m || 'N/A'} / ${flagText}">
                <strong>${row.market}</strong>
                <span>${level}</span>
                <em>${changeText}</em>
                <small>${flagText}</small>
            </span>
        `;
    }).join('');
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
        if (filter === 'YANG_STOCK') keyword = '양 종목';
        btn.classList.toggle('active', btn.textContent.trim() === keyword);
    });

    if (filter === 'All') {
        // 국내 주도 테마만 표시
        const filtered = allData.filter(item => item.category === 'domestic_theme');
        render(filtered);
    } else if (filter === 'Pass') {
        const filtered = allData.filter(item => (item.is_profitable || '').includes('Pass') && item.category === 'domestic_theme');
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
    } else if (filter === 'YANG_STOCK') {
        const filtered = allData.filter(item => item.category === 'yang_stock');
        render(filtered);
    }
}

function parsePercent(value) {
    if (!value || value === 'N/A') return 0;
    return Number(String(value).replace('%', '').replace('+', '')) || 0;
}


function parseNumberValue(value) {
    if (value === null || value === undefined || value === 'N/A') return 0;
    return Number(String(value).replace(/[^0-9.-]/g, '')) || 0;
}

function isUsStock(item) {
    return /^[A-Za-z]/.test(item.code || '');
}

function formatStockPrice(item, value) {
    const numeric = Number(value) || 0;
    if (!numeric) return 'N/A';
    if (isUsStock(item)) {
        return `$${numeric.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
    return `${Math.round(numeric).toLocaleString()}\uC6D0`;
}

function getRelevantMarketRisk(item) {
    const statusItem = allData.find(row => row.category === 'market_status');
    const rows = statusItem && Array.isArray(statusItem.market_status) ? statusItem.market_status : [];
    if (!rows.length) return { level: 'N/A', flags: [] };

    const markets = isUsStock(item)
        ? ['S&P500', '\uB098\uC2A4\uB2E5', 'Russell 1000']
        : ['\uCF54\uC2A4\uD53C', '\uCF54\uC2A4\uB2E5'];
    const matched = rows.filter(row => markets.includes(row.market));
    const targetRows = matched.length ? matched : rows;
    const rank = { '\uC704\uD5D8': 3, '\uC8FC\uC758': 2, '\uC591\uD638': 1 };
    return targetRows.reduce((worst, row) => {
        const currentRank = rank[row.level] || 0;
        const worstRank = rank[worst.level] || 0;
        return currentRank > worstRank ? row : worst;
    }, { level: 'N/A', flags: [] });
}

function getCustomActionNote(item) {
    const key = String(item.code || '').toUpperCase();
    const notes = {
        '316140': {
            mode: 'ready',
            note: '\uBB3C\uD0C0\uAE30 \uD6C4\uBCF4\uB85C\uB294 \uAC00\uC7A5 \uAD1C\uCC2E\uC740 \uD3B8. \uC800PBR, \uBC30\uB2F9, \uC740\uD589\uC8FC\uB77C \uBD84\uD560 \uC811\uADFC \uAC00\uB2A5.'
        },
        '271560': {
            mode: 'caution',
            note: '\uBC29\uC5B4\uC8FC \uC131\uACA9\uC740 \uC788\uC74C. 125,000\uC6D0 \uC9C0\uD0A4\uBA74 \uAD00\uCC30/\uC18C\uC561 \uCD94\uAC00\uB294 \uAC00\uB2A5. \uAE68\uC9C0\uBA74 \uBCF4\uB958.'
        },
        '006040': {
            mode: 'caution',
            note: '\uC2E4\uC801/\uC800PER/PBR\uC740 \uAD1C\uCC2E\uC74C. \uB2E4\uB9CC HMM \uBD88\uD655\uC2E4\uC131 \uB54C\uBB38\uC5D0 \uBB34\uB9AC\uD55C \uBB3C\uD0C0\uAE30\uB294 \uBCC4\uB85C.'
        },
        '006400': {
            mode: 'danger',
            note: '\uBB3C\uD0C0\uAE30 \uC870\uC2EC. \uC5C5\uD669 \uD68C\uBCF5 \uBCA0\uD305 \uC885\uBAA9\uC774\uB77C 400,000\uC6D0 \uBC29\uC5B4 \uD655\uC778 \uC804\uC5D0\uB294 \uC704\uD5D8.'
        },
        '010120': {
            mode: 'danger',
            note: '\uBB3C\uD0C0\uAE30 \uC870\uC2EC. \uAE30\uC5C5\uC740 \uC88B\uC9C0\uB9CC \uACE0\uBC38\uB958 \uC131\uC7A5 \uD14C\uB9C8\uC8FC\uB77C \uC9C0\uC218 \uBE60\uC9C8 \uB54C \uB354 \uD754\uB4E4\uB9BC.'
        },
        '047810': {
            mode: 'danger',
            note: '\uBB3C\uD0C0\uAE30 \uC870\uC2EC. \uBC29\uC0B0 \uC2A4\uD1A0\uB9AC\uB294 \uC788\uC9C0\uB9CC \uC800\uD3C9\uAC00\uAC00 \uC544\uB2C8\uB77C \uC131\uC7A5 \uD504\uB9AC\uBBF8\uC5C4 \uC885\uBAA9. 140,000\uC6D0 \uBC29\uC5B4 \uD655\uC778 \uD544\uC694.'
        }
    };
    return notes[key] || null;
}
function getAutoActionNote(item, context) {
    const name = item.name || item.code || '\uC774 \uC885\uBAA9';
    const pe = parseNumberValue(item.per);
    const pb = parseNumberValue(item.pbr);
    const targetGap = context.targetGap;
    const monthReturn = context.monthReturn;
    const rsi = context.rsi;
    const isMarketDanger = context.isMarketDanger;
    const isMarketCaution = context.isMarketCaution;
    const isChartWeak = context.isChartWeak;
    const myReturn = context.myReturn;
    const code = String(item.code || '').toUpperCase();
    const textKey = `${name} ${code}`.toUpperCase();
    const isEtf = /ETF|KODEX|TIGER|VOO|XNDU|QDTE|S&P|NASDAQ/.test(textKey);
    const isValue = (pb > 0 && pb <= 1.1) || (pe > 0 && pe <= 12);
    const isHighValueGrowth = (pe >= 35 || pb >= 4 || targetGap < 8) && !isEtf;
    const isOversold = rsi > 0 && rsi < 35;
    const isStrongLoss = myReturn <= -20 || monthReturn <= -20;

    if (isMarketDanger) {
        if (isEtf) {
            return { mode: 'caution', note: '\uC9C0\uC218\uD615\uC740 \uD55C \uBC88\uC5D0 \uBB3C\uD0C0\uAE30\uBCF4\uB2E4 \uC2DC\uC7A5\uC704\uD5D8 \uC644\uD654 \uD6C4 \uBD84\uD560\uC774 \uB354 \uC801\uD569.' };
        }
        if (isValue && !isChartWeak) {
            return { mode: 'caution', note: '\uC800\uD3C9\uAC00 \uC9C0\uD45C\uB294 \uC788\uC9C0\uB9CC \uC2DC\uC7A5\uC704\uD5D8 \uAD6C\uAC04. \uAE09\uD55C \uBB3C\uD0C0\uAE30\uBCF4\uB2E4 \uC18C\uC561 \uBD84\uD560/\uD604\uAE08\uBCF4\uC720 \uC6B0\uC120.' };
        }
        if (isHighValueGrowth) {
            return { mode: 'danger', note: '\uACE0\uBC38\uB958/\uC131\uC7A5 \uC131\uACA9\uC774 \uAC15\uD574 \uC9C0\uC218 \uD558\uB77D\uC5D0 \uB354 \uCDE8\uC57D. \uBC18\uB4F1 \uD655\uC778 \uC804 \uBB3C\uD0C0\uAE30 \uC870\uC2EC.' };
        }
        return { mode: 'danger', note: '\uC2DC\uC7A5\uC704\uD5D8\uC774 \uD06C\uBA74 \uAC1C\uBCC4 \uC800\uD3C9\uAC00\uB3C4 \uC798 \uC791\uB3D9\uD558\uC9C0 \uC54A\uC74C. \uCD94\uAC00\uB9E4\uC218\uBCF4\uB2E4 \uD558\uB77D \uBA48\uCD94\uB294\uC9C0 \uD655\uC778.' };
    }

    if (isStrongLoss && isOversold) {
        return { mode: 'caution', note: '\uB0D9\uD3ED\uACFC\uB300 \uAD6C\uAC04\uC77C \uC218\uB294 \uC788\uC9C0\uB9CC \uCD94\uC138\uAC00 \uC57D\uD568. \uCCAB \uBC18\uB4F1\uBCF4\uB2E4 \uC9C0\uC9C0\uD655\uC778 \uD6C4 \uC18C\uC561\uB9CC.' };
    }
    if (isChartWeak) {
        return { mode: 'caution', note: '\uCC28\uD2B8\uAC00 \uC57D\uD574\uC9C4 \uC0C1\uD0DC. \uD604\uC7AC\uAC00 \uCD94\uACA9\uBCF4\uB2E4 \uB300\uAE30/\uD68C\uBCF5\uAC00 \uD655\uC778\uC774 \uB354 \uC911\uC694.' };
    }
    if (targetGap >= 25 && isValue) {
        return { mode: 'ready', note: '\uBAA9\uD45C\uAC00\uB300\uBE44 \uC5EC\uC720\uC640 \uC800\uD3C9\uAC00 \uC9C0\uD45C\uAC00 \uC788\uC74C. \uB2E4\uB9CC \uD55C\uBC88\uC5D0 \uD06C\uAC8C \uC0AC\uAE30\uBCF4\uB2E4 \uBD84\uD560 \uC811\uADFC.' };
    }
    if (targetGap < 8 && targetGap !== 0) {
        return { mode: 'caution', note: '\uBAA9\uD45C\uAC00\uB300\uBE44 \uC5EC\uC720\uAC00 \uD06C\uC9C0 \uC54A\uC544 \uBB3C\uD0C0\uAE30 \uB9E4\uB825\uC774 \uC57D\uD568. \uCD94\uAC00\uB9E4\uC218\uBCF4\uB2E4 \uBCF4\uC720/\uB300\uAE30.' };
    }
    if (isEtf) {
        return { mode: isMarketCaution ? 'caution' : 'neutral', note: '\uC9C0\uC218\uD615\uC740 \uAC1C\uBCC4\uC8FC\uBCF4\uB2E4 \uBD84\uD560\uAE30\uAC04\uC774 \uC911\uC694. \uC2DC\uC7A5 \uC0C1\uD0DC\uAC00 \uC8FC\uC758\uBA74 \uD22C\uC785 \uC18D\uB3C4\uB97C \uB0AE\uCD94\uB294 \uD3B8.' };
    }
    if (myReturn <= -10) {
        return { mode: 'neutral', note: '\uC190\uC2E4\uAD6C\uAC04\uC774\uC9C0\uB9CC \uC9C0\uD45C\uAC00 \uD06C\uAC8C \uB098\uBE60\uC9C0\uC9C0 \uC54A\uC73C\uBA74 \uC18C\uC561 \uBD84\uD560\uB9CC \uAC80\uD1A0.' };
    }
    return { mode: 'neutral', note: '\uD604\uC7AC\uB294 \uAD00\uCC30 \uC704\uC8FC. \uCD94\uAC00\uB9E4\uC218\uB294 \uD558\uB77D\uC774 \uBA48\uCD94\uACE0 \uB300\uAE30/\uD68C\uBCF5\uAC00\uB97C \uB118\uB294\uC9C0 \uD655\uC778.' };
}
function buildActionGuideHtml(item) {
    if (item.category !== 'yang_stock') return '';

    const current = parseNumberValue(item.current_price);
    const purchase = parseNumberValue(item.purchase_price);
    if (!current || !purchase) return '';

    const myReturn = parsePercent(item.my_return);
    const targetGap = parsePercent(item.upside);
    const monthReturn = parsePercent(item.change_1m);
    const rsi = parseNumberValue(item.rsi);
    const stockRiskFlags = Array.isArray(item.risk_flags) ? item.risk_flags : [];
    const marketRisk = getRelevantMarketRisk(item);
    const marketLevel = marketRisk.level || 'N/A';
    const isMarketDanger = marketLevel === '\uC704\uD5D8';
    const isMarketCaution = marketLevel === '\uC8FC\uC758';
    const isChartWeak = monthReturn <= -12 || (rsi > 0 && rsi < 38);
    const hasEnoughGap = targetGap >= 15;

    let addPrice = current * 0.95;
    let addLabel = '\uC18C\uC561';
    let note = '\uD604\uC7AC\uAC00 \uC544\uB798\uC5D0\uC11C \uBD84\uD560\uB85C\uB9CC \uD655\uC778';
    let mode = 'neutral';

    if (isMarketDanger) {
        addPrice = current * 0.90;
        addLabel = '\uBCF4\uB958';
        note = '\uC2DC\uC7A5\uC704\uD5D8 \uAD6C\uAC04\uC774\uB77C \uBB3C\uD0C0\uAE30\uBCF4\uB2E4 \uD604\uAE08\uBCF4\uC720\uAC00 \uC6B0\uC120';
        mode = 'danger';
    } else if (isMarketCaution || isChartWeak || !hasEnoughGap) {
        addPrice = current * 0.93;
        addLabel = '\uB300\uAE30';
        note = '\uBC18\uB4F1 \uD655\uC778 \uC804\uAE4C\uC9C0 \uCD94\uAC00\uB9E4\uC218 \uAE30\uC900\uC744 \uB192\uC774\uB294 \uAD6C\uAC04';
        mode = 'caution';
    } else if (myReturn <= -10) {
        addLabel = '\uBD84\uD560';
        note = '\uD3C9\uADE0\uAC00\uB97C \uB0AE\uCD9C \uB54C\uB294 \uC815\uD574\uB454 \uAE08\uC561\uB9CC \uC0AC\uC6A9';
        mode = 'ready';
    }

    const autoAction = getAutoActionNote(item, {
        myReturn,
        targetGap,
        monthReturn,
        rsi,
        isMarketDanger,
        isMarketCaution,
        isChartWeak
    });
    if (autoAction) {
        note = autoAction.note;
        mode = autoAction.mode || mode;
    }

    const customAction = getCustomActionNote(item);
    if (customAction) {
        note = customAction.note;
        mode = customAction.mode || mode;
    }

    const waitPrice = current * (isChartWeak ? 1.07 : 1.05);
    const stopPrice = current * (isMarketDanger ? 0.92 : 0.90);
    const riskText = stockRiskFlags.length ? stockRiskFlags.slice(0, 2).join(', ') : '\uC885\uBAA9\uC704\uD5D8 \uB0AE\uC74C';

    return `
        <div class="action-guide ${mode}">
            <div class="action-guide-head">
                <strong>\uCC38\uACE0 \uB300\uC751\uAC00</strong>
                <span>\uC2DC\uC7A5 ${marketLevel} &middot; ${riskText}</span>
            </div>
            <div class="action-price-grid">
                <span><b>\uBB3C\uD0C0\uAE30 ${addLabel}</b><strong>${formatStockPrice(item, addPrice)}</strong></span>
                <span><b>\uB300\uAE30/\uD68C\uBCF5</b><strong>${formatStockPrice(item, waitPrice)}</strong></span>
                <span><b>\uC190\uC808\uACBD\uACE0</b><strong>${formatStockPrice(item, stopPrice)}</strong></span>
            </div>
            <p>${note}</p>
        </div>
    `;
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

    // 중복 종목 제거 및 테마 병합
    const uniqueItemsMap = new Map();
    data.forEach(item => {
        const key = item.code || item.name;
        if (uniqueItemsMap.has(key)) {
            const existing = uniqueItemsMap.get(key);
            if (item.theme && !existing.themes.includes(item.theme)) {
                existing.themes.push(item.theme);
            }
        } else {
            uniqueItemsMap.set(key, {
                ...item,
                themes: item.theme ? [item.theme] : []
            });
        }
    });

    const uniqueItems = Array.from(uniqueItemsMap.values()).map(item => {
        const fullThemes = item.themes.join(', ');
        let displayTheme = fullThemes;
        if (item.themes.length > 2) {
            displayTheme = item.themes.slice(0, 2).join(', ') + '...';
        }
        return {
            ...item,
            theme: displayTheme,
            fullTheme: fullThemes
        };
    });

    const items = uniqueItems
        .sort((a, b) => getSizeMetric(b) - getSizeMetric(a))
        .slice(0, 36);

    const tiles = items.map((item, index) => {
        const change = parsePercent(item.change_1m);
        const span = getHeatSpanByRank(index);
        const flags = Array.isArray(item.risk_flags) ? item.risk_flags : [];
        const peakLabel = flags.includes('고점주의') ? '고점주의' : '고점아님';
        const sizeLabel = item.market_cap ? '시총 기준' : '거래대금 기준';
        return `
            <div class="heatmap-tile" title="${sizeLabel}\n테마: ${item.fullTheme}" style="--tile-color:${getHeatColor(change)}; grid-column: span ${span.col}; grid-row: span ${span.row};">
                <div class="heatmap-stock">${item.name}</div>
                <div class="heatmap-theme" title="${item.fullTheme}">${item.theme}</div>
                <div class="heatmap-change">
                    <span>1M: ${item.change_1m || 'N/A'}</span>
                    <span style="opacity: 0.8; font-size: 0.7rem; font-weight: 700; margin-left: 2px;">3M: ${item.change_3m || 'N/A'}</span>
                </div>
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

    container.appendChild(createHeatmapSection('국내 테마 히트맵 (크기: 시가총액 / 색상: 1M, 3M 수익률)', domesticTheme));
    container.appendChild(createHeatmapSection('미국 테마 히트맵 (크기: 시가총액 / 색상: 1M, 3M 수익률)', usTheme));
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
                const isUS = /^[A-Za-z]/.test(s.code);
                const currency = isUS ? '$' : '원';
                const fVal = s.fair_value && s.fair_value !== "N/A" ? Number(s.fair_value).toLocaleString() : "분석중";
                const cVal = s.current_price ? Number(s.current_price).toLocaleString() : "N/A";
                
                const fairValueDisplay = isUS && fVal !== "분석중" ? `${currency}${fVal}` : (fVal !== "분석중" ? `${fVal}${currency}` : fVal);
                const currentPriceDisplay = isUS ? `${currency}${cVal}` : `${cVal}${currency}`;
                
                premiumHtml = `
                    <div class="upside-row">
                        <span class="fair-value">적정가 ${fairValueDisplay} <span style="margin-left: 8px; opacity: 0.6;">현재가 ${currentPriceDisplay}</span></span>
                        <span class="upside-badge">${s.upside} 목표가대비</span>
                    </div>
                `;
            }

            // 양 종목을 위한 내 수익률/매수가 영역 추가
            let purchaseHtml = '';
            if (s.category === 'yang_stock' && s.purchase_price && s.purchase_price !== "N/A") {
                const myReturnClass = s.my_return && s.my_return.includes('+') ? 'up' : (s.my_return && s.my_return.includes('-') ? 'down' : '');
                const isUS = /^[A-Za-z]/.test(s.code);
                const currency = isUS ? '$' : '원';
                const formattedPrice = Number(s.purchase_price).toLocaleString();
                const displayPrice = isUS ? `${currency}${formattedPrice}` : `${formattedPrice}${currency}`;
                purchaseHtml = `
                    <div class="purchase-row" style="background: rgba(255,255,255,0.04); padding: 8px 10px; border-radius: 4px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; border: 1px dashed rgba(255,255,255,0.1);">
                        <span style="font-size: 0.8rem; color: #aaa; font-weight: 500;">내 매수가: <strong style="color: #fff; font-size: 0.85rem;">${displayPrice}</strong></span>
                        <span class="change-val ${myReturnClass}" style="font-size: 0.85rem; font-weight: 800; padding: 2px 6px; border-radius: 4px;">수익률 ${s.my_return || 'N/A'}</span>
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

            const actionGuideHtml = buildActionGuideHtml(s);

            stocksHtml += `
                <div class="stock-item-wrapper">
                    ${purchaseHtml}
                    <div class="stock-item">
                        <span class="stock-name"><span class="rank">#${idx + 1}</span> ${s.name} ${changeHtml}</span>
                        <span class="profit-status ${statusClass}">${s.is_profitable}</span>
                    </div>
                    <div class="stock-indicators">
                        ${indicatorsHtml}
                    </div>
                    ${premiumHtml}
                    ${gradesHtml}
                    ${actionGuideHtml}
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


