/**
 * 競艇予想サイトのメインJavaScriptファイル
 */

/**
 * 競艇AI予測API連携モジュール
 */
class BoatraceAPI {
    constructor(baseUrl = 'https://bortrace-ai-api-36737145161.asia-northeast1.run.app/api') {
        this.baseUrl = baseUrl;
    }
    
    async getVenues() {
        try {
            const response = await fetch(`${this.baseUrl}/venues`);
            if (!response.ok) {
                throw new Error('会場情報の取得に失敗しました');
            }
            return await response.json();
        } catch (error) {
            console.error('APIエラー:', error);
            return {};
        }
    }
    
    async getTodayRaces() { 
        try {
            const response = await fetch(`${this.baseUrl}/races/today`);
            if (!response.ok) throw new Error('レース情報取得失敗');
            return await response.json();
        } catch (error) {
            console.error('APIエラー:', error);
            return [];
        }
    }
    
    async getRacePrediction(raceId) {
        try {
            const response = await fetch(`${this.baseUrl}/prediction/${raceId}`);
            if (!response.ok) throw new Error('予測データ取得失敗');
            return await response.json();
        } catch (error) {
            console.error('APIエラー:', error);
            return null;
        }
    }

    async getPerformanceStats() {
        try {
            const response = await fetch(`${this.baseUrl}/stats`);
            if (!response.ok) throw new Error('統計データ取得失敗');
            return await response.json();
        } catch (error) {
            console.error('APIエラー:', error);
            return null;
        }
    }
}

// グローバルインスタンス
const boatraceAPI = new BoatraceAPI();

document.addEventListener('DOMContentLoaded', function() {
    // 初期化
    initApp();
    
    // タブ切り替え機能
    initTabs();
    
    // アニメーション
    initAnimations();
    
    // ボタンのイベントリスナー
    initEventListeners();
});

async function initApp() {
    await loadVenues(); 
    await loadRealTimeData();
    await loadAIPrediction();  // ← この行を追加
    await updatePerformanceStats();
    setInterval(async () => {
        await loadRealTimeData();
        await loadAIPrediction();  // ← この行を追加
    }, 5 * 60 * 1000);
}

// 今日のレース情報を読み込む
async function loadTodayRaces() {
    try {
        // APIから今日のレース一覧を取得
        const races = await boatraceAPI.getTodayRaces();
        
        if (races && races.length > 0) {
            // 最初のレースの予測を表示
            const firstRace = races[0];
            await displayRacePrediction(firstRace.race_id);
            
            // レースセレクターを作成（後で実装する場合）
            createRaceSelector(races);
        } else {
            console.log('今日のレースはありません');
        }
    } catch (error) {
        console.error('レース情報取得エラー:', error);
    }
}

async function loadRealTimeData() {
    const loading = document.getElementById('loading');
    const error = document.getElementById('error');
    const raceInfo = document.getElementById('race-info');
    const predictionContainer = document.getElementById('prediction-container');
    const statusIndicator = document.getElementById('status-indicator');

    try {
        // UI状態をリセット
        loading.style.display = 'block';
        error.style.display = 'none';
        raceInfo.style.display = 'none';
        predictionContainer.style.display = 'none';
        
        statusIndicator.className = 'status-indicator status-loading';
        statusIndicator.innerHTML = '<i class="fas fa-spinner fa-spin"></i> データ読み込み中...';

        // 実際のAPIからデータ取得
        const response = await fetch(`${boatraceAPI.baseUrl}/real-data-test`);
        
        if (!response.ok) {
            throw new Error(`HTTP Error: ${response.status}`);
        }

        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        // 成功時の処理
        loading.style.display = 'none';
        raceInfo.style.display = 'block';
        predictionContainer.style.display = 'block';
        
        statusIndicator.className = 'status-indicator status-success';
        statusIndicator.innerHTML = '<i class="fas fa-check-circle"></i> データ取得成功';

        // リアルデータを表示
        if (data.racer_extraction && data.racer_extraction.racers) {
            displayRealRacers(data.racer_extraction.racers);
            
            // レース情報更新
            updateRaceInfoFromReal(data);
        } else {
            throw new Error('選手データが見つかりません');
        }

            // タイムスタンプ更新（エラーハンドリング付き）
    if (data.timestamp) {
        updateTimestamp(data.timestamp);
    } else {
        console.warn('タイムスタンプデータがありません');
    }

    } catch (err) {
        console.error('データ取得エラー:', err);
        loading.style.display = 'none';
        error.style.display = 'block';
        
        statusIndicator.className = 'status-indicator status-error';
        statusIndicator.innerHTML = '<i class="fas fa-exclamation-triangle"></i> データ取得エラー';
        
        document.getElementById('error-message').textContent = err.message;
    }
}

