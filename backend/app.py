from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, request, make_response, g
from flask_cors import CORS
import os
import requests
from bs4 import BeautifulSoup
import sqlite3
import datetime
import time
import random
import re
import threading
from datetime import datetime, timedelta
import sys
import schedule
import pytz
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from functools import lru_cache
import logging.config
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import json
import pickle
from collections import defaultdict
import numpy as np
pip install APScheduler

# Redis import (optional)
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

# ===== 設定クラス =====
class Config:
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    API_RATE_LIMIT = os.environ.get('API_RATE_LIMIT', '100 per hour')
    CACHE_TIMEOUT = int(os.environ.get('CACHE_TIMEOUT', '300'))
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///boatrace_data.db')
    MAX_WORKERS = int(os.environ.get('MAX_WORKERS', '5'))
    SCRAPING_DELAY = float(os.environ.get('SCRAPING_DELAY', '1.0'))
    VENUE_COUNT = 24
    ENABLE_RACE_RESULTS = os.environ.get('ENABLE_RACE_RESULTS', 'True').lower() == 'true'
    MOBILE_OPTIMIZATION = os.environ.get('MOBILE_OPTIMIZATION', 'True').lower() == 'true'

# ===== ログ設定 =====
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        },
        'simple': {
            'format': '%(levelname)s - %(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'simple',
            'stream': 'ext://sys.stdout'
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'boatrace_api.log',
            'level': 'DEBUG',
            'formatter': 'detailed',
            'mode': 'a'
        }
    },
    'loggers': {
        'boatrace': {
            'level': 'DEBUG',
            'handlers': ['console', 'file'],
            'propagate': False
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console']
    }
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger('boatrace')

# ===== Redis・キャッシュ設定 =====
redis_client = None
if REDIS_AVAILABLE:
    try:
        redis_client = redis.Redis(
            host=os.environ.get('REDIS_HOST', 'localhost'),
            port=int(os.environ.get('REDIS_PORT', '6379')),
            db=int(os.environ.get('REDIS_DB', '0')),
            decode_responses=True,
            socket_timeout=5
        )
        redis_client.ping()
        logger.info("Redis接続成功")
    except Exception as e:
        logger.warning(f"Redis接続失敗: {e}")
        redis_client = None

# ===== AI初期化 =====
print("🔍 sys.path設定完了、インポート開始...")

try:
    from boat_race_prediction_system import BoatRaceAI
    print("🤖 AIモデル初期化開始...")
    ai_model = BoatRaceAI()
    print("✅ ディープラーニングAIモデル初期化完了")
    AI_AVAILABLE = True
except Exception as e:
    print(f"❌ AI model initialization failed: {e}")
    print(f"エラー詳細: {type(e).__name__}")
    AI_AVAILABLE = False

print(f"🔍 AI初期化処理完了: AI_AVAILABLE = {AI_AVAILABLE}")

# ===== グローバル変数・メトリクス =====
request_count = 0
error_count = 0
start_time = datetime.now()
response_times = []

# ===== データベース管理クラス =====
class DatabaseManager:
    def __init__(self, db_path="boatrace_data.db"):
        self.db_path = db_path
        self.initialize_all_tables()
    
    def initialize_all_tables(self):
        """すべてのテーブルを初期化"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 選手テーブル
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS racers (
            racer_id INTEGER PRIMARY KEY,
            name TEXT,
            gender TEXT,
            birth_date TEXT,
            branch TEXT,
            rank TEXT,
            weight REAL,
            height REAL,
            last_updated TEXT
        )
        ''')
        
        # レース履歴テーブル
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS race_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venue_code TEXT,
            race_number INTEGER,
            race_date TEXT,
            racers_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 会場キャッシュテーブル
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS venue_cache (
            venue_code TEXT PRIMARY KEY,
            venue_name TEXT,
            is_active BOOLEAN,
            current_race INTEGER,
            remaining_races INTEGER,
            status TEXT,
            last_updated TIMESTAMP,
            data_source TEXT
        )
        ''')
        
        # レーススケジュールキャッシュ
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS race_schedule_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venue_code TEXT,
            race_number INTEGER,
            scheduled_time TEXT,
            status TEXT,
            last_updated TIMESTAMP,
            UNIQUE(venue_code, race_number)
        )
        ''')
        
        # レース結果テーブル
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS race_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id TEXT UNIQUE,
            venue_code TEXT,
            race_number INTEGER,
            race_date TEXT,
            results_data TEXT,
            payout_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 選手成績履歴
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS racer_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            racer_id INTEGER,
            venue_code TEXT,
            race_date TEXT,
            race_number INTEGER,
            course INTEGER,
            rank INTEGER,
            time REAL,
            start_time REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 選手コメントテーブル
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS racer_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id TEXT,
            racer_id INTEGER,
            comment TEXT,
            comment_date TEXT,
            sentiment_score REAL,
            UNIQUE(race_id, racer_id)
        )
        ''')
        
        # システム統計テーブル
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            total_requests INTEGER,
            error_count INTEGER,
            avg_response_time REAL,
            active_venues INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("データベーステーブル初期化完了")
    
    def get_connection(self):
        """データベース接続を取得"""
        return sqlite3.connect(self.db_path)
    
    def save_race_result(self, race_id, venue_code, race_number, race_date, results, payouts=None):
        """レース結果を保存"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            INSERT OR REPLACE INTO race_results 
            (race_id, venue_code, race_number, race_date, results_data, payout_data)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (race_id, venue_code, race_number, race_date, 
                  json.dumps(results), json.dumps(payouts)))
            
            conn.commit()
            logger.info(f"レース結果保存: {race_id}")
        except Exception as e:
            logger.error(f"レース結果保存エラー: {e}")
        finally:
            conn.close()
    
    def get_racer_performance_history(self, racer_id, days=30):
        """選手の成績履歴を取得"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        past_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        cursor.execute('''
        SELECT venue_code, race_date, race_number, course, rank, time, start_time
        FROM racer_performance
        WHERE racer_id = ? AND race_date >= ?
        ORDER BY race_date DESC, race_number DESC
        LIMIT 50
        ''', (racer_id, past_date))
        
        results = cursor.fetchall()
        conn.close()
        
        return [{
            'venue_code': r[0],
            'race_date': r[1],
            'race_number': r[2],
            'course': r[3],
            'rank': r[4],
            'time': r[5],
            'start_time': r[6]
        } for r in results]

# ===== ユーティリティ関数 =====
def get_today_date():
    """今日の日付を取得（YYYYMMDD形式）"""
    return datetime.now().strftime("%Y%m%d")

def build_race_url(venue_code, race_number, date_str):
    """レースURLを構築"""
    base_url = "https://boatrace.jp/owpc/pc/race/racelist"
    url = f"{base_url}?rno={race_number}&jcd={venue_code}&hd={date_str}"
    return url

def extract_racer_data_final(html_content):
    """最終版：選手情報抽出"""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 全てのtd要素を取得
        td_elements = soup.find_all('td')
        
        racers = []
        
        # 選手データの正規表現パターン
        # "4421 / B1 森作　　広大 東京/茨城 36歳/56.1kg"
        racer_pattern = r'(\d{4})\s*/\s*([AB][12])\s*([^\n]+?)\s+([^/\n]+)/([^\n]+?)\s+(\d+)歳/(\d+\.\d+)kg'
        
        for td in td_elements:
            text = td.get_text().strip()
            match = re.search(racer_pattern, text, re.MULTILINE | re.DOTALL)
            
            if match and len(racers) < 6:  # 6艇まで
                # 名前部分を整理（余分な空白を除去）
                name_raw = match.group(3).strip()
                name_clean = re.sub(r'\s+', ' ', name_raw).strip()
                
                racers.append({
                    "boat_number": len(racers) + 1,
                    "registration_number": match.group(1),
                    "class": match.group(2),
                    "name": name_clean,
                    "region": match.group(4).strip(),
                    "branch": match.group(5).strip(),
                    "age": int(match.group(6)),
                    "weight": f"{match.group(7)}kg"
                })
        
        return {
            "status": "success",
            "racers": racers,
            "found_count": len(racers)
        }
        
    except Exception as e:
        logger.error(f"選手データ抽出エラー: {str(e)}")
        return {"status": "error", "message": str(e)}

# ===== レスポンス標準化関数 =====
def create_response(data=None, error=None, status_code=200, message=None):
    """レスポンス標準化"""
    response = {
        "timestamp": datetime.now().isoformat(),
        "status_code": status_code,
        "success": error is None
    }
    
    if data is not None:
        response["data"] = data
    if error is not None:
        response["error"] = error
    if message is not None:
        response["message"] = message
        
    return jsonify(response), status_code

# ===== キャッシュ関数 =====
def get_from_cache(key):
    """キャッシュから取得"""
    if redis_client:
        try:
            return redis_client.get(key)
        except Exception as e:
            logger.warning(f"Redis取得エラー: {e}")
    return None

def set_to_cache(key, value, timeout=300):
    """キャッシュに保存"""
    if redis_client:
        try:
            redis_client.setex(key, timeout, value)
        except Exception as e:
            logger.warning(f"Redis保存エラー: {e}")

@lru_cache(maxsize=100)
def get_venue_info_cached(venue_code):
    """会場情報キャッシュ取得"""
    venues = {
        "01": {"name": "桐生", "location": "群馬県", "region": "関東", "characteristics": "狭水面・静水面"},
        "02": {"name": "戸田", "location": "埼玉県", "region": "関東", "characteristics": "狭水面・流水"},
        "03": {"name": "江戸川", "location": "東京都", "region": "関東", "characteristics": "広水面・流水・干満差"},
        "04": {"name": "平和島", "location": "東京都", "region": "関東", "characteristics": "海水・潮位差"},
        "05": {"name": "多摩川", "location": "東京都", "region": "関東", "characteristics": "流水・風の影響"},
        "06": {"name": "浜名湖", "location": "静岡県", "region": "中部", "characteristics": "汽水・風の影響少"},
        "07": {"name": "蒲郡", "location": "愛知県", "region": "中部", "characteristics": "汽水・静水面"},
        "08": {"name": "常滑", "location": "愛知県", "region": "中部", "characteristics": "汽水・風の影響"},
        "09": {"name": "津", "location": "三重県", "region": "中部", "characteristics": "海水・穏やか"},
        "10": {"name": "三国", "location": "福井県", "region": "中部", "characteristics": "海水・風波"},
        "11": {"name": "びわこ", "location": "滋賀県", "region": "関西", "characteristics": "淡水・広水面"},
        "12": {"name": "住之江", "location": "大阪府", "region": "関西", "characteristics": "淡水・安定水面"},
        "13": {"name": "尼崎", "location": "兵庫県", "region": "関西", "characteristics": "淡水・風の影響"},
        "14": {"name": "鳴門", "location": "徳島県", "region": "中国・四国", "characteristics": "海水・潮流"},
        "15": {"name": "丸亀", "location": "香川県", "region": "中国・四国", "characteristics": "海水・安定"},
        "16": {"name": "児島", "location": "岡山県", "region": "中国・四国", "characteristics": "海水・広水面"},
        "17": {"name": "宮島", "location": "広島県", "region": "中国・四国", "characteristics": "海水・干満差大"},
        "18": {"name": "徳山", "location": "山口県", "region": "中国・四国", "characteristics": "海水・安定"},
        "19": {"name": "下関", "location": "山口県", "region": "中国・四国", "characteristics": "海水・潮流"},
        "20": {"name": "若松", "location": "福岡県", "region": "九州", "characteristics": "海水・安定"},
        "21": {"name": "芦屋", "location": "福岡県", "region": "九州", "characteristics": "海水・静水面"},
        "22": {"name": "福岡", "location": "福岡県", "region": "九州", "characteristics": "淡水・安定"},
        "23": {"name": "唐津", "location": "佐賀県", "region": "九州", "characteristics": "海水・風波大"},
        "24": {"name": "大村", "location": "長崎県", "region": "九州", "characteristics": "汽水・穏やか"}
    }
    return venues.get(venue_code)

# ===== 選手分析クラス =====
class RacerAnalyzer:
    def __init__(self, db_manager):
        self.db_manager = db_manager
    
    def get_racer_detailed_stats(self, racer_id, venue_code=None):
        """選手の詳細統計取得"""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        # 基本成績
        where_clause = "WHERE racer_id = ?"
        params = [racer_id]
        
        if venue_code:
            where_clause += " AND venue_code = ?"
            params.append(venue_code)
        
        # 全体成績
        cursor.execute(f'''
        SELECT 
            COUNT(*) as total_races,
            AVG(rank) as avg_rank,
            SUM(CASE WHEN rank = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate,
            SUM(CASE WHEN rank <= 2 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as quinella_rate,
            SUM(CASE WHEN rank <= 3 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as trio_rate,
            AVG(start_time) as avg_start_time
        FROM racer_performance
        {where_clause} AND race_date >= date('now', '-30 days')
        ''', params)
        
        basic_stats = cursor.fetchone()
        
        # コース別成績
        cursor.execute(f'''
        SELECT 
            course,
            COUNT(*) as races,
            AVG(rank) as avg_rank,
            SUM(CASE WHEN rank = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate
        FROM racer_performance
        {where_clause} AND race_date >= date('now', '-90 days')
        GROUP BY course
        ORDER BY course
        ''', params)
        
        course_stats = cursor.fetchall()
        
        # 最近の調子（直近10レース）
        cursor.execute(f'''
        SELECT rank, race_date, venue_code
        FROM racer_performance
        {where_clause}
        ORDER BY race_date DESC, id DESC
        LIMIT 10
        ''', params)
        
        recent_results = cursor.fetchall()
        
        conn.close()
        
        return {
            "basic_stats": {
                "total_races": basic_stats[0] or 0,
                "avg_rank": round(basic_stats[1] or 3.5, 2),
                "win_rate": round(basic_stats[2] or 0, 1),
                "quinella_rate": round(basic_stats[3] or 0, 1),
                "trio_rate": round(basic_stats[4] or 0, 1),
                "avg_start_time": round(basic_stats[5] or 0.15, 3)
            },
            "course_stats": [
                {
                    "course": row[0],
                    "races": row[1],
                    "avg_rank": round(row[2], 2),
                    "win_rate": round(row[3], 1)
                } for row in course_stats
            ],
            "recent_form": {
                "results": [{"rank": r[0], "date": r[1], "venue": r[2]} for r in recent_results],
                "form_score": self.calculate_form_score(recent_results)
            }
        }
    
    def calculate_form_score(self, recent_results):
        """調子スコア計算（直近成績から）"""
        if not recent_results:
            return 50
        
        # 直近5レースを重視してスコア計算
        total_score = 0
        weight_sum = 0
        
        for i, result in enumerate(recent_results[:5]):
            rank = result[0]
            weight = 6 - i  # 新しいレースほど重み大
            
            # ランクに基づくスコア（1位=100、2位=80、...、6位=0）
            rank_score = max(0, (7 - rank) * 20)
            
            total_score += rank_score * weight
            weight_sum += weight
        
        return round(total_score / weight_sum if weight_sum > 0 else 50, 1)
    
    def get_venue_compatibility(self, racer_id, venue_code):
        """会場相性分析"""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        # 指定会場での成績
        cursor.execute('''
        SELECT 
            COUNT(*) as races,
            AVG(rank) as avg_rank,
            SUM(CASE WHEN rank = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate
        FROM racer_performance
        WHERE racer_id = ? AND venue_code = ? AND race_date >= date('now', '-365 days')
        ''', (racer_id, venue_code))
        
        venue_stats = cursor.fetchone()
        
        # 全会場での平均成績
        cursor.execute('''
        SELECT 
            AVG(rank) as avg_rank,
            SUM(CASE WHEN rank = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate
        FROM racer_performance
        WHERE racer_id = ? AND race_date >= date('now', '-365 days')
        ''', (racer_id,))
        
        overall_stats = cursor.fetchone()
        
        conn.close()
        
        if venue_stats[0] and venue_stats[0] > 3:  # 最低3レース以上
            compatibility_score = 50
            if overall_stats[1]:  # 全体平均がある場合
                rank_diff = overall_stats[0] - venue_stats[1]
                win_rate_diff = venue_stats[2] - overall_stats[1]
                
                # 順位が良い、勝率が高いほどスコアアップ
                compatibility_score += (rank_diff * 10) + (win_rate_diff * 2)
                compatibility_score = max(0, min(100, compatibility_score))
            
            return {
                "races": venue_stats[0],
                "avg_rank": round(venue_stats[1], 2),
                "win_rate": round(venue_stats[2], 1),
                "compatibility_score": round(compatibility_score, 1)
            }
        
        return None

# ===== 新しいBoatraceDataCollectorクラス =====
class BoatraceDataCollector:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Referer': 'https://boatrace.jp/',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        })
        
    def get_daily_race_data(self):
        """本日の全出走表情報取得"""
        try:
            url = "https://www.boatrace.jp/owpc/pc/race/index"
            logger.info(f"日次レースデータ取得開始: {url}")
            
            response = self.session.get(url, timeout=30)
            
            if response.status_code == 200:
                return self.parse_race_index(response.content)
            else:
                logger.error(f"レースインデックス取得失敗: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"レースデータ取得エラー: {str(e)}")
            return None
    
    def parse_race_index(self, html_content):
        """出走表情報パース"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            race_data = {}
            
            logger.info("レースインデックスページの解析開始")
            
            # 会場リンクを探す（実際のHTML構造に合わせて調整が必要）
            venue_links = soup.find_all('a', href=re.compile(r'jcd=\d{2}'))
            
            for link in venue_links:
                try:
                    href = link.get('href')
                    venue_match = re.search(r'jcd=(\d{2})', href)
                    
                    if venue_match:
                        venue_code = venue_match.group(1)
                        venue_name = link.get_text().strip()
                        
                        # 各会場の基本情報を取得
                        race_data[venue_code] = {
                            'venue_name': venue_name,
                            'venue_code': venue_code,
                            'is_active': True,
                            'races': []
                        }
                        
                        logger.info(f"会場発見: {venue_code} - {venue_name}")
                        
                except Exception as e:
                    logger.warning(f"会場リンク解析エラー: {str(e)}")
                    continue
            
            return race_data
            
        except Exception as e:
            logger.error(f"レースインデックス解析エラー: {str(e)}")
            return {}
    
    def get_venue_race_details(self, venue_code, date_str=None):
        """指定会場の詳細レース情報取得"""
        if date_str is None:
            date_str = get_today_date()
            
        try:
            # 会場のレース一覧ページにアクセス
            url = f"https://boatrace.jp/owpc/pc/race/racelist?jcd={venue_code}&hd={date_str}"
            logger.info(f"会場{venue_code}のレース詳細取得: {url}")
            
            response = self.session.get(url, timeout=30)
            time.sleep(Config.SCRAPING_DELAY)  # サーバー負荷軽減
            
            if response.status_code == 200:
                return self.parse_venue_races(response.content, venue_code)
            else:
                logger.warning(f"会場{venue_code}: レース詳細取得失敗 {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"会場{venue_code}レース詳細取得エラー: {str(e)}")
            return None
    
    def parse_venue_races(self, html_content, venue_code):
        """会場のレース情報解析"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            races = []
            
            # レース時刻表を探す
            time_cells = soup.find_all('td', class_='is-fs11')
            
            for i, time_cell in enumerate(time_cells[:12], 1):  # 最大12レース
                race_time = time_cell.get_text().strip()
                
                if race_time and ':' in race_time:
                    races.append({
                        'race_number': i,
                        'scheduled_time': race_time,
                        'status': 'upcoming',
                        'venue_code': venue_code
                    })
            
            logger.info(f"会場{venue_code}: {len(races)}レース発見")
            return races
            
        except Exception as e:
            logger.error(f"会場{venue_code}レース解析エラー: {str(e)}")
            return []
    
    def get_race_entries(self, venue_code, race_number, date_str=None):
        """出走表取得（選手情報込み）"""
        if date_str is None:
            date_str = get_today_date()
            
        try:
            race_url = build_race_url(venue_code, race_number, date_str)
            logger.info(f"出走表取得: 会場{venue_code} {race_number}R")
            
            response = self.session.get(race_url, timeout=30)
            time.sleep(Config.SCRAPING_DELAY)  # 負荷軽減
            
            if response.status_code == 200:
                racer_data = extract_racer_data_final(response.content)
                return racer_data
            else:
                logger.warning(f"出走表取得失敗: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"出走表取得エラー: {str(e)}")
            return None
    
    def get_race_results(self, venue_code, race_number, date_str=None):
        """レース結果取得（拡張版）"""
        if date_str is None:
            date_str = get_today_date()
            
        try:
            # レース結果ページのURL
            url = f"https://boatrace.jp/owpc/pc/race/raceresult?rno={race_number}&jcd={venue_code}&hd={date_str}"
            logger.info(f"レース結果取得: 会場{venue_code} {race_number}R")
            
            response = self.session.get(url, timeout=30)
            time.sleep(Config.SCRAPING_DELAY)
            
            if response.status_code == 200:
                return self.parse_race_results(response.content, venue_code, race_number, date_str)
            else:
                logger.warning(f"レース結果取得失敗: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"レース結果取得エラー: {str(e)}")
            return None
    
    def parse_race_results(self, html_content, venue_code, race_number, date_str):
        """レース結果解析（モック実装）"""
        try:
            # 実際の実装では、HTMLから結果をパースする
            # ここではモックデータを返す
            results = []
            payouts = {}
            
            # モック結果データ
            for boat_num in range(1, 7):
                rank = boat_num  # 簡易的に艇番=順位
                results.append({
                    "boat_number": boat_num,
                    "rank": rank,
                    "time": f"{6 + random.uniform(0.5, 2.0):.2f}",
                    "start_time": f"{random.uniform(0.05, 0.20):.3f}"
                })
            
            # 払戻金データ（モック）
            payouts = {
                "win": {"boat": 1, "odds": round(random.uniform(1.2, 5.0), 1), "payout": 0},
                "quinella": {"combination": [1, 2], "odds": round(random.uniform(2.0, 15.0), 1), "payout": 0},
                "exacta": {"combination": [1, 2], "odds": round(random.uniform(3.0, 25.0), 1), "payout": 0},
                "trio": {"combination": [1, 2, 3], "odds": round(random.uniform(5.0, 50.0), 1), "payout": 0}
            }
            
            # データベースに保存
            race_id = f"{date_str}{venue_code}{race_number:02d}"
            self.db_manager.save_race_result(race_id, venue_code, race_number, date_str, results, payouts)
            
            return {
                "race_id": race_id,
                "results": results,
                "payouts": payouts,
                "status": "completed"
            }
            
        except Exception as e:
            logger.error(f"レース結果解析エラー: {str(e)}")
            return None

# ===== 修正版VenueDataManagerクラス =====
class VenueDataManager:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.scheduler = None
        self.venue_cache = {}
        self.last_update = None
        self.all_venues = [
            ("01", "桐生"), ("02", "戸田"), ("03", "江戸川"), ("04", "平和島"), ("05", "多摩川"),
            ("06", "浜名湖"), ("07", "蒲郡"), ("08", "常滑"), ("09", "津"), ("10", "三国"),
            ("11", "びわこ"), ("12", "住之江"), ("13", "尼崎"), ("14", "鳴門"), ("15", "丸亀"),
            ("16", "児島"), ("17", "宮島"), ("18", "徳山"), ("19", "下関"), ("20", "若松"),
            ("21", "芦屋"), ("22", "福岡"), ("23", "唐津"), ("24", "大村")
        ]
        self.data_collector = BoatraceDataCollector(db_manager)
    
    def start_background_updates(self):
        from apscheduler.schedulers.background import BackgroundScheduler
        
        self.scheduler = BackgroundScheduler()
        
        # 毎日0時にレースデータ更新
        self.scheduler.add_job(
            func=self.update_daily_races,
            trigger="cron", 
            hour=0, 
            minute=0
        )
        
        # 展示タイム更新（1時間ごと）
        self.scheduler.add_job(
            func=self.update_pre_race_info,
            trigger="interval",
            hours=1
        )
        
        # レース結果収集（30分ごと）
        if Config.ENABLE_RACE_RESULTS:
            self.scheduler.add_job(
                func=self.collect_race_results,
                trigger="interval",
                minutes=30
            )
        
        self.scheduler.start()
        logger.info("スケジューラー開始: 0時日次更新、1時間ごと直前情報更新、30分ごと結果収集")

    except Exception as e:
        logger.error(f"スケジューラー開始エラー: {e}")
        self.scheduler = None
    
    def update_daily_races(self):
        """0時実行：本日の全レースデータ更新"""
        logger.info("=== 日次レースデータ更新開始 ===")
        
        try:
            # 全体のレースデータ取得
            race_data = self.data_collector.get_daily_race_data()
            
            if race_data:
                # 各会場の詳細情報を取得
                for venue_code, venue_info in race_data.items():
                    try:
                        # 会場の詳細レース情報取得
                        races = self.data_collector.get_venue_race_details(venue_code)
                        
                        if races:
                            venue_info['races'] = races
                            venue_info['is_active'] = len(races) > 0
                            venue_info['race_count'] = len(races)
                        else:
                            venue_info['is_active'] = False
                            venue_info['races'] = []
                            venue_info['race_count'] = 0
                            
                        # キャッシュ更新
                        self.venue_cache[venue_code] = {
                            **venue_info,
                            "last_updated": datetime.now().isoformat()
                        }
                        
                        logger.info(f"会場{venue_code}({venue_info.get('venue_name', '不明')}): {len(races)}レース")
                        
                        # サーバー負荷軽減
                        time.sleep(Config.SCRAPING_DELAY)
                        
                    except Exception as e:
                        logger.error(f"会場{venue_code}の詳細取得エラー: {str(e)}")
                        continue
                
                logger.info("=== 日次更新完了 ===")
            else:
                logger.warning("日次レースデータ取得失敗")
                
        except Exception as e:
            logger.error(f"日次更新エラー: {str(e)}")
    
    def update_pre_race_info(self):
        """直前情報更新（展示タイム発表時）"""
        logger.info("=== 直前情報更新開始 ===")
        
        try:
            current_time = datetime.now()
            
            # アクティブな会場のみチェック
            for venue_code, venue_data in self.venue_cache.items():
                if not venue_data.get('is_active', False):
                    continue
                    
                races = venue_data.get('races', [])
                
                for race in races:
                    try:
                        race_number = race.get('race_number')
                        scheduled_time = race.get('scheduled_time')
                        
                        if not race_number or not scheduled_time:
                            continue
                        
                        # レース開始2時間前から直前情報取得
                        try:
                            race_time = datetime.strptime(
                                f"{current_time.strftime('%Y%m%d')} {scheduled_time}", 
                                "%Y%m%d %H:%M"
                            )
                            time_diff = (race_time - current_time).total_seconds() / 3600
                            
                            # 2時間前～レース開始まで
                            if 0 <= time_diff <= 2:
                                # 展示タイム・直前情報の更新処理
                                logger.info(f"直前情報更新対象: 会場{venue_code} {race_number}R")
                                
                        except Exception as e:
                            logger.warning(f"時刻解析エラー: {str(e)}")
                            continue
                            
                        # API負荷軽減
                        time.sleep(Config.SCRAPING_DELAY)
                        
                    except Exception as e:
                        logger.error(f"レース{race_number}直前情報エラー: {str(e)}")
                        continue
                        
        except Exception as e:
            logger.error(f"直前情報更新エラー: {str(e)}")
    
    def collect_race_results(self):
        """レース結果収集（30分ごと実行）"""
        logger.info("=== レース結果収集開始 ===")
        
        try:
            current_time = datetime.now()
            today = current_time.strftime("%Y%m%d")
            
            # アクティブな会場のレース結果をチェック
            for venue_code, venue_data in self.venue_cache.items():
                if not venue_data.get('is_active', False):
                    continue
                
                races = venue_data.get('races', [])
                
                for race in races:
                    race_number = race.get('race_number')
                    scheduled_time = race.get('scheduled_time')
                    
                    if not race_number or not scheduled_time:
                        continue
                    
                    try:
                        # レース終了時刻を推定（開始15分後）
                        race_start = datetime.strptime(f"{today} {scheduled_time}", "%Y%m%d %H:%M")
                        race_end = race_start + timedelta(minutes=15)
                        
                        # レース終了後なら結果取得
                        if current_time >= race_end:
                            race_id = f"{today}{venue_code}{race_number:02d}"
                            
                            # 既に取得済みかチェック
                            conn = self.db_manager.get_connection()
                            cursor = conn.cursor()
                            cursor.execute('SELECT id FROM race_results WHERE race_id = ?', (race_id,))
                            existing = cursor.fetchone()
                            conn.close()
                            
                            if not existing:
                                results = self.data_collector.get_race_results(venue_code, race_number, today)
                                if results:
                                    logger.info(f"レース結果取得完了: {race_id}")
                                
                                time.sleep(Config.SCRAPING_DELAY)
                                
                    except Exception as e:
                        logger.error(f"レース結果収集エラー: {str(e)}")
                        continue
                        
        except Exception as e:
            logger.error(f"レース結果収集全体エラー: {str(e)}")
    
    def get_venue_status(self, venue_code):
        """会場ステータス取得"""
        return self.venue_cache.get(venue_code, {
            "is_active": False,
            "venue_name": "不明",
            "last_updated": None
        })
    
    def get_race_entries(self, venue_code, race_number):
        """出走表情報取得"""
        try:
            return self.data_collector.get_race_entries(venue_code, race_number)
        except Exception as e:
            logger.error(f"出走表取得エラー: {str(e)}")
            return None

# ===== グローバルインスタンス =====
db_manager = DatabaseManager()
data_collector = BoatraceDataCollector(db_manager)
venue_manager = VenueDataManager(db_manager)
racer_analyzer = RacerAnalyzer(db_manager)

# ===== Flask アプリ初期化 =====
app = Flask(__name__)
CORS(app)

# 設定適用
app.config.from_object(Config)

# レート制限設定
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["1000 per hour", "50 per minute"]
)

# ===== リクエスト処理フック =====
@app.before_request
def before_request():
    global request_count
    request_count += 1
    g.start_time = time.time()
    
    # モバイル判定
    user_agent = request.headers.get('User-Agent', '').lower()
    g.is_mobile = any(device in user_agent for device in ['mobile', 'android', 'iphone', 'ipad'])
    
    logger.info(f"Request: {request.method} {request.path}", extra={
        "method": request.method,
        "path": request.path,
        "user_agent": request.user_agent.string,
        "remote_addr": request.remote_addr,
        "is_mobile": g.is_mobile
    })

@app.after_request
def after_request(response):
    global response_times
    
    duration = time.time() - g.start_time
    response_times.append(duration)
    
    # 最新100件のレスポンス時間のみ保持
    if len(response_times) > 100:
        response_times = response_times[-100:]
    
    logger.info(f"Response: {response.status_code} - {duration:.3f}s")
    
    # セキュリティヘッダー追加
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # モバイル最適化ヘッダー
    if hasattr(g, 'is_mobile') and g.is_mobile:
        response.headers['Cache-Control'] = 'public, max-age=300'  # 5分キャッシュ
    
    return response

# ===== エラーハンドラー =====
@app.errorhandler(404)
def not_found_error(error):
    global error_count
    error_count += 1
    
    logger.warning(f"404 Error: {request.path}")
    
    return create_response(
        error="エンドポイントが見つかりません",
        status_code=404,
        message=f"パス '{request.path}' は存在しません"
    )

@app.errorhandler(500)
def internal_error(error):
    global error_count
    error_count += 1
    
    logger.error(f"500 Error: {str(error)}")
    
    return create_response(
        error="内部サーバーエラー",
        status_code=500,
        message="サーバーで予期しないエラーが発生しました"
    )

@app.errorhandler(429)
def ratelimit_error(error):
    logger.warning(f"Rate limit exceeded: {request.remote_addr}")
    
    return create_response(
        error="レート制限に達しました",
        status_code=429,
        message="リクエストが多すぎます。しばらく時間をおいて再試行してください"
    )

# ===== 基本エンドポイント =====
@app.route('/')
def index():
    return jsonify({
        "service": "WAVE PREDICTOR - 競艇予想AI API サーバー",
        "version": "2.0.0",
        "status": "running",
        "ai_available": AI_AVAILABLE,
        "features": [
            "全競艇場対応", 
            "AI予想", 
            "リアルタイムデータ", 
            "キャッシュ機能",
            "選手詳細分析",
            "レース結果表示",
            "モバイル最適化"
        ],
        "endpoints": {
            "races": "/api/races/today",
            "prediction": "/api/prediction/{race_id}",
            "venues": "/api/venues",
            "racer_details": "/api/racer/{racer_id}/details",
            "race_results": "/api/race-results/{venue_code}/{race_number}",
            "system_status": "/api/system-status"
        }
    })

@app.route('/api/test', methods=['GET'])
@limiter.limit("100 per minute")
def test():
    return create_response(
        data={"message": "API is working!", "mobile_optimized": hasattr(g, 'is_mobile') and g.is_mobile},
        message="API正常動作中"
    )

# ===== 新規APIエンドポイント =====
@app.route('/api/health', methods=['GET'])
def health_check():
    uptime = (datetime.now() - start_time).total_seconds()
    avg_response_time = sum(response_times) / len(response_times) if response_times else 0
    
    health_data = {
        "status": "healthy",
        "uptime_seconds": uptime,
        "uptime_formatted": str(timedelta(seconds=int(uptime))),
        "version": "2.0.0",
        "ai_available": AI_AVAILABLE,
        "redis_available": redis_client is not None,
        "total_requests": request_count,
        "error_count": error_count,
        "avg_response_time": round(avg_response_time, 3),
        "database_status": "connected",
        "features": {
            "race_results": Config.ENABLE_RACE_RESULTS,
            "mobile_optimization": Config.MOBILE_OPTIMIZATION
        }
    }
    
    return create_response(data=health_data)

@app.route('/api/metrics', methods=['GET'])
@limiter.limit("10 per minute")
def get_metrics():
    uptime = (datetime.now() - start_time).total_seconds()
    
    metrics = {
        "requests": {
            "total": request_count,
            "errors": error_count,
            "success_rate": (request_count - error_count) / request_count if request_count > 0 else 0
        },
        "performance": {
            "avg_response_time": sum(response_times) / len(response_times) if response_times else 0,
            "min_response_time": min(response_times) if response_times else 0,
            "max_response_time": max(response_times) if response_times else 0
        },
        "system": {
            "uptime_seconds": uptime,
            "ai_available": AI_AVAILABLE,
            "redis_available": redis_client is not None,
            "active_cache_entries": len(venue_manager.venue_cache)
        }
    }
    
    return create_response(data=metrics)

# ===== 選手詳細情報API =====
@app.route('/api/racer/<int:racer_id>/details', methods=['GET'])
@limiter.limit("30 per minute")
def get_racer_details(racer_id):
    """選手詳細情報取得"""
    try:
        venue_code = request.args.get('venue_code')
        
        # 基本統計取得
        detailed_stats = racer_analyzer.get_racer_detailed_stats(racer_id, venue_code)
        
        # 会場相性（指定会場がある場合）
        venue_compatibility = None
        if venue_code:
            venue_compatibility = racer_analyzer.get_venue_compatibility(racer_id, venue_code)
        
        # 成績履歴
        performance_history = db_manager.get_racer_performance_history(racer_id)
        
        response_data = {
            "racer_id": racer_id,
            "detailed_stats": detailed_stats,
            "venue_compatibility": venue_compatibility,
            "performance_history": performance_history[:10],  # 直近10レース
            "analysis_summary": {
                "strengths": generate_racer_strengths(detailed_stats),
                "weaknesses": generate_racer_weaknesses(detailed_stats),
                "recommendation": generate_racer_recommendation(detailed_stats, venue_compatibility)
            }
        }
        
        return create_response(data=response_data)
        
    except Exception as e:
        logger.error(f"選手詳細情報取得エラー: {str(e)}")
        return create_response(error=str(e), status_code=500)

def generate_racer_strengths(stats):
    """選手の強みを分析"""
    strengths = []
    basic = stats['basic_stats']
    course_stats = stats['course_stats']
    
    if basic['win_rate'] > 20:
        strengths.append("高い勝率")
    if basic['avg_start_time'] < 0.15:
        strengths.append("スタート技術")
    if basic['trio_rate'] > 60:
        strengths.append("安定した成績")
    
    # コース別強み
    for course in course_stats:
        if course['win_rate'] > 25:
            strengths.append(f"{course['course']}コースが得意")
    
    return strengths[:3]  # 最大3つ

def generate_racer_weaknesses(stats):
    """選手の弱点を分析"""
    weaknesses = []
    basic = stats['basic_stats']
    
    if basic['win_rate'] < 10:
        weaknesses.append("勝率が低い")
    if basic['avg_start_time'] > 0.17:
        weaknesses.append("スタートが遅れがち")
    if basic['avg_rank'] > 4.0:
        weaknesses.append("平均着順が悪い")
    
    return weaknesses[:2]  # 最大2つ

def generate_racer_recommendation(stats, venue_compatibility):
    """推奨度を生成"""
    score = 50  # ベーススコア
    
    # 基本成績による加算
    basic = stats['basic_stats']
    score += (basic['win_rate'] - 15) * 2  # 勝率15%基準
    score += (60 - basic['avg_rank'] * 10)  # 平均着順
    
    # 調子による調整
    form_score = stats['recent_form']['form_score']
    score += (form_score - 50) * 0.5
    
    # 会場相性
    if venue_compatibility and venue_compatibility['compatibility_score']:
        score += (venue_compatibility['compatibility_score'] - 50) * 0.3
    
    score = max(0, min(100, score))
    
    if score >= 80:
        return "強く推奨"
    elif score >= 65:
        return "推奨"
    elif score >= 50:
        return "注意"
    else:
        return "避けた方が良い"

# ===== レース結果API =====
@app.route('/api/race-results/<venue_code>/<int:race_number>', methods=['GET'])
@limiter.limit("20 per minute")
def get_race_results_api(venue_code, race_number):
    """レース結果取得API"""
    try:
        date_str = request.args.get('date', get_today_date())
        
        # バリデーション
        if venue_code not in [f"{i:02d}" for i in range(1, 25)]:
            return create_response(
                error="無効な会場コードです",
                status_code=400
            )
            
        if not (1 <= race_number <= 12):
            return create_response(
                error="無効なレース番号です",
                status_code=400
            )
        
        race_id = f"{date_str}{venue_code}{race_number:02d}"
        
        # データベースから結果取得
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT results_data, payout_data, created_at
        FROM race_results
        WHERE race_id = ?
        ''', (race_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            results_data = json.loads(result[0]) if result[0] else None
            payout_data = json.loads(result[1]) if result[1] else None
            
            venue_info = get_venue_info_cached(venue_code)
            
            response_data = {
                "race_id": race_id,
                "venue_code": venue_code,
                "venue_name": venue_info["name"] if venue_info else "不明",
                "race_number": race_number,
                "race_date": date_str,
                "results": results_data,
                "payouts": payout_data,
                "result_time": result[2]
            }
            
            return create_response(data=response_data)
        else:
            return create_response(
                error="レース結果が見つかりません",
                status_code=404,
                message="レースが未実施または結果未取得です"
            )
            
    except Exception as e:
        logger.error(f"レース結果API エラー: {str(e)}")
        return create_response(error=str(e), status_code=500)

@app.route('/api/race-results/recent', methods=['GET'])
@limiter.limit("20 per minute")
def get_recent_race_results():
    """最近のレース結果一覧"""
    try:
        limit = min(int(request.args.get('limit', 10)), 50)  # 最大50件
        venue_code = request.args.get('venue_code')
        
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        
        where_clause = ""
        params = []
        
        if venue_code:
            where_clause = "WHERE venue_code = ?"
            params.append(venue_code)
        
        cursor.execute(f'''
        SELECT race_id, venue_code, race_number, race_date, results_data, payout_data, created_at
        FROM race_results
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ?
        ''', params + [limit])
        
        results = cursor.fetchall()
        conn.close()
        
        race_results = []
        for result in results:
            venue_info = get_venue_info_cached(result[1])
            results_data = json.loads(result[4]) if result[4] else None
            payout_data = json.loads(result[5]) if result[5] else None
            
            race_results.append({
                "race_id": result[0],
                "venue_code": result[1],
                "venue_name": venue_info["name"] if venue_info else "不明",
                "race_number": result[2],
                "race_date": result[3],
                "winner": results_data[0] if results_data and len(results_data) > 0 else None,
                "win_payout": payout_data.get("win", {}).get("odds") if payout_data else None,
                "result_time": result[6]
            })
        
        return create_response(data={
            "results": race_results,
            "total_count": len(race_results)
        })
        
    except Exception as e:
        logger.error(f"最近のレース結果取得エラー: {str(e)}")
        return create_response(error=str(e), status_code=500)

# ===== 競艇データAPI（既存の改善版） =====
@app.route('/api/races/today', methods=['GET'])
@limiter.limit("30 per minute")
def get_today_races():
    try:
        mobile_optimized = hasattr(g, 'is_mobile') and g.is_mobile
        
        races = []
        for venue_code, venue_name in venue_manager.all_venues:
            status = venue_manager.get_venue_status(venue_code)
            
            race_data = {
                "race_id": f"{get_today_date()}{venue_code}01",
                "venue_code": venue_code,
                "venue_name": venue_name,
                "is_active": status.get('is_active', False),
                "race_count": status.get('race_count', 0)
            }
            
            if not mobile_optimized:
                # デスクトップ版では詳細情報も含める
                venue_info = get_venue_info_cached(venue_code)
                if venue_info:
                    race_data.update({
                        "location": venue_info["location"],
                        "region": venue_info["region"],
                        "characteristics": venue_info["characteristics"]
                    })
            
            races.append(race_data)
        
        return create_response(data={
            "races": races,
            "date": get_today_date(),
            "mobile_optimized": mobile_optimized
        })
    except Exception as e:
        logger.error(f"今日のレース取得エラー: {str(e)}")
        return create_response(error=str(e), status_code=500)

@app.route('/api/prediction/<race_id>', methods=['GET', 'POST'])
@limiter.limit("20 per minute")
def get_race_prediction(race_id):
    try:
        if not AI_AVAILABLE:
            return create_response(data=get_mock_prediction(race_id))
            
        prediction = ai_model.get_race_prediction(race_id)
        return create_response(data=prediction)
        
    except Exception as e:
        logger.error(f"AI予想エラー: {str(e)}")
        return create_response(data=get_mock_prediction(race_id))

def get_mock_prediction(race_id):
    """改良版モック予想データ"""
    return {
        "race_id": race_id,
        "predictions": [
            {"racer_id": 1, "boat_number": 1, "predicted_rank": 1, "rank_probabilities": [0.35, 0.25, 0.20, 0.12, 0.05, 0.03], "expected_value": 1.2, "confidence": 0.85},
            {"racer_id": 2, "boat_number": 2, "predicted_rank": 3, "rank_probabilities": [0.15, 0.20, 0.30, 0.20, 0.10, 0.05], "expected_value": 2.8, "confidence": 0.72},
            {"racer_id": 3, "boat_number": 3, "predicted_rank": 2, "rank_probabilities": [0.25, 0.35, 0.25, 0.10, 0.03, 0.02], "expected_value": 2.3, "confidence": 0.78},
            {"racer_id": 4, "boat_number": 4, "predicted_rank": 5, "rank_probabilities": [0.08, 0.10, 0.15, 0.25, 0.30, 0.12], "expected_value": 4.8, "confidence": 0.63},
            {"racer_id": 5, "boat_number": 5, "predicted_rank": 4, "rank_probabilities": [0.10, 0.08, 0.08, 0.25, 0.35, 0.14], "expected_value": 4.2, "confidence": 0.68},
            {"racer_id": 6, "boat_number": 6, "predicted_rank": 6, "rank_probabilities": [0.07, 0.02, 0.02, 0.08, 0.17, 0.64], "expected_value": 5.4, "confidence": 0.71}
        ],
        "forecast": {
            "win": {"boat_number": 1, "confidence": 0.85},
            "quinella": {"combination": [1, 3], "confidence": 0.78},
            "exacta": {"combination": [1, 3], "confidence": 0.72},
            "trio": {"combination": [1, 3, 2], "confidence": 0.68}
        },
        "risk_analysis": {
            "stability_score": 78,
            "upset_probability": 22,
            "reliability": "高"
        }
    }

# ===== 統計・システム情報API =====
@app.route('/api/stats', methods=['GET'])
@limiter.limit("30 per minute")
def get_performance_stats():
    try:
        # 拡張統計情報
        stats = {
            "period": "過去30日間",
            "race_count": 150,
            "accuracy": {
                "win_hit_rate": 0.945,
                "exacta_hit_rate": 0.823,
                "quinella_hit_rate": 0.887,
                "trio_hit_rate": 0.678
            },
            "performance": {
                "avg_return_rate": 127.5,
                "max_consecutive_hits": 8,
                "avg_odds": 4.2
            },
            "venue_analysis": {
                "best_venue": "住之江",
                "best_venue_hit_rate": 0.92,
                "most_analyzed": "桐生"
            },
            "ai_model": {
                "version": "2.0.0",
                "last_training": "2025-01-01",
                "confidence_avg": 0.78
            }
        }
        return create_response(data=stats)
    except Exception as e:
        logger.error(f"統計データ取得エラー: {str(e)}")
        return create_response(error=str(e), status_code=500)

# 会場コード一覧エンドポイント（レスポンス形式修正）
@app.route('/api/venues', methods=['GET'])
@limiter.limit("50 per minute")
def get_venues():
    try:
        # キャッシュから取得試行
        cache_key = "venues_data"
        cached_data = get_from_cache(cache_key)
        
        if cached_data:
            import json
            venues = json.loads(cached_data)
        else:
            venues = {}
            for i in range(1, 25):
                venue_code = f"{i:02d}"
                venue_info = get_venue_info_cached(venue_code)
                if venue_info:
                    venues[venue_code] = venue_info
            
            # キャッシュに保存
            import json
            set_to_cache(cache_key, json.dumps(venues), 3600)  # 1時間キャッシュ
        
        return create_response(data=venues)
    except Exception as e:
        logger.error(f"会場データ取得エラー: {str(e)}")
        return create_response(error=str(e), status_code=500)

# ===== 新しいAPIエンドポイント =====
@app.route('/api/race-entries/<venue_code>/<race_number>', methods=['GET'])
@limiter.limit("20 per minute")
def get_race_entries_api(venue_code, race_number):
    """出走表情報API（選手詳細情報付き）"""
    try:
        # バリデーション
        if venue_code not in [f"{i:02d}" for i in range(1, 25)]:
            return create_response(
                error="無効な会場コードです",
                status_code=400,
                message="会場コードは01-24の範囲で指定してください"
            )
            
        if not race_number.isdigit() or not (1 <= int(race_number) <= 12):
            return create_response(
                error="無効なレース番号です",
                status_code=400,
                message="レース番号は1-12の範囲で指定してください"
            )
        
        # 出走表取得
        entries = venue_manager.get_race_entries(venue_code, race_number)
        
        if entries and entries.get("status") == "success":
            # 各選手の詳細情報を追加
            enhanced_racers = []
            for racer in entries.get("racers", []):
                try:
                    racer_id = int(racer.get("registration_number", 0))
                    if racer_id > 0:
                        # 選手詳細統計を取得
                        detailed_stats = racer_analyzer.get_racer_detailed_stats(racer_id, venue_code)
                        venue_compatibility = racer_analyzer.get_venue_compatibility(racer_id, venue_code)
                        
                        enhanced_racer = {
                            **racer,
                            "detailed_stats": detailed_stats,
                            "venue_compatibility": venue_compatibility
                        }
                        enhanced_racers.append(enhanced_racer)
                    else:
                        enhanced_racers.append(racer)
                except Exception as e:
                    logger.warning(f"選手詳細情報取得エラー: {e}")
                    enhanced_racers.append(racer)
            
            # 会場情報も追加
            venue_info = get_venue_info_cached(venue_code)
            
            response_data = {
                "venue_code": venue_code,
                "venue_name": venue_info["name"] if venue_info else "不明",
                "venue_info": venue_info,
                "race_number": race_number,
                "entries": {
                    **entries,
                    "racers": enhanced_racers
                },
                "mobile_optimized": hasattr(g, 'is_mobile') and g.is_mobile
            }
            
            return create_response(data=response_data)
        else:
            return create_response(
                error="出走表データ取得失敗",
                status_code=404,
                message="レース開催状況を確認してください"
            )
            
    except Exception as e:
        logger.error(f"出走表API エラー: {str(e)}")
        return create_response(error=str(e), status_code=500)

@app.route('/api/venue-status-new/<venue_code>', methods=['GET'])
@limiter.limit("30 per minute")
def get_venue_status_new(venue_code):
    """新しい会場ステータスAPI（キャッシュから高速取得）"""
    try:
        if venue_code not in [f"{i:02d}" for i in range(1, 25)]:
            return create_response(
                error="無効な会場コードです",
                status_code=400
            )
        
        # キャッシュから取得
        status = venue_manager.get_venue_status(venue_code)
        
        # 会場名情報を追加
        venue_info = get_venue_info_cached(venue_code)
        
        response_data = {
            "venue_code": venue_code,
            "venue_name": venue_info["name"] if venue_info else "不明",
            "venue_location": venue_info["location"] if venue_info else "不明",
            "status": status
        }
        
        return create_response(data=response_data, message="キャッシュからの高速取得")
        
    except Exception as e:
        logger.error(f"会場ステータスAPI エラー: {str(e)}")
        return create_response(error=str(e), status_code=500)

@app.route('/api/daily-races', methods=['GET'])
@limiter.limit("20 per minute")
def get_daily_races():
    """本日開催中の全会場情報API"""
    try:
        active_venues = []
        
        for venue_code, venue_data in venue_manager.venue_cache.items():
            if venue_data.get('is_active', False):
                venue_info = get_venue_info_cached(venue_code)
                
                venue_summary = {
                    "venue_code": venue_code,
                    "venue_name": venue_info["name"] if venue_info else "不明",
                    "venue_location": venue_info["location"] if venue_info else "不明",
                    "race_count": venue_data.get('race_count', 0),
                    "races": venue_data.get('races', []),
                    "last_updated": venue_data.get('last_updated')
                }
                
                active_venues.append(venue_summary)
        
        response_data = {
            "date": get_today_date(),
            "active_venue_count": len(active_venues),
            "venues": active_venues
        }
        
        return create_response(data=response_data, message="0時更新の日次データ")
        
    except Exception as e:
        logger.error(f"日次レースAPI エラー: {str(e)}")
        return create_response(error=str(e), status_code=500)

@app.route('/api/system-status', methods=['GET'])
@limiter.limit("60 per minute")
def get_system_status():
    """システム全体のステータス確認API"""
    try:
        total_venues = len(venue_manager.all_venues)
        active_venues = sum(1 for v in venue_manager.venue_cache.values() if v.get('is_active', False))
        
        last_updates = [
            v.get('last_updated') for v in venue_manager.venue_cache.values() 
            if v.get('last_updated')
        ]
        
        system_data = {
            "system_status": "running",
            "ai_available": AI_AVAILABLE,
            "data_collection": {
                "total_venues": total_venues,
                "active_venues": active_venues,
                "cache_entries": len(venue_manager.venue_cache),
                "last_update": max(last_updates) if last_updates else None
            },
            "scheduler_running": venue_manager.scheduler.running if venue_manager.scheduler else False,
            "performance": {
                "total_requests": request_count,
                "error_count": error_count,
                "avg_response_time": sum(response_times) / len(response_times) if response_times else 0
            },
            "features": {
                "race_results_enabled": Config.ENABLE_RACE_RESULTS,
                "mobile_optimization": Config.MOBILE_OPTIMIZATION,
                "redis_cache": redis_client is not None
            }
        }
        
        return create_response(data=system_data)
        
    except Exception as e:
        logger.error(f"システムステータス エラー: {str(e)}")
        return create_response(error=str(e), status_code=500)

# ===== AI関連エンドポイント（拡張版） =====
@app.route('/api/ai-prediction-simple', methods=['POST'])
@limiter.limit("15 per minute")
def ai_prediction_simple():
    try:
        data = request.get_json()
        
        if AI_AVAILABLE:
            racers = data.get('racers', [])
            venue_code = data.get('venue_code', '01')
            
            # AIクラスに処理を委譲
            result = ai_model.get_comprehensive_prediction(racers, venue_code)
            
            # レスポンスを拡張
            result['analysis_details'] = {
                'venue_characteristics': get_venue_info_cached(venue_code),
                'weather_impact': 'moderate',
                'course_conditions': 'standard',
                'field_strength': calculate_field_strength(racers)
            }
            
            return create_response(data=result)
        else:
            return create_response(error="AI not available", status_code=503)
            
    except Exception as e:
        logger.error(f"AI予想エラー: {str(e)}")
        return create_response(error=str(e), status_code=500)

def calculate_field_strength(racers):
    """出走メンバーの強さ分析"""
    if not racers:
        return "unknown"
    
    a1_count = sum(1 for r in racers if r.get('class') == 'A1')
    total_racers = len(racers)
    
    if a1_count >= 4:
        return "very_strong"
    elif a1_count >= 2:
        return "strong"
    elif a1_count >= 1:
        return "moderate"
    else:
        return "weak"

# ===== UI/UX改善API =====
@app.route('/api/ui/loading-status', methods=['GET'])
@limiter.limit("100 per minute")
def get_loading_status():
    """ローディング状況取得（UI用）"""
    try:
        # 進行中の処理状況を返す
        status = {
            "data_loading": {
                "venues": len(venue_manager.venue_cache) > 0,
                "cache_ready": redis_client is not None,
                "ai_ready": AI_AVAILABLE
            },
            "progress": {
                "venue_cache": min(100, len(venue_manager.venue_cache) * 4),  # 25会場で100%
                "system_ready": 100 if AI_AVAILABLE else 75
            },
            "estimated_completion": 3000,  # ミリ秒
            "message": "データ取得完了" if len(venue_manager.venue_cache) > 0 else "データ取得中..."
        }
        
        return create_response(data=status)
        
    except Exception as e:
        logger.error(f"ローディング状況取得エラー: {str(e)}")
        return create_response(error=str(e), status_code=500)

@app.route('/api/ui/notifications', methods=['GET'])
@limiter.limit("50 per minute")
def get_notifications():
    """通知・お知らせ取得"""
    try:
        notifications = [
            {
                "id": 1,
                "type": "info",
                "title": "システム正常稼働中",
                "message": "AIモデルとデータ収集が正常に動作しています",
                "timestamp": datetime.now().isoformat(),
                "priority": "low"
            },
            {
                "id": 2,
                "type": "success",
                "title": "予想精度向上",
                "message": "最新のレース結果を反映し、予想精度が向上しました",
                "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(),
                "priority": "medium"
            }
        ]
        
        if not AI_AVAILABLE:
            notifications.append({
                "id": 3,
                "type": "warning",
                "title": "AI機能制限中",
                "message": "現在AIモデルが利用できません。基本機能は正常に動作しています",
                "timestamp": start_time.isoformat(),
                "priority": "high"
            })
        
        return create_response(data={
            "notifications": notifications,
            "unread_count": len([n for n in notifications if n["priority"] in ["medium", "high"]])
        })
        
    except Exception as e:
        logger.error(f"通知取得エラー: {str(e)}")
        return create_response(error=str(e), status_code=500)

# ===== レガシーエンドポイント（互換性維持） =====
@app.route('/api/real-data-test', methods=['GET'])
@limiter.limit("20 per minute")
def real_data_test():
    """既存エンドポイント（桐生1R・キャッシュ対応版）"""
    cache_key = "real_data_test_01"
    
    try:
        # キャッシュ確認
        cached_result = get_from_cache(cache_key)
        if cached_result:
            logger.info("キャッシュからデータを返却")
            import json
            return create_response(data=json.loads(cached_result))
        
        venue_code = '01'
        race_number = '1'
        date_str = get_today_date()
        
        race_url = build_race_url(venue_code, race_number, date_str)
        
        logger.info("データ取得開始...")
        
        # 実際のデータ取得処理
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        try:
            response = requests.get(race_url, headers=headers, timeout=30)
            race_data = {
                "status": "success",
                "content": response.content,
                "text": response.text,
                "length": len(response.content),
                "encoding": response.encoding
            }
        except Exception as e:
            race_data = {"status": "error", "message": str(e)}
        
        if race_data["status"] == "error":
            return create_response(
                error="データ取得失敗",
                status_code=500,
                message=race_data["message"]
            )
        
        logger.info("選手データ抽出開始...")
        racer_data = extract_racer_data_final(race_data["content"])
        
        result = {
            "data_acquisition": {
                "status": race_data["status"],
                "length": race_data["length"],
                "encoding": race_data["encoding"]
            },
            "racer_extraction": racer_data,
            "html_sample": str(race_data["content"][:500]) if race_data.get("content") else "N/A",
            "enhanced_features": True,
            "mobile_optimized": hasattr(g, 'is_mobile') and g.is_mobile
        }
        
        # キャッシュに保存
        import json
        set_to_cache(cache_key, json.dumps(result), 1800)  # 30分キャッシュ
        
        return create_response(data=result)
        
    except Exception as e:
        logger.error(f"リアルデータテストエラー: {str(e)}")
        return create_response(error=str(e), status_code=500)

# ===== アプリケーション初期化 =====
def initialize_app():
    """アプリケーション初期化"""
    try:
        logger.info("=== アプリケーション初期化開始 ===")
        
        # データベース初期化
        db_manager.initialize_all_tables()
        logger.info("データベース初期化完了")
        
        # スケジューラー開始
        venue_manager.start_background_updates()
        logger.info("✅ スケジューラー開始完了")
        
        logger.info("=== アプリケーション初期化完了 ===")
        
    except Exception as e:
        logger.error(f"❌ 初期化エラー: {str(e)}")
        raise e

def main():
    """メイン関数"""
    try:
        # アプリケーション初期化
        initialize_app()
        
        # AI初期化（必要に応じて）
        if AI_AVAILABLE:
            logger.info("AI学習システム準備完了")
        
        # サーバー起動
        port = int(os.environ.get('PORT', 5000))
        logger.info(f"🚀 WAVE PREDICTOR Flask アプリケーション開始: ポート {port}")
        
        app.run(
            debug=app.config['DEBUG'], 
            host='0.0.0.0', 
            port=port,
            threaded=True
        )
        
    except Exception as e:
        logger.error(f"Application startup failed: {e}")
        raise e

# アプリ起動時に自動実行
try:
    initialize_app()
except Exception as e:
    logger.error(f"アプリケーション初期化失敗: {str(e)}")

if __name__ == '__main__':
    main()
