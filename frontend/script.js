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
    await loadRealTimeData();  // ← 新しい関数
    await updatePerformanceStats();
    setInterval(async () => {
        await loadRealTimeData();
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

// レース情報を更新
function updateRaceInfo(prediction) {
    // モックデータを使用（APIの結果に合わせて調整）
    const raceInfo = {
        venue: '住之江',
        race_number: 12,
        race_date: '2025-05-17T15:30:00',
        weather: {
            wind: '3m/s (北東)',
            surface: '穏やか',
            temperature: 22,
            grade: 'SG'
        }
    };
    
    // レースヘッダーの更新
    const raceHeader = document.querySelector('.race-header h3');
    if (raceHeader) {
        raceHeader.textContent = `${raceInfo.venue}競艇 第${raceInfo.race_number}レース`;
    }
    
    // レース日時の更新
    const raceDate = document.querySelector('.race-header span');
    if (raceDate) {
        const date = new Date(raceInfo.race_date);
        const formattedDate = `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日 ${date.getHours()}:${date.getMinutes().toString().padStart(2, '0')}開始`;
        raceDate.textContent = formattedDate;
    }
    
    // 詳細情報の更新
    const detailBoxes = document.querySelectorAll('.race-details .detail-box');
    if (detailBoxes.length >= 4) {
        detailBoxes[0].innerHTML = `<i class="fas fa-wind"></i> 風速: ${raceInfo.weather.wind}`;
        detailBoxes[1].innerHTML = `<i class="fas fa-water"></i> 水面: ${raceInfo.weather.surface}`;
        detailBoxes[2].innerHTML = `<i class="fas fa-temperature-high"></i> 気温: ${raceInfo.weather.temperature}°C`;
        detailBoxes[3].innerHTML = `<i class="fas fa-medal"></i> グレード: ${raceInfo.weather.grade}`;
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

    const venueSelect = document.getElementById('venueSelect');
    const refreshBtn = document.getElementById('refreshBtn');
    
    venueSelect.addEventListener('change', function() {
        if (this.value) {
            loadVenueData(this.value);
        }
    });
    
    refreshBtn.addEventListener('click', function() {
        const selectedVenue = venueSelect.value;
        if (selectedVenue) {
            loadVenueData(selectedVenue);
        }
    });
    
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
}

// 会場一覧を読み込む
async function loadVenues() {
    try {
        const venues = await boatraceAPI.getVenues();
        const venueSelect = document.getElementById('venueSelect');
        
        for (const [code, venueData] of Object.entries(venues)) {
            const option = document.createElement('option');
            option.value = code;
            option.textContent = `${venueData.name}（${venueData.location}）`;
            venueSelect.appendChild(option);
        }
    } catch (error) {
        console.error('会場一覧取得エラー:', error);
    }
}

// 選択した会場のデータを取得
async function loadVenueData(venueCode) {
    try {
        const response = await fetch(`${boatraceAPI.baseUrl}/kyotei/${venueCode}`);
        const data = await response.json();
        
        if (data.racer_extraction && data.racer_extraction.racers) {
            updateRaceDataTable(data);
        }
    } catch (error) {
        console.error('会場データ取得エラー:', error);
    }
}

// 実際のレースデータでテーブルを更新
function updateRaceDataTable(data) {
    const tbody = document.querySelector('.prediction-table tbody');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    data.racer_extraction.racers.forEach(racer => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td><span class="player-number">${racer.boat_number}</span></td>
            <td class="player-name">${racer.name}</td>
            <td>${racer.class}</td>
            <td>${racer.age}歳</td>
            <td class="prediction-score">-</td>
            <td>${racer.weight}</td>
            <td>${racer.region}/${racer.branch}</td>
        `;
        tbody.appendChild(row);
    });
    
    // 会場名を更新
    const raceHeader = document.querySelector('.race-header h3');
    if (raceHeader) {
        raceHeader.textContent = `${data.venue_name}競艇 第1レース`;
    }
}