// レース予測を表示
async function displayRacePrediction(raceId) {
    try {
        // APIからレース予測を取得
        const prediction = await boatraceAPI.getRacePrediction(raceId);
        
        if (!prediction) {
            console.error('予測データがありません');
            return;
        }
        
        // レース情報の更新
        updateRaceInfo(prediction);
        
        // 予測テーブルの更新
        updatePredictionTable(prediction);
        
    } catch (error) {
        console.error('予測表示エラー:', error);
    }
}

function updateRaceInfo(prediction) {
    // レースヘッダーの更新
    const raceHeader = document.querySelector('.race-header h3');
    if (raceHeader) {
        raceHeader.textContent = `桐生競艇 第1レース`;
    }
    
    // レース日時の更新
    const raceDate = document.querySelector('.race-header span');
    if (raceDate) {
        const now = new Date();
        const formattedDate = `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日`;
        raceDate.textContent = formattedDate;
    }
    
    // 詳細情報の更新
    const detailBoxes = document.querySelectorAll('.race-details .detail-box');
    if (detailBoxes.length >= 4) {
        detailBoxes[0].innerHTML = `<i class="fas fa-map-marker-alt"></i> 桐生競艇場`;
        detailBoxes[1].innerHTML = `<i class="fas fa-trophy"></i> レース番号: 1R`;
        detailBoxes[2].innerHTML = `<i class="fas fa-clock"></i> 最終更新: ${new Date().toLocaleTimeString('ja-JP')}`;
        detailBoxes[3].innerHTML = `<i class="fas fa-database"></i> 予測データ取得成功`;
    }
}

function updateRaceInfoFromReal(data) {
    // レースヘッダーの更新
    const raceHeader = document.querySelector('.race-header h3');
    if (raceHeader) {
        raceHeader.textContent = `桐生競艇 第1レース`;
    }
    
    // レース日時の更新
    const raceDate = document.querySelector('.race-header span');
    if (raceDate) {
        const now = new Date();
        const formattedDate = `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日`;
        raceDate.textContent = formattedDate;
    }
    
    // 詳細情報の更新
    const detailBoxes = document.querySelectorAll('.race-details .detail-box');
    if (detailBoxes.length >= 4) {
        detailBoxes[0].innerHTML = `<i class="fas fa-map-marker-alt"></i> 桐生競艇場`;
        detailBoxes[1].innerHTML = `<i class="fas fa-trophy"></i> レース番号: 1R`;
        detailBoxes[2].innerHTML = `<i class="fas fa-clock"></i> 最終更新: ${new Date().toLocaleTimeString('ja-JP')}`;
        detailBoxes[3].innerHTML = `<i class="fas fa-database"></i> データ取得成功`;
    }
}

// 予測テーブルを更新
function updatePredictionTable(prediction) {
    // モックデータを使用（APIの結果に合わせて調整）
    const predictions = [
        { boat_number: 1, name: '山田太郎', grade: 'A1', win_rate: 6.78, predicted_rank: 1, condition: 'up', note: '初日からスタート絶好調' },
        { boat_number: 2, name: '鈴木一郎', grade: 'A1', win_rate: 6.52, predicted_rank: 3, condition: 'normal', note: '2コースでの実績高い' },
        { boat_number: 3, name: '佐藤次郎', grade: 'A1', win_rate: 7.01, predicted_rank: 2, condition: 'up', note: '展示タイム1着' },
        { boat_number: 4, name: '田中三郎', grade: 'A2', win_rate: 5.43, predicted_rank: 5, condition: 'down', note: '直近成績振るわず' },
        { boat_number: 5, name: '高橋四郎', grade: 'A1', win_rate: 6.21, predicted_rank: 4, condition: 'normal', note: '住之江得意選手' },
        { boat_number: 6, name: '伊藤五郎', grade: 'A2', win_rate: 5.19, predicted_rank: 6, condition: 'down', note: 'モーター不調気味' }
    ];
    
    const tbody = document.querySelector('.prediction-table tbody');
    if (!tbody) return;
    
    // テーブルをクリア
    tbody.innerHTML = '';
    
    // 各選手の予測を表示
    predictions.forEach(player => {
        // 選手の調子に応じたアイコンを設定
        let conditionIcon = '';
        if (player.condition === 'up') {
            conditionIcon = '<i class="fas fa-arrow-up trend-up"></i> 好調';
        } else if (player.condition === 'down') {
            conditionIcon = '<i class="fas fa-arrow-down trend-down"></i> 不調';
        } else {
            conditionIcon = '<i class="fas fa-arrow-right"></i> 普通';
        }
        
        // 行を作成
        const row = document.createElement('tr');
        
        row.innerHTML = `
            <td><span class="player-number">${player.boat_number}</span></td>
            <td class="player-name">${player.name}</td>
            <td>${player.grade}</td>
            <td>${player.win_rate.toFixed(2)}</td>
            <td class="prediction-score">${player.predicted_rank}</td>
            <td>${conditionIcon}</td>
            <td>${player.note || '-'}</td>
        `;
        
        tbody.appendChild(row);
    });
}

