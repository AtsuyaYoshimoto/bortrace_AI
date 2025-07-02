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
    console.log('アプリケーション初期化開始');
    
    try {
        await loadVenues(); 
        await loadRealTimeData();
        await loadAIPrediction();
        await updatePerformanceStats();
        
        console.log('初期化完了');
        
        // 定期更新
        setInterval(async () => {
            console.log('定期更新実行');
            await loadVenues(); // 会場状況も定期更新
            await loadRealTimeData();
            await loadAIPrediction();
        }, 5 * 60 * 1000);
        
    } catch (error) {
        console.error('初期化エラー:', error);
    }
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

// APIベースの正確な実装
async function loadAccurateVenueData() {
    try {
        console.log('=== 正確な競艇データ取得 ===');
        
        const [venuesResponse, statusResponse] = await Promise.all([
            fetch(`${boatraceAPI.baseUrl}/venues`),
            fetch(`${boatraceAPI.baseUrl}/venue-status`)
        ]);
        
        const venues = await venuesResponse.json();
        const venueStatusData = await statusResponse.json();
        
        const venueGrid = document.getElementById('venue-grid');
        venueGrid.innerHTML = '';
        
        Object.entries(venues).forEach(([code, venueData]) => {
            const status = venueStatusData.venue_status?.[code];
            
            const venueCard = document.createElement('div');
            venueCard.className = 'venue-card';
            
            if (status?.is_active) {
                venueCard.classList.add('active');
                
                // 現在の状況を判定
                let currentStatus = 'レース中';
                let raceInfo = '';
                
                if (status.status === 'live') {
                    currentStatus = 'LIVE';
                    raceInfo = `${status.current_race || ''}R進行中 (残り${status.remaining_races || 0}R)`;
                } else if (status.remaining_races === 0) {
                    currentStatus = '終了';
                    raceInfo = '本日終了';
                } else {
                    raceInfo = `残り${status.remaining_races}R`;
                }
                
                venueCard.innerHTML = `
                    <div class="venue-status-indicator live">${currentStatus}</div>
                    <div class="venue-name">${venueData.name}</div>
                    <div class="venue-location">${venueData.location}</div>
                    <div class="venue-race-status">${raceInfo}</div>
                `;
                
                venueCard.onclick = () => selectVenue(code, venueData.name);
            } else {
                venueCard.classList.add('inactive');
                venueCard.innerHTML = `
                    <div class="venue-status-indicator closed">休場</div>
                    <div class="venue-name">${venueData.name}</div>
                    <div class="venue-location">${venueData.location}</div>
                    <div class="venue-race-status">本日開催なし</div>
                `;
            }
            
            venueGrid.appendChild(venueCard);
        });
        
    } catch (error) {
        console.error('データ取得エラー:', error);
    }
}

// レース選択も正確なAPIを使用
async function showAccurateRaceSelector() {
    const raceSelector = document.getElementById('race-selector');
    const raceButtons = document.getElementById('race-buttons');
    
    raceSelector.style.display = 'block';
    raceButtons.innerHTML = '';
    
    try {
        const response = await fetch(`${boatraceAPI.baseUrl}/venue-schedule/${selectedVenue}`);
        const scheduleData = await response.json();
        
        if (scheduleData?.schedule) {
            scheduleData.schedule.forEach((race) => {
                const raceBtn = document.createElement('button');
                raceBtn.className = 'race-btn';
                raceBtn.classList.add(race.status); // completed, live, upcoming
                
                let statusText = '';
                if (race.status === 'live') statusText = '<div class="race-status">LIVE</div>';
                if (race.status === 'completed') statusText = '<div class="race-status">終了</div>';
                
                raceBtn.innerHTML = `
                    <div>${race.race_number}R</div>
                    <div class="race-time">${race.scheduled_time}</div>
                    ${statusText}
                `;
                
                raceBtn.onclick = () => selectRace(race.race_number);
                raceButtons.appendChild(raceBtn);
            });
        }
    } catch (error) {
        console.error('スケジュール取得エラー:', error);
    }
}

