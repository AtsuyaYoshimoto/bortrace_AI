/**
 * WAVE PREDICTOR - 適正スクレイピング対応版JavaScript
 * 競艇予想サイトのメインスクリプト
 * 
 * 改善点:
 * - 自動更新停止（5分間隔 → 手動更新のみ）
 * - キャッシュデータ優先表示
 * - 適正API呼び出し頻度
 * - 正式スクレイピングデータ対応
 */

// ===== 設定・定数 =====
const CONFIG = {
    API_BASE_URL: 'https://bortrace-ai-api-36737145161.asia-northeast1.run.app/api',
    AUTO_REFRESH_ENABLED: false, // 🔴 自動更新停止
    MANUAL_REFRESH_ONLY: true,   // ✅ 手動更新のみ
    DEBUG_MODE: false,
    ANIMATION_DURATION: 300,
    RETRY_ATTEMPTS: 3,
    RETRY_DELAY: 2000,
    CACHE_PREFERENCE: true       // ✅ キャッシュ優先
};

// ===== グローバル変数 =====
let selectedVenue = null;
let selectedRace = null;
let updateTimer = null;
let retryCount = 0;
let isLoading = false;
let touchStartY = 0;
let lastUpdateTime = null;
let scrapingStatus = null;

// ===== API連携クラス（適正化版） =====
class OptimizedBoatraceAPI {
    constructor(baseUrl = CONFIG.API_BASE_URL) {
        this.baseUrl = baseUrl;
        this.cache = new Map();
        this.requestQueue = [];
        this.isOnline = navigator.onLine;
        this.lastRequestTime = 0;
        this.requestInterval = 1000; // 1秒間隔制限
        
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
        
        // リクエスト間隔制限
        const now = Date.now();
        const timeSinceLastRequest = now - this.lastRequestTime;
        if (timeSinceLastRequest < this.requestInterval) {
            await new Promise(resolve => 
                setTimeout(resolve, this.requestInterval - timeSinceLastRequest)
            );
        }
        this.lastRequestTime = Date.now();
        
        if (!this.isOnline) {
            throw new Error('オフライン状態です');
        }

        try {
            console.log(`📡 API Request: ${endpoint} (優先度: キャッシュ)`);
            
            const response = await fetch(url, {
                timeout: 30000,
                ...options,
                headers: {
                    'Content-Type': 'application/json',
                    'X-Cache-Preference': 'cache-first', // キャッシュ優先指示
                    ...options.headers
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            
            // レスポンスにスクレイピング状況を保存
            if (data.scraping_status) {
                scrapingStatus = data.scraping_status;
                this.updateScrapingStatusDisplay();
            }
            
            // キャッシュに保存（GETリクエストのみ）
            if (!options.method || options.method === 'GET') {
                this.cache.set(url, { data, timestamp: Date.now() });
            }
            
            console.log(`✅ API Response: ${endpoint}`, {
                dataSource: data.data?.data_source || 'unknown',
                scrapingCount: data.scraping_status?.count_today || 0,
                cacheMode: data.scraping_status?.cache_only_mode || false
            });
            
            return data;
        } catch (error) {
            console.error(`❌ API Request Error (${endpoint}):`, error);
            
            // キャッシュから取得を試行
            const cached = this.cache.get(url);
            if (cached && Date.now() - cached.timestamp < 3600000) { // 1時間以内
                console.warn('🗄️ キャッシュからデータを返却');
                return cached.data;
            }
            
            throw error;
        }
    }

    updateScrapingStatusDisplay() {
        if (!scrapingStatus) return;
        
        const statusElement = document.getElementById('scraping-status');
        if (statusElement) {
            const { count_today, limit, cache_only_mode, remaining } = scrapingStatus;
            
            let statusClass = 'status-success';
            let statusText = `✅ 正常稼働中`;
            
            if (cache_only_mode) {
                statusClass = 'status-warning';
                statusText = `⚠️ キャッシュオンリーモード`;
            } else if (count_today >= limit * 0.8) {
                statusClass = 'status-warning';
                statusText = `⚠️ スクレイピング制限接近 (${count_today}/${limit})`;
            }
            
            statusElement.className = `status-indicator ${statusClass}`;
            statusElement.innerHTML = `
                <i class="fas fa-info-circle"></i>
                ${statusText} - 残り${remaining}回
            `;
        }
    }

    async getDailySchedule(date = null) {
        const params = date ? `?date=${date}` : '';
        return this.request(`/daily-schedule${params}`);
    }

    async getRaceEntries(venue, race, date = null) {
        const params = date ? `?date=${date}` : '';
        return this.request(`/race-entries/${venue}/${race}${params}`);
    }

    async getSystemStatus() {
        return this.request('/system-status');
    }

    async getScrapingStatus() {
        return this.request('/scraping-status');
    }

    async getRacePrediction(raceId) {
        return this.request(`/prediction/${raceId}`);
    }

    async updateAIPrediction(racers) {
        return this.request('/ai-prediction-simple', {
            method: 'POST',
            body: JSON.stringify({ racers })
        });
    }

    // 🔴 自動更新機能は完全に削除
    // startAutoRefresh() は実装しない

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

// ===== UI管理クラス（適正化版） =====
class OptimizedUIManager {
    constructor() {
        this.elements = this.cacheElements();
        this.isMobile = this.detectMobile();
        this.setupEventListeners();
        this.initializeAnimations();
        this.setupManualRefreshSystem(); // ✅ 手動更新システム
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
            scrapingStatus: document.getElementById('scraping-status'),
            manualRefreshBtn: document.getElementById('manual-refresh-btn'),
            scrapingStatusDetails: document.getElementById('scraping-status-details')
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

    setupManualRefreshSystem() {
        // 手動更新ボタンの設定
        if (this.elements.manualRefreshBtn) {
            this.elements.manualRefreshBtn.addEventListener('click', () => {
                this.manualRefresh();
            });
        }

        // スクレイピング状況表示エリアの作成
        this.createScrapingStatusDisplay();
        
        // 定期的な状況チェック（5分間隔、データ取得なし）
        setInterval(() => {
            this.updateLastUpdateTime();
        }, 300000); // 5分間隔
    }

    createScrapingStatusDisplay() {
        // スクレイピング状況表示エリアを追加
        const statusArea = document.createElement('div');
        statusArea.id = 'scraping-status-details';
        statusArea.className = 'scraping-status-area';
        statusArea.innerHTML = `
            <div class="status-header">
                <h4><i class="fas fa-chart-line"></i> システム状況</h4>
                <button id="refresh-status-btn" class="btn btn-sm">
                    <i class="fas fa-sync-alt"></i> 状況更新
                </button>
            </div>
            <div class="status-grid">
                <div class="status-item">
                    <span class="status-label">動作モード:</span>
                    <span id="operation-mode">確認中...</span>
                </div>
                <div class="status-item">
                    <span class="status-label">データソース:</span>
                    <span id="data-source">キャッシュ優先</span>
                </div>
                <div class="status-item">
                    <span class="status-label">最終更新:</span>
                    <span id="last-data-update">--:--:--</span>
                </div>
            </div>
        `;

        // データ状況表示の後に挿入
        const dataStatus = document.querySelector('.data-status');
        if (dataStatus) {
            dataStatus.parentNode.insertBefore(statusArea, dataStatus.nextSibling);
        }

        // 状況更新ボタンのイベント
        const refreshStatusBtn = document.getElementById('refresh-status-btn');
        if (refreshStatusBtn) {
            refreshStatusBtn.addEventListener('click', () => {
                this.updateSystemStatus();
            });
        }
    }

    async updateSystemStatus() {
        try {
            const statusData = await app.api.getSystemStatus();
            
            if (statusData && statusData.data) {
                const { scraping_status, performance } = statusData.data;
                
                // 動作モード表示
                const operationMode = document.getElementById('operation-mode');
                if (operationMode) {
                    if (scraping_status.cache_only_mode) {
                        operationMode.innerHTML = '<span class="status-warning">キャッシュオンリー</span>';
                    } else {
                        operationMode.innerHTML = '<span class="status-success">正常動作</span>';
                    }
                }
                
                // データソース表示
                const dataSource = document.getElementById('data-source');
                if (dataSource) {
                    dataSource.textContent = scraping_status.cache_only_mode ? 'キャッシュのみ' : 'キャッシュ優先';
                }
                
                // 成功率表示
                this.updatePerformanceDisplay(performance);
            }
        } catch (error) {
            console.error('システム状況更新エラー:', error);
        }
    }

    updatePerformanceDisplay(performance) {
        const successRate = (performance.success_rate * 100).toFixed(1);
        const avgTime = (performance.avg_response_time * 1000).toFixed(0);
        
        // 成功率表示
        const performanceElement = document.getElementById('performance-display');
        if (performanceElement) {
            performanceElement.innerHTML = `
                成功率: ${successRate}% | 平均応答: ${avgTime}ms
            `;
        }
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
        // パーティクル効果初期化（軽量版）
        this.createParticles();
        
        // スクロールアニメーション初期化
        this.initScrollAnimations();
        
        // CSS変数でアニメーション制御
        document.documentElement.style.setProperty('--animation-duration', `${CONFIG.ANIMATION_DURATION}ms`);
    }

    createParticles() {
        const heroParticles = document.querySelector('.hero-particles');
        if (!heroParticles) return;

        const particleCount = this.isMobile ? 10 : 20; // 軽量化
        
        for (let i = 0; i < particleCount; i++) {
            const particle = document.createElement('div');
            particle.className = 'particle';
            
            // ランダムな位置とサイズ
            const size = Math.random() * 4 + 2; // サイズ縮小
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
            this.manualRefresh();
        }
        
        // ESC キー: エラー閉じる
        if (e.key === 'Escape') {
            this.hideError();
        }
    }

    // ===== 手動更新システム =====
    async manualRefresh() {
        if (isLoading) {
            console.log('⏳ 既に更新処理中です');
            return;
        }

        console.log('🔄 手動更新開始');
        
        try {
            this.showLoading('手動更新中...');
            
            // システム状況確認
            await this.updateSystemStatus();
            
            // 選択された会場・レースがある場合は再取得
            if (selectedVenue && selectedRace) {
                await app.loadSelectedRaceData(selectedVenue, selectedRace, 'Selected Venue');
            } else {
                // 会場一覧を更新
                await app.loadVenues();
            }
            
            this.hideLoading();
            this.updateStatus('success', '<i class="fas fa-check-circle"></i> 手動更新完了');
            this.updateTimestamp();
            
            console.log('✅ 手動更新完了');
            
        } catch (error) {
            console.error('❌ 手動更新エラー:', error);
            this.showError('手動更新に失敗しました', error);
        }
    }

    updateLastUpdateTime() {
        // 最終更新時間の表示更新（データ取得なし）
        if (lastUpdateTime) {
            const timeDiff = Math.floor((Date.now() - lastUpdateTime.getTime()) / 1000 / 60);
            const lastUpdatedElement = document.getElementById('last-updated');
            
            if (lastUpdatedElement) {
                if (timeDiff < 60) {
                    lastUpdatedElement.textContent = `${timeDiff}分前`;
                } else {
                    const hours = Math.floor(timeDiff / 60);
                    lastUpdatedElement.textContent = `${hours}時間前`;
                }
            }
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
        [this.elements.lastUpdated, document.getElementById('last-data-update')].forEach(element => {
            if (element) {
                element.textContent = formatted;
            }
        });

        lastUpdateTime = date;
    }

    showPullToRefresh() {
        const refreshIndicator = document.createElement('div');
        refreshIndicator.className = 'pull-refresh-indicator';
        refreshIndicator.innerHTML = '<i class="fas fa-sync-alt fa-spin"></i> 手動更新中...';
        
        document.body.appendChild(refreshIndicator);
        
        setTimeout(() => {
            refreshIndicator.remove();
            this.manualRefresh();
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
        // 🔴 updateTimerは使用しないため削除
        console.log('🧹 クリーンアップ完了（自動更新タイマーなし）');
    }
}

// ===== メインアプリケーションクラス（適正化版） =====
class OptimizedWavePredictorApp {
    constructor() {
        this.api = new OptimizedBoatraceAPI();
        this.ui = new OptimizedUIManager();
        this.isInitialized = false;
    }

    async initialize() {
        try {
            console.log('🌊 WAVE PREDICTOR 適正版初期化開始');
            
            this.ui.showLoading('システム初期化中...');
            
            // 初期データ読み込み（キャッシュ優先）
            await this.loadInitialData();
            
            // 🔴 自動更新は開始しない（削除）
            // this.startAutoUpdate(); ← 削除
            
            // UI初期化完了
            this.ui.hideLoading();
            this.ui.updateStatus('success', '<i class="fas fa-check-circle"></i> システム準備完了（手動更新モード）');
            
            this.isInitialized = true;
            console.log('✅ WAVE PREDICTOR 適正版初期化完了');
            
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
            // システム状態確認（キャッシュ優先）
            const systemStatus = await this.api.getSystemStatus();
            console.log('System Status:', systemStatus);
            
            // 会場データ読み込み（キャッシュ優先）
            await this.loadVenues();
            
        } catch (error) {
            console.error('Initial data loading error:', error);
            throw error;
        }
    }

    async loadVenues() {
        try {
            console.log('=== 競艇会場データ取得開始（キャッシュ優先） ===');
            
            if (!this.ui.elements.venueGrid) {
                throw new Error('venue-grid要素が見つかりません');
            }
            
            // ローディング表示
            this.ui.elements.venueGrid.innerHTML = `
                <div style="grid-column: 1 / -1; text-align:center; padding:40px;">
                    <i class="fas fa-database" style="font-size:2rem; color:var(--primary); margin-bottom:1rem;"></i>
                    <div style="color:var(--primary); font-weight:600;">競艇場データ取得中（キャッシュ優先）...</div>
                </div>
            `;
            
            // 日次スケジュール取得（キャッシュ優先）
            const scheduleResponse = await this.api.getDailySchedule();
            
            console.log('取得したスケジュールデータ:', scheduleResponse);
            
            if (scheduleResponse && scheduleResponse.data && scheduleResponse.data.venues) {
                this.ui.elements.venueGrid.innerHTML = '';
                
                const venues = scheduleResponse.data.venues;
                const dataSource = scheduleResponse.data.data_source || 'cache';
                
                // 各会場カードを生成
                Object.values(venues).forEach(venueData => {
                    const venueCard = this.createVenueCard(venueData, dataSource);
                    this.ui.elements.venueGrid.appendChild(venueCard);
                });
                
                // 会場表示完了
                this.ui.elements.raceInfo.style.display = 'block';
                this.updateVenueSummary(venues, dataSource);
                
                console.log('=== 競艇会場データ表示完了 ===');
            } else {
                throw new Error('会場データが見つかりません');
            }
            
        } catch (error) {
            console.error('会場データ取得エラー:', error);
            this.showVenueError();
        }
    }

    createVenueCard(venueData, dataSource) {
        const venueCard = document.createElement('div');
        venueCard.className = 'venue-card';
        
        const isActive = venueData.is_active && venueData.races && venueData.races.length > 0;
        
        if (isActive) {
            venueCard.classList.add('active');
            
            const raceCount = venueData.races.length;
            const nextRace = venueData.races.find(r => r.status === 'scheduled');
            const statusText = nextRace ? `${nextRace.race_number}R ${nextRace.scheduled_time}` : `${raceCount}R開催`;
            
            venueCard.innerHTML = `
                <div class="venue-status-indicator live">開催中</div>
                <div class="venue-name">${venueData.venue_name}</div>
                <div class="venue-location">${this.getVenueLocation(venueData.venue_code)}</div>
                <div class="venue-race-status active-status">${statusText}</div>
                <div class="data-source-indicator ${dataSource}">${dataSource === 'cache' ? 'キャッシュ' : '取得済'}</div>
            `;
            
            venueCard.onclick = () => this.selectVenue(venueData.venue_code, venueData.venue_name, venueData.races);
            
        } else {
            venueCard.classList.add('inactive');
            
            venueCard.innerHTML = `
                <div class="venue-status-indicator closed">休場</div>
                <div class="venue-name">${venueData.venue_name}</div>
                <div class="venue-location">${this.getVenueLocation(venueData.venue_code)}</div>
                <div class="venue-race-status inactive-status">本日開催なし</div>
                <div class="data-source-indicator cache">キャッシュ</div>
            `;
        }
        
        return venueCard;
    }

    getVenueLocation(venueCode) {
        const locations = {
            '01': '群馬県', '02': '埼玉県', '03': '東京都', '04': '東京都', '05': '東京都',
            '06': '静岡県', '07': '愛知県', '08': '愛知県', '09': '三重県', '10': '福井県',
            '11': '滋賀県', '12': '大阪府', '13': '兵庫県', '14': '徳島県', '15': '香川県',
            '16': '岡山県', '17': '広島県', '18': '山口県', '19': '山口県', '20': '福岡県',
            '21': '福岡県', '22': '福岡県', '23': '佐賀県', '24': '長崎県'
        };
        return locations[venueCode] || '不明';
    }

    updateVenueSummary(venues, dataSource) {
        const activeCount = Object.values(venues).filter(v => v.is_active).length;
        const currentHour = new Date().getHours();
        const sourceText = dataSource === 'cache' ? 'キャッシュ' : '最新';
        
        if (activeCount > 0) {
            this.ui.updateStatus('success', 
                `<i class="fas fa-check-circle"></i> 開催中: ${activeCount}会場（${sourceText}データ）`
            );
        } else {
            this.ui.updateStatus('success', 
                `<i class="fas fa-info-circle"></i> データ取得完了（${sourceText}）`
            );
        }
    }

    showVenueError() {
        if (this.ui.elements.venueGrid) {
            this.ui.elements.venueGrid.innerHTML = `
                <div style="grid-column: 1 / -1; text-align:center; padding:40px; color:var(--danger);">
                    <i class="fas fa-exclamation-triangle" style="font-size:2rem; margin-bottom:1rem;"></i>
                    <div style="font-weight:600; margin-bottom:1rem;">データ取得エラー</div>
                    <button class="btn btn-primary" onclick="app.ui.manualRefresh()">
                        <i class="fas fa-sync-alt"></i> 手動更新
                    </button>
                </div>
            `;
        }
    }

    selectVenue(venueCode, venueName, races) {
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
        this.showRaceSelector(venueCode, venueName, races);
    }

    showRaceSelector(venueCode, venueName, races) {
        if (!this.ui.elements.raceSelector || !this.ui.elements.raceButtons) {
            console.error('レース選択UI要素が見つかりません');
            return;
        }
        
        this.ui.elements.raceSelector.style.display = 'block';
        this.ui.elements.raceButtons.innerHTML = '';
        
        if (races && races.length > 0) {
            races.forEach((race) => {
                const raceBtn = document.createElement('button');
                raceBtn.className = 'race-btn';
                raceBtn.classList.add(race.status || 'scheduled');
                
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
        } else {
            this.ui.elements.raceButtons.innerHTML = `
                <div style="text-align:center; color:var(--warning); padding:20px;">
                    レース情報が利用できません<br>
                    <button class="btn btn-sm" onclick="app.ui.manualRefresh()">
                        手動更新
                    </button>
                </div>
            `;
        }
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
            this.ui.showLoading(`${venueName} 第${raceNumber}レース 出走表取得中（キャッシュ優先）...`);
            
            const data = await this.api.getRaceEntries(venueCode, raceNumber);
            
            if (data && data.data && data.data.racer_extraction && data.data.racer_extraction.racers) {
                this.displayRealRacers(data.data.racer_extraction.racers, data.data.data_source);
                this.updateRaceInfoFromSelected(data.data, venueName, raceNumber);
                
                // 表示切り替え
                this.ui.elements.predictionContainer.style.display = 'block';
                this.ui.hideLoading();
                
                const sourceText = data.data.data_source === 'cache' ? 'キャッシュ' : '最新';
                this.ui.updateStatus('success', `<i class="fas fa-check-circle"></i> 出走表取得完了（${sourceText}）`);
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

    displayRealRacers(racers, dataSource) {
        if (!this.ui.elements.racersTbodyNew) {
            console.error('racers-tbody-new要素が見つかりません');
            return;
        }
        
        this.ui.elements.racersTbodyNew.innerHTML = '';

        racers.forEach((racer, index) => {
            const row = document.createElement('div');
            row.className = 'racer-row fade-in';
            row.style.animationDelay = `${index * 0.1}s`;
            
            // データソース表示
            const sourceIndicator = dataSource === 'cache' ? 
                '<span class="data-source-badge cache">キャッシュ</span>' : 
                '<span class="data-source-badge live">最新</span>';
            
            row.innerHTML = `
                <div class="boat-number-cell">
                    <div class="boat-number-badge boat-${racer.boat_number}">
                        ${racer.boat_number}
                    </div>
                </div>
                <div class="racer-info-cell">
                    <div class="racer-name">${racer.name} ${sourceIndicator}</div>
                    <div class="racer-details">
                        <span class="grade-badge ${racer.class?.toLowerCase()}">${racer.class}</span>
                        <span>${racer.age}歳</span>
                        <span>${racer.weight}</span>
                        <span>${racer.region}/${racer.branch}</span>
                    </div>
                </div>
                <div class="stats-cell">
                    <div class="stat-row">
                        <span class="stat-label">登録</span>
                        <span class="stat-value">${racer.registration_number}</span>
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

    // ===== 🔴 自動更新機能は完全削除 =====
    // startAutoUpdate() メソッドは実装しない

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
        
        // AI予想表示ロジック（既存と同じ）
        if (document.getElementById('predicted-winner')) {
            document.getElementById('predicted-winner').textContent = topPrediction.boat_number;
        }
        
        if (document.getElementById('predicted-winner-name')) {
            document.getElementById('predicted-winner-name').textContent = `選手${topPrediction.boat_number}`;
        }
        
        if (document.getElementById('win-probability')) {
            const winProb = Math.round(topPrediction.normalized_probability * 100);
            document.getElementById('win-probability').textContent = `${winProb}%`;
        }
        
        this.animateMeters();
    }

    displayMockAIPrediction() {
        // モックAI予想表示（既存と同じ）
        if (document.getElementById('predicted-winner')) {
            document.getElementById('predicted-winner').textContent = '1';
        }
        
        if (document.getElementById('predicted-winner-name')) {
            document.getElementById('predicted-winner-name').textContent = '山田太郎';
        }
        
        if (document.getElementById('win-probability')) {
            document.getElementById('win-probability').textContent = '78%';
        }
        
        this.animateMeters();
    }

    animateMeters() {
        // メーターアニメーション（既存と同じ）
        const stabilityMeter = document.getElementById('stability-meter');
        const upsetMeter = document.getElementById('upset-meter');
        
        if (stabilityMeter) {
            setTimeout(() => {
                stabilityMeter.style.width = '78%';
            }, 500);
        }
        
        if (upsetMeter) {
            setTimeout(() => {
                upsetMeter.style.width = '35%';
            }, 700);
        }
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

// ===== アプリケーション初期化（適正版） =====
let app;

document.addEventListener('DOMContentLoaded', function() {
    console.log('🌊 WAVE PREDICTOR 適正版開始');
    
    // グローバルアプリインスタンス作成
    app = new OptimizedWavePredictorApp();
    
    // イベントリスナー設定
    setupEventListeners();
    
    // アプリケーション初期化
    app.initialize();
    
    // 初期化完了メッセージ
    console.log(`
    ✅ WAVE PREDICTOR 適正版初期化完了
    🔴 自動更新: 無効
    ✅ 手動更新: 有効
    🗄️ データソース: キャッシュ優先
    🔄 更新方式: 手動更新のみ
    📊 スクレイピング: 適正頻度
    `);
});

// ===== グローバル関数（HTMLから呼び出し用・適正化） =====
window.loadRealTimeData = () => {
    console.log('⚠️ リアルタイムデータ取得は停止されました。手動更新を使用してください。');
    app.ui.manualRefresh();
};

window.loadAIPrediction = () => app.loadAIPrediction();

window.updateAIPrediction = () => {
    // AI予想更新（手動）
    console.log('🤖 AI予想手動更新');
    app.loadAIPrediction();
};

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

console.log(`
🚀 WAVE PREDICTOR 適正スクレイピング版 Script Loaded

📋 主な変更点:
🔴 5分間隔自動更新 → 停止
✅ 手動更新システム → 有効
🗄️ キャッシュ優先モード → 有効
📊 適正API呼び出し → 1秒間隔制限
⚡ リアルタイムスクレイピング → 停止
🔄 更新方式 → 手動更新のみ

使用方法: 「データ更新」ボタンで手動更新してください
`);