// パフォーマンス統計を更新
async function updatePerformanceStats() {
    try {
        // APIから統計情報を取得
        const stats = await boatraceAPI.getPerformanceStats();
        
        if (!stats) {
            console.error('統計データがありません');
            return;
        }
        
        // モックデータを使用（APIの結果に合わせて調整）
        const mockStats = {
            win_rate: 0.945,
            exacta_rate: 0.823,
            trifecta_rate: 0.678,
            avg_payout: 28500
        };
        
        // 統計カードの更新
        const statNumbers = document.querySelectorAll('.stat-number');
        if (statNumbers.length >= 4) {
            statNumbers[0].textContent = `${(mockStats.win_rate * 100).toFixed(1)}%`;
            statNumbers[1].textContent = `${(mockStats.exacta_rate * 100).toFixed(1)}%`;
            statNumbers[2].textContent = `${(mockStats.trifecta_rate * 100).toFixed(1)}%`;
            statNumbers[3].textContent = `¥${mockStats.avg_payout.toLocaleString()}`;
        }
        
    } catch (error) {
        console.error('統計情報取得エラー:', error);
    }
}

// レース選択セレクターを作成
function createRaceSelector(races) {
    // 実装予定（多くのレースを選択するためのUIを追加）
    console.log('レースセレクター：将来の実装');
}

// タブ切り替え機能
function initTabs() {
    const tabs = document.querySelectorAll('.model-tab');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', function() {
            // アクティブなタブを切り替え
            tabs.forEach(t => t.classList.remove('active'));
            this.classList.add('active');
            
            // タブコンテンツの切り替え（実際の実装ではコンテンツを表示）
            console.log(`タブ切り替え: ${this.textContent}`);
        });
    });
}

// アニメーション初期化
function initAnimations() {
    // 要素のアニメーション
    const elementsToAnimate = document.querySelectorAll('.feature-card, .stat-card, .news-card');
    elementsToAnimate.forEach(elem => {
        elem.style.opacity = 0;
        elem.style.transform = 'translateY(20px)';
        elem.style.transition = 'all 0.5s ease-out';
    });
    
    // スクロール時のアニメーション
    function animateOnScroll() {
        elementsToAnimate.forEach(elem => {
            const elemPosition = elem.getBoundingClientRect().top;
            const screenPosition = window.innerHeight / 1.3;
            
            if (elemPosition < screenPosition) {
                elem.style.opacity = 1;
                elem.style.transform = 'translateY(0)';
            }
        });
    }
    
    // 精度メーターアニメーション
    setTimeout(() => {
        const accuracyFill = document.querySelector('.accuracy-fill');
        if (accuracyFill) {
            accuracyFill.style.width = '87%';
        }
    }, 500);
    
    // スクロールイベントリスナー
    window.addEventListener('scroll', animateOnScroll);
    
    // 初期表示時にもアニメーション実行
    animateOnScroll();
}

