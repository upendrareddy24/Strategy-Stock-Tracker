let currentStrategyForUpload = null;
let strategies = [];

document.addEventListener('DOMContentLoaded', () => {
    init();
});

async function init() {
    showLoading('Initializing dashboard...');
    await fetchStrategies();
    await fetchStocks();
    hideLoading();
}

async function fetchStrategies() {
    const res = await fetch('/api/strategies');
    strategies = await res.json();
    renderStrategyCards();
    updateStrategySelect();
}

function renderStrategyCards() {
    const grid = document.getElementById('strategyGrid');
    grid.innerHTML = '';

    strategies.forEach(strat => {
        const card = document.createElement('div');
        card.className = 'strategy-card';
        card.id = `strategy-${strat.name}`;

        card.innerHTML = `
            <div class="strategy-header">
                <div class="strategy-title-container">
                    <span class="strategy-name" 
                          contenteditable="true" 
                          onblur="renameStrategy(${strat.id}, this)"
                          onkeydown="handleRenameKey(event, this)">${strat.display_name}</span>
                    <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 2px;">${strat.name}</div>
                </div>
                <span class="strategy-badge" style="background: ${strat.color}22; color: ${strat.color}; border: 1px solid ${strat.color}44;">${strat.tier}</span>
            </div>
            
            <div id="stats-${strat.name}" style="display: flex; gap: 10px; margin-bottom: 20px; font-size: 0.75rem; font-weight: 700;">
                <div style="flex: 1; background: rgba(255,255,255,0.03); padding: 8px; border-radius: 6px; border: 1px solid var(--border-color);">
                    <div style="color: var(--text-secondary); text-transform: uppercase; font-size: 0.6rem; margin-bottom: 2px;">Strat ROI</div>
                    <span class="strat-roi-val" style="color: white;">0.00%</span>
                </div>
                <div style="flex: 1; background: rgba(255,255,255,0.03); padding: 8px; border-radius: 6px; border: 1px solid var(--border-color);">
                    <div style="color: var(--text-secondary); text-transform: uppercase; font-size: 0.6rem; margin-bottom: 2px;">Win Rate</div>
                    <span class="strat-win-val" style="color: white;">0%</span>
                </div>
            </div>

            <div class="upload-section">
                <button class="btn"
                    style="width: 100%; margin-bottom: 20px; background: ${strat.color}11; border: 1px dashed ${strat.color}66; color: ${strat.color};"
                    onclick="triggerUpload('${strat.name}')">
                    <i class="fas fa-file-upload"></i> Upload Selection
                </button>
            </div>
            <div class="stock-list" id="list-${strat.name}"></div>
        `;
        grid.appendChild(card);
    });
}

function updateStrategySelect() {
    const select = document.getElementById('strategySelect');
    select.innerHTML = strategies.map(s => `<option value="${s.name}">${s.display_name}</option>`).join('');
}

async function fetchStocks() {
    const res = await fetch('/api/stocks');
    const stocks = await res.json();
    renderStocks(stocks);
}