async function loadVenues() {
    try {
        console.log('=== 競艇会場データ取得開始 ===');
        
        const venueGrid = document.getElementById('venue-grid');
        if (!venueGrid) {
            console.error('venue-grid要素が見つかりません');
            return;
        }
        
        // ローディング表示
        venueGrid.innerHTML = `
            <div style="grid-column: 1 / -1; text-align:center; padding:40px;">
                <i class="fas fa-spinner fa-spin" style="font-size:2rem; color:var(--primary); margin-bottom:1rem;"></i>
                <div style="color:var(--primary); font-weight:600;">競艇場状況取得中...</div>
            </div>
        `;
        
        // APIから会場データ取得
        const [venues, statusResponse] = await Promise.all([
            boatraceAPI.getVenues(),
            fetch(`${boatraceAPI.baseUrl}/venue-status`)
        ]);
        
        const venueStatusData = await statusResponse.json();
        console.log('取得した会場状況:', venueStatusData);
        
        venueGrid.innerHTML = '';
        
        // 開催中の会場を優先表示
        const sortedVenues = Object.entries(venues).sort(([codeA], [codeB]) => {
            const statusA = venueStatusData.venue_status?.[codeA];
            const statusB = venueStatusData.venue_status?.[codeB];
            const priorityA = statusA?.is_active ? 3 : 1;
            const priorityB = statusB?.is_active ? 3 : 1;
            return priorityB - priorityA;
        });
        
        // 各会場カードを生成
        sortedVenues.forEach(([code, venueData]) => {
            const status = venueStatusData.venue_status?.[code];
            const venueCard = createVenueCard(code, venueData, status);
            venueGrid.appendChild(venueCard);
        });
        
        // 状況サマリーを更新
        updateVenueSummary(venueStatusData);
        
        console.log('=== 競艇会場データ表示完了 ===');
        
    } catch (error) {
        console.error('会場データ取得エラー:', error);
        showVenueError();
    }
}

function createVenueCard(code, venueData, status) {
    const venueCard = document.createElement('div');
    venueCard.className = 'venue-card';
    
    if (status?.is_active) {
        // 開催中の会場
        venueCard.classList.add('active');
        
        const statusText = status.status === 'live' ? 'LIVE' : 'レース中';
        const raceInfo = `${status.current_time || ''} (残り${status.remaining_races}R)`;
        
        venueCard.innerHTML = `
            <div class="venue-status-indicator live">${statusText}</div>
            <div class="venue-name">${venueData.name}</div>
            <div class="venue-location">${venueData.location}</div>
            <div class="venue-race-status active-status">${raceInfo}</div>
        `;
        
        venueCard.onclick = () => selectVenue(code, venueData.name);
        
    } else {
        // 非開催の会場
        venueCard.classList.add('inactive');
        
        let statusText = '休場';
        let reason = '本日開催なし';
        
        if (status?.status === 'error') {
            statusText = 'エラー';
            reason = 'データ取得不能';
        } else if (status?.status === 'not_checked') {
            statusText = '未確認';
            reason = '確認対象外';
        }
        
        venueCard.innerHTML = `
            <div class="venue-status-indicator closed">${statusText}</div>
            <div class="venue-name">${venueData.name}</div>
            <div class="venue-location">${venueData.location}</div>
            <div class="venue-race-status inactive-status">${reason}</div>
        `;
    }
    
    return venueCard;
}

function updateVenueSummary(venueStatusData) {
    const statusIndicator = document.getElementById('status-indicator');
    if (!statusIndicator) return;
    
    const activeCount = venueStatusData.active_venues || 0;
    const checkedCount = venueStatusData.checked_venues || 0;
    const currentHour = venueStatusData.current_hour || new Date().getHours();
    
    if (activeCount > 0) {
        statusIndicator.className = 'status-indicator status-success';
        statusIndicator.innerHTML = `
            <i class="fas fa-check-circle"></i> 
            開催中: ${activeCount}会場 (${currentHour}時台・${checkedCount}会場確認済み)
        `;
    } else {
        statusIndicator.className = 'status-indicator status-success';
        statusIndicator.innerHTML = `
            <i class="fas fa-info-circle"></i> 
            開催なし (${currentHour}時台・${checkedCount}会場確認済み)
        `;
    }
}

function showVenueError() {
    const venueGrid = document.getElementById('venue-grid');
    if (venueGrid) {
        venueGrid.innerHTML = `
            <div style="grid-column: 1 / -1; text-align:center; padding:40px; color:var(--danger);">
                <i class="fas fa-exclamation-triangle" style="font-size:2rem; margin-bottom:1rem;"></i>
                <div style="font-weight:600; margin-bottom:1rem;">データ取得エラー</div>
                <button class="btn btn-primary" onclick="loadVenues()">
                    <i class="fas fa-sync-alt"></i> 再試行
                </button>
            </div>
        `;
    }
}

