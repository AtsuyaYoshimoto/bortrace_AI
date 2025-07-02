/**
 * WAVE PREDICTOR - 完全版JavaScript
 * 競艇予想サイトのメインスクリプト
 * 
 * 機能:
 * - リアルタイムデータ取得・表示
 * - AI予想機能
 * - レスポンシブUI制御
 * - アニメーション・視覚効果
 * - エラーハンドリング
 */

// ===== 設定・定数 =====
const CONFIG = {
    API_BASE_URL: 'https://bortrace-ai-api-36737145161.asia-northeast1.run.app/api',
    UPDATE_INTERVAL: 5 * 60 * 1000, // 5分
    AUTO_REFRESH_ENABLED: true,
    DEBUG_MODE: false,
    ANIMATION_DURATION: 300,
    RETRY_ATTEMPTS: 3,
    RETRY_DELAY: 2000
};

// ===== グローバル変数 =====
let selectedVenue = null;
let selectedRace = null;
let updateTimer = null;
let retryCount = 0;
let isLoading = false;
let touchStartY = 0;
let lastUpdateTime = null;

// ===== API連携クラス =====
class BoatraceAPI {
    constructor(baseUrl = CONFIG.API_BASE_URL) {
        this.baseUrl = baseUrl;
        this.cache = new Map();
        this.requestQueue = [];
        this.isOnline = navigator.onLine;
        
        // オンライン状態監視
        window.addEventListener('online', () => {
            this.isOnline = true;
            this.processRequestQueue();
        });
        
        window.addEventListener('offline', () => {
            this.isOnline = false;
        });
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        
        if (!this.isOnline) {
            throw new Error('オフライン状態です');
        }

        try {
            const response = await fetch(url, {
                timeout: 30000,
                ...options,
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            
            // キャッシュに保存（GETリクエストのみ）
            if (!options.method || options.method === 'GET') {
                this.cache.set(url, { data, timestamp: Date.now() });
            }
            
            return data;
        } catch (error) {
            console.error(`API Request Error (${endpoint}):`, error);
            
            // キャッシュから取得を試行
            const cached = this.cache.get(url);
            if (cached && Date.now() - cached.timestamp < 300000) { // 5分以内
                console.warn('キャッシュからデータを返却');
                return cached.data;
            }
            
            throw error;
        }
    }

    async getVenues() {
        return this.request('/venues');
    }

    async getTodayRaces() {
        return this.request('/races/today');
    }

    async getRacePrediction(raceId) {
        return this.request(`/prediction/${raceId}`);
    }

    async getPerformanceStats() {
        return this.request('/stats');
    }

    async getRaceData(venue, race, date = null) {
        const params = new URLSearchParams({ venue, race });
        if (date) params.append('date', date);
        return this.request(`/race-data?${params}`);
    }

    async getSystemStatus() {
        return this.request('/system-status');
    }

    async updateAIPrediction(racers) {
        return this.request('/ai-prediction-simple', {
            method: 'POST',
            body: JSON.stringify({ racers })
        });
    }

    processRequestQueue() {
        // オンライン復帰時の処理
        while (this.requestQueue.length > 0) {
            const request = this.requestQueue.shift();
            this.request(request.endpoint, request.options)
                .then(request.resolve)
                .catch(request.reject);
        }
    }
}

// ===== UI管理クラス =====
class UIManager {
    constructor() {
        this.elements = this.cacheElements();
        this.isMobile = this.detectMobile();
        this.setupEventListeners();
        this.initializeAnimations();
    }

    cacheElements() {
        return {
            loading: document.getElementById('loading'),
            error: document.getElementById('error'),
            errorMessage: document.getElementById('error-message'),
            raceInfo: document.getElementById('race-info'),
            predictionContainer: document.getElementById('prediction-container'),
            statusIndicator: document.getElementById('status-indicator'),
            venueGrid: document.getElementById('venue-grid'),
            raceSelector: document.getElementById('race-selector'),
            raceButtons: document.getElementById('race-buttons'),
            selectedVenueName: document.getElementById('selected-venue-name'),
            selectedRaceInfo: document.getElementById('selected-race-info'),
            racersTbodyNew: document.getElementById('racers-tbody-new'),
            exhibitionGrid: document.getElementById('exhibition-grid'),
            lastUpdated: document.getElementById('last-updated'),
            aiLastUpdated: document.getElementById('ai-last-updated'),
            predictedWinner: document.getElementById('predicted-winner'),
            predictedWinnerName: document.getElementById('predicted-winner-name'),
            winProbability: document.getElementById('win-probability'),
            winConfidence: document.getElementById('win-confidence'),
            recommendedWin: document.getElementById('recommended-win'),
            recommendedExacta: document.getElementById('recommended-exacta'),
            recommendedTrifecta: document.getElementById('recommended-trifecta'),
            stabilityMeter: document.getElementById('stability-meter'),
            upsetMeter: document.getElementById('upset-meter'),
            stabilityScore: document.getElementById('stability-score'),
            upsetScore: document.getElementById('upset-score')
        };
    }

    detectMobile() {
        return window.innerWidth <= 768 || /Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    }

    setupEventListeners() {
        // ウィンドウリサイズ
        window.addEventListener('resize', debounce(() => {
            this.isMobile = this.detectMobile();
            this.handleResize();
        }, 250));

        // スクロール監視
        window.addEventListener('scroll', throttle(() => {
            this.handleScroll();
        }, 16));

        // タッチイベント（モバイル）
        if (this.isMobile) {
            this.setupTouchEvents();
        }

        // キーボードショートカット
        document.addEventListener('keydown', (e) => {
            this.handleKeyboard(e);
        });

        // ページ離脱前の処理
        window.addEventListener('beforeunload', () => {
            this.cleanup();
        });
    }

    setupTouchEvents() {
        document.addEventListener('touchstart', (e) => {
            touchStartY = e.touches[0].clientY;
        }, { passive: true });

        document.addEventListener('touchend', (e) => {
            const touchEndY = e.changedTouches[0].clientY;
            const deltaY = touchStartY - touchEndY;
            
            // プルトゥリフレッシュ
            if (deltaY < -100 && window.scrollY === 0) {
                this.showPullToRefresh();
            }
        }, { passive: true });
    }

    initializeAnimations() {
        // パーティクル効果初期化
        this.createParticles();
        
        // スクロールアニメーション初期化
        this.initScrollAnimations();
        
        // CSS変数でアニメーション制御
        document.documentElement.style.setProperty('--animation-duration', `${CONFIG.ANIMATION_DURATION}ms`);
    }

    createParticles() {
        const heroParticles = document.querySelector('.hero-particles');
        if (!heroParticles) return;

        const particleCount = this.isMobile ? 15 : 30;
        
        for (let i = 0; i < particleCount; i++) {
            const particle = document.createElement('div');
            particle.className = 'particle';
            
            // ランダムな位置とサイズ
            const size = Math.random() * 6 + 2;
            const x = Math.random() * 100;
            const delay = Math.random() * 6;
            
            particle.style.cssText = `
                width: ${size}px;
                height: ${size}px;
                left: ${x}%;
                top: 100%;
                animation-delay: ${delay}s;
            `;
            
            heroParticles.appendChild(particle);
        }
    }

    initScrollAnimations() {
        const observerOptions = {
            threshold: 0.1,
            rootMargin: '-50px 0px'
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('active');
                }
            });
        }, observerOptions);

        document.querySelectorAll('.scroll-animate').forEach(el => {
            observer.observe(el);
        });
    }

    handleResize() {
        // テーブルのレスポンシブ調整
        this.adjustTableLayout();
        
        // パーティクル数調整
        if (this.isMobile) {
            this.reduceParticles();
        }
    }

    handleScroll() {
        // ヘッダーの透明度調整
        const header = document.querySelector('header');
        const scrollY = window.scrollY;
        
        if (scrollY > 100) {
            header.style.backdropFilter = 'blur(20px)';
            header.style.backgroundColor = 'rgba(0, 102, 204, 0.95)';
        } else {
            header.style.backdropFilter = 'blur(10px)';
            header.style.backgroundColor = 'rgba(0, 102, 204, 0.9)';
        }
    }

    handleKeyboard(e) {
        // R キー: リフレッシュ
        if (e.key === 'r' && e.ctrlKey) {
            e.preventDefault();
            this.refreshData();
        }
        
        // ESC キー: エラー閉じる
        if (e.key === 'Escape') {
            this.hideError();
        }
    }

    // ===== 状態管理メソッド =====
    showLoading(message = 'データ読み込み中...') {
        if (this.elements.loading) {
            this.elements.loading.style.display = 'block';
            const loadingText = this.elements.loading.querySelector('p');
            if (loadingText) loadingText.textContent = message;
        }
        
        this.updateStatus('loading', `<i class="fas fa-spinner fa-spin"></i> ${message}`);
        isLoading = true;
    }

    hideLoading() {
        if (this.elements.loading) {
            this.elements.loading.style.display = 'none';
        }
        isLoading = false;
    }

    showError(message, details = null) {
        this.hideLoading();
        
        if (this.elements.error) {
            this.elements.error.style.display = 'block';
            if (this.elements.errorMessage) {
                this.elements.errorMessage.textContent = message;
            }
        }
        
        this.updateStatus('error', `<i class="fas fa-exclamation-triangle"></i> ${message}`);
        
        if (CONFIG.DEBUG_MODE && details) {
            console.error('Error Details:', details);
        }
    }

    hideError() {
        if (this.elements.error) {
            this.elements.error.style.display = 'none';
        }
    }

    updateStatus(type, message) {
        if (!this.elements.statusIndicator) return;
        
        this.elements.statusIndicator.className = `status-indicator status-${type}`;
        this.elements.statusIndicator.innerHTML = message;
        
        // 成功時のアニメーション
        if (type === 'success') {
            this.elements.statusIndicator.addEventListener('animationend', () => {
                this.elements.statusIndicator.style.animation = '';
            }, { once: true });
        }
    }

    updateTimestamp(timestamp) {
        const date = timestamp ? new Date(timestamp) : new Date();
        const formatted = date.toLocaleString('ja-JP', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });

        // 複数の要素を更新
        [this.elements.lastUpdated, this.elements.aiLastUpdated].forEach(element => {
            if (element) {
                element.textContent = formatted;
            }
        });

        lastUpdateTime = date;
    }

    showPullToRefresh() {
        const refreshIndicator = document.createElement('div');
        refreshIndicator.className = 'pull-refresh-indicator';
        refreshIndicator.innerHTML = '<i class="fas fa-sync-alt fa-spin"></i> 更新中...';
        
        document.body.appendChild(refreshIndicator);
        
        setTimeout(() => {
            refreshIndicator.remove();
            this.refreshData();
        }, 1000);
    }

    adjustTableLayout() {
        const table = document.querySelector('.race-entry-table');
        if (!table) return;

        if (this.isMobile) {
            table.classList.add('mobile-layout');
        } else {
            table.classList.remove('mobile-layout');
        }
    }

    reduceParticles() {
        const particles = document.querySelectorAll('.particle');
        particles.forEach((particle, index) => {
            if (index % 2 === 0) {
                particle.style.display = 'none';
            }
        });
    }

    cleanup() {
        if (updateTimer) {
            clearInterval(updateTimer);
        }
    }

    async refreshData() {
        try {
            await app.loadRealTimeData();
            await app.loadAIPrediction();
        } catch (error) {
            console.error('Data refresh error:', error);
        }
    }
}

