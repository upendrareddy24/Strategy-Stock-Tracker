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
        item.className = 'stock-item';

        const roiClass = stock.roi >= 0 ? 'roi-positive' : 'roi-negative';
        const roiSign = stock.roi >= 0 ? '+' : '';

        const dailyClass = stock.daily_change >= 0 ? 'roi-positive' : 'roi-negative';
        const dailySign = stock.daily_change >= 0 ? '+' : '';

        const dateObj = new Date(stock.added_date);
        const dateStr = dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

        item.innerHTML = `
            <div style="flex: 1;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span class="stock-ticker">${stock.ticker}</span>
                    <span style="font-size: 0.7rem; color: var(--text-secondary); opacity: 0.7;">${dateStr}</span>
                </div>
                <div style="font-size: 0.85rem; color: var(--text-secondary);">
                    <div style="display: flex; justify-content: space-between;">
                        <span>Entry: $${stock.entry_price.toFixed(2)}</span>
                        <span>Cur: $${stock.current_price.toFixed(2)}</span>
                    </div>
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
        const data = await res.json();
        if (data.error) alert(data.error);
        else {
            await fetchStocks();
            closeModal();
            document.getElementById('tickerInput').value = '';
        }
    } catch (err) {
        alert('Error connection to server');
    }
    hideLoading();
}

async function deleteStock(id) {
    await fetch(`/api/delete_stock/${id}`, { method: 'DELETE' });
    fetchStocks();
}

async function updatePrices() {
    showLoading('Syncing global markets...');
    const res = await fetch('/api/update_prices');
    const stocks = await res.json();
    renderStocks(stocks);
    hideLoading();
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
