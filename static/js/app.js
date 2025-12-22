let currentStrategyForUpload = null;

document.addEventListener('DOMContentLoaded', () => {
    fetchStocks();
});

function fetchStocks() {
    showLoading('Loading stocks...');
    fetch('/api/stocks')
        .then(res => res.json())
        .then(stocks => {
            renderStocks(stocks);
            hideLoading();
        });
}

function renderStocks(stocks) {
    const lists = {
        '1SQ_INSB_52W': document.getElementById('list-1SQ_INSB_52W'),
        '2HvolHK': document.getElementById('list-2HvolHK'),
        '2_3XvolSq': document.getElementById('list-2_3XvolSq'),
        '2SQ_Bull_HK': document.getElementById('list-2SQ_Bull_HK'),
        '2HK_RVOL_SQ': document.getElementById('list-2HK_RVOL_SQ')
    };

    // Clear lists
    Object.values(lists).forEach(list => list.innerHTML = '');

    stocks.forEach(stock => {
        const item = document.createElement('div');
        item.className = 'stock-item';

        const roiClass = stock.roi >= 0 ? 'roi-positive' : 'roi-negative';
        const roiSign = stock.roi >= 0 ? '+' : '';

        const dailyClass = stock.daily_change >= 0 ? 'roi-positive' : 'roi-negative';
        const dailySign = stock.daily_change >= 0 ? '+' : '';

        // Format date: "Oct 24, 2023"
        const dateObj = new Date(stock.added_date);
        const dateStr = dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

        item.innerHTML = `
            <div class="stock-info" style="flex: 1;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                    <span class="stock-ticker">${stock.ticker}</span>
                    <span style="font-size: 0.75rem; color: #8b949e; background: rgba(255,255,255,0.05); padding: 2px 6px; border-radius: 4px;">${dateStr}</span>
                </div>
                <div class="stock-price">
                    <div style="display: flex; justify-content: space-between;">
                        <span>Entry: $${stock.entry_price.toFixed(2)}</span>
                        <span>Cur: $${stock.current_price.toFixed(2)}</span>
                    </div>
                </div>
            </div>
            <div class="stock-performance" style="margin-left: 15px; display: flex; flex-direction: column; align-items: flex-end;">
                <div class="${roiClass}" style="font-weight: 700; font-size: 1rem;">Total: ${roiSign}${stock.roi}%</div>
                <div class="${dailyClass}" style="font-size: 0.85rem; margin-top: 2px;">Daily: ${dailySign}${stock.daily_change.toFixed(2)}%</div>
                <button onclick="deleteStock(${stock.id})" style="background: transparent; border: none; color: #8b949e; cursor: pointer; font-size: 0.8rem; margin-top: 8px; padding: 4px;">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `;

        if (lists[stock.strategy]) {
            lists[stock.strategy].appendChild(item);
        }
    });
}

function openAddModal() {
    document.getElementById('addModal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('addModal').style.display = 'none';
}

function addStock() {
    const ticker = document.getElementById('tickerInput').value;
    const strategy = document.getElementById('strategySelect').value;

    if (!ticker) return alert('Please enter a ticker');

    showLoading('Adding stock...');
    fetch('/api/add_stock', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker, strategy })
    })
        .then(res => res.json())
        .then(data => {
            if (data.error) alert(data.error);
            else {
                fetchStocks();
                closeModal();
                document.getElementById('tickerInput').value = '';
            }
        })
        .catch(err => alert('Error adding stock'));
}

function deleteStock(id) {
    if (!confirm('Are you sure you want to delete this stock?')) return;

    fetch(`/api/delete_stock/${id}`, { method: 'DELETE' })
        .then(() => fetchStocks());
}

function updatePrices() {
    showLoading('Updating live prices...');
    fetch('/api/update_prices')
        .then(res => res.json())
        .then(stocks => {
            renderStocks(stocks);
            hideLoading();
        });
}

function triggerUpload(strategy) {
    currentStrategyForUpload = strategy;
    document.getElementById('fileUpload').click();
}

function handleFileUpload(input) {
    if (!input.files || !input.files[0]) return;

    const file = input.files[0];
    const formData = new FormData();
    formData.append('file', file);
    formData.append('strategy', currentStrategyForUpload);

    showLoading('Processing file with OCR/Excel analysis...');
    fetch('/api/upload', {
        method: 'POST',
        body: formData
    })
        .then(res => res.json())
        .then(data => {
            if (data.error) alert(data.error);
            else {
                fetchStocks();
                alert(`Successfully added ${data.length} stocks!`);
            }
            input.value = '';
        })
        .catch(err => {
            alert('Error uploading file');
            hideLoading();
        });
}

function showLoading(text) {
    document.getElementById('loadingText').innerText = text;
    document.getElementById('loading').style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loading').style.display = 'none';
}