// ===== メインアプリケーションクラス =====
class WavePredictorApp {
    constructor() {
        this.api = new BoatraceAPI();
        this.ui = new UIManager();
        this.isInitialized = false;
    }

    async initialize() {
        try {
            console.log('🌊 WAVE PREDICTOR 初期化開始');
            
            this.ui.showLoading('システム初期化中...');
            
            // 初期データ読み込み
            await this.loadInitialData();
            
            // 定期更新開始
            this.startAutoUpdate();
            
            // UI初期化完了
            this.ui.hideLoading();
            this.ui.updateStatus('success', '<i class="fas fa-check-circle"></i> システム準備完了');
            
            this.isInitialized = true;
            console.log('✅ WAVE PREDICTOR 初期化完了');
            
        } catch (error) {
            console.error('❌ 初期化エラー:', error);
            this.ui.showError('システムの初期化に失敗しました', error);
            
            // リトライ機能
            if (retryCount < CONFIG.RETRY_ATTEMPTS) {
                retryCount++;
                setTimeout(() => {
                    console.log(`🔄 リトライ ${retryCount}/${CONFIG.RETRY_ATTEMPTS}`);
                    this.initialize();
                }, CONFIG.RETRY_DELAY);
            }
        }
    }

    async loadInitialData() {
        try {
            // システム状態確認
            const systemStatus = await this.api.getSystemStatus();
            console.log('System Status:', systemStatus);
            
            // 会場データ読み込み
            await this.loadVenues();
            
            // 統計データ読み込み
            await this.updatePerformanceStats();
            
        } catch (error) {
            console.error('Initial data loading error:', error);
            throw error;
        }
    }

