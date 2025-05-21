/**
 * 競艇AI予測API連携モジュール
 */

class BoatraceAPI {
    constructor(baseUrl = 'http://localhost:5000/api') {
        this.baseUrl = baseUrl;
        this.predictions = {};
        this.lastUpdated = {};
    }

    // 今日のレース一覧を取得
    async getTodayRaces() {
        try {
            const response = await fetch(`${this.baseUrl}/races/today`);
            if (!response.ok) {
                throw new Error('レース情報の取得に失敗しました');
            }
            const races = await response.json();
            return races;
        } catch (error) {
            console.error('APIエラー:', error);
            return [];
        }
    }

    // 特定レースの予測を取得
    async getRacePrediction(raceId) {
        try {
            // キャッシュチェック（30分以内の予測を再利用）
            const now = new Date();
            if (this.predictions[raceId] && this.lastUpdated[raceId]) {
                const cacheTime = (now - this.lastUpdated[raceId]) / 1000 / 60; // 分単位
                if (cacheTime < 30) {
                    console.log(`キャッシュされた予測を使用: ${raceId}`);
                    return this.predictions[raceId];
                }
            }

            // 新規データ取得
            const response = await fetch(`${this.baseUrl}/prediction/${raceId}`);
            if (!response.ok) {
                throw new Error('予測データの取得に失敗しました');
            }
            const prediction = await response.json();
            
            // キャッシュに保存
            this.predictions[raceId] = prediction;
            this.lastUpdated[raceId] = now;
            
            return prediction;
        } catch (error) {
            console.error('APIエラー:', error);
            return null;
        }
    }

    // 特定日のレース一覧を取得
    async getRacesByDate(date) {
        try {
            const response = await fetch(`${this.baseUrl}/races/${date}`);
            if (!response.ok) {
                throw new Error('レース情報の取得に失敗しました');
            }
            const races = await response.json();
            return races;
        } catch (error) {
            console.error('APIエラー:', error);
            return [];
        }
    }

    // パフォーマンス統計を取得
    async getPerformanceStats(days = 30) {
        try {
            const response = await fetch(`${this.baseUrl}/stats?days=${days}`);
            if (!response.ok) {
                throw new Error('統計データの取得に失敗しました');
            }
            const stats = await response.json();
            return stats;
        } catch (error) {
            console.error('APIエラー:', error);
            return null;
        }
    }

    // レース会場の一覧を取得
    async getVenues() {
        try {
            const response = await fetch(`${this.baseUrl}/venues`);
            if (!response.ok) {
                throw new Error('会場情報の取得に失敗しました');
            }
            const venues = await response.json();
            return venues;
        } catch (error) {
            console.error('APIエラー:', error);
            return [];
        }
    }

    // 日次レポートを取得
    async getDailyReport(date) {
        try {
            const response = await fetch(`${this.baseUrl}/report/${date}`);
            if (!response.ok) {
                throw new Error('日次レポートの取得に失敗しました');
            }
            const report = await response.json();
            return report;
        } catch (error) {
            console.error('APIエラー:', error);
            return null;
        }
    }
}

// グローバルインスタンスを作成
const boatraceAPI = new BoatraceAPI();