async function showRaceSelector() {
    await showAccurateRaceSelector();
}

async function getFallbackVenueStatus() {
    console.log('フォールバック: ローカル判定を使用');
    
    const venueStatus = {};
    const venues = {
        '01': '桐生', '12': '住之江', '20': '若松', '22': '福岡'
    };
    
    // 最小限のフォールバック
    Object.keys(venues).forEach(code => {
        venueStatus[code] = {
            is_active: false,
            venue_name: venues[code],
            status: "api_error",
            remaining_races: 0,
            message: "データ取得中..."
        };
    });
    
    return venueStatus;
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

async function showRaceSelector() {
    const raceSelector = document.getElementById('race-selector');
    const raceButtons = document.getElementById('race-buttons');
    
    raceSelector.style.display = 'block';
    raceButtons.innerHTML = '<div style="text-align:center;">レース時間取得中...</div>';
    
    try {
        console.log(`会場${selectedVenue}のリアルタイムスケジュール取得中...`);
        
        const response = await fetch(`${boatraceAPI.baseUrl}/venue-schedule/${selectedVenue}`);
        const scheduleData = await response.json();
        
        console.log('取得したスケジュール:', scheduleData);
        
        raceButtons.innerHTML = '';
        
        if (scheduleData?.schedule && scheduleData.schedule.length > 0) {
            scheduleData.schedule.forEach((race) => {
                const raceBtn = document.createElement('button');
                raceBtn.className = 'race-btn';
                raceBtn.classList.add(race.status);
                
                let statusText = '';
                if (race.status === 'live') statusText = '<div class="race-status">LIVE</div>';
                if (race.status === 'completed') statusText = '<div class="race-status">終了</div>';
                
                raceBtn.innerHTML = `
                    <div>${race.race_number}R</div>
                    <div class="race-time">${race.scheduled_time}</div>
                    ${statusText}
                `;
                
                raceBtn.onclick = () => selectRace(race.race_number);
                raceButtons.appendChild(raceBtn);
            });
        } else {
            raceButtons.innerHTML = '<div style="text-align:center;color:#6c757d;">スケジュールが見つかりません</div>';
        }
        
    } catch (error) {
        console.error('スケジュール取得エラー:', error);
        raceButtons.innerHTML = `
            <div style="text-align:center;color:#dc3545;">
                スケジュール取得エラー<br>
                <button class="btn btn-sm" onclick="showRaceSelector()">再試行</button>
            </div>
        `;
    }
}

// 実際のレーススケジュール取得関数
async function getVenueSchedule(venueCode) {
    try {
        const response = await fetch(`${boatraceAPI.baseUrl}/venue-schedule/${venueCode}`);
        if (!response.ok) throw new Error('スケジュール取得失敗');
        return await response.json();
    } catch (error) {
        console.error('スケジュール取得エラー:', error);
        return null;
    }
}

// フォールバック用レースボタン作成を修正
function createFallbackRaceButtons() {
    const raceButtons = document.getElementById('race-buttons');
    
    // 現在時刻を取得
    const now = new Date();
    const currentHour = now.getHours();
    const currentMinute = now.getMinutes();
    const currentTime = currentHour * 60 + currentMinute;
    
    // 実際の競艇時間（10:30から30分間隔で12レース）
    const raceSchedule = [
        { race: 1, time: '10:30' }, { race: 2, time: '11:00' }, { race: 3, time: '11:30' },
        { race: 4, time: '12:00' }, { race: 5, time: '12:30' }, { race: 6, time: '13:00' },
        { race: 7, time: '13:30' }, { race: 8, time: '14:00' }, { race: 9, time: '14:30' },
        { race: 10, time: '15:00' }, { race: 11, time: '15:30' }, { race: 12, time: '16:00' }
    ];
    
    raceSchedule.forEach(({ race, time }) => {
        const raceBtn = document.createElement('button');
        raceBtn.className = 'race-btn';
        
        // 時刻から状況判定
        const [hour, minute] = time.split(':').map(Number);
        const raceStartMinutes = hour * 60 + minute;
        const raceEndMinutes = raceStartMinutes + 25; // レース時間約25分
        
        let status = 'upcoming';
        let statusText = '';
        
        if (currentTime > raceEndMinutes) {
            status = 'completed';
            statusText = '終了';
        } else if (currentTime >= raceStartMinutes && currentTime <= raceEndMinutes) {
            status = 'live';
            statusText = 'LIVE';
        } else if (currentTime >= raceStartMinutes - 10) { // 10分前から
            status = 'upcoming';
            statusText = '準備中';
        } else {
            status = 'upcoming';
            statusText = '';
        }
        
        raceBtn.classList.add(status);
        raceBtn.innerHTML = `
            <div>${race}R</div>
            <div class="race-time">${time}</div>
            ${statusText ? `<div class="race-status">${statusText}</div>` : ''}
        `;
        
        raceBtn.onclick = () => selectRace(race);
        raceButtons.appendChild(raceBtn);
    });
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

// 既存のdisplayRealRacers関数を以下に置き換え
function displayRealRacers(racers) {
    const tbody = document.getElementById('racers-tbody-new');
    if (!tbody) {
        console.error('racers-tbody-new要素が見つかりません');
        return;
    }
    
    tbody.innerHTML = '';

    racers.forEach((racer, index) => {
        const row = document.createElement('div');
        row.className = 'racer-row fade-in';
        row.style.animationDelay = `${index * 0.1}s`;
        
        // モック成績データ（実際のAPIデータに置き換え可能）
        const mockStats = {
            win_rate: (Math.random() * 8 + 2).toFixed(2),
            place_rate: (Math.random() * 30 + 40).toFixed(1),
            trio_rate: (Math.random() * 20 + 60).toFixed(1)
        };
        
        row.innerHTML = `
            <div class="boat-number-cell">
                <div class="boat-number-badge boat-${racer.boat_number}">
                    ${racer.boat_number}
                </div>
            </div>
            <div class="racer-info-cell">
                <div class="racer-name">${racer.name}</div>
                <div class="racer-details">
                    <span class="grade-badge ${racer.class?.toLowerCase()}">${racer.class}</span>
                    <span>${racer.age}歳</span>
                    <span>${racer.weight}</span>
                    <span>${racer.region}/${racer.branch}</span>
                </div>
            </div>
            <div class="stats-cell">
                <div class="stat-row">
                    <span class="stat-label">勝率</span>
                    <span class="stat-value">${mockStats.win_rate}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">2連率</span>
                    <span class="stat-value">${mockStats.place_rate}%</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">3連率</span>
                    <span class="stat-value">${mockStats.trio_rate}%</span>
                </div>
            </div>
            <div class="motor-info-cell">
                <div class="motor-number">#${Math.floor(Math.random() * 100) + 1}</div>
                <div class="motor-rate">${(Math.random() * 20 + 30).toFixed(1)}%</div>
            </div>
            <div class="conditions-cell">
                <i class="fas fa-arrow-up trend-up"></i>
            </div>
        `;
        
        tbody.appendChild(row);
    });
}

// 展示タイム表示関数
function displayExhibitionTimes(racers) {
    const exhibitionGrid = document.getElementById('exhibition-grid');
    if (!exhibitionGrid) return;
    
    exhibitionGrid.innerHTML = '';
    
    // モック展示タイムデータ
    const exhibitionData = racers.map((racer, index) => ({
        boat_number: racer.boat_number,
        time: (6.8 + Math.random() * 0.4).toFixed(2),
        rank: index + 1
    }));
    
    // タイム順にソート
    exhibitionData.sort((a, b) => parseFloat(a.time) - parseFloat(b.time));
    exhibitionData.forEach((item, index) => item.rank = index + 1);
    
    // 元の艇番順に戻して表示
    exhibitionData.sort((a, b) => a.boat_number - b.boat_number);
    
    exhibitionData.forEach(item => {
        const exhibitionItem = document.createElement('div');
        exhibitionItem.className = `exhibition-item boat-${item.boat_number}`;
        
        exhibitionItem.innerHTML = `
            <div class="exhibition-boat">${item.boat_number}号艇</div>
            <div class="exhibition-time">${item.time}</div>
            <div class="exhibition-rank">${item.rank}位</div>
        `;
        
        exhibitionGrid.appendChild(exhibitionItem);
    });
}

// displayRealRacers関数の最後に以下を追加
function displayRealRacers(racers) {
    // 既存のコード...
    
    // 最後に展示タイム表示を追加
    displayExhibitionTimes(racers);
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

function selectVenue(venueCode, venueName) {
    selectedVenue = venueCode;
    
    // 選択状態の更新
    document.querySelectorAll('.venue-card').forEach(card => {
        card.classList.remove('selected');
    });
    event.target.closest('.venue-card').classList.add('selected');
    
    // 選択情報を更新
    document.getElementById('selected-venue-name').textContent = venueName;
    
    // レース選択UIを表示
    showRaceSelector(venueCode, venueName);
}

async function showRaceSelector(venueCode, venueName) {
    const raceSelector = document.getElementById('race-selector');
    const raceButtons = document.getElementById('race-buttons');
    
    if (!raceSelector || !raceButtons) {
        console.error('レース選択UI要素が見つかりません');
        return;
    }
    
    raceSelector.style.display = 'block';
    raceButtons.innerHTML = '<div style="text-align:center; padding:20px;">レース情報取得中...</div>';
    
    try {
        // 現在時刻から推定レース生成（23:35なら残り3レース程度）
        const currentHour = new Date().getHours();
        const currentMinute = new Date().getMinutes();
        
        // ナイター会場の場合（15:00-21:00が一般的だが延長あり）
        const raceSchedule = generateRaceSchedule(currentHour, currentMinute);
        
        raceButtons.innerHTML = '';
        
        raceSchedule.forEach((race) => {
            const raceBtn = document.createElement('button');
            raceBtn.className = 'race-btn';
            raceBtn.classList.add(race.status);
            
            let statusText = '';
            if (race.status === 'live') statusText = '<div class="race-status">LIVE</div>';
            if (race.status === 'completed') statusText = '<div class="race-status">終了</div>';
            
            raceBtn.innerHTML = `
                <div>${race.race_number}R</div>
                <div class="race-time">${race.scheduled_time}</div>
                ${statusText}
            `;
            
            raceBtn.onclick = () => selectRace(race.race_number, venueCode, venueName);
            raceButtons.appendChild(raceBtn);
        });
        
    } catch (error) {
        console.error('レース情報取得エラー:', error);
        raceButtons.innerHTML = `
            <div style="text-align:center; color:var(--danger); padding:20px;">
                レース情報取得エラー<br>
                <button class="btn btn-sm" onclick="showRaceSelector('${venueCode}', '${venueName}')">
                    再試行
                </button>
            </div>
        `;
    }
}

function generateRaceSchedule(currentHour, currentMinute) {
    const races = [];
    const baseHour = 15; // ナイター開始時刻
    const currentTimeMinutes = currentHour * 60 + currentMinute;
    
    for (let i = 1; i <= 12; i++) {
        const raceStartMinutes = baseHour * 60 + (i - 1) * 30;
        const raceEndMinutes = raceStartMinutes + 25;
        
        const hour = Math.floor(raceStartMinutes / 60);
        const minute = raceStartMinutes % 60;
        
        let status = 'upcoming';
        if (currentTimeMinutes > raceEndMinutes) {
            status = 'completed';
        } else if (currentTimeMinutes >= raceStartMinutes && currentTimeMinutes <= raceEndMinutes) {
            status = 'live';
        }
        
        races.push({
            race_number: i,
            scheduled_time: `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`,
            status: status
        });
    }
    
    return races;
}

function selectRace(raceNumber, venueCode, venueName) {
    selectedRace = raceNumber;
    
    // 選択状態の更新
    document.querySelectorAll('.race-btn').forEach(btn => {
        btn.classList.remove('selected');
    });
    event.target.classList.add('selected');
    
    // 選択情報を更新
    document.getElementById('selected-race-info').textContent = ` - 第${raceNumber}レース`;
    
    // 出走表データを取得
    loadSelectedRaceData(venueCode, raceNumber, venueName);
}

async function loadSelectedRaceData(venueCode, raceNumber, venueName) {
    try {
        const response = await fetch(`${boatraceAPI.baseUrl}/race-data?venue=${venueCode}&race=${raceNumber}`);
        const data = await response.json();
        
        if (data.racer_extraction && data.racer_extraction.racers) {
            displayRealRacers(data.racer_extraction.racers);
            
            // レース情報を更新
            document.querySelector('.race-header h3').textContent = `${venueName} 第${raceNumber}レース`;
            document.getElementById('venue-name').textContent = venueName;
            document.getElementById('race-number').textContent = `${raceNumber}R`;
            
            // 表示切り替え
            document.getElementById('race-info').style.display = 'block';
            document.getElementById('prediction-container').style.display = 'block';
        }
        
    } catch (error) {
        console.error('レースデータ取得エラー:', error);
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