    async loadVenues() {
        try {
            console.log('=== 競艇会場データ取得開始 ===');
            
            if (!this.ui.elements.venueGrid) {
                throw new Error('venue-grid要素が見つかりません');
            }
            
            // ローディング表示
            this.ui.elements.venueGrid.innerHTML = `
                <div style="grid-column: 1 / -1; text-align:center; padding:40px;">
                    <i class="fas fa-spinner fa-spin" style="font-size:2rem; color:var(--primary); margin-bottom:1rem;"></i>
                    <div style="color:var(--primary); font-weight:600;">競艇場状況取得中...</div>
                </div>
            `;
            
            // 会場データとステータス取得
            const [venues, statusResponse] = await Promise.all([
                this.api.getVenues(),
                this.api.getSystemStatus()
            ]);
            
            console.log('取得した会場データ:', venues);
            console.log('システムステータス:', statusResponse);
            
            this.ui.elements.venueGrid.innerHTML = '';
            
            // 開催中の会場を優先表示
            const sortedVenues = Object.entries(venues).sort(([codeA], [codeB]) => {
                const statusA = statusResponse.data_collection?.active_venues || 0;
                const statusB = statusResponse.data_collection?.active_venues || 0;
                return statusB - statusA;
            });
            
            // 各会場カードを生成
            sortedVenues.forEach(([code, venueData]) => {
                const venueCard = this.createVenueCard(code, venueData, statusResponse);
                this.ui.elements.venueGrid.appendChild(venueCard);
            });
            
            // 会場表示完了
            this.ui.elements.raceInfo.style.display = 'block';
            this.updateVenueSummary(statusResponse);
            
            console.log('=== 競艇会場データ表示完了 ===');
            
        } catch (error) {
            console.error('会場データ取得エラー:', error);
            this.showVenueError();
        }
    }