// イベントリスナーの初期化
function initEventListeners() {
    // 会員登録フォーム
    const signupForm = document.querySelector('.signup-form');
    if (signupForm) {
        signupForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const email = this.querySelector('input[type="email"]').value;
            alert(`${email} を登録しました。メールをご確認ください。`);
        });
    }

    // ナビゲーションリンク（スムーズスクロール）
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            
            const targetId = this.getAttribute('href');
            const targetElement = document.querySelector(targetId);
            
            if (targetElement) {
                window.scrollTo({
                    top: targetElement.offsetTop - 80,
                    behavior: 'smooth'
                });
            }
        });
    });

    const aiUpdateBtn = document.querySelector('.ai-update-btn');
    if (aiUpdateBtn) {
        aiUpdateBtn.addEventListener('click', updateAIPrediction);
    }
    
    // AI予想を更新ボタンの代替セレクター
    const aiButtons = document.querySelectorAll('button');
    aiButtons.forEach(btn => {
        if (btn.textContent.includes('AI予想') || btn.textContent.includes('🤖')) {
            btn.addEventListener('click', updateAIPrediction);
        }
    });
}

// グローバル変数追加
let selectedVenue = null;
let selectedRace = null;

// 新しい関数追加
function selectVenue(venueCode, venueName) {
    selectedVenue = venueCode;
    
    // 選択状態の更新
    document.querySelectorAll('.venue-card').forEach(card => {
        card.classList.remove('selected');
    });
    event.target.classList.add('selected');
    
    // レース選択表示
    showRaceSelector();
    
    // 情報表示更新
    document.getElementById('selected-venue-name').textContent = venueName;
    document.getElementById('selected-race-info').textContent = '';
}

function showRaceSelector() {
    const raceSelector = document.getElementById('race-selector');
    const raceButtons = document.getElementById('race-buttons');
    
    raceSelector.style.display = 'block';
    raceButtons.innerHTML = '';
    
    // 1R〜12Rのボタン作成
    for (let i = 1; i <= 12; i++) {
        const raceBtn = document.createElement('button');
        raceBtn.className = 'race-btn';
        raceBtn.textContent = `${i}R`;
        raceBtn.onclick = () => selectRace(i);
        raceButtons.appendChild(raceBtn);
    }
}

function selectRace(raceNumber) {
    selectedRace = raceNumber;
    
    // 選択状態の更新
    document.querySelectorAll('.race-btn').forEach(btn => {
        btn.classList.remove('selected');
    });
    event.target.classList.add('selected');
    
    // データ取得
    loadSelectedRaceData();
    
    // 情報表示更新
    document.getElementById('selected-race-info').textContent = ` - 第${raceNumber}レース`;
}

async function loadSelectedRaceData() {
    if (!selectedVenue || !selectedRace) return;
    
    try {
        const response = await fetch(`${boatraceAPI.baseUrl}/race-data?venue=${selectedVenue}&race=${selectedRace}`);
        const data = await response.json();
        
        if (data.racer_extraction && data.racer_extraction.racers) {
            displayRealRacers(data.racer_extraction.racers);
            updateRaceInfoFromSelected(data);
        }
    } catch (error) {
        console.error('レースデータ取得エラー:', error);
    }
}

function updateRaceInfoFromSelected(data) {
    const raceHeader = document.querySelector('.race-header h3');
    if (raceHeader) {
        raceHeader.textContent = `${data.race_info.venue_name} 第${data.race_info.race_number}レース`;
    }
    
    // 詳細情報も更新
    const venueNameElement = document.getElementById('venue-name');
    const raceNumberElement = document.getElementById('race-number');
    
    if (venueNameElement) {
        venueNameElement.textContent = data.race_info.venue_name;
    }
    
    if (raceNumberElement) {
        raceNumberElement.textContent = `${data.race_info.race_number}R`;
    }
}
// 実際の選手データを表示（追加が必要）
function displayRealRacers(racers) {
    const tbody = document.getElementById('racers-tbody');
    tbody.innerHTML = '';

    racers.forEach((racer, index) => {
        const row = document.createElement('tr');
        row.className = 'fade-in';
        row.style.animationDelay = `${index * 0.1}s`;
        
        // クラス別の色分け
        let classColor = '';
        switch(racer.class) {
            case 'A1': classColor = 'class-a1'; break;
            case 'A2': classColor = 'class-a2'; break;
            case 'B1': classColor = 'class-b1'; break;
            case 'B2': classColor = 'class-b2'; break;
            default: classColor = 'class-b1';
        }
        
        row.innerHTML = `
            <td><span class="player-number">${racer.boat_number}</span></td>
            <td class="player-name">${racer.name}</td>
            <td><span class="class-badge ${classColor}">${racer.class}</span></td>
            <td>${racer.age}歳</td>
            <td>${racer.weight}</td>
            <td>${racer.region}</td>
            <td>${racer.branch}</td>
            <td>#${racer.registration_number}</td>
        `;
        
        tbody.appendChild(row);
    });
}