function renderStocks(stocks) {
    // Clear all lists first
    strategies.forEach(strat => {
        const list = document.getElementById(`list-${strat.name}`);
        if (list) list.innerHTML = '';
    });

    stocks.forEach(stock => {
        const list = document.getElementById(`list-${stock.strategy}`);
        if (!list) return;

        const item = document.createElement('div');

        // Dynamic Trend Coloring
        let trendClass = 'trend-neutral';
        if (stock.daily_change > 0) trendClass = 'trend-positive';
        else if (stock.daily_change < 0) trendClass = 'trend-negative';

        // Buy Signal Detection (e.g., > 2.5% daily move)
        const isBuySignal = stock.daily_change >= 2.5 ? 'buy-signal' : '';

        item.className = `stock-item ${trendClass} ${isBuySignal}`;

        const roiClass = stock.roi >= 0 ? 'roi-positive' : 'roi-negative';
        const roiSign = stock.roi >= 0 ? '+' : '';

        const dailyClass = stock.daily_change >= 0 ? 'roi-positive' : 'roi-negative';
        const dailySign = stock.daily_change >= 0 ? '+' : '';

        const dateObj = new Date(stock.added_date);
        const dateStr = dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

        const firstTrackedObj = new Date(stock.first_tracked);
        const firstTrackedStr = firstTrackedObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

        item.innerHTML = `
            <div style="flex: 1;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span class="stock-ticker">${stock.ticker}</span>
                    <div style="text-align: right;">
                        <span style="display: block; font-size: 0.7rem; color: var(--accent-blue); opacity: 0.9; font-weight: 600;">Last Check: ${dateStr}</span>
                        <span style="display: block; font-size: 0.65rem; color: var(--text-secondary); opacity: 0.6;">Tracking since: ${firstTrackedStr}</span>
                    </div>
                </div>
                <div style="font-size: 0.85rem; color: var(--text-secondary); display: flex; align-items: center; gap: 10px;">
                    <div style="flex: 1;">
                        <div style="display: flex; justify-content: space-between;">
                            <span>Entry: $${stock.entry_price.toFixed(2)}</span>
                            <span>Cur: $${stock.current_price.toFixed(2)}</span>
                        </div>
                        <div style="font-size: 0.7rem; color: var(--text-secondary); margin-top: 2px;">
                            Vol: ${formatVolume(stock.volume)} | 
                            <span style="color: ${stock.relative_volume >= 2 ? 'var(--accent-orange)' : 'var(--text-secondary)'}; font-weight: ${stock.relative_volume >= 2 ? '800' : '400'}">
                                RVOL: ${stock.relative_volume.toFixed(2)}x
                            </span>
                        </div>
                    </div>
                    <!-- Sparkline Container -->
                    <div class="sparkline-container" data-values="${stock.movement_history.join(',')}" style="width: 60px; height: 25px;"></div>
                </div>
                <div style="margin-top: 10px; font-size: 0.75rem; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 8px; color: #8b949e; line-height: 1.4;">
                    <i class="fas fa-bolt" style="color: var(--accent-orange); margin-right: 5px;"></i>
                    <span style="font-style: italic;">${stock.last_catalyst}</span>
                </div>
            </div>
            <div style="margin-left: 15px; display: flex; flex-direction: column; align-items: flex-end; justify-content: space-between;">
                <div style="text-align: right;">
                    <div class="${roiClass}" style="font-weight: 700; font-size: 1rem;">${roiSign}${stock.roi}%</div>
                    <div class="${dailyClass}" style="font-size: 0.75rem;">${dailySign}${stock.daily_change.toFixed(2)}%</div>
                </div>
                <button onclick="deleteStock(${stock.id})" style="background: transparent; border: none; color: #444; cursor: pointer; transition: color 0.2s;" onmouseover="this.style.color='var(--accent-red)'" onmouseout="this.style.color='#444'">
                    <i class="fas fa-times-circle"></i>
                </button>
            </div>
        `;
        list.appendChild(item);
    });

    // Calculate Analytics per Strategy (Historical)
    strategies.forEach(strat => {
        // Render List: Only stocks currently in this lane
        const stratStocks = stocks.filter(s => s.strategy === strat.name);

        // History Stats: Stocks that originated from this strategy
        const originStocks = stocks.filter(s => {
            if (s.original_strategy) return s.original_strategy === strat.name;
            return s.strategy === strat.name; // Fallback
        });

        const statsEl = document.getElementById(`stats-${strat.name}`);
        if (!statsEl) return;

        // Hide stats for Target/Stop lanes themselves (optional, but cleaner)
        if (['Target_Reached', 'Stop_Loss'].includes(strat.name)) {
            statsEl.style.opacity = '0.3';
        }

        if (originStocks.length === 0) return;

        // Calculate Win Rate based on Target Hits
        // Definition of "Win": ROI >= 5% OR Strategy is "Target_Reached"
        const winners = originStocks.filter(s => s.roi >= 5.0 || s.strategy === 'Target_Reached').length;
        const winRate = (winners / originStocks.length) * 100;

        // ROI Average
        const totalRoi = originStocks.reduce((acc, s) => acc + s.roi, 0);
        const avgRoi = totalRoi / originStocks.length;

        const roiValEl = statsEl.querySelector('.strat-roi-val');
        const winValEl = statsEl.querySelector('.strat-win-val');

        roiValEl.innerText = `${avgRoi.toFixed(2)}%`;
        roiValEl.style.color = avgRoi >= 0 ? 'var(--accent-green)' : 'var(--accent-red)';

        winValEl.innerText = `${winRate.toFixed(0)}%`;
        winValEl.style.color = winRate >= 50 ? 'var(--accent-green)' : 'var(--text-primary)';
    });

    initSparklines();
}

