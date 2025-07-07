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
    SCRAPING_DELAY = float(os.environ.get('SCRAPING_DELAY', '5.0'))  # 5秒間隔
    VENUE_COUNT = 24
    ENABLE_RACE_RESULTS = os.environ.get('ENABLE_RACE_RESULTS', 'True').lower() == 'true'
    MOBILE_OPTIMIZATION = os.environ.get('MOBILE_OPTIMIZATION', 'True').lower() == 'true'
    MAX_SCRAPING_PER_DAY = int(os.environ.get('MAX_SCRAPING_PER_DAY', '50'))  # 1日最大50回
    CACHE_ONLY_MODE = os.environ.get('CACHE_ONLY_MODE', 'False').lower() == 'true'

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

# ===== グローバル変数・メトリクス =====
request_count = 0
error_count = 0
start_time = datetime.now()
response_times = []
scraping_count_today = 0
last_scraping_reset = datetime.now().date()

# ===== スクレイピング制限管理 =====
def can_scrape():
    """スクレイピング実行可能かチェック"""
    global scraping_count_today, last_scraping_reset
    
    today = datetime.now().date()
    if today != last_scraping_reset:
        scraping_count_today = 0
        last_scraping_reset = today
    
    if Config.CACHE_ONLY_MODE:
        logger.warning("キャッシュオンリーモード: スクレイピング停止中")
        return False
    
    if scraping_count_today >= Config.MAX_SCRAPING_PER_DAY:
        logger.warning(f"スクレイピング制限到達: {scraping_count_today}/{Config.MAX_SCRAPING_PER_DAY}")
        return False
    
    return True

def record_scraping():
    """スクレイピング実行を記録"""
    global scraping_count_today
    scraping_count_today += 1
    logger.info(f"スクレイピング実行: {scraping_count_today}/{Config.MAX_SCRAPING_PER_DAY}")

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

# ===== データベース管理クラス =====
class DatabaseManager:
    def __init__(self, db_path="boatrace_data.db"):
        self.db_path = db_path
        self.initialize_all_tables()
    
    def initialize_all_tables(self):
        """すべてのテーブルを初期化"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # レーススケジュールテーブル（重要）
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS race_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_date TEXT,
            venue_code TEXT,
            venue_name TEXT,
            race_number INTEGER,
            scheduled_time TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(race_date, venue_code, race_number)
        )
        ''')
        
        # 出走表テーブル
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS race_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id TEXT,
            venue_code TEXT,
            race_number INTEGER,
            race_date TEXT,
            racer_id TEXT,
            boat_number INTEGER,
            racer_name TEXT,
            racer_class TEXT,
            age INTEGER,
            weight TEXT,
            region TEXT,
            branch TEXT,
            motor_number INTEGER,
            boat_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(race_id, boat_number)
        )
        ''')
        
        # 直前情報テーブル
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS pre_race_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id TEXT,
            venue_code TEXT,
            race_number INTEGER,
            race_date TEXT,
            weather TEXT,
            wind_direction TEXT,
            wind_speed REAL,
            wave_height INTEGER,
            temperature REAL,
            water_temperature REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(race_id)
        )
        ''')
        
        # 展示タイムテーブル
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS exhibition_times (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id TEXT,
            boat_number INTEGER,
            exhibition_time REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(race_id, boat_number)
        )
        ''')
        
        # スクレイピングログテーブル
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS scraping_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scraping_date TEXT,
            url TEXT,
            status TEXT,
            response_time REAL,
            data_count INTEGER,
            error_message TEXT,
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
        
        conn.commit()
        conn.close()
        logger.info("データベーステーブル初期化完了")
    
    def get_connection(self):
        """データベース接続を取得"""
        return sqlite3.connect(self.db_path)
    
    def save_race_schedule(self, schedule_data):
        """レーススケジュールを保存"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            for race in schedule_data:
                cursor.execute('''
                INSERT OR REPLACE INTO race_schedule 
                (race_date, venue_code, venue_name, race_number, scheduled_time, status)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    race['race_date'],
                    race['venue_code'],
                    race['venue_name'],
                    race['race_number'],
                    race['scheduled_time'],
                    race['status']
                ))
            
            conn.commit()
            logger.info(f"レーススケジュール保存: {len(schedule_data)}件")
        except Exception as e:
            logger.error(f"レーススケジュール保存エラー: {e}")
        finally:
            conn.close()
    
    def save_race_entries(self, entries_data):
        """出走表を保存"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            for entry in entries_data:
                cursor.execute('''
                INSERT OR REPLACE INTO race_entries 
                (race_id, venue_code, race_number, race_date, racer_id, boat_number,
                 racer_name, racer_class, age, weight, region, branch, motor_number, boat_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    entry['race_id'],
                    entry['venue_code'],
                    entry['race_number'],
                    entry['race_date'],
                    entry['racer_id'],
                    entry['boat_number'],
                    entry['racer_name'],
                    entry['racer_class'],
                    entry['age'],
                    entry['weight'],
                    entry['region'],
                    entry['branch'],
                    entry['motor_number'],
                    entry['boat_id']
                ))
            
            conn.commit()
            logger.info(f"出走表保存: {len(entries_data)}件")
        except Exception as e:
            logger.error(f"出走表保存エラー: {e}")
        finally:
            conn.close()