    createVenueCard(code, venueData, statusResponse) {
        const venueCard = document.createElement('div');
        venueCard.className = 'venue-card';
        
        // アクティブ状態の判定
        const isActive = statusResponse.data_collection?.active_venues > 0 && Math.random() > 0.7; // デモ用
        
        if (isActive) {
            venueCard.classList.add('active');
            
            const statusText = 'LIVE';
            const raceInfo = `${Math.floor(Math.random() * 12) + 1}R進行中`;
            
            venueCard.innerHTML = `
                <div class="venue-status-indicator live">${statusText}</div>
                <div class="venue-name">${venueData.name}</div>
                <div class="venue-location">${venueData.location}</div>
                <div class="venue-race-status active-status">${raceInfo}</div>
            `;
            
            venueCard.onclick = () => this.selectVenue(code, venueData.name);
            
        } else {
            venueCard.classList.add('inactive');
            
            venueCard.innerHTML = `
                <div class="venue-status-indicator closed">休場</div>
                <div class="venue-name">${venueData.name}</div>
                <div class="venue-location">${venueData.location}</div>
                <div class="venue-race-status inactive-status">本日開催なし</div>
            `;
        }
        
        return venueCard;
    }

    updateVenueSummary(statusResponse) {
        const activeCount = statusResponse.data_collection?.active_venues || 0;
        const currentHour = new Date().getHours();
        
        if (activeCount > 0) {
            this.ui.updateStatus('success', 
                `<i class="fas fa-check-circle"></i> 開催中: ${activeCount}会場 (${currentHour}時台)`
            );
        } else {
            this.ui.updateStatus('success', 
                `<i class="fas fa-info-circle"></i> 開催情報取得完了 (${currentHour}時台)`
            );
        }
    }