function initSparklines() {
    // Simple SVG sparkline implementation since we want to avoid heavy dependencies
    document.querySelectorAll('.sparkline-container').forEach(container => {
        const values = container.getAttribute('data-values').split(',').map(Number).filter(v => !isNaN(v));
        if (values.length < 2) return;

        const width = 60;
        const height = 25;
        const min = Math.min(...values, 0);
        const max = Math.max(...values, 1);
        const range = max - min;

        const points = values.map((v, i) => {
            const x = (i / (values.length - 1)) * width;
            const y = height - ((v - min) / range) * height;
            return `${x},${y}`;
        }).join(' ');

        const color = values[values.length - 1] >= 0 ? 'var(--accent-green)' : 'var(--accent-red)';

        container.innerHTML = `
            <svg width="${width}" height="${height}" style="overflow: visible;">
                <polyline points="${points}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
        `;
    });
}

function exportData() {
    window.location.href = '/api/export';
}

function formatVolume(num) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num;
}

async function renameStrategy(id, element) {
    const newName = element.innerText.trim();
    if (!newName) return;

    try {
        const res = await fetch('/api/rename_strategy', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id, display_name: newName })
        });
        const data = await res.json();
        if (data.success) {
            // Update local strategy object and select box
            const strat = strategies.find(s => s.id === id);
            if (strat) strat.display_name = newName;
            updateStrategySelect();
        }
    } catch (err) {
        console.error('Rename failed', err);
    }
}

function handleRenameKey(e, element) {
    if (e.key === 'Enter') {
        e.preventDefault();
        element.blur();
    }
}

async function clearAll() {
    if (!confirm('CRITICAL ACTION: Delete all tickers in all strategies?')) return;

    showLoading('Purging tracker data...');
    await fetch('/api/clear_all', { method: 'DELETE' });
    await fetchStocks();
    hideLoading();
}

function openAddModal() {
    document.getElementById('addModal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('addModal').style.display = 'none';
}

async function addStock() {
    const ticker = document.getElementById('tickerInput').value.trim();
    const strategy = document.getElementById('strategySelect').value;

    if (!ticker) return alert('Please enter a ticker');

    showLoading(`Fetching live data for ${ticker}...`);
    try {
        const res = await fetch('/api/add_stock', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticker, strategy })
        });

        if (!res.ok) {
            const errorText = await res.text();
            throw new Error(errorText || `Server error: ${res.status}`);
        }

        const data = await res.json();
        if (data.error) alert(data.error);
        else {
            await fetchStocks();
            closeModal();
            document.getElementById('tickerInput').value = '';
        }
    } catch (err) {
        console.error("Add stock failed:", err);
        alert(`System Busy: Heroku might be timing out or the ticker is unknown. Try again in a moment.`);
    }
    hideLoading();
}

async function deleteStock(id) {
    await fetch(`/api/delete_stock/${id}`, { method: 'DELETE' });
    fetchStocks();
}

async function updatePrices() {
    showLoading('Syncing global markets...');
    try {
        const res = await fetch('/api/update_prices');
        if (!res.ok) throw new Error(`Server returned ${res.status}`);
        const stocks = await res.json();
        renderStocks(stocks);
    } catch (err) {
        console.error("Update failed:", err);
        alert("Market sync timed out or failed. Check console for details.");
    } finally {
        hideLoading();
    }
}

function triggerUpload(strategy) {
    currentStrategyForUpload = strategy;
    document.getElementById('fileUpload').click();
}

async function handleFileUpload(input) {
    if (!input.files || !input.files[0]) return;

    const file = input.files[0];
    const formData = new FormData();
    formData.append('file', file);
    formData.append('strategy', currentStrategyForUpload);

    showLoading('AI Scanning: OCR & Excel Parse...');
    try {
        const res = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        if (data.error) alert(data.error);
        else {
            await fetchStocks();
            alert(`Succesfully deployed ${data.length} tickers to ${currentStrategyForUpload}`);
        }
    } catch (err) {
        alert('Upload integration failed');
    }
    input.value = '';
    hideLoading();
}

function showLoading(text) {
    document.getElementById('loadingText').innerText = text;
    document.getElementById('loading').style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loading').style.display = 'none';
}