function updateTimestamp(timestamp) {
    const date = new Date(timestamp);
    const formatted = date.toLocaleString('ja-JP', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    
    // 複数の要素を試行（確実に更新）
    const possibleElements = [
        'last-updated',
        'selected-race-info', 
        'ai-last-updated'
    ];
    
    let updated = false;
    
    for (const elementId of possibleElements) {
        const element = document.getElementById(elementId);
        if (element) {
            element.textContent = `最終更新: ${formatted}`;
            updated = true;
            break;
        }
    }
    
    // どの要素も見つからない場合は新しく作成
    if (!updated) {
        const detailBoxes = document.querySelector('.race-details');
        if (detailBoxes) {
            const timeBox = document.createElement('div');
            timeBox.className = 'detail-box';
            timeBox.innerHTML = `<i class="fas fa-clock"></i> 最終更新: ${formatted}`;
            detailBoxes.appendChild(timeBox);
        }
    }
}

// モックデータ生成関数（loadAIPrediction関数の前に追加）
function generateMockAIPrediction() {
    return {
        race_id: "20250528_01_01",
        forecast: {
            win: 1,
            exacta: [1, 3],
            trio: [1, 3, 2]
        },
        predictions: [
            { boat_number: 1, racer_id: 10001, predicted_rank: 1, rank_probabilities: [0.45, 0.25, 0.15, 0.10, 0.03, 0.02], expected_value: 1.85 },
            { boat_number: 2, racer_id: 10002, predicted_rank: 4, rank_probabilities: [0.15, 0.20, 0.25, 0.25, 0.10, 0.05], expected_value: 3.65 },
            { boat_number: 3, racer_id: 10003, predicted_rank: 2, rank_probabilities: [0.25, 0.30, 0.20, 0.15, 0.08, 0.02], expected_value: 2.50 }
        ]
    };
}

/**
 * AI予想データの取得と表示
 */

// 既存のloadAIPrediction関数を以下に置き換え
async function loadAIPrediction() {
    try {
        console.log('AI予想データ取得開始...');
        
        // 固定のレースID（後で動的に変更可能）
        const today = new Date();
        const dateStr = today.getFullYear().toString() + 
                       (today.getMonth() + 1).toString().padStart(2, '0') + 
                       today.getDate().toString().padStart(2, '0');
        const raceId = `${dateStr}0101`; // 桐生1レース
        
        const response = await fetch(`${boatraceAPI.baseUrl}/prediction/${raceId}`);
        
        if (!response.ok) {
            throw new Error(`HTTP Error: ${response.status}`);
        }
        
        const prediction = await response.json();
        
        // AI予想セクションを表示
        const aiSection = document.getElementById('ai-predictions');
        if (aiSection) {
            aiSection.style.display = 'block';
        }
        
        // 予測結果を表示
        if (prediction.ai_predictions && prediction.ai_predictions.predictions && prediction.ai_predictions.predictions.length > 0) {
            const topPrediction = prediction.ai_predictions.predictions[0];
            
            // DOM要素の存在チェック付きで更新
            const winnerElement = document.getElementById('predicted-winner');
            if (winnerElement) {
                winnerElement.textContent = topPrediction.boat_number;
            }
            
            const winnerNameElement = document.getElementById('predicted-winner-name');
            if (winnerNameElement) {
                winnerNameElement.textContent = `選手${topPrediction.boat_number}`;
            }
            
            const probabilityElement = document.getElementById('win-probability');
            if (probabilityElement) {
                const winProb = Math.round(topPrediction.normalized_probability * 100);
                probabilityElement.textContent = `${winProb}%`;
            }
            
            const confidenceElement = document.getElementById('win-confidence');
            if (confidenceElement) {
                confidenceElement.textContent = '85';
            }
        }
        updateAITimestamp();
        console.log('AI予想データ取得完了');
        
    } catch (error) {
        console.error('AI予想エラー:', error);
        // エラー時はモックデータ表示
        document.getElementById('predicted-winner').textContent = '1';
        document.getElementById('predicted-winner-name').textContent = '予測中...';
        document.getElementById('win-probability').textContent = '-%';
    }
}

function updateAITimestamp() {
    const now = new Date();
    const timeString = now.toLocaleTimeString('ja-JP');
    const timestampElement = document.getElementById('ai-last-updated');
    if (timestampElement) {
        timestampElement.textContent = `最終更新: ${timeString}`;
    } else {
        console.warn('ai-last-updated要素が見つかりません');
    }
}

async function updateAIPrediction() {
    try {
        console.log('AI予想更新開始...');
        
        // 現在表示中の選手データを取得
        const currentRacers = getCurrentRacersData();
        
        if (!currentRacers || currentRacers.length === 0) {
            alert('選手データが読み込まれていません');
            return;
        }
        
        // AI予想API呼び出し
        const response = await fetch(`${boatraceAPI.baseUrl}/ai-prediction-simple`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                racers: currentRacers
            })
        });
        
        if (!response.ok) {
            throw new Error(`AI予想API エラー: ${response.status}`);
        }
        
        const aiResult = await response.json();
        
        // AI予想結果を画面に表示
        displayAIPredictionResult(aiResult);
        
    } catch (error) {
        console.error('AI予想エラー:', error);
        
        (`AI予想の更新に失敗しました: ${error.message}`);
    }
}