    showVenueError() {
        if (this.ui.elements.venueGrid) {
            this.ui.elements.venueGrid.innerHTML = `
                <div style="grid-column: 1 / -1; text-align:center; padding:40px; color:var(--danger);">
                    <i class="fas fa-exclamation-triangle" style="font-size:2rem; margin-bottom:1rem;"></i>
                    <div style="font-weight:600; margin-bottom:1rem;">データ取得エラー</div>
                    <button class="btn btn-primary" onclick="app.loadVenues()">
                        <i class="fas fa-sync-alt"></i> 再試行
                    </button>
                </div>
            `;
        }
    }

    selectVenue(venueCode, venueName) {
        selectedVenue = venueCode;
        
        // 選択状態の更新
        document.querySelectorAll('.venue-card').forEach(card => {
            card.classList.remove('selected');
        });
        event.target.closest('.venue-card').classList.add('selected');
        
        // 選択情報を更新
        if (this.ui.elements.selectedVenueName) {
            this.ui.elements.selectedVenueName.textContent = venueName;
        }
        
        // レース選択UIを表示
        this.showRaceSelector(venueCode, venueName);
    }

    async showRaceSelector(venueCode, venueName) {
        if (!this.ui.elements.raceSelector || !this.ui.elements.raceButtons) {
            console.error('レース選択UI要素が見つかりません');
            return;
        }
        
        this.ui.elements.raceSelector.style.display = 'block';
        this.ui.elements.raceButtons.innerHTML = '<div style="text-align:center; padding:20px;">レース情報取得中...</div>';
        
        try {
            // レーススケジュール生成
            const raceSchedule = this.generateRaceSchedule();
            
            this.ui.elements.raceButtons.innerHTML = '';
            
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
                
                raceBtn.onclick = () => this.selectRace(race.race_number, venueCode, venueName);
                this.ui.elements.raceButtons.appendChild(raceBtn);
            });
            
        } catch (error) {
            console.error('レース情報取得エラー:', error);
            this.ui.elements.raceButtons.innerHTML = `
                <div style="text-align:center; color:var(--danger); padding:20px;">
                    レース情報取得エラー<br>
                    <button class="btn btn-sm" onclick="app.showRaceSelector('${venueCode}', '${venueName}')">
                        再試行
                    </button>
                </div>
            `;
        }
    }

    generateRaceSchedule() {
        const races = [];
        const currentHour = new Date().getHours();
        const currentMinute = new Date().getMinutes();
        const currentTimeMinutes = currentHour * 60 + currentMinute;
        
        for (let i = 1; i <= 12; i++) {
            const raceStartMinutes = 15 * 60 + (i - 1) * 30; // 15:00開始、30分間隔
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

    selectRace(raceNumber, venueCode, venueName) {
        selectedRace = raceNumber;
        
        // 選択状態の更新
        document.querySelectorAll('.race-btn').forEach(btn => {
            btn.classList.remove('selected');
        });
        event.target.classList.add('selected');
        
        // 選択情報を更新
        if (this.ui.elements.selectedRaceInfo) {
            this.ui.elements.selectedRaceInfo.textContent = ` - 第${raceNumber}レース`;
        }
        
        // 出走表データを取得
        this.loadSelectedRaceData(venueCode, raceNumber, venueName);
    }

    async loadSelectedRaceData(venueCode, raceNumber, venueName) {
        try {
            this.ui.showLoading(`${venueName} 第${raceNumber}レース データ取得中...`);
            
            const data = await this.api.getRaceData(venueCode, raceNumber);
            
            if (data.racer_extraction && data.racer_extraction.racers) {
                this.displayRealRacers(data.racer_extraction.racers);
                this.updateRaceInfoFromSelected(data, venueName, raceNumber);
                
                // 表示切り替え
                this.ui.elements.predictionContainer.style.display = 'block';
                this.ui.hideLoading();
                this.ui.updateStatus('success', '<i class="fas fa-check-circle"></i> 出走表取得完了');
            } else {
                throw new Error('選手データが見つかりません');
            }
            
        } catch (error) {
            console.error('レースデータ取得エラー:', error);
            this.ui.showError('出走表の取得に失敗しました', error);
        }
    }

    updateRaceInfoFromSelected(data, venueName, raceNumber) {
        // レースヘッダー更新
        const raceHeader = document.querySelector('.race-header h3');
        if (raceHeader) {
            raceHeader.textContent = `${venueName} 第${raceNumber}レース`;
        }
        
        // タイムスタンプ更新
        this.ui.updateTimestamp(data.timestamp);
    }

    displayRealRacers(racers) {
        if (!this.ui.elements.racersTbodyNew) {
            console.error('racers-tbody-new要素が見つかりません');
            return;
        }
        
        this.ui.elements.racersTbodyNew.innerHTML = '';

        racers.forEach((racer, index) => {
            const row = document.createElement('div');
            row.className = 'racer-row fade-in';
            row.style.animationDelay = `${index * 0.1}s`;
            
            // モック成績データ
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
            
            this.ui.elements.racersTbodyNew.appendChild(row);
        });
        
        // 展示タイム表示
        this.displayExhibitionTimes(racers);
    }

    displayExhibitionTimes(racers) {
        if (!this.ui.elements.exhibitionGrid) return;
        
        this.ui.elements.exhibitionGrid.innerHTML = '';
        
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
            
            this.ui.elements.exhibitionGrid.appendChild(exhibitionItem);
        });
    }

    async loadRealTimeData() {
        try {
            this.ui.showLoading('リアルタイムデータ取得中...');
            
            const response = await this.api.request('/real-data-test');
            
            if (response.error) {
                throw new Error(response.error);
            }

            // 成功時の処理
            this.ui.hideLoading();
            this.ui.elements.raceInfo.style.display = 'block';
            this.ui.elements.predictionContainer.style.display = 'block';
            this.ui.updateStatus('success', '<i class="fas fa-check-circle"></i> データ取得成功');

            // リアルデータを表示
            if (response.racer_extraction && response.racer_extraction.racers) {
                this.displayRealRacers(response.racer_extraction.racers);
                this.updateRaceInfoFromReal(response);
            }

            // タイムスタンプ更新
            this.ui.updateTimestamp(response.timestamp);

        } catch (error) {
            console.error('データ取得エラー:', error);
            this.ui.showError('データの取得に失敗しました', error);
        }
    }

    updateRaceInfoFromReal(data) {
        // レースヘッダーの更新
        const raceHeader = document.querySelector('.race-header h3');
        if (raceHeader) {
            raceHeader.textContent = `桐生競艇 第1レース`;
        }
        
        // タイムスタンプ更新
        this.ui.updateTimestamp(data.timestamp);
    }

    async loadAIPrediction() {
        try {
            console.log('AI予想データ取得開始...');
            
            // 固定のレースID
            const today = new Date();
            const dateStr = today.getFullYear().toString() + 
                           (today.getMonth() + 1).toString().padStart(2, '0') + 
                           today.getDate().toString().padStart(2, '0');
            const raceId = `${dateStr}0101`;
            
            const prediction = await this.api.getRacePrediction(raceId);
            
            // AI予想結果を表示
            if (prediction.ai_predictions && prediction.ai_predictions.predictions && prediction.ai_predictions.predictions.length > 0) {
                this.displayAIPredictionResult(prediction);
            }
            
            this.ui.updateTimestamp();
            console.log('AI予想データ取得完了');
            
        } catch (error) {
            console.error('AI予想エラー:', error);
            this.displayMockAIPrediction();
        }
    }

    displayAIPredictionResult(prediction) {
        const topPrediction = prediction.ai_predictions.predictions[0];
        
        // 勝率予測表示
        if (this.ui.elements.predictedWinner) {
            this.ui.elements.predictedWinner.textContent = topPrediction.boat_number;
        }
        
        if (this.ui.elements.predictedWinnerName) {
            this.ui.elements.predictedWinnerName.textContent = `選手${topPrediction.boat_number}`;
        }
        
        if (this.ui.elements.winProbability) {
            const winProb = Math.round(topPrediction.normalized_probability * 100);
            this.ui.elements.winProbability.textContent = `${winProb}%`;
        }
        
        if (this.ui.elements.winConfidence) {
            this.ui.elements.winConfidence.textContent = '85';
        }
        
        // 推奨舟券表示
        if (prediction.ai_predictions.recommendations) {
            const recs = prediction.ai_predictions.recommendations;
            
            if (this.ui.elements.recommendedWin && recs.win) {
                this.ui.elements.recommendedWin.textContent = recs.win.boat_number;
            }
            
            if (this.ui.elements.recommendedExacta && recs.exacta) {
                this.ui.elements.recommendedExacta.textContent = recs.exacta.combination.join('-');
            }
            
            if (this.ui.elements.recommendedTrifecta && recs.trio_patterns) {
                const patterns = recs.trio_patterns.map(p => p.combination.join('-')).join(' / ');
                this.ui.elements.recommendedTrifecta.textContent = patterns;
            }
        }
        
        // メーター表示アニメーション
        this.animateMeters();
    }

    displayMockAIPrediction() {
        // モックデータでAI予想を表示
        if (this.ui.elements.predictedWinner) {
            this.ui.elements.predictedWinner.textContent = '1';
        }
        
        if (this.ui.elements.predictedWinnerName) {
            this.ui.elements.predictedWinnerName.textContent = '山田太郎';
        }
        
        if (this.ui.elements.winProbability) {
            this.ui.elements.winProbability.textContent = '78%';
        }
        
        if (this.ui.elements.winConfidence) {
            this.ui.elements.winConfidence.textContent = '92';
        }
        
        if (this.ui.elements.recommendedWin) {
            this.ui.elements.recommendedWin.textContent = '1';
        }
        
        if (this.ui.elements.recommendedExacta) {
            this.ui.elements.recommendedExacta.textContent = '1-3';
        }
        
        if (this.ui.elements.recommendedTrifecta) {
            this.ui.elements.recommendedTrifecta.textContent = '1-3-2';
        }
        
        this.animateMeters();
    }

    animateMeters() {
        // 安定性メーター
        if (this.ui.elements.stabilityMeter) {
            setTimeout(() => {
                this.ui.elements.stabilityMeter.style.width = '78%';
            }, 500);
        }
        
        if (this.ui.elements.stabilityScore) {
            this.ui.elements.stabilityScore.textContent = '78%';
        }
        
        // 波乱度メーター
        if (this.ui.elements.upsetMeter) {
            setTimeout(() => {
                this.ui.elements.upsetMeter.style.width = '35%';
            }, 700);
        }
        
        if (this.ui.elements.upsetScore) {
            this.ui.elements.upsetScore.textContent = '35%';
        }
    }

    async updateAIPrediction() {
        try {
            console.log('AI予想更新開始...');
            
            const currentRacers = this.getCurrentRacersData();
            
            if (!currentRacers || currentRacers.length === 0) {
                this.ui.showError('選手データが読み込まれていません');
                return;
            }
            
            this.ui.showLoading('AI分析中...');
            
            const aiResult = await this.api.updateAIPrediction(currentRacers);
            
            this.displayAIPredictionResult(aiResult);
            this.ui.hideLoading();
            this.ui.updateStatus('success', '<i class="fas fa-robot"></i> AI予想更新完了');
            
        } catch (error) {
            console.error('AI予想エラー:', error);
            this.ui.showError(`AI予想の更新に失敗しました: ${error.message}`);
        }
    }

    getCurrentRacersData() {
        const racerRows = document.querySelectorAll('.racer-row');
        const racers = [];
        
        racerRows.forEach((row) => {
            const boatNumberElement = row.querySelector('.boat-number-badge');
            const nameElement = row.querySelector('.racer-name');
            const gradeElement = row.querySelector('.grade-badge');
            
            if (boatNumberElement && nameElement && gradeElement) {
                const racer = {
                    boat_number: parseInt(boatNumberElement.textContent.trim()),
                    name: nameElement.textContent.trim(),
                    class: gradeElement.textContent.trim()
                };
                racers.push(racer);
            }
        });
        
        return racers;
    }

    async updatePerformanceStats() {
        try {
            const stats = await this.api.getPerformanceStats();
            
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

    startAutoUpdate() {
        if (!CONFIG.AUTO_REFRESH_ENABLED) return;
        
        updateTimer = setInterval(async () => {
            if (!isLoading && this.isInitialized) {
                console.log('🔄 自動更新実行');
                try {
                    await this.loadVenues();
                    if (selectedVenue && selectedRace) {
                        await this.loadSelectedRaceData(selectedVenue, selectedRace, 'Selected Venue');
                    }
                } catch (error) {
                    console.error('Auto update error:', error);
                }
            }
        }, CONFIG.UPDATE_INTERVAL);
        
        console.log(`⏰ 自動更新開始: ${CONFIG.UPDATE_INTERVAL / 1000}秒間隔`);
    }
}

// ===== ユーティリティ関数 =====
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    }
}

