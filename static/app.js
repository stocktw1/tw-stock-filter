/**
 * 台股技術指標篩選器 - 前端邏輯控制器 (Vanilla JS)
 */

document.addEventListener('DOMContentLoaded', () => {
    // 狀態變數
    let currentPeriod = '日線';
    let savedFormulas = {};
    let currentResults = [];
    let sortColumn = 'symbol';
    let sortAsc = true;

    // DOM 元素
    const periodButtons = document.querySelectorAll('.period-btn');
    const indicatorButtons = document.querySelectorAll('.btn-ind');
    const operatorButtons = document.querySelectorAll('.btn-op');
    const formulaInput = document.getElementById('formula-input');
    const btnClearFormula = document.getElementById('btn-clear-formula');
    const shiftNInput = document.getElementById('shift-n-input');
    const btnInsertShift = document.getElementById('btn-insert-shift');

    const savedFormulasSelect = document.getElementById('saved-formulas-select');
    const btnLoadFormula = document.getElementById('btn-load-formula');
    const btnDeleteFormula = document.getElementById('btn-delete-formula');
    const newFormulaNameInput = document.getElementById('new-formula-name');
    const btnSaveFormula = document.getElementById('btn-save-formula');

    const btnTestRun = document.getElementById('btn-test-run');
    const btnFullRun = document.getElementById('btn-full-run');

    const progressContainer = document.getElementById('progress-container');
    const progressStatusText = document.getElementById('progress-status-text');
    const progressPercentage = document.getElementById('progress-percentage');
    const progressBarFill = document.getElementById('progress-bar-fill');

    const resultsSummaryText = document.getElementById('result-summary-text');
    const resultsToolbar = document.getElementById('results-toolbar');
    const resultsTable = document.getElementById('results-table');
    const resultsTbody = document.getElementById('results-tbody');
    const tableSearchInput = document.getElementById('table-search-input');
    const btnExportCsv = document.getElementById('btn-export-csv');
    const stockCountText = document.getElementById('stock-count-text');

    // ----------------------------------------------------
    // 1. 初始化與載入後端狀態
    // ----------------------------------------------------
    async function init() {
        await fetchServerStatus();
        await fetchSavedFormulas();
        setupEventListeners();
    }

    async function fetchServerStatus() {
        try {
            const res = await fetch('/api/status');
            const data = await res.json();
            if (data.status === 'ok') {
                stockCountText.textContent = `資料庫共 ${data.stock_count} 檔個股 (${data.latest_date})`;
            }
        } catch (e) {
            stockCountText.textContent = '後端連線正常';
        }
    }

    async function fetchSavedFormulas() {
        try {
            const res = await fetch('/api/formulas');
            savedFormulas = await res.json();
            renderSavedFormulasOptions();
        } catch (e) {
            console.error('無法載入常用公式:', e);
        }
    }

    function renderSavedFormulasOptions() {
        savedFormulasSelect.innerHTML = '<option value="">-- 請選擇已儲存的公式 --</option>';
        for (const [name, formula] of Object.entries(savedFormulas)) {
            const option = document.createElement('option');
            option.value = name;
            option.textContent = name;
            savedFormulasSelect.appendChild(option);
        }
    }

    // ----------------------------------------------------
    // 2. 週期切換與文字插入
    // ----------------------------------------------------
    function setupEventListeners() {
        // 週期切換
        periodButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                periodButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentPeriod = btn.getAttribute('data-period');
                updateShiftButtonText();
            });
        });

        // 插入指標
        indicatorButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const name = btn.getAttribute('data-name');
                const code = btn.getAttribute('data-code');
                let prefix = '';
                if (currentPeriod === '週線') prefix = '週';
                if (currentPeriod === '月線') prefix = '月';

                let textToInsert = '';
                if (code.includes('(')) {
                    const params = code.substring(code.indexOf('('));
                    textToInsert = `${prefix}${name}${params} `;
                } else {
                    textToInsert = `${prefix}${name} `;
                }
                insertTextIntoFormula(textToInsert);
            });
        });

        // 插入運算符號
        operatorButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const insertText = btn.getAttribute('data-insert');
                if (insertText) {
                    insertTextIntoFormula(insertText);
                }
            });
        });

        // 插入 n日前 / n週前 / n月前
        btnInsertShift.addEventListener('click', () => {
            const nVal = shiftNInput.value || 1;
            let unit = '日';
            if (currentPeriod === '週線') unit = '週';
            if (currentPeriod === '月線') unit = '月';
            insertTextIntoFormula(`${nVal}${unit}前 `);
        });

        // 清空公式
        btnClearFormula.addEventListener('click', () => {
            formulaInput.value = '';
            formulaInput.focus();
        });

        // 載入公式
        btnLoadFormula.addEventListener('click', () => {
            const selectedName = savedFormulasSelect.value;
            if (selectedName && savedFormulas[selectedName]) {
                formulaInput.value = savedFormulas[selectedName];
                formulaInput.focus();
            } else {
                alert('請先選擇要載入的公式！');
            }
        });

        // 儲存公式
        btnSaveFormula.addEventListener('click', async () => {
            const name = newFormulaNameInput.value.trim();
            const formula = formulaInput.value.trim();
            if (!name) {
                alert('請輸入公式名稱！');
                return;
            }
            if (!formula) {
                alert('請先輸入篩選條件公式！');
                return;
            }
            try {
                const res = await fetch('/api/formulas', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, formula })
                });
                if (res.ok) {
                    savedFormulas[name] = formula;
                    renderSavedFormulasOptions();
                    savedFormulasSelect.value = name;
                    newFormulaNameInput.value = '';
                    alert(`✅ 公式「${name}」已儲存成功！`);
                }
            } catch (e) {
                alert('儲存公式失敗: ' + e);
            }
        });

        // 刪除公式
        btnDeleteFormula.addEventListener('click', async () => {
            const selectedName = savedFormulasSelect.value;
            if (!selectedName) return;
            if (!confirm(`確定要刪除公式「${selectedName}」嗎？`)) return;

            try {
                const res = await fetch(`/api/formulas/${encodeURIComponent(selectedName)}`, {
                    method: 'DELETE'
                });
                if (res.ok) {
                    delete savedFormulas[selectedName];
                    renderSavedFormulasOptions();
                }
            } catch (e) {
                alert('刪除失敗: ' + e);
            }
        });

        // 執行篩選
        btnTestRun.addEventListener('click', () => executeScreening(true));
        btnFullRun.addEventListener('click', () => executeScreening(false));

        // 表格搜尋與排序
        tableSearchInput.addEventListener('input', renderTable);
        btnExportCsv.addEventListener('click', exportToCsv);

        document.querySelectorAll('#results-table th[data-sort]').forEach(th => {
            th.addEventListener('click', () => {
                const col = th.getAttribute('data-sort');
                if (sortColumn === col) {
                    sortAsc = !sortAsc;
                } else {
                    sortColumn = col;
                    sortAsc = true;
                }
                renderTable();
            });
        });
    }

    function updateShiftButtonText() {
        let unit = '日';
        if (currentPeriod === '週線') unit = '週';
        if (currentPeriod === '月線') unit = '月';
        btnInsertShift.textContent = `n${unit}前`;
    }

    function insertTextIntoFormula(text) {
        const startPos = formulaInput.selectionStart;
        const endPos = formulaInput.selectionEnd;
        const currentVal = formulaInput.value;

        formulaInput.value = currentVal.substring(0, startPos) + text + currentVal.substring(endPos);
        formulaInput.selectionStart = formulaInput.selectionEnd = startPos + text.length;
        formulaInput.focus();
    }

    // ----------------------------------------------------
    // 3. 執行篩選請求
    // ----------------------------------------------------
    async function executeScreening(isTest) {
        const formula = formulaInput.value.trim();
        if (!formula) {
            alert('請先輸入篩選條件公式！');
            formulaInput.focus();
            return;
        }

        // 鎖定介面與開啟進度條
        btnTestRun.disabled = true;
        btnFullRun.disabled = true;
        progressContainer.style.display = 'block';
        progressBarFill.style.width = '20%';
        progressPercentage.textContent = '20%';
        progressStatusText.textContent = isTest ? '正在隨機抽樣 10 檔股票運算中...' : '正在平行分析全市場股票數據...';

        try {
            const startTime = performance.now();
            const res = await fetch('/api/screen', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    formula: formula,
                    period_type: currentPeriod,
                    is_test: isTest
                })
            });

            progressBarFill.style.width = '90%';
            progressPercentage.textContent = '90%';

            const data = await res.json();
            const duration = ((performance.now() - startTime) / 1000).toFixed(2);

            progressBarFill.style.width = '100%';
            progressPercentage.textContent = '100%';

            if (!res.ok || data.error) {
                alert('篩選發生錯誤: ' + (data.error || '未知錯誤'));
                resultsSummaryText.textContent = `❌ 錯誤: ${data.error}`;
                currentResults = [];
            } else {
                currentResults = data.matches || [];
                resultsSummaryText.textContent = `🎉 篩選完成！共分析 ${data.total_scanned} 檔股票，耗時 ${duration} 秒，找到 ${currentResults.length} 檔符合條件。`;
                resultsToolbar.style.display = currentResults.length > 0 ? 'flex' : 'none';
            }

            renderTable();
        } catch (e) {
            alert('請求伺服器失敗，請確認後端是否正在運行: ' + e);
            resultsSummaryText.textContent = '❌ 連線失敗';
        } finally {
            btnTestRun.disabled = false;
            btnFullRun.disabled = false;
            setTimeout(() => {
                progressContainer.style.display = 'none';
                progressBarFill.style.width = '0%';
            }, 800);
        }
    }

    // ----------------------------------------------------
    // 4. 渲染結果表格與匯出
    // ----------------------------------------------------
    function renderTable() {
        const query = tableSearchInput.value.trim().toLowerCase();
        let filtered = currentResults.filter(item => {
            if (!query) return true;
            return item.symbol.toLowerCase().includes(query) ||
                   item.date.includes(query) ||
                   item.indicators.toLowerCase().includes(query);
        });

        // 排序
        filtered.sort((a, b) => {
            let valA = a[sortColumn];
            let valB = b[sortColumn];
            if (sortColumn === 'close') {
                valA = parseFloat(valA) || 0;
                valB = parseFloat(valB) || 0;
            }
            if (valA < valB) return sortAsc ? -1 : 1;
            if (valA > valB) return sortAsc ? 1 : -1;
            return 0;
        });

        if (filtered.length === 0) {
            resultsTbody.innerHTML = `
                <tr class="empty-row">
                    <td colspan="4" class="text-center">${currentResults.length === 0 ? '查無符合條件的股票' : '無符合搜尋關鍵字的股票'}</td>
                </tr>
            `;
            return;
        }

        resultsTbody.innerHTML = filtered.map(item => `
            <tr>
                <td><span class="badge-ticker">${item.symbol}</span></td>
                <td>${item.date}</td>
                <td><span class="price-tag">${item.close}</span></td>
                <td>${item.indicators || '-'}</td>
            </tr>
        `).join('');
    }

    function exportToCsv() {
        if (!currentResults || currentResults.length === 0) {
            alert('目前沒有資料可供匯出！');
            return;
        }

        const headers = ['股票代碼', '基準日期', '收盤價', '指標數據明細'];
        const csvRows = [headers.join(',')];

        currentResults.forEach(r => {
            const escapedInd = `"${(r.indicators || '').replace(/"/g, '""')}"`;
            csvRows.push([r.symbol, r.date, r.close, escapedInd].join(','));
        });

        const csvString = '\uFEFF' + csvRows.join('\n');
        const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.setAttribute('href', url);
        link.setAttribute('download', `台股技術篩選結果_${new Date().toISOString().slice(0, 10)}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    // 啟動初始化
    init();
});