/**
 * 現在表示中の選手データを取得
 */
function getCurrentRacersData() {
    const racerRows = document.querySelectorAll('#racers-tbody tr');
    const racers = [];
    
    racerRows.forEach((row, index) => {
        const cells = row.querySelectorAll('td');
        if (cells.length >= 8) {
            const racer = {
                boat_number: parseInt(cells[0].textContent.trim()),
                name: cells[1].textContent.trim(),
                class: cells[2].textContent.trim(),
                age: parseInt(cells[3].textContent.replace('歳', '')),
                weight: cells[4].textContent.trim(),
                region: cells[5].textContent.trim(),
                branch: cells[6].textContent.trim(),
                registration_number: cells[7].textContent.replace('#', '').trim()
            };
            racers.push(racer);
        }
    });
    
    return racers;
}

/**
 * AI予想結果を表示
 */
function displayAIPredictionResult(aiResult) {
    console.log('AI予想結果:', aiResult);
    
    if (aiResult.ai_predictions && aiResult.ai_predictions.predictions) {
        const predictions = aiResult.ai_predictions.predictions;
        predictions.sort((a, b) => a.predicted_rank - b.predicted_rank);
        
        // 画面の予想結果セクションに表示
        const winnerElement = document.getElementById('predicted-winner');
        if (winnerElement) {
            winnerElement.textContent = predictions[0].boat_number;
        }
        
        const probabilityElement = document.getElementById('win-probability');
        if (probabilityElement) {
            const winProb = Math.round(predictions[0].normalized_probability * 100);
            probabilityElement.textContent = `${winProb}%`;
        }
        
        // 推奨舟券の存在確認
        if (aiResult.ai_predictions.recommendations) {
            const recs = aiResult.ai_predictions.recommendations;
            console.log('全recommendations:', recs);
            console.log('trio_patterns:', recs.trio_patterns);
            
            if (document.getElementById('recommended-win')) {
                document.getElementById('recommended-win').textContent = recs.win.boat_number;
            }
            if (document.getElementById('recommended-exacta')) {
                document.getElementById('recommended-exacta').textContent = recs.exacta.combination.join('-');
            }
　　　　　　　　if (document.getElementById('recommended-trifecta')) {
                if (recs.trio_patterns && recs.trio_patterns.length > 0) {
        // 複数パターンを表示
                    let patternsText = '';
                    recs.trio_patterns.forEach((pattern, index) => {
                        if (index > 0) patternsText += ' / ';
                        patternsText += pattern.combination.join('-');
                    });
                    document.getElementById('recommended-trifecta').textContent = patternsText;
                }
　　　　　　　　}
        } else {
            console.log('recommendations が存在しません');
        }
    }
    console.log('AI予想結果が画面に表示されました');
}

// initEventListeners関数のAI部分を以下に修正
function initAIButton() {
    const aiButtons = document.querySelectorAll('button');
    aiButtons.forEach(btn => {
        if (btn.textContent.includes('AI予想') || btn.textContent.includes('🤖')) {
            btn.onclick = updateAIPrediction;
        }
    });
}