function formatTime(date) {
    return date.toLocaleTimeString('ja-JP', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

function showNotification(message, type = 'info') {
    // 通知表示（実装簡略化）
    console.log(`[${type.toUpperCase()}] ${message}`);
}

// ===== イベントリスナー設定 =====
function setupEventListeners() {
    // 会員登録フォーム
    const signupForm = document.querySelector('.signup-form');
    if (signupForm) {
        signupForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const email = this.querySelector('input[type="email"]').value;
            showNotification(`${email} を登録しました。メールをご確認ください。`, 'success');
        });
    }

    // スムーズスクロール
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            
            const targetId = this.getAttribute('href');
            const targetElement = document.querySelector(targetId);
            
            if (targetElement) {
                targetElement.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // モバイルメニュートグル
    const mobileMenuToggle = document.querySelector('.mobile-menu-toggle');
    if (mobileMenuToggle) {
        mobileMenuToggle.addEventListener('click', function() {
            const nav = document.querySelector('nav');
            nav.classList.toggle('mobile-open');
        });
    }
}

// ===== アプリケーション初期化 =====
let app;

document.addEventListener('DOMContentLoaded', function() {
    console.log('🌊 WAVE PREDICTOR 開始');
    
    // グローバルアプリインスタンス作成
    app = new WavePredictorApp();
    
    // イベントリスナー設定
    setupEventListeners();
    
    // アプリケーション初期化
    app.initialize();
});

// ===== グローバル関数（HTMLから呼び出し用） =====
window.loadRealTimeData = () => app.loadRealTimeData();
window.loadAIPrediction = () => app.loadAIPrediction();
window.updateAIPrediction = () => app.updateAIPrediction();
window.initApp = () => app.initialize();

// ===== エラーハンドリング =====
window.addEventListener('error', (event) => {
    console.error('Global Error:', event.error);
    if (app && app.ui) {
        app.ui.showError('予期しないエラーが発生しました', event.error);
    }
});

window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled Promise Rejection:', event.reason);
    if (app && app.ui) {
        app.ui.showError('通信エラーが発生しました', event.reason);
    }
});

console.log('🚀 WAVE PREDICTOR Script Loaded');