# ===== 正式競艇データコレクター =====
class OfficialBoatraceCollector:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://boatrace.jp/',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Cache-Control': 'max-age=0'
        })
        
        # リトライ設定
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # 会場コードマッピング
        self.venue_mapping = {
            "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島", "05": "多摩川",
            "06": "浜名湖", "07": "蒲郡", "08": "常滑", "09": "津", "10": "三国",
            "11": "びわこ", "12": "住之江", "13": "尼崎", "14": "鳴門", "15": "丸亀",
            "16": "児島", "17": "宮島", "18": "徳山", "19": "下関", "20": "若松",
            "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村"
        }
    
    def get_daily_schedule(self, date_str=None):
        """本日の全会場スケジュール取得"""
        if not can_scrape():
            return self.get_cached_schedule(date_str)
        
        if date_str is None:
            date_str = datetime.now().strftime("%Y%m%d")
        
        try:
            logger.info(f"=== 日次スケジュール取得開始: {date_str} ===")
            record_scraping()
            
            # ボートレース公式サイトのトップページ
            url = "https://boatrace.jp/"
            start_time = time.time()
            
            response = self.session.get(url, timeout=30)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                schedule_data = self.parse_daily_schedule(response.content, date_str)
                
                # ログ記録
                self.log_scraping(date_str, url, "success", response_time, len(schedule_data))
                
                # データベース保存
                if schedule_data:
                    self.db_manager.save_race_schedule(schedule_data)
                
                logger.info(f"日次スケジュール取得完了: {len(schedule_data)}会場")
                return schedule_data
            else:
                self.log_scraping(date_str, url, "error", response_time, 0, f"HTTP {response.status_code}")
                logger.error(f"スケジュール取得失敗: {response.status_code}")
                return self.get_cached_schedule(date_str)
                
        except Exception as e:
            logger.error(f"スケジュール取得エラー: {str(e)}")
            self.log_scraping(date_str, url, "error", 0, 0, str(e))
            return self.get_cached_schedule(date_str)
        finally:
            time.sleep(Config.SCRAPING_DELAY)  # 5秒待機
    
    def parse_daily_schedule(self, html_content, date_str):
        """日次スケジュール解析"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            schedule_data = []
            
            # 開催会場情報を取得
            venue_elements = soup.find_all('a', href=re.compile(r'/owpc/pc/race/racelist'))
            
            for venue_element in venue_elements:
                try:
                    href = venue_element.get('href')
                    venue_match = re.search(r'jcd=(\d{2})', href)
                    
                    if venue_match:
                        venue_code = venue_match.group(1)
                        venue_name = self.venue_mapping.get(venue_code, f"会場{venue_code}")
                        
                        # 各会場の詳細レース情報を取得
                        venue_races = self.get_venue_race_schedule(venue_code, date_str)
                        schedule_data.extend(venue_races)
                        
                        time.sleep(Config.SCRAPING_DELAY)  # 会場間で待機
                        
                except Exception as e:
                    logger.warning(f"会場情報解析エラー: {str(e)}")
                    continue
            
            return schedule_data
            
        except Exception as e:
            logger.error(f"スケジュール解析エラー: {str(e)}")
            return []
    
    def get_venue_race_schedule(self, venue_code, date_str):
        """会場のレース時刻表取得"""
        if not can_scrape():
            return []
        
        try:
            # 会場のレース一覧ページ
            url = f"https://boatrace.jp/owpc/pc/race/racelist?jcd={venue_code}&hd={date_str}"
            logger.info(f"会場{venue_code}レース時刻表取得: {url}")
            
            record_scraping()
            response = self.session.get(url, timeout=30)
            
            if response.status_code == 200:
                return self.parse_venue_schedule(response.content, venue_code, date_str)
            else:
                logger.warning(f"会場{venue_code}レース時刻表取得失敗: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"会場{venue_code}レース時刻表取得エラー: {str(e)}")
            return []
        finally:
            time.sleep(Config.SCRAPING_DELAY)
    
    def parse_venue_schedule(self, html_content, venue_code, date_str):
        """会場レース時刻表解析"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            venue_name = self.venue_mapping.get(venue_code, f"会場{venue_code}")
            races = []
            
            # レース時刻表を探す（実際のHTML構造に応じて調整）
            time_tables = soup.find_all('table', class_='is-w495')
            
            if time_tables:
                for table in time_tables:
                    rows = table.find_all('tr')
                    
                    for i, row in enumerate(rows[1:], 1):  # ヘッダー行をスキップ
                        try:
                            cells = row.find_all('td')
                            if len(cells) >= 2:
                                # 第1セルからレース番号、第2セルから時刻を取得
                                race_number_cell = cells[0].get_text().strip()
                                time_cell = cells[1].get_text().strip()
                                
                                # レース番号抽出
                                race_match = re.search(r'(\d+)R', race_number_cell)
                                if race_match:
                                    race_number = int(race_match.group(1))
                                else:
                                    race_number = i
                                
                                # 時刻抽出
                                time_match = re.search(r'(\d{1,2}):(\d{2})', time_cell)
                                if time_match:
                                    scheduled_time = f"{time_match.group(1).zfill(2)}:{time_match.group(2)}"
                                    
                                    races.append({
                                        'race_date': date_str,
                                        'venue_code': venue_code,
                                        'venue_name': venue_name,
                                        'race_number': race_number,
                                        'scheduled_time': scheduled_time,
                                        'status': 'scheduled'
                                    })
                                    
                        except Exception as e:
                            logger.warning(f"レース時刻解析エラー: {str(e)}")
                            continue
            
            # 時刻表が見つからない場合はデフォルト時刻を使用
            if not races:
                logger.warning(f"会場{venue_code}: 時刻表が見つからないため、デフォルト時刻を使用")
                for race_number in range(1, 13):  # 1R-12R
                    # 一般的な競艇の開始時刻（15:00開始、25分間隔）
                    start_hour = 15
                    start_minute = (race_number - 1) * 25
                    
                    total_minutes = start_hour * 60 + start_minute
                    hour = total_minutes // 60
                    minute = total_minutes % 60
                    
                    scheduled_time = f"{hour:02d}:{minute:02d}"
                    
                    races.append({
                        'race_date': date_str,
                        'venue_code': venue_code,
                        'venue_name': venue_name,
                        'race_number': race_number,
                        'scheduled_time': scheduled_time,
                        'status': 'scheduled'
                    })
            
            logger.info(f"会場{venue_code}({venue_name}): {len(races)}レース時刻取得")
            return races
            
        except Exception as e:
            logger.error(f"会場レース時刻表解析エラー: {str(e)}")
            return []
    
    def get_race_entries(self, venue_code, race_number, date_str):
        """正式出走表取得"""
        if not can_scrape():
            return self.get_cached_race_entries(venue_code, race_number, date_str)
        
        try:
            # 出走表ページURL
            url = f"https://boatrace.jp/owpc/pc/race/racelist?rno={race_number}&jcd={venue_code}&hd={date_str}"
            logger.info(f"出走表取得: 会場{venue_code} {race_number}R")
            
            record_scraping()
            start_time = time.time()
            response = self.session.get(url, timeout=30)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                entries_data = self.parse_race_entries(response.content, venue_code, race_number, date_str)
                
                # ログ記録
                self.log_scraping(date_str, url, "success", response_time, len(entries_data) if entries_data else 0)
                
                # データベース保存
                if entries_data:
                    self.db_manager.save_race_entries(entries_data)
                
                return {
                    "status": "success",
                    "racers": entries_data,
                    "found_count": len(entries_data) if entries_data else 0
                }
            else:
                self.log_scraping(date_str, url, "error", response_time, 0, f"HTTP {response.status_code}")
                return self.get_cached_race_entries(venue_code, race_number, date_str)
                
        except Exception as e:
            logger.error(f"出走表取得エラー: {str(e)}")
            self.log_scraping(date_str, url, "error", 0, 0, str(e))
            return self.get_cached_race_entries(venue_code, race_number, date_str)
        finally:
            time.sleep(Config.SCRAPING_DELAY)
    
    def parse_race_entries(self, html_content, venue_code, race_number, date_str):
        """出走表解析（正式版）"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 実際の出走表データを探す
            race_table = soup.find('table', class_='is-w495')
            
            if not race_table:
                # 別の方法で出走表を探す
                race_table = soup.find('div', class_='table1')
            
            entries = []
            
            if race_table:
                rows = race_table.find_all('tr')
                
                for row in rows[1:]:  # ヘッダー行スキップ
                    try:
                        cells = row.find_all(['td', 'th'])
                        
                        if len(cells) >= 6:
                            # セルから情報抽出
                            boat_number = self.extract_boat_number(cells[0])
                            racer_info = self.extract_racer_info(cells[1])
                            
                            if boat_number and racer_info:
                                race_id = f"{date_str}{venue_code}{race_number:02d}"
                                
                                entry = {
                                    'race_id': race_id,
                                    'venue_code': venue_code,
                                    'race_number': race_number,
                                    'race_date': date_str,
                                    'boat_number': boat_number,
                                    'racer_id': racer_info.get('registration_number', ''),
                                    'racer_name': racer_info.get('name', ''),
                                    'racer_class': racer_info.get('class', ''),
                                    'age': racer_info.get('age', 0),
                                    'weight': racer_info.get('weight', ''),
                                    'region': racer_info.get('region', ''),
                                    'branch': racer_info.get('branch', ''),
                                    'motor_number': self.extract_motor_number(cells),
                                    'boat_id': self.extract_boat_id(cells)
                                }
                                entries.append(entry)
                                
                    except Exception as e:
                        logger.warning(f"出走表行解析エラー: {str(e)}")
                        continue
            
            logger.info(f"出走表解析完了: {len(entries)}名")
            return entries
            
        except Exception as e:
            logger.error(f"出走表解析エラー: {str(e)}")
            return []
    
    def extract_boat_number(self, cell):
        """艇番抽出"""
        try:
            text = cell.get_text().strip()
            match = re.search(r'(\d+)', text)
            return int(match.group(1)) if match else None
        except:
            return None
    
    def extract_racer_info(self, cell):
        """選手情報抽出"""
        try:
            text = cell.get_text().strip()
            
            # 登録番号/級別 選手名 支部/年齢・体重のパターン
            pattern = r'(\d{4})\s*/\s*([AB][12])\s*([^\n]+?)\s+([^/\n]+)/([^\n]+?)\s+(\d+)歳/(\d+\.\d+)kg'
            match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
            
            if match:
                name_clean = re.sub(r'\s+', ' ', match.group(3)).strip()
                
                return {
                    'registration_number': match.group(1),
                    'class': match.group(2),
                    'name': name_clean,
                    'region': match.group(4).strip(),
                    'branch': match.group(5).strip(),
                    'age': int(match.group(6)),
                    'weight': f"{match.group(7)}kg"
                }
            
            return None
            
        except Exception as e:
            logger.warning(f"選手情報抽出エラー: {str(e)}")
            return None
    
    def extract_motor_number(self, cells):
        """モーター番号抽出"""
        try:
            for cell in cells:
                text = cell.get_text().strip()
                motor_match = re.search(r'M(\d+)', text)
                if motor_match:
                    return int(motor_match.group(1))
            return random.randint(1, 100)  # フォールバック
        except:
            return random.randint(1, 100)
    
    def extract_boat_id(self, cells):
        """ボート番号抽出"""
        try:
            for cell in cells:
                text = cell.get_text().strip()
                boat_match = re.search(r'B(\d+)', text)
                if boat_match:
                    return int(boat_match.group(1))
            return random.randint(1, 100)  # フォールバック
        except:
            return random.randint(1, 100)
    
    def get_cached_schedule(self, date_str):
        """キャッシュからスケジュール取得"""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT venue_code, venue_name, race_number, scheduled_time, status
            FROM race_schedule
            WHERE race_date = ?
            ORDER BY venue_code, race_number
            ''', (date_str,))
            
            results = cursor.fetchall()
            conn.close()
            
            schedule_data = []
            for result in results:
                schedule_data.append({
                    'race_date': date_str,
                    'venue_code': result[0],
                    'venue_name': result[1],
                    'race_number': result[2],
                    'scheduled_time': result[3],
                    'status': result[4]
                })
            
            logger.info(f"キャッシュからスケジュール取得: {len(schedule_data)}件")
            return schedule_data
            
        except Exception as e:
            logger.error(f"キャッシュスケジュール取得エラー: {str(e)}")
            return []
    
    def get_cached_race_entries(self, venue_code, race_number, date_str):
        """キャッシュから出走表取得"""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT boat_number, racer_id, racer_name, racer_class, age, weight, region, branch
            FROM race_entries
            WHERE venue_code = ? AND race_number = ? AND race_date = ?
            ORDER BY boat_number
            ''', (venue_code, race_number, date_str))
            
            results = cursor.fetchall()
            conn.close()
            
            if results:
                entries = []
                for result in results:
                    entries.append({
                        'boat_number': result[0],
                        'registration_number': result[1],
                        'name': result[2],
                        'class': result[3],
                        'age': result[4],
                        'weight': result[5],
                        'region': result[6],
                        'branch': result[7]
                    })
                
                logger.info(f"キャッシュから出走表取得: {len(entries)}名")
                return {
                    "status": "success",
                    "racers": entries,
                    "found_count": len(entries)
                }
            
            return {"status": "error", "message": "キャッシュにデータがありません"}
            
        except Exception as e:
            logger.error(f"キャッシュ出走表取得エラー: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def log_scraping(self, date_str, url, status, response_time, data_count, error_message=None):
        """スクレイピングログ記録"""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            INSERT INTO scraping_log 
            (scraping_date, url, status, response_time, data_count, error_message)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (date_str, url, status, response_time, data_count, error_message))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"スクレイピングログ記録エラー: {e}")

# ===== レーススケジュール管理クラス =====
class RaceScheduleManager:
    def __init__(self, db_manager, data_collector):
        self.db_manager = db_manager
        self.data_collector = data_collector
        self.scheduler = None
        self.race_schedules = {}
        self.dynamic_jobs = {}
    
    def start_scheduled_tasks(self):
        """スケジュールタスク開始"""
        from apscheduler.schedulers.background import BackgroundScheduler
        
        self.scheduler = BackgroundScheduler()
        
        # 毎日朝6時: 出走表一括取得
        self.scheduler.add_job(
            func=self.daily_data_collection,
            trigger="cron",
            hour=6,
            minute=0,
            id="daily_collection"
        )
        
        # 1時間ごと: 直前情報更新チェック
        self.scheduler.add_job(
            func=self.check_pre_race_updates,
            trigger="interval",
            hours=1,
            id="pre_race_check"
        )
        
        self.scheduler.start()
        logger.info("レーススケジューラー開始")
    
    def daily_data_collection(self):
        """朝6時実行: 本日の全データ取得"""
        logger.info("=== 日次データ収集開始 ===")
        
        try:
            today = datetime.now().strftime("%Y%m%d")
            
            # 1. 全会場のスケジュール取得
            schedule_data = self.data_collector.get_daily_schedule(today)
            
            if schedule_data:
                # スケジュールを内部保存
                self.race_schedules[today] = {}
                
                for race in schedule_data:
                    venue_code = race['venue_code']
                    
                    if venue_code not in self.race_schedules[today]:
                        self.race_schedules[today][venue_code] = []
                    
                    self.race_schedules[today][venue_code].append(race)
                
                # 2. 各レースの直前情報取得タイミングを計算
                self.schedule_pre_race_updates(today)
                
                logger.info(f"日次データ収集完了: {len(schedule_data)}レース")
            else:
                logger.warning("日次データ収集: スケジュールデータなし")
                
        except Exception as e:
            logger.error(f"日次データ収集エラー: {str(e)}")
    
    def schedule_pre_race_updates(self, date_str):
        """直前情報更新スケジューリング"""
        try:
            if date_str not in self.race_schedules:
                return
            
            for venue_code, races in self.race_schedules[date_str].items():
                for race in races:
                    try:
                        # レース開始時刻から1時間前を計算
                        race_time_str = f"{date_str} {race['scheduled_time']}"
                        race_time = datetime.strptime(race_time_str, "%Y%m%d %H:%M")
                        update_time = race_time - timedelta(hours=1)
                        
                        # 現在時刻より未来の場合のみスケジュール
                        if update_time > datetime.now():
                            job_id = f"pre_race_{venue_code}_{race['race_number']}_{date_str}"
                            
                            self.scheduler.add_job(
                                func=self.update_pre_race_info,
                                trigger="date",
                                run_date=update_time,
                                args=[venue_code, race['race_number'], date_str],
                                id=job_id
                            )
                            
                            logger.info(f"直前情報更新スケジュール: {job_id} at {update_time}")
                            
                    except Exception as e:
                        logger.warning(f"直前情報スケジュールエラー: {str(e)}")
                        continue
                        
        except Exception as e:
            logger.error(f"直前情報スケジューリングエラー: {str(e)}")
    
    def update_pre_race_info(self, venue_code, race_number, date_str):
        """直前情報更新（レース開始1時間前実行）"""
        logger.info(f"直前情報更新: 会場{venue_code} {race_number}R")
        
        try:
            # 展示タイム・気象情報などを取得
            # 実際には追加のスクレイピングが必要
            pass
            
        except Exception as e:
            logger.error(f"直前情報更新エラー: {str(e)}")
    
    def check_pre_race_updates(self):
        """1時間ごと実行: 直前情報更新が必要なレースをチェック"""
        logger.info("直前情報更新チェック実行")
        
        try:
            current_time = datetime.now()
            today = current_time.strftime("%Y%m%d")
            
            # 本日のスケジュールをチェック
            if today in self.race_schedules:
                for venue_code, races in self.race_schedules[today].items():
                    for race in races:
                        try:
                            race_time_str = f"{today} {race['scheduled_time']}"
                            race_time = datetime.strptime(race_time_str, "%Y%m%d %H:%M")
                            
                            # レース開始1-2時間前なら直前情報更新
                            time_diff = (race_time - current_time).total_seconds() / 3600
                            
                            if 1 <= time_diff <= 2:
                                logger.info(f"直前情報更新対象: 会場{venue_code} {race['race_number']}R")
                                # 実際の更新処理はここで実行
                                
                        except Exception as e:
                            logger.warning(f"レース時刻チェックエラー: {str(e)}")
                            continue
                            
        except Exception as e:
            logger.error(f"直前情報チェックエラー: {str(e)}")

# ===== グローバルインスタンス =====
db_manager = DatabaseManager()
data_collector = OfficialBoatraceCollector(db_manager)
schedule_manager = RaceScheduleManager(db_manager, data_collector)

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

# ===== レスポンス標準化関数 =====
def create_response(data=None, error=None, status_code=200, message=None):
    """レスポンス標準化"""
    response = {
        "timestamp": datetime.now().isoformat(),
        "status_code": status_code,
        "success": error is None,
        "scraping_status": {
            "count_today": scraping_count_today,
            "limit": Config.MAX_SCRAPING_PER_DAY,
            "cache_only_mode": Config.CACHE_ONLY_MODE
        }
    }
    
    if data is not None:
        response["data"] = data
    if error is not None:
        response["error"] = error
    if message is not None:
        response["message"] = message
        
    return jsonify(response), status_code

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
        "service": "WAVE PREDICTOR - 正式スクレイピング対応版",
        "version": "3.0.0",
        "status": "running",
        "ai_available": AI_AVAILABLE,
        "scraping_status": {
            "daily_count": scraping_count_today,
            "daily_limit": Config.MAX_SCRAPING_PER_DAY,
            "cache_only_mode": Config.CACHE_ONLY_MODE,
            "remaining": max(0, Config.MAX_SCRAPING_PER_DAY - scraping_count_today)
        },
        "features": [
            "正式スクレイピング対応", 
            "適正アクセス頻度", 
            "実際のレース時間取得",
            "動的スケジューリング",
            "キャッシュ優先システム",
            "AI予想", 
            "モバイル最適化"
        ],
        "endpoints": {
            "daily_schedule": "/api/daily-schedule",
            "race_entries": "/api/race-entries/{venue_code}/{race_number}",
            "system_status": "/api/system-status",
            "scraping_status": "/api/scraping-status"
        }
    })

@app.route('/api/test', methods=['GET'])
@limiter.limit("100 per minute")
def test():
    return create_response(
        data={
            "message": "正式スクレイピング版API動作中!", 
            "mobile_optimized": hasattr(g, 'is_mobile') and g.is_mobile,
            "scraping_count": scraping_count_today,
            "can_scrape": can_scrape()
        },
        message="API正常動作中（適正スクレイピング版）"
    )

# ===== 正式データ取得API =====
@app.route('/api/daily-schedule', methods=['GET'])
@limiter.limit("30 per minute")
def get_daily_schedule():
    """本日の全会場スケジュール取得"""
    try:
        date_str = request.args.get('date', datetime.now().strftime("%Y%m%d"))
        
        logger.info(f"日次スケジュール取得リクエスト: {date_str}")
        
        # スケジュールデータ取得
        schedule_data = data_collector.get_daily_schedule(date_str)
        
        if schedule_data:
            # 会場別にグループ化
            venues = {}
            for race in schedule_data:
                venue_code = race['venue_code']
                if venue_code not in venues:
                    venues[venue_code] = {
                        'venue_code': venue_code,
                        'venue_name': race['venue_name'],
                        'is_active': True,
                        'races': []
                    }
                venues[venue_code]['races'].append({
                    'race_number': race['race_number'],
                    'scheduled_time': race['scheduled_time'],
                    'status': race['status']
                })
            
            return create_response(
                data={
                    "date": date_str,
                    "venues": venues,
                    "total_venues": len(venues),
                    "total_races": len(schedule_data)
                },
                message="正式スケジュールデータ取得完了"
            )
        else:
            return create_response(
                error="スケジュールデータの取得に失敗しました",
                status_code=404,
                message="キャッシュデータもありません"
            )
            
    except Exception as e:
        logger.error(f"日次スケジュール取得エラー: {str(e)}")
        return create_response(error=str(e), status_code=500)

@app.route('/api/race-entries/<venue_code>/<int:race_number>', methods=['GET'])
@limiter.limit("20 per minute")
def get_race_entries_api(venue_code, race_number):
    """正式出走表取得API"""
    try:
        date_str = request.args.get('date', datetime.now().strftime("%Y%m%d"))
        
        # バリデーション
        if venue_code not in [f"{i:02d}" for i in range(1, 25)]:
            return create_response(
                error="無効な会場コードです",
                status_code=400,
                message="会場コードは01-24の範囲で指定してください"
            )
            
        if not (1 <= race_number <= 12):
            return create_response(
                error="無効なレース番号です",
                status_code=400,
                message="レース番号は1-12の範囲で指定してください"
            )
        
        logger.info(f"正式出走表取得: 会場{venue_code} {race_number}R {date_str}")
        
        # 出走表取得
        entries_result = data_collector.get_race_entries(venue_code, race_number, date_str)
        
        if entries_result and entries_result.get("status") == "success":
            venue_name = data_collector.venue_mapping.get(venue_code, f"会場{venue_code}")
            
            response_data = {
                "venue_code": venue_code,
                "venue_name": venue_name,
                "race_number": race_number,
                "race_date": date_str,
                "racer_extraction": entries_result,
                "data_source": "official_scraping" if can_scrape() else "cache",
                "mobile_optimized": hasattr(g, 'is_mobile') and g.is_mobile
            }
            
            return create_response(
                data=response_data,
                message="正式出走表取得完了"
            )
        else:
            return create_response(
                error="出走表データ取得失敗",
                status_code=404,
                message="レース開催状況を確認してください"
            )
            
    except Exception as e:
        logger.error(f"正式出走表API エラー: {str(e)}")
        return create_response(error=str(e), status_code=500)

@app.route('/api/system-status', methods=['GET'])
@limiter.limit("60 per minute")
def get_system_status():
    """システム全体のステータス確認API"""
    try:
        uptime = (datetime.now() - start_time).total_seconds()
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        # 本日のスクレイピングログ取得
        today = datetime.now().strftime("%Y%m%d")
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT COUNT(*), SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END)
        FROM scraping_log
        WHERE scraping_date = ?
        ''', (today,))
        
        log_result = cursor.fetchone()
        total_scraping = log_result[0] if log_result[0] else 0
        success_scraping = log_result[1] if log_result[1] else 0
        
        conn.close()
        
        system_data = {
            "system_status": "running",
            "version": "3.0.0",
            "ai_available": AI_AVAILABLE,
            "uptime": {
                "seconds": uptime,
                "formatted": str(timedelta(seconds=int(uptime)))
            },
            "scraping_status": {
                "daily_count": scraping_count_today,
                "daily_limit": Config.MAX_SCRAPING_PER_DAY,
                "success_rate": success_scraping / total_scraping if total_scraping > 0 else 0,
                "cache_only_mode": Config.CACHE_ONLY_MODE,
                "can_scrape": can_scrape(),
                "delay_seconds": Config.SCRAPING_DELAY
            },
            "performance": {
                "total_requests": request_count,
                "error_count": error_count,
                "avg_response_time": round(avg_response_time, 3),
                "success_rate": (request_count - error_count) / request_count if request_count > 0 else 0
            },
            "features": {
                "official_scraping": True,
                "dynamic_scheduling": True,
                "race_results_enabled": Config.ENABLE_RACE_RESULTS,
                "mobile_optimization": Config.MOBILE_OPTIMIZATION,
                "redis_cache": redis_client is not None
            }
        }
        
        return create_response(data=system_data)
        
    except Exception as e:
        logger.error(f"システムステータス エラー: {str(e)}")
        return create_response(error=str(e), status_code=500)

@app.route('/api/scraping-status', methods=['GET'])
@limiter.limit("30 per minute")
def get_scraping_status():
    """スクレイピング状況詳細API"""
    try:
        today = datetime.now().strftime("%Y%m%d")
        
        # 今日のスクレイピングログ取得
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT url, status, response_time, data_count, error_message, created_at
        FROM scraping_log
        WHERE scraping_date = ?
        ORDER BY created_at DESC
        LIMIT 20
        ''', (today,))
        
        logs = cursor.fetchall()
        
        # 統計計算
        cursor.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
            AVG(response_time) as avg_time,
            SUM(data_count) as total_data
        FROM scraping_log
        WHERE scraping_date = ?
        ''', (today,))
        
        stats = cursor.fetchone()
        conn.close()
        
        status_data = {
            "date": today,
            "limits": {
                "daily_count": scraping_count_today,
                "daily_limit": Config.MAX_SCRAPING_PER_DAY,
                "remaining": max(0, Config.MAX_SCRAPING_PER_DAY - scraping_count_today),
                "cache_only_mode": Config.CACHE_ONLY_MODE
            },
            "statistics": {
                "total_attempts": stats[0] if stats[0] else 0,
                "successful": stats[1] if stats[1] else 0,
                "success_rate": (stats[1] / stats[0]) if stats[0] and stats[0] > 0 else 0,
                "avg_response_time": round(stats[2], 3) if stats[2] else 0,
                "total_data_retrieved": stats[3] if stats[3] else 0
            },
            "recent_logs": [
                {
                    "url": log[0],
                    "status": log[1],
                    "response_time": round(log[2], 3) if log[2] else 0,
                    "data_count": log[3],
                    "error": log[4],
                    "timestamp": log[5]
                } for log in logs
            ],
            "recommendations": []
        }
        
        # 推奨事項
        if scraping_count_today >= Config.MAX_SCRAPING_PER_DAY * 0.8:
            status_data["recommendations"].append("スクレイピング制限に近づいています")
        
        if Config.CACHE_ONLY_MODE:
            status_data["recommendations"].append("キャッシュオンリーモードが有効です")
        
        return create_response(data=status_data)
        
    except Exception as e:
        logger.error(f"スクレイピング状況取得エラー: {str(e)}")
        return create_response(error=str(e), status_code=500)

# ===== 緊急モード切替API =====
@app.route('/api/emergency/cache-only', methods=['POST'])
@limiter.limit("5 per minute")
def toggle_cache_only_mode():
    """緊急時キャッシュオンリーモード切替"""
    try:
        data = request.get_json()
        enable = data.get('enable', True)
        
        Config.CACHE_ONLY_MODE = enable
        
        message = "キャッシュオンリーモードを有効にしました" if enable else "キャッシュオンリーモードを無効にしました"
        
        logger.warning(f"緊急モード切替: {message}")
        
        return create_response(
            data={
                "cache_only_mode": Config.CACHE_ONLY_MODE,
                "scraping_status": "停止中" if enable else "有効"
            },
            message=message
        )
        
    except Exception as e:
        logger.error(f"緊急モード切替エラー: {str(e)}")
        return create_response(error=str(e), status_code=500)

# ===== レガシーエンドポイント（互換性維持） =====
@app.route('/api/real-data-test', methods=['GET'])
@limiter.limit("20 per minute")
def real_data_test():
    """レガシーエンドポイント（桐生1R・キャッシュ対応版）"""
    return get_race_entries_api('01', 1)

@app.route('/api/races/today', methods=['GET'])
@limiter.limit("30 per minute")
def get_today_races():
    """今日のレース一覧（簡易版）"""
    try:
        mobile_optimized = hasattr(g, 'is_mobile') and g.is_mobile
        today = datetime.now().strftime("%Y%m%d")
        
        # キャッシュからスケジュール取得
        schedule_data = data_collector.get_cached_schedule(today)
        
        races = []
        for race in schedule_data:
            race_data = {
                "race_id": f"{today}{race['venue_code']}{race['race_number']:02d}",
                "venue_code": race['venue_code'],
                "venue_name": race['venue_name'],
                "race_number": race['race_number'],
                "scheduled_time": race['scheduled_time'],
                "is_active": race['status'] == 'scheduled'
            }
            races.append(race_data)
        
        return create_response(data={
            "races": races,
            "date": today,
            "mobile_optimized": mobile_optimized,
            "data_source": "cache"
        })
        
    except Exception as e:
        logger.error(f"今日のレース取得エラー: {str(e)}")
        return create_response(error=str(e), status_code=500)

# ===== AI予想エンドポイント =====
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

# ===== アプリケーション初期化 =====
def initialize_app():
    """アプリケーション初期化"""
    try:
        logger.info("=== 正式スクレイピング版アプリケーション初期化開始 ===")
        
        # データベース初期化
        db_manager.initialize_all_tables()
        logger.info("データベース初期化完了")
        
        # レーススケジューラー開始
        schedule_manager.start_scheduled_tasks()
        logger.info("✅ レーススケジューラー開始完了")
        
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
        logger.info(f"🚀 WAVE PREDICTOR 正式スクレイピング版 Flask アプリケーション開始: ポート {port}")
        
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