// 初期化に追加
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(initAIButton, 1000);
});

/**
 * 競艇場開催状況UI機能
 * script.jsの最後に追加
 */

// グローバル変数
let currentSelectedVenue = null;
let currentSelectedRace = null;
let venueStatusData = {};

/**
 * 地域フィルター初期化
 */
function initRegionFilter() {
    const regionBtns = document.querySelectorAll('.region-btn');
    const venueCards = document.querySelectorAll('.venue-card');

    regionBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            // アクティブ状態の切り替え
            regionBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');

            const selectedRegion = this.dataset.region;

            // 会場カードの表示/非表示
            venueCards.forEach(card => {
                if (selectedRegion === 'all' || card.dataset.region === selectedRegion) {
                    card.style.display = 'block';
                } else {
                    card.style.display = 'none';
                }
            });
        });
    });
}

/**
 * 会場選択
 */
function selectVenue(venueCode, venueName) {
    currentSelectedVenue = venueCode;
    
    // 選択状態の更新
    document.querySelectorAll('.venue-card').forEach(card => {
        card.classList.remove('selected');
    });
    
    const selectedCard = document.querySelector(`[data-venue="${venueCode}"]`);
    if (selectedCard) {
        selectedCard.classList.add('selected');
    }
    
    // 詳細パネル表示
    showVenueDetail(venueCode, venueName);
}
    
/**
 * レース選択
 */
function selectRace(venueCode, raceNumber, venueName) {
    currentSelectedRace = raceNumber;
    
    // 選択状態の更新
    document.querySelectorAll('.race-slot').forEach(slot => {
        slot.classList.remove('selected');
    });
    
    event.target.closest('.race-slot').classList.add('selected');
    
    // 出走表データ取得
    loadSelectedRaceData(venueCode, raceNumber, venueName);
}

/**
 * 選択されたレースのデータ取得
 */
async function loadSelectedRaceData(venueCode = currentSelectedVenue, raceNumber = currentSelectedRace, venueName = '') {
    if (!venueCode || !raceNumber) {
        console.log('会場またはレースが選択されていません');
        return;
    }
    
    try {
        const response = await fetch(`${boatraceAPI.baseUrl}/race-data?venue=${venueCode}&race=${raceNumber}`);
        const data = await response.json();
        
        if (data.racer_extraction && data.racer_extraction.racers) {
            // レース情報表示
            showRaceInfo(venueCode, raceNumber, venueName || data.race_info?.venue_name);
            
            // 選手データ表示
            displayRealRacers(data.racer_extraction.racers);
            
            // AI予想取得
            await loadAIPrediction();
        }
    } catch (error) {
        console.error('レースデータ取得エラー:', error);
        showRaceError('レースデータの取得に失敗しました');
    }
}

/**
 * レース情報表示
 */
function showRaceInfo(venueCode, raceNumber, venueName) {
    const raceInfo = document.getElementById('race-info');
    const predictionContainer = document.getElementById('prediction-container');
    const raceTitle = document.getElementById('race-title');
    const venueNameElement = document.getElementById('venue-name');
    const raceNumberElement = document.getElementById('race-number');
    const dataStatusElement = document.getElementById('data-status');
    
    if (raceInfo) raceInfo.style.display = 'block';
    if (predictionContainer) predictionContainer.style.display = 'block';
    
    if (raceTitle) raceTitle.textContent = `${venueName || '競艇場'} 第${raceNumber}レース`;
    if (venueNameElement) venueNameElement.textContent = venueName || '競艇場';
    if (raceNumberElement) raceNumberElement.textContent = `${raceNumber}R`;
    if (dataStatusElement) dataStatusElement.textContent = 'データ取得成功';
    
    // タイムスタンプ更新
    updateTimestamp(new Date().toISOString());
}

/**
 * 詳細パネルを閉じる
 */
function closeDetail() {
    const detailPanel = document.getElementById('detail-panel');
    if (detailPanel) {
        detailPanel.classList.remove('active');
    }
}

/**
 * エラー表示
 */
