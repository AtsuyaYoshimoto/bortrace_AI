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

// 既存のloadVenues関数を置き換え
async function loadVenues() {
    try {
        const venues = await boatraceAPI.getVenues();
        const venueGrid = document.getElementById('venue-grid');
        
        venueGrid.innerHTML = '';
        
        for (const [code, venueData] of Object.entries(venues)) {
            const venueCard = document.createElement('div');
            venueCard.className = 'venue-card';
            venueCard.textContent = venueData.name;
            venueCard.onclick = () => selectVenue(code, venueData.name);
            venueGrid.appendChild(venueCard);
        }
    } catch (error) {
        console.error('会場一覧取得エラー:', error);
    }
}

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
    
    // 要素の存在チェックを追加
    const lastUpdatedElement = document.getElementById('last-updated');
    if (lastUpdatedElement) {
        lastUpdatedElement.textContent = formatted;
    } else {
        console.warn('last-updated要素が見つかりません');
        // 代替として、他の場所に時刻を表示
        const raceDate = document.querySelector('.race-header span');
        if (raceDate) {
            raceDate.textContent = `最終更新: ${formatted}`;
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
        if (prediction.predictions && prediction.predictions.length > 0) {
            const topPrediction = prediction.predictions[0];
            
            document.getElementById('predicted-winner').textContent = topPrediction.boat_number;
            document.getElementById('predicted-winner-name').textContent = `選手${topPrediction.boat_number}`;
            document.getElementById('win-probability').textContent = `${Math.round(topPrediction.rank_probabilities[0] * 100)}%`;
            document.getElementById('win-confidence').textContent = '85';
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

 * AI予想を更新する関数
 */
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
        
        alert('🤖 AI予想が更新されました！');
        
    } catch (error) {
        console.error('AI予想エラー:', error);
        alert(`AI予想の更新に失敗しました: ${error.message}`);
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
        
        // 予想順位でソート
        predictions.sort((a, b) => a.predicted_rank - b.predicted_rank);
        
        // トップ3を取得
        const top3 = predictions.slice(0, 3);
        
        // 画面に表示（要素が存在する場合）
        if (document.getElementById('predicted-winner')) {
            document.getElementById('predicted-winner').textContent = top3[0].boat_number;
        }
        
        if (document.getElementById('win-probability')) {
            const winProb = Math.round(top3[0].normalized_probability * 100);
            document.getElementById('win-probability').textContent = `${winProb}%`;
        }
        
        // 推奨舟券表示
        if (aiResult.ai_predictions.recommendations) {
            const recs = aiResult.ai_predictions.recommendations;
            console.log('推奨舟券:', recs);
            
            // 単勝、2連単、3連複の推奨を表示
            alert(`🎯 AI推奨舟券\n単勝: ${recs.win.boat_number}番\n2連単: ${recs.exacta.combination.join('-')}\n3連複: ${recs.trio.combination.join('-')}`);
        }
        
        // 信頼度表示
        const confidenceLevel = aiResult.ai_predictions.analysis_summary.confidence_level;
        console.log(`AI信頼度: ${confidenceLevel}`);
    }
}