function showVenueError(message) {
    const loading = document.getElementById('loading');
    const error = document.getElementById('error');
    const errorMessage = document.getElementById('error-message');
    const statusIndicator = document.getElementById('status-indicator');
    
    if (loading) loading.style.display = 'none';
    if (error) error.style.display = 'block';
    if (errorMessage) errorMessage.textContent = message;
    if (statusIndicator) {
        statusIndicator.className = 'status-indicator status-error';
        statusIndicator.innerHTML = '<i class="fas fa-exclamation-triangle"></i> エラー';
    }
}

function showRaceError(message) {
    alert(message); // 簡易実装
}

 //showVenueDetail関数を実API版に置き換え
 
async function showVenueDetail(venueCode, venueName) {
    const detailPanel = document.getElementById('detail-panel');
    const detailTitle = document.getElementById('detail-title');
    const raceTimeline = document.getElementById('race-timeline');
    
    if (!detailPanel || !detailTitle || !raceTimeline) return;
    
    // タイトル更新
    detailTitle.textContent = `${venueName}競艇場 詳細情報`;
    
    try {
        // 実際のスケジュールデータを取得
        const response = await fetch(`${boatraceAPI.baseUrl}/venue-schedule/${venueCode}`);
        const scheduleData = await response.json();
        
        if (!scheduleData.is_active) {
            raceTimeline.innerHTML = '<div class="no-races">本日は開催されていません</div>';
            detailPanel.classList.add('active');
            return;
        }
        
        // レースタイムライン生成（実データ使用）
        raceTimeline.innerHTML = '';
        
        scheduleData.schedule.forEach(raceInfo => {
            const raceSlot = document.createElement('div');
            let slotClass = `race-slot ${raceInfo.status}`;
            
            raceSlot.className = slotClass;
            raceSlot.innerHTML = `
                <div class="race-number">${raceInfo.race_number}R</div>
                <div class="race-schedule">${raceInfo.status === 'completed' ? '済' : raceInfo.scheduled_time}</div>
            `;
            
            // 未来・進行中のレースにクリックイベント
            if (raceInfo.status === 'upcoming' || raceInfo.status === 'live') {
                raceSlot.addEventListener('click', function() {
                    selectRace(venueCode, raceInfo.race_number, venueName);
                });
            }
            
            raceTimeline.appendChild(raceSlot);
        });
        
    } catch (error) {
        console.error('スケジュール取得エラー:', error);
        raceTimeline.innerHTML = '<div class="error">スケジュール取得に失敗しました</div>';
    }
    
    // パネル表示
    detailPanel.classList.add('active');
    detailPanel.scrollIntoView({ behavior: 'smooth' });
}

/**
 * 仮実装関数を削除（不要になったため）
 */
// isVenueActive関数は削除
// getVenueRaceInfo関数は削除

/**
 * 定期更新機能を追加
 */
function startVenueStatusAutoUpdate() {
    // 5分ごとに開催状況を更新
    setInterval(async () => {
        try {
            const response = await fetch(`${boatraceAPI.baseUrl}/venue-status`);
            const venueStatus = await response.json();
            
            // 既存のカードを更新
            for (const [venueCode, statusData] of Object.entries(venueStatus.venue_status)) {
                updateVenueCard(venueCode, statusData);
            }
            
            console.log('開催状況を更新しました');
        } catch (error) {
            console.error('開催状況更新エラー:', error);
        }
    }, 5 * 60 * 1000); // 5分間隔
}

/**
 * 会場カードの情報を更新
 */
function updateVenueCard(venueCode, statusData) {
    const venueCard = document.querySelector(`[data-venue="${venueCode}"]`);
    if (!venueCard) return;
    
    const isActive = statusData.is_active;
    
    // アクティブ状態更新
    venueCard.className = `venue-card ${isActive ? 'active' : 'inactive'}`;
    
    // 内容更新
    const currentRace = venueCard.querySelector('.current-race');
    const raceTime = venueCard.querySelector('.race-time');
    const nextTime = venueCard.querySelector('.next-time');
    const remainingRaces = venueCard.querySelectorAll('.stat-number')[1];
    
    if (currentRace) currentRace.textContent = isActive ? `第${statusData.current_race}R` : '本日開催なし';
    if (raceTime) raceTime.textContent = statusData.current_time || '-';
    if (nextTime) nextTime.textContent = statusData.next_race || '調査中';
    if (remainingRaces) remainingRaces.textContent = statusData.remaining_races || '-';
}

// 初期化時に自動更新開始
document.addEventListener('DOMContentLoaded', function() {
    startVenueStatusAutoUpdate();
});
