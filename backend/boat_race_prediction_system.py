"""
競艇予想ディープラーニングAIシステム
- 選手データ、過去の成績、コンディション、コメントなどを分析
- リアルタイムデータ取得と予測モデルの更新
- 結果のフィードバックによる継続的な精度向上
"""

import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential, load_model, Model
from tensorflow.keras.layers import Dense, LSTM, Dropout, Input, Embedding, Flatten, Concatenate
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import ModelCheckpoint, EarlyStopping
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.model_selection import train_test_split
import requests
from bs4 import BeautifulSoup
import schedule
import time
import json
import os
import datetime
import logging
import re
from transformers import BertJapaneseTokenizer, TFBertModel
import sqlite3
from concurrent.futures import ThreadPoolExecutor

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("boatrace_ai.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("BoatraceAI")

class BoatRaceDataCollector:
    """
    競艇データの収集クラス
    - 選手情報
    - レース結果
    - 出走表
    - 水面状況
    - 選手コメント
    などを取得
    """
    
    def __init__(self, db_path="boatrace_data.db"):
        """初期化"""
        self.db_path = db_path
        self.initialize_database()
        self.venues = [
            "桐生", "戸田", "江戸川", "平和島", "多摩川", "浜名湖", 
            "蒲郡", "常滑", "津", "三国", "びわこ", "住之江",
            "尼崎", "鳴門", "丸亀", "児島", "宮島", "徳山",
            "下関", "若松", "芦屋", "福岡", "唐津", "大村"
        ]
        self.base_url = "https://boatrace.jp/"
        
    def initialize_database(self):
        """データベースの初期化"""
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
        
        # 成績テーブル
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS race_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id TEXT,
            venue TEXT,
            race_number INTEGER,
            race_date TEXT,
            racer_id INTEGER,
            boat_number INTEGER,
            course INTEGER,
            rank INTEGER,
            time REAL,
            start_time REAL,
            UNIQUE(race_id, racer_id)
        )
        ''')
        
        # 水面状況テーブル
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS water_conditions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id TEXT UNIQUE,
            venue TEXT,
            race_date TEXT,
            temperature REAL,
            water_temperature REAL,
            wave_height REAL,
            wind_direction TEXT,
            wind_speed REAL,
            weather TEXT
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
            UNIQUE(race_id, racer_id)
        )
        ''')
        
        # 出走表テーブル
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS race_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id TEXT,
            venue TEXT,
            race_number INTEGER,
            race_date TEXT,
            racer_id INTEGER,
            boat_number INTEGER,
            course INTEGER,
            motor_number INTEGER,
            boat_id INTEGER,
            weight REAL,
            UNIQUE(race_id, racer_id)
        )
        ''')
        
        conn.commit()
        conn.close()
        
    def get_race_schedule(self, date=None):
        """指定日の全レース予定を取得"""
        if date is None:
            date = datetime.datetime.now().strftime("%Y%m%d")
        
        schedule_url = f"{self.base_url}race_list/{date}"
        # 実際には、ここでrequestsを使ってHTMLを取得し、BeautifulSoupでパース
        # このサンプルコードでは、ダミーデータを返す
        
        logger.info(f"レーススケジュール取得: {date}")
        
        # ダミーデータ
        races = []
        for venue in self.venues[:3]:  # サンプル用に3つの会場のみ
            for race_number in range(1, 13):
                race_id = f"{date}{self.venues.index(venue)+1:02d}{race_number:02d}"
                races.append({
                    "race_id": race_id,
                    "venue": venue,
                    "race_number": race_number,
                    "race_date": date
                })
        
        return races
    
    def get_race_entries(self, race_id):
        """出走表情報の取得"""
        # 実際にはWebスクレイピングで取得
        venue_code = race_id[8:10]
        race_number = race_id[10:12]
        race_date = race_id[0:8]
        
        logger.info(f"出走表情報取得: {race_id}")
        
        # ダミーデータ
        entries = []
        for boat_number in range(1, 7):
            entries.append({
                "race_id": race_id,
                "venue": self.venues[int(venue_code)-1],
                "race_number": int(race_number),
                "race_date": race_date,
                "racer_id": 10000 + (int(venue_code) * 100) + boat_number,
                "boat_number": boat_number,
                "course": boat_number,
                "motor_number": 100 + boat_number,
                "boat_id": 200 + boat_number,
                "weight": 52.0 + boat_number / 10.0
            })
        
        # データベースに保存
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for entry in entries:
            cursor.execute('''
            INSERT OR REPLACE INTO race_entries 
            (race_id, venue, race_number, race_date, racer_id, boat_number, course, motor_number, boat_id, weight)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                entry["race_id"], entry["venue"], entry["race_number"], entry["race_date"],
                entry["racer_id"], entry["boat_number"], entry["course"], entry["motor_number"],
                entry["boat_id"], entry["weight"]
            ))
        
        conn.commit()
        conn.close()
        return entries
    
    def get_water_condition(self, race_id):
        """水面状況の取得"""
        # 実際にはWebスクレイピングで取得
        venue_code = race_id[8:10]
        race_date = race_id[0:8]
        
        logger.info(f"水面状況取得: {race_id}")
        
        # ダミーデータ
        condition = {
            "race_id": race_id,
            "venue": self.venues[int(venue_code)-1],
            "race_date": race_date,
            "temperature": 25.0 + np.random.normal(0, 2),
            "water_temperature": 20.0 + np.random.normal(0, 1),
            "wave_height": np.random.choice([0, 1, 2, 3, 5, 10]),
            "wind_direction": np.random.choice(["北", "北東", "東", "南東", "南", "南西", "西", "北西"]),
            "wind_speed": np.random.normal(3, 1),
            "weather": np.random.choice(["晴", "曇", "雨", "荒天"])
        }
        
        # データベースに保存
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT OR REPLACE INTO water_conditions 
        (race_id, venue, race_date, temperature, water_temperature, wave_height, wind_direction, wind_speed, weather)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            condition["race_id"], condition["venue"], condition["race_date"],
            condition["temperature"], condition["water_temperature"], condition["wave_height"],
            condition["wind_direction"], condition["wind_speed"], condition["weather"]
        ))
        
        conn.commit()
        conn.close()
        return condition
    
    def get_racer_comments(self, race_id):
        """選手コメントの取得"""
        # 実際にはWebスクレイピングで取得
        venue_code = race_id[8:10]
        race_date = race_id[0:8]
        
        logger.info(f"選手コメント取得: {race_id}")
        
        # ダミーデータ
        comments = []
        comment_templates = [
            "調子は良い。自信を持ってレースに臨む。",
            "モーターの調子が良くないが、スタートで挽回したい。",
            "絶好調。イン取れれば勝てる。",
            "昨日の調整で問題を解決。いい走りができそう。",
            "風の影響が心配だが、経験を活かして対応する。",
            "集中して自分のレースをする。"
        ]
        
        for boat_number in range(1, 7):
            racer_id = 10000 + (int(venue_code) * 100) + boat_number
            comments.append({
                "race_id": race_id,
                "racer_id": racer_id,
                "comment": comment_templates[boat_number-1],
                "comment_date": race_date
            })
        
        # データベースに保存
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for comment in comments:
            cursor.execute('''
            INSERT OR REPLACE INTO racer_comments 
            (race_id, racer_id, comment, comment_date)
            VALUES (?, ?, ?, ?)
            ''', (
                comment["race_id"], comment["racer_id"], comment["comment"], comment["comment_date"]
            ))
        
        conn.commit()
        conn.close()
        return comments
    
    def get_race_results(self, race_id):
        """レース結果の取得"""
        # 実際にはWebスクレイピングで取得
        venue_code = race_id[8:10]
        race_number = race_id[10:12]
        race_date = race_id[0:8]
        
        logger.info(f"レース結果取得: {race_id}")
        
        # ダミーデータ
        # 通常は1-6位までの結果だが、失格や欠場などを考慮
        results = []
        times = sorted([6 + np.random.normal(0, 0.2) for _ in range(6)])
        start_times = sorted([0.1 + np.random.normal(0, 0.05) for _ in range(6)])
        
        for boat_number in range(1, 7):
            rank = boat_number  # 単純化のため、艇番と順位を一致させる
            racer_id = 10000 + (int(venue_code) * 100) + boat_number
            
            results.append({
                "race_id": race_id,
                "venue": self.venues[int(venue_code)-1],
                "race_number": int(race_number),
                "race_date": race_date,
                "racer_id": racer_id,
                "boat_number": boat_number,
                "course": boat_number,
                "rank": rank,
                "time": times[rank-1],
                "start_time": start_times[rank-1]
            })
        
        # データベースに保存
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for result in results:
            cursor.execute('''
            INSERT OR REPLACE INTO race_results 
            (race_id, venue, race_number, race_date, racer_id, boat_number, course, rank, time, start_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                result["race_id"], result["venue"], result["race_number"], result["race_date"],
                result["racer_id"], result["boat_number"], result["course"], result["rank"],
                result["time"], result["start_time"]
            ))
        
        conn.commit()
        conn.close()
        return results
    
    def update_racer_info(self, racer_id):
        """選手情報の更新"""
        # 実際にはWebスクレイピングで取得
        logger.info(f"選手情報更新: {racer_id}")
        
        # ダミーデータ
        venue_id = (racer_id - 10000) // 100
        boat_number = racer_id - 10000 - (venue_id * 100)
        
        racer_info = {
            "racer_id": racer_id,
            "name": f"選手{racer_id}",
            "gender": "男" if boat_number % 2 == 0 else "女",
            "birth_date": f"{1980 + boat_number}-01-01",
            "branch": self.venues[venue_id % len(self.venues)],
            "rank": np.random.choice(["A1", "A2", "B1", "B2"]),
            "weight": 65.0 + np.random.normal(0, 5),
            "height": 170.0 + np.random.normal(0, 7),
            "last_updated": datetime.datetime.now().strftime("%Y-%m-%d")
        }
        
        # データベースに保存
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT OR REPLACE INTO racers 
        (racer_id, name, gender, birth_date, branch, rank, weight, height, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            racer_info["racer_id"], racer_info["name"], racer_info["gender"], racer_info["birth_date"],
            racer_info["branch"], racer_info["rank"], racer_info["weight"], racer_info["height"],
            racer_info["last_updated"]
        ))
        
        conn.commit()
        conn.close()
        return racer_info
    
    def collect_daily_data(self, date=None):
        """1日分のデータを収集"""
        if date is None:
            date = datetime.datetime.now().strftime("%Y%m%d")
            
        logger.info(f"日次データ収集開始: {date}")
        
        # レーススケジュール取得
        races = self.get_race_schedule(date)
        
        # 各レースの情報を取得
        with ThreadPoolExecutor(max_workers=5) as executor:
            # 出走表取得
            executor.map(self.get_race_entries, [race["race_id"] for race in races])
            
            # 水面状況取得
            executor.map(self.get_water_condition, [race["race_id"] for race in races])
            
            # 選手コメント取得
            executor.map(self.get_racer_comments, [race["race_id"] for race in races])
        
        logger.info(f"日次データ収集完了: {date}")
        return races
    
    def collect_race_results(self, date=None):
        """レース結果収集"""
        if date is None:
            date = datetime.datetime.now().strftime("%Y%m%d")
            
        logger.info(f"レース結果収集開始: {date}")
        
        # レーススケジュール取得
        races = self.get_race_schedule(date)
        
        # 各レースの結果を取得
        with ThreadPoolExecutor(max_workers=5) as executor:
            executor.map(self.get_race_results, [race["race_id"] for race in races])
            
        logger.info(f"レース結果収集完了: {date}")
        return races


class BoatRaceFeatureExtractor:
    """
    特徴量抽出クラス
    - 選手の過去成績
    - コース別成績
    - 天候条件下の成績
    - 選手の調子
    - テキスト分析（コメント）
    など
    """
    
    def __init__(self, db_path="boatrace_data.db"):
        """初期化"""
        self.db_path = db_path
        self.tokenizer = None
        # 必要に応じてBERTトークナイザーの初期化
        # self.tokenizer = BertJapaneseTokenizer.from_pretrained('cl-tohoku/bert-base-japanese-whole-word-masking')

    def get_racer_statistics(self, racer_id, days=30):
        """選手の直近成績取得"""
        logger.info(f"選手統計取得: {racer_id}, 期間: {days}日")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        current_date = datetime.datetime.now()
        past_date = (current_date - datetime.timedelta(days=days)).strftime("%Y%m%d")
        
        # 直近の着順データ
        cursor.execute('''
        SELECT rank, course, time, start_time, venue
        FROM race_results
        WHERE racer_id = ? AND race_date >= ?
        ORDER BY race_date DESC, race_number DESC
        ''', (racer_id, past_date))
        
        recent_results = cursor.fetchall()
        
        # 平均着順、コース別着順など統計量を計算
        if not recent_results:
            conn.close()
            return {
                "racer_id": racer_id,
                "avg_rank": None,
                "win_rate": 0,
                "top3_rate": 0,
                "avg_start_time": None,
                "course_performance": {},
                "venue_performance": {},
                "recent_races": 0
            }
        
        ranks = [r[0] for r in recent_results]
        courses = [r[1] for r in recent_results]
        start_times = [r[3] for r in recent_results if r[3] is not None]
        venues = [r[4] for r in recent_results]
        
        # コース別成績
        course_performance = {}
        for course in range(1, 7):
            course_ranks = [rank for i, rank in enumerate(ranks) if courses[i] == course]
            if course_ranks:
                avg_rank = sum(course_ranks) / len(course_ranks)
                wins = course_ranks.count(1)
                top3 = sum(1 for r in course_ranks if r <= 3)
                
                course_performance[course] = {
                    "avg_rank": avg_rank,
                    "win_rate": wins / len(course_ranks),
                    "top3_rate": top3 / len(course_ranks),
                    "count": len(course_ranks)
                }
        
        # 会場別成績
        venue_performance = {}
        for venue in set(venues):
            venue_ranks = [rank for i, rank in enumerate(ranks) if venues[i] == venue]
            if venue_ranks:
                avg_rank = sum(venue_ranks) / len(venue_ranks)
                wins = venue_ranks.count(1)
                top3 = sum(1 for r in venue_ranks if r <= 3)
                
                venue_performance[venue] = {
                    "avg_rank": avg_rank,
                    "win_rate": wins / len(venue_ranks),
                    "top3_rate": top3 / len(venue_ranks),
                    "count": len(venue_ranks)
                }
        
        conn.close()
        
        # 統計量をまとめる
        stats = {
            "racer_id": racer_id,
            "avg_rank": sum(ranks) / len(ranks),
            "win_rate": ranks.count(1) / len(ranks),
            "top3_rate": sum(1 for r in ranks if r <= 3) / len(ranks),
            "avg_start_time": sum(start_times) / len(start_times) if start_times else None,
            "course_performance": course_performance,
            "venue_performance": venue_performance,
            "recent_races": len(ranks)
        }
        
        return stats

    def get_weather_performance(self, racer_id, weather_type, days=180):
        """天候条件別の選手成績"""
        logger.info(f"天候別成績取得: {racer_id}, 天候: {weather_type}")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        current_date = datetime.datetime.now()
        past_date = (current_date - datetime.timedelta(days=days)).strftime("%Y%m%d")
        
        # 天候別の成績データ取得
        cursor.execute('''
        SELECT r.rank, w.wave_height, w.wind_speed, w.weather
        FROM race_results r
        JOIN water_conditions w ON r.race_id = w.race_id
        WHERE r.racer_id = ? AND r.race_date >= ? AND w.weather = ?
        ''', (racer_id, past_date, weather_type))
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return {
                "racer_id": racer_id,
                "weather": weather_type,
                "avg_rank": None,
                "win_rate": 0,
                "race_count": 0
            }
        
        ranks = [r[0] for r in results]
        
        stats = {
            "racer_id": racer_id,
            "weather": weather_type,
            "avg_rank": sum(ranks) / len(ranks),
            "win_rate": ranks.count(1) / len(ranks) if ranks else 0,
            "race_count": len(ranks)
        }
        
        return stats

    def analyze_comment_sentiment(self, comment):
        """コメントの感情分析・テキスト特徴抽出"""
        # 実際にはBERTなどでテキスト分析
        if not comment:
            return {
                "sentiment": 0,
                "confidence": 0,
                "key_topics": []
            }
        
        # 簡易感情分析（実際にはより高度な分析が必要）
        positive_words = ["調子", "良い", "自信", "絶好調", "解決", "いい"]
        negative_words = ["悪い", "心配", "問題", "難しい", "厳しい"]
        
        sentiment = 0
        for word in positive_words:
            if word in comment:
                sentiment += 0.2
        
        for word in negative_words:
            if word in comment:
                sentiment -= 0.2
        
        sentiment = max(-1, min(1, sentiment))  # -1から1の範囲に正規化
        
        # トピック抽出（簡易版）
        key_topics = []
        topic_words = {
            "スタート": ["スタート", "飛び", "出し"],
            "コース": ["コース", "イン", "アウト"],
            "調子": ["調子", "絶好調", "不調"],
            "機材": ["モーター", "ボート", "エンジン"],
            "外部要因": ["風", "波", "天候"]
        }
        
        for topic, words in topic_words.items():
            for word in words:
                if word in comment:
                    key_topics.append(topic)
                    break
        
        result = {
            "sentiment": sentiment,
            "confidence": 0.7,  # 簡易実装なので固定値
            "key_topics": key_topics
        }
        
        return result

    def get_race_features(self, race_id):
        """レース毎の特徴量を抽出"""
        logger.info(f"レース特徴抽出: {race_id}")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 出走表取得
        cursor.execute('''
        SELECT racer_id, boat_number, course, motor_number, boat_id, weight
        FROM race_entries
        WHERE race_id = ?
        ORDER BY boat_number
        ''', (race_id,))
        
        entries = cursor.fetchall()
        
        if not entries:
            conn.close()
            return None
        
        # 水面状況取得
        cursor.execute('''
        SELECT temperature, water_temperature, wave_height, wind_direction, wind_speed, weather
        FROM water_conditions
        WHERE race_id = ?
        ''', (race_id,))
        
        water_condition = cursor.fetchone()
        
        # 選手コメント取得
        cursor.execute('''
        SELECT racer_id, comment
        FROM racer_comments
        WHERE race_id = ?
        ''', (race_id,))
        
        comments = {row[0]: row[1] for row in cursor.fetchall()}
        
        conn.close()
        
        # レース情報
        race_info = {
            "race_id": race_id,
            "venue": race_id[8:10],
            "race_number": int(race_id[10:12]),
            "race_date": race_id[0:8],
        }
        
        # 水面状況の特徴
        water_features = {}
        if water_condition:
            water_features = {
                "temperature": water_condition[0],
                "water_temperature": water_condition[1],
                "wave_height": water_condition[2],
                "wind_direction": water_condition[3],
                "wind_speed": water_condition[4],
                "weather": water_condition[5]
            }
        
        # 各選手の特徴抽出
        racer_features = []
        for entry in entries:
            racer_id = entry[0]
            
            # 選手統計取得
            racer_stats = self.get_racer_statistics(racer_id)
            
            # 天候条件下での成績
            weather_stats = self.get_weather_performance(
                racer_id, 
                water_features.get("weather", "晴")
            ) if water_features else {}
            
            # コメント分析
            comment = comments.get(racer_id, "")
            comment_analysis = self.analyze_comment_sentiment(comment)
            
            # 艇番・コース情報
            position_info = {
                "boat_number": entry[1],
                "course": entry[2],
                "motor_number": entry[3],
                "boat_id": entry[4],
                "weight": entry[5]
            }
            
            # 全ての特徴をまとめる
            racer_feature = {
                "racer_id": racer_id,
                "position": position_info,
                "statistics": racer_stats,
                "weather_performance": weather_stats,
                "comment": comment,
                "comment_analysis": comment_analysis
            }
            
            racer_features.append(racer_feature)
        
        # レース全体の特徴量をまとめる
        race_features = {
            "race_info": race_info,
            "water_condition": water_features,
            "racers": racer_features
        }
        
        return race_features


class BoatRacePredictionModel:
    """
    競艇予測モデルクラス
    - 特徴量の前処理
    - モデルの訓練
    - 予測の実行
    - モデルの評価・更新
    """
    
    def __init__(self, model_dir="models"):
        """初期化"""
        self.model_dir = model_dir
        self.main_model = None
        self.features_scaler = None
        self.comment_model = None
        self.race_history = {}
        
        # モデル保存用ディレクトリ作成
        os.makedirs(self.model_dir, exist_ok=True)
        
        # モデルのロード（存在する場合）
        self.load_models()
    
    def load_models(self):
        """既存モデルのロード"""
        try:
            model_path = os.path.join(self.model_dir, "boatrace_model.h5")
            scaler_path = os.path.join(self.model_dir, "features_scaler.pkl")
            comment_model_path = os.path.join(self.model_dir, "comment_model.h5")
            
            if os.path.exists(model_path):
                logger.info("メインモデルをロード中...")
                self.main_model = load_model(model_path)
                logger.info("メインモデルのロード完了")
            
            if os.path.exists(scaler_path):
                logger.info("特徴量スケーラーをロード中...")
                with open(scaler_path, 'rb') as f:
                    self.features_scaler = pickle.load(f)
                logger.info("特徴量スケーラーのロード完了")
            
            if os.path.exists(comment_model_path):
                logger.info("コメント分析モデルをロード中...")
                self.comment_model = load_model(comment_model_path)
                logger.info("コメント分析モデルのロード完了")
                
        except Exception as e:
            logger.error(f"モデルロードエラー: {str(e)}")
            # モデルがロードできない場合は新規作成
            self.main_model = None
            self.features_scaler = None
            self.comment_model = None
    
    def save_models(self):
        """モデルの保存"""
        if self.main_model:
            model_path = os.path.join(self.model_dir, "boatrace_model.h5")
            self.main_model.save(model_path)
            logger.info(f"メインモデル保存完了: {model_path}")
        
        if self.features_scaler:
            scaler_path = os.path.join(self.model_dir, "features_scaler.pkl")
            with open(scaler_path, 'wb') as f:
                pickle.dump(self.features_scaler, f)
            logger.info(f"特徴量スケーラー保存完了: {scaler_path}")
        
        if self.comment_model:
            comment_model_path = os.path.join(self.model_dir, "comment_model.h5")
            self.comment_model.save(comment_model_path)
            logger.info(f"コメント分析モデル保存完了: {comment_model_path}")
    
    def preprocess_features(self, race_features, training=False):
        """特徴量の前処理"""
        # レース情報の数値特徴量
        race_data = race_features["race_info"]
        water_data = race_features["water_condition"]
        
        # 水面情報の数値変換
        wind_direction_mapping = {
            "北": 0, "北東": 45, "東": 90, "南東": 135,
            "南": 180, "南西": 225, "西": 270, "北西": 315
        }
        weather_mapping = {
            "晴": 0, "曇": 1, "雨": 2, "荒天": 3
        }
        
        # 各選手の特徴量作成
        racer_features_list = []
        
        for racer in race_features["racers"]:
            # 基本情報
            position = racer["position"]
            stats = racer["statistics"]
            weather_perf = racer["weather_performance"]
            comment_analysis = racer["comment_analysis"]
            
            # 特徴量抽出
            features = [
                # 艇番・コース情報
                position["boat_number"],
                position["course"],
                position["motor_number"],
                position["boat_id"],
                position["weight"],
                
                # 選手成績統計
                stats.get("avg_rank", 3.5),  # デフォルト値
                stats.get("win_rate", 0.0),
                stats.get("top3_rate", 0.0),
                stats.get("avg_start_time", 0.2),
                stats.get("recent_races", 0),
                
                # コース別成績（1コースの場合）
                stats.get("course_performance", {}).get(1, {}).get("avg_rank", 3.5),
                stats.get("course_performance", {}).get(1, {}).get("win_rate", 0.0),
                
                # コース別成績（現在のコース）
                stats.get("course_performance", {}).get(position["course"], {}).get("avg_rank", 3.5),
                stats.get("course_performance", {}).get(position["course"], {}).get("win_rate", 0.0),
                
                # 会場での成績
                stats.get("venue_performance", {}).get(race_data["venue"], {}).get("avg_rank", 3.5),
                stats.get("venue_performance", {}).get(race_data["venue"], {}).get("win_rate", 0.0),
                
                # 天候条件での成績
                weather_perf.get("avg_rank", 3.5),
                weather_perf.get("win_rate", 0.0),
                weather_perf.get("race_count", 0),
                
                # コメント分析
                comment_analysis.get("sentiment", 0.0),
                comment_analysis.get("confidence", 0.0),
                
                # コメントトピック（ダミー変数）
                1 if "スタート" in comment_analysis.get("key_topics", []) else 0,
                1 if "コース" in comment_analysis.get("key_topics", []) else 0,
                1 if "調子" in comment_analysis.get("key_topics", []) else 0,
                1 if "機材" in comment_analysis.get("key_topics", []) else 0,
                1 if "外部要因" in comment_analysis.get("key_topics", []) else 0,
            ]
            
            racer_features_list.append(features)
        
        # 水面状況の特徴量
        water_features = [
            water_data.get("temperature", 25.0),
            water_data.get("water_temperature", 20.0),
            water_data.get("wave_height", 0.0),
            wind_direction_mapping.get(water_data.get("wind_direction", "北"), 0),
            water_data.get("wind_speed", 0.0),
            weather_mapping.get(water_data.get("weather", "晴"), 0)
        ]
        
        # すべての選手の特徴量を同一の配列に
        all_features = np.array(racer_features_list)
        
        # スケーリング処理
        if training and (self.features_scaler is None):
            # 学習時かつスケーラーがない場合は新規作成
            self.features_scaler = StandardScaler()
            all_features_scaled = self.features_scaler.fit_transform(all_features)
        elif self.features_scaler is not None:
            # スケーラーが存在する場合は変換のみ
            all_features_scaled = self.features_scaler.transform(all_features)
        else:
            # スケーラーがない場合はそのまま
            all_features_scaled = all_features
        
        # 水面特徴量は別途スケーリング
        water_features = np.array(water_features).reshape(1, -1)
        
        return all_features_scaled, water_features, racer_features_list
    
    def create_model(self):
        """モデルの構築"""
        logger.info("新規モデルを構築中...")
        
        # 選手特徴量の入力
        racer_input = Input(shape=(26,), name="racer_features")
        racer_dense1 = Dense(64, activation="relu")(racer_input)
        racer_dense2 = Dense(32, activation="relu")(racer_dense1)
        racer_output = Dense(16, activation="relu")(racer_dense2)
        
        # 水面状況の入力
        water_input = Input(shape=(6,), name="water_features")
        water_dense = Dense(8, activation="relu")(water_input)
        
        # 特徴量の結合
        merged = Concatenate()([racer_output, water_dense])
        merged_dense = Dense(32, activation="relu")(merged)
        dropout = Dropout(0.2)(merged_dense)
        
        # 出力層（順位予測）- 6艇なので1-6位の確率分布
        output = Dense(6, activation="softmax", name="rank_probs")(dropout)
        
        # モデル構築
        model = Model(inputs=[racer_input, water_input], outputs=output)
        
        # コンパイル
        model.compile(
            optimizer=Adam(learning_rate=0.001),
            loss="categorical_crossentropy",
            metrics=["accuracy"]
        )
        
        logger.info("モデル構築完了")
        logger.info(model.summary())
        
        return model
    
    def create_comment_model(self):
        """コメント分析モデルの構築"""
        logger.info("コメント分析モデルを構築中...")
        
        # BERTを使用した日本語コメント分析モデル
        # 本番実装では、実際のBERTモデルを使用
        # ここではダミーのLSTMモデルを作成
        
        model = Sequential([
            Embedding(input_dim=10000, output_dim=128, input_length=100),
            LSTM(64, return_sequences=True),
            LSTM(32),
            Dense(16, activation="relu"),
            Dense(3, activation="softmax")  # ネガティブ、ニュートラル、ポジティブの3クラス
        ])
        
        model.compile(
            optimizer=Adam(learning_rate=0.001),
            loss="categorical_crossentropy",
            metrics=["accuracy"]
        )
        
        logger.info("コメント分析モデル構築完了")
        
        return model
    
    def train_model(self, train_data, epochs=10, batch_size=32):
        """モデルの学習"""
        logger.info(f"モデル学習開始: エポック数={epochs}, バッチサイズ={batch_size}")
        
        X_racers = []
        X_water = []
        y = []
        
        # 学習データの準備
        for race_id, race_data in train_data.items():
            race_features = race_data["features"]
            race_results = race_data["results"]
            
            # 特徴量の前処理
            racer_features, water_features, _ = self.preprocess_features(race_features, training=True)
            
            # ラベルの作成（順位をone-hotエンコーディング）
            for racer in race_results:
                rank = racer["rank"]
                boat_number = racer["boat_number"]
                
                # 6位までの順位に制限（失格や欠場は除外）
                if 1 <= rank <= 6:
                    y_onehot = np.zeros(6)
                    y_onehot[rank-1] = 1
                    
                    # 選手の特徴量とラベルを追加
                    X_racers.append(racer_features[boat_number-1])
                    X_water.append(water_features[0])
                    y.append(y_onehot)
        
        # numpy配列に変換
        X_racers = np.array(X_racers)
        X_water = np.array(X_water)
        y = np.array(y)
        
        # モデルがない場合は新規作成
        if self.main_model is None:
            self.main_model = self.create_model()
        
        # チェックポイントのコールバック
        checkpoint = ModelCheckpoint(
            os.path.join(self.model_dir, "boatrace_model_best.h5"),
            monitor="val_accuracy",
            save_best_only=True,
            verbose=1
        )
        
        early_stop = EarlyStopping(
            monitor="val_accuracy",
            patience=5,
            verbose=1
        )
        
        # モデル学習
        history = self.main_model.fit(
            [X_racers, X_water], y,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=0.2,
            callbacks=[checkpoint, early_stop],
            verbose=1
        )
        
        # モデルの保存
        self.save_models()
        
        logger.info("モデル学習完了")
        
        return history
    
    def predict_race(self, race_features):
        """レース結果の予測"""
        logger.info(f"レース予測: {race_features['race_info']['race_id']}")
        
        # モデルがない場合は新規作成
        if self.main_model is None:
            logger.warning("モデルが存在しないため、新規作成します")
            self.main_model = self.create_model()
            # 学習済みモデルがないため精度は低い
        
        # 特徴量の前処理
        racer_features, water_features, raw_features = self.preprocess_features(race_features)
        
        # 各選手の予測
        predictions = []
        
        # バッチ予測（全選手一度に）
        X_racers = racer_features
        X_water = np.repeat(water_features, len(racer_features), axis=0)
        
        # 予測実行
        rank_probs = self.main_model.predict([X_racers, X_water])
        
        # 各選手の予測結果を整形
        for i, racer in enumerate(race_features["racers"]):
            racer_id = racer["racer_id"]
            boat_number = racer["position"]["boat_number"]
            
            # 着順確率（1-6位）
            probs = rank_probs[i]
            
            # 最も確率の高い着順
            predicted_rank = np.argmax(probs) + 1
            
            # 予測結果の保存
            predictions.append({
                "racer_id": racer_id,
                "boat_number": boat_number,
                "predicted_rank": predicted_rank,
                "rank_probabilities": probs.tolist(),
                "expected_value": sum((i+1) * p for i, p in enumerate(probs))
            })
        
        # 期待値でソート（期待値が低い方が上位予測）
        predictions.sort(key=lambda x: x["expected_value"])
        
        # 予測結果のフォーマット
        result = {
            "race_id": race_features["race_info"]["race_id"],
            "predictions": predictions,
            "forecast": {
                "win": predictions[0]["boat_number"],
                "quinella": [predictions[0]["boat_number"], predictions[1]["boat_number"]],
                "exacta": [predictions[0]["boat_number"], predictions[1]["boat_number"]],
                "trio": [predictions[0]["boat_number"], predictions[1]["boat_number"], predictions[2]["boat_number"]]
            }
        }
        
        return result
    
    def evaluate_prediction(self, prediction, actual_results):
        """予測結果の評価"""
        logger.info(f"予測評価: {prediction['race_id']}")
        
        race_id = prediction["race_id"]
        predicted_ranks = {p["boat_number"]: p["predicted_rank"] for p in prediction["predictions"]}
        actual_ranks = {r["boat_number"]: r["rank"] for r in actual_results}
        
        # 的中率の計算
        hit_count = sum(1 for boat_num, pred_rank in predicted_ranks.items() 
                       if actual_ranks.get(boat_num) == pred_rank)
        hit_rate = hit_count / len(predicted_ranks) if predicted_ranks else 0
        
        # 的中した舟券の計算
        forecasts = prediction["forecast"]
        
        # 単勝
        win_hit = any(actual_ranks.get(boat_num) == 1 for boat_num in [forecasts["win"]])
        
        # 2連単（1着と2着の艇が予測通りかチェック）
        exacta_boats = forecasts["exacta"]
        exacta_hit = (actual_ranks.get(exacta_boats[0]) == 1 and 
                     actual_ranks.get(exacta_boats[1]) == 2)
        
        # 2連複（予測した2艇が1着と2着に含まれるかチェック）
        quinella_boats = set(forecasts["quinella"])
        actual_top2 = {boat_num for boat_num, rank in actual_ranks.items() if rank in [1, 2]}
        quinella_hit = len(quinella_boats.intersection(actual_top2)) == 2
        
        # 3連複（予測した3艇が1着、2着、3着に含まれるかチェック）
        trio_boats = set(forecasts["trio"])
        actual_top3 = {boat_num for boat_num, rank in actual_ranks.items() if rank in [1, 2, 3]}
        trio_hit = len(trio_boats.intersection(actual_top3)) == 3
        
        # 評価結果
        evaluation = {
            "race_id": race_id,
            "hit_rate": hit_rate,
            "win_hit": win_hit,
            "exacta_hit": exacta_hit,
            "quinella_hit": quinella_hit,
            "trio_hit": trio_hit
        }
        
        # レース履歴に保存
        self.race_history[race_id] = {
            "prediction": prediction,
            "actual": actual_results,
            "evaluation": evaluation
        }
        
        logger.info(f"予測評価結果: {evaluation}")
        
        return evaluation
    
    def get_performance_stats(self, days=30):
        """予測モデルの成績統計"""
        logger.info(f"成績統計取得: 過去{days}日間")
        
        current_date = datetime.datetime.now()
        past_date = (current_date - datetime.timedelta(days=days)).strftime("%Y%m%d")
        
        # 対象期間のレース履歴を抽出
        target_races = {
            race_id: data for race_id, data in self.race_history.items()
            if race_id[:8] >= past_date
        }
        
        if not target_races:
            return {
                "period": f"過去{days}日間",
                "race_count": 0,
                "avg_hit_rate": 0,
                "win_hit_rate": 0,
                "exacta_hit_rate": 0,
                "quinella_hit_rate": 0,
                "trio_hit_rate": 0,
            }
        
        # 成績集計
        hit_rates = []
        win_hits = 0
        exacta_hits = 0
        quinella_hits = 0
        trio_hits = 0
        
        for race_id, data in target_races.items():
            eval_data = data["evaluation"]
            hit_rates.append(eval_data["hit_rate"])
            
            if eval_data["win_hit"]:
                win_hits += 1
            
            if eval_data["exacta_hit"]:
                exacta_hits += 1
            
            if eval_data["quinella_hit"]:
                quinella_hits += 1
            
            if eval_data["trio_hit"]:
                trio_hits += 1
        
        race_count = len(target_races)
        
        stats = {
            "period": f"過去{days}日間",
            "race_count": race_count,
            "avg_hit_rate": sum(hit_rates) / race_count if hit_rates else 0,
            "win_hit_rate": win_hits / race_count,
            "exacta_hit_rate": exacta_hits / race_count,
            "quinella_hit_rate": quinella_hits / race_count,
            "trio_hit_rate": trio_hits / race_count,
        }
        
        return stats


class BoatRaceAI:
    """
    競艇AI予測システムのメインクラス
    - データ収集
    - 特徴抽出
    - 予測モデル
    - 結果評価
    を統合
    """
    
    def __init__(self, db_path="boatrace_data.db"):
        """初期化"""
        self.db_path = db_path
        self.data_collector = BoatRaceDataCollector(db_path)
        self.feature_extractor = BoatRaceFeatureExtractor(db_path)
        self.prediction_model = BoatRacePredictionModel()
        self.current_predictions = {}
        
        logger.info("競艇AI予測システム初期化完了")

    def _get_venue_characteristics(self, venue_code):
        """全国24競艇場の特性データベース"""
        venue_db = {
            '01': {'name': '桐生', 'water_type': 'fresh', 'course_width': 'narrow', 'inner_advantage': 0.85, 'wind_effect': 'high', 'difficulty': 'medium'},
            '02': {'name': '戸田', 'water_type': 'fresh', 'course_width': 'narrow', 'inner_advantage': 0.80, 'wind_effect': 'medium', 'difficulty': 'hard'},
            '03': {'name': '江戸川', 'water_type': 'tidal', 'course_width': 'wide', 'inner_advantage': 0.60, 'wind_effect': 'very_high', 'difficulty': 'very_hard'},
            '04': {'name': '平和島', 'water_type': 'sea', 'course_width': 'standard', 'inner_advantage': 0.75, 'wind_effect': 'high', 'difficulty': 'hard'},
            '05': {'name': '多摩川', 'water_type': 'fresh', 'course_width': 'standard', 'inner_advantage': 0.78, 'wind_effect': 'medium', 'difficulty': 'medium'},
            '06': {'name': '浜名湖', 'water_type': 'fresh', 'course_width': 'wide', 'inner_advantage': 0.72, 'wind_effect': 'low', 'difficulty': 'easy'},
            '07': {'name': '蒲郡', 'water_type': 'fresh', 'course_width': 'standard', 'inner_advantage': 0.76, 'wind_effect': 'medium', 'difficulty': 'medium'},
            '08': {'name': '常滑', 'water_type': 'fresh', 'course_width': 'standard', 'inner_advantage': 0.74, 'wind_effect': 'medium', 'difficulty': 'medium'},
            '09': {'name': '津', 'water_type': 'fresh', 'course_width': 'standard', 'inner_advantage': 0.77, 'wind_effect': 'low', 'difficulty': 'easy'},
            '10': {'name': '三国', 'water_type': 'fresh', 'course_width': 'narrow', 'inner_advantage': 0.82, 'wind_effect': 'high', 'difficulty': 'medium'},
            '11': {'name': 'びわこ', 'water_type': 'fresh', 'course_width': 'wide', 'inner_advantage': 0.71, 'wind_effect': 'medium', 'difficulty': 'medium'},
            '12': {'name': '住之江', 'water_type': 'fresh', 'course_width': 'wide', 'inner_advantage': 0.70, 'wind_effect': 'medium', 'difficulty': 'medium'},
            '13': {'name': '尼崎', 'water_type': 'fresh', 'course_width': 'standard', 'inner_advantage': 0.75, 'wind_effect': 'medium', 'difficulty': 'medium'},
            '14': {'name': '鳴門', 'water_type': 'sea', 'course_width': 'standard', 'inner_advantage': 0.73, 'wind_effect': 'high', 'difficulty': 'hard'},
            '15': {'name': '丸亀', 'water_type': 'sea', 'course_width': 'standard', 'inner_advantage': 0.74, 'wind_effect': 'medium', 'difficulty': 'medium'},
            '16': {'name': '児島', 'water_type': 'sea', 'course_width': 'wide', 'inner_advantage': 0.69, 'wind_effect': 'high', 'difficulty': 'hard'},
            '17': {'name': '宮島', 'water_type': 'sea', 'course_width': 'standard', 'inner_advantage': 0.72, 'wind_effect': 'high', 'difficulty': 'hard'},
            '18': {'name': '徳山', 'water_type': 'sea', 'course_width': 'standard', 'inner_advantage': 0.76, 'wind_effect': 'medium', 'difficulty': 'medium'},
            '19': {'name': '下関', 'water_type': 'sea', 'course_width': 'standard', 'inner_advantage': 0.73, 'wind_effect': 'high', 'difficulty': 'hard'},
            '20': {'name': '若松', 'water_type': 'sea', 'course_width': 'standard', 'inner_advantage': 0.75, 'wind_effect': 'medium', 'difficulty': 'medium'},
            '21': {'name': '芦屋', 'water_type': 'sea', 'course_width': 'standard', 'inner_advantage': 0.77, 'wind_effect': 'medium', 'difficulty': 'medium'},
            '22': {'name': '福岡', 'water_type': 'fresh', 'course_width': 'standard', 'inner_advantage': 0.78, 'wind_effect': 'low', 'difficulty': 'easy'},
            '23': {'name': '唐津', 'water_type': 'sea', 'course_width': 'wide', 'inner_advantage': 0.68, 'wind_effect': 'very_high', 'difficulty': 'very_hard'},
            '24': {'name': '大村', 'water_type': 'fresh', 'course_width': 'narrow', 'inner_advantage': 0.83, 'wind_effect': 'low', 'difficulty': 'easy'}
        }
        return venue_db.get(venue_code, venue_db['01'])

    def _get_weather_conditions(self):
        """気象条件シミュレーション"""
        import random
        return {
            'wind_direction': random.choice(['北', '北東', '東', '南東', '南', '南西', '西', '北西']),
            'wind_strength': random.choice(['無風', '微風', '弱風', '中風', '強風']),
            'wave_height': random.randint(0, 3),
            'temperature': random.randint(15, 35),
            'water_temp': random.randint(10, 30),
            'impact_level': random.choice(['低', '中', '高'])
        }
        
    def _calculate_detailed_racer_score(self, racer, venue_data, weather_data):
        """詳細な選手スコア計算"""
        score = 50  # ベーススコア
        breakdown = {}
        
        # 1. 基本能力評価（40点満点）
        class_scores = {'A1': 40, 'A2': 30, 'B1': 20, 'B2': 10}
        class_score = class_scores.get(racer.get('class', 'B2'), 10)
        score += class_score
        breakdown['class_ability'] = class_score
        
        # 2. 年齢・体重評価（20点満点）
        age = racer.get('age', 30)
        age_score = 20 if 25 <= age <= 32 else 15 if 22 <= age <= 38 else 10
        
        weight_str = racer.get('weight', '55.0kg')
        try:
            weight = float(weight_str.replace('kg', ''))
            weight_score = 10 if weight < 50 else 8 if weight < 52 else 5
        except:
            weight_score = 5
        
        physical_score = age_score + weight_score
        score += physical_score
        breakdown['physical'] = physical_score
        
        # 3. コース別評価（25点満点）
        boat_num = racer.get('boat_number', 1)
        course_score = self._calculate_course_advantage(boat_num, venue_data)
        score += course_score
        breakdown['course'] = course_score
        
        # 4. 気象条件適性（15点満点）
        weather_score = self._calculate_weather_adaptation(racer, weather_data, boat_num)
        score += weather_score
        breakdown['weather'] = weather_score
        
        motor_score = self._analyze_motor_performance(racer)
        score += motor_score
        breakdown['motor'] = motor_score

        # 6. 調子・フォーム（15点満点）
        form_score = self._analyze_racer_form(racer)
        score += form_score
        breakdown['form'] = form_score

        # 7. 前走成績（20点満点）
        recent_score = self._analyze_recent_performance(racer)
        score += recent_score
        breakdown['recent'] = recent_score

        # 8. スタートタイミング（10点満点）
        start_score = self._analyze_start_timing(racer, boat_num)
        score += start_score
        breakdown['start'] = start_score
        
        # 9. 出走状況（5点満点）
        situation_score = self._analyze_race_situation(racers_data, racer)
        score += situation_score
        breakdown['situation'] = situation_score
        
        return score

    def _calculate_course_advantage(self, boat_number, venue_data):
        """コース有利度計算"""
        base_scores = {1: 25, 2: 18, 3: 12, 4: 8, 5: 5, 6: 3}
        base_score = base_scores.get(boat_number, 3)
        
        # 会場特性による補正
        inner_advantage = venue_data['inner_advantage']
        if inner_advantage > 0.8 and boat_number == 1:
            base_score += 5  # インコース超有利会場
        elif inner_advantage < 0.7 and boat_number >= 4:
            base_score += 3  # アウト有利会場
        
        return base_score
    
    def _calculate_weather_adaptation(self, racer, weather_data, boat_number):
        """気象条件適性計算"""
        score = 10  # ベーススコア
        
        # 風の影響
        if weather_data['wind_strength'] in ['強風', '中風']:
            if boat_number == 1:
                score += 3  # インコースは風に強い
            elif boat_number >= 5:
                score -= 2  # アウトコースは風に弱い
        
        # 波の影響
        if weather_data['wave_height'] >= 2:
            try:
                weight = float(racer.get('weight', '55kg').replace('kg', ''))
                if weight < 50:
                    score -= 2  # 軽い選手は波に弱い
            except:
                pass
        
        return max(0, score)

    def _analyze_motor_performance(self, racer):
        """モーター成績分析（10点満点）"""
        import random
        
        # クラスに基づくモーター調整力
        class_motor_bonus = {
            'A1': random.randint(7, 10),
            'A2': random.randint(5, 8), 
            'B1': random.randint(3, 6),
            'B2': random.randint(1, 4)
        }
        return class_motor_bonus.get(racer.get('class', 'B2'), 3)

    def _analyze_racer_form(self, racer):
        """選手の調子・フォーム分析（15点満点）"""
        score = 10  # ベーススコア
        
        # 年齢による調子判定
        age = racer.get('age', 30)
        if 25 <= age <= 32:
            score += 5  # 全盛期
        elif 22 <= age <= 38:
            score += 3  # 安定期
        elif age > 45:
            score -= 2  # 衰退期
        
        # クラス別安定度
        racer_class = racer.get('class', 'B2')
        if racer_class == 'A1':
            score += 3  # 安定した実力
        elif racer_class == 'A2':
            score += 2
        
        # 体重による体調管理評価
        try:
            weight = float(racer.get('weight', '55kg').replace('kg', ''))
            if 48 <= weight <= 52:
                score += 2  # 適正体重維持
            elif weight > 56:
                score -= 1  # 体調管理不安
        except:
            pass
        
        return min(15, max(0, score))

    def _analyze_recent_performance(self, racer):
        """前走成績分析（20点満点）"""
        score = 10  # ベーススコア
        
        # 登録番号から簡易的な成績シミュレーション
        reg_num = racer.get('registration_number', '4000')
        try:
            last_digit = int(reg_num[-1])
            
            # 末尾数字による前走成績評価
            if last_digit in [1, 2]:
                score += 8  # 好調
            elif last_digit in [3, 4, 5]:
                score += 5  # 普通
            elif last_digit in [6, 7]:
                score += 2  # やや不調
            else:
                score -= 2  # 不調
                
            # クラスによる安定度補正
            racer_class = racer.get('class', 'B2')
            if racer_class == 'A1':
                score += 2  # A1は安定
            elif racer_class == 'B2':
                score -= 1  # B2は波がある
                
        except:
            score = 10
        
        return min(20, max(0, score))

    def _analyze_start_timing(self, racer, boat_number):
        """スタートタイミング分析（10点満点）"""
        score = 5  # ベーススコア
        
        # クラス別スタート技術
        racer_class = racer.get('class', 'B2')
        if racer_class == 'A1':
            score += 4  # スタート上手
        elif racer_class == 'A2':
            score += 2
        elif racer_class == 'B1':
            score += 1
        
        # 艇番別スタート有利度
        if boat_number == 1:
            score += 1  # インは比較的楽
        elif boat_number >= 5:
            score -= 1  # アウトは難しい
        
        return min(10, max(0, score))

    def _analyze_race_situation(self, racers_data, racer):
        """当日出走状況分析（5点満点）"""
        score = 3  # ベーススコア
        
        # 相手関係の分析
        opponent_classes = [r.get('class', 'B2') for r in racers_data if r != racer]
        a1_count = opponent_classes.count('A1')
        
        racer_class = racer.get('class', 'B2')
        
        # 格上相手が多い場合の評価
        if racer_class == 'A1' and a1_count <= 1:
            score += 2  # A1で相手が弱い
        elif racer_class == 'B2' and a1_count >= 3:
            score -= 1  # B2で相手が強い
        
        return min(5, max(0, score))
        
    def get_comprehensive_prediction(self, racers_data, venue_code='01'):
        """総合的な競艇予想分析"""
        logger.info(f"総合予想開始: 会場{venue_code}, 選手数{len(racers_data)}")
        
        if not racers_data:
            return {
                "ai_predictions": {
                    "predictions": [{"boat_number": 1, "predicted_rank": 1, "normalized_probability": 0.30}],
                    "recommendations": {"win": {"boat_number": 1}}
                }
            }
    
        # 会場特性と気象条件を取得
        venue_data = self._get_venue_characteristics(venue_code)
        weather_data = self._get_weather_conditions()
        
        # 選手評価（詳細版）
        racer_scores = []
        for racer in racers_data:
            score = self._calculate_detailed_racer_score(racer, venue_data, weather_data)
            racer_scores.append({
                'boat_number': racer.get('boat_number', 1),
                'score': score,
                'venue': venue_data['name'],
                'weather': weather_data['impact_level']
            })
        
        # スコア順ソート
        racer_scores.sort(key=lambda x: x['score'], reverse=True)
        top3 = [r['boat_number'] for r in racer_scores[:3]]
        
        return {
            "ai_predictions": {
                "predictions": [
                    {"boat_number": top3[0], "predicted_rank": 1, "normalized_probability": 0.35},
                    {"boat_number": top3[1], "predicted_rank": 2, "normalized_probability": 0.28},
                    {"boat_number": top3[2], "predicted_rank": 3, "normalized_probability": 0.20}
                ],
                "recommendations": {
                    "win": {"boat_number": top3[0]},
                    "exacta": {"combination": top3[:2]},
                    "trio": {"combination": top3}
                }
            }
        }
        
    def collect_historical_data(self, days=30):
        """過去データの収集"""
        logger.info(f"過去データ収集開始: {days}日分")
        
        current_date = datetime.datetime.now()
        collected_data = {}
        
        # 指定日数分のデータを収集
        for day in range(days):
            target_date = (current_date - datetime.timedelta(days=day)).strftime("%Y%m%d")
            logger.info(f"データ収集中: {target_date}")
            
            # レース予定取得
            races = self.data_collector.get_race_schedule(target_date)
            
            # 各レースのデータ収集
            for race in races:
                race_id = race["race_id"]
                
                # 出走表取得
                entries = self.data_collector.get_race_entries(race_id)
                
                # 水面状況取得
                water_condition = self.data_collector.get_water_condition(race_id)
                
                # 選手コメント取得
                comments = self.data_collector.get_racer_comments(race_id)
                
                # レース結果取得
                results = self.data_collector.get_race_results(race_id)
                
                # 選手情報の更新
                for entry in entries:
                    self.data_collector.update_racer_info(entry["racer_id"])
                
                # 収集データを保存
                collected_data[race_id] = {
                    "race_info": race,
                    "entries": entries,
                    "water_condition": water_condition,
                    "comments": comments,
                    "results": results
                }
        
        logger.info(f"過去データ収集完了: {len(collected_data)}レース")
        return collected_data
    
    def prepare_training_data(self, collected_data):
        """学習データの準備"""
        logger.info("学習データ準備開始")
        
        training_data = {}
        
        for race_id, race_data in collected_data.items():
            # 特徴量抽出
            race_features = self.feature_extractor.get_race_features(race_id)
            
            if race_features and race_data["results"]:
                training_data[race_id] = {
                    "features": race_features,
                    "results": race_data["results"]
                }
        
        logger.info(f"学習データ準備完了: {len(training_data)}レース")
        return training_data
    
    def train_prediction_model(self, training_data=None, epochs=10):
        """予測モデルの学習"""
        logger.info("予測モデル学習開始")
        
        if not training_data:
            # 過去データ収集
            collected_data = self.collect_historical_data(days=30)
            training_data = self.prepare_training_data(collected_data)
        
        # モデル学習
        history = self.prediction_model.train_model(training_data, epochs=epochs)
        
        logger.info("予測モデル学習完了")
        return history
    
    def predict_daily_races(self, date=None):
        """指定日の全レースを予測"""
        if date is None:
            date = datetime.datetime.now().strftime("%Y%m%d")
            
        logger.info(f"日次予測開始: {date}")
        
        # レース予定取得
        races = self.data_collector.get_race_schedule(date)
        predictions = {}
        
        # 各レースの予測
        for race in races:
            race_id = race["race_id"]
            
            # 特徴量抽出
            race_features = self.feature_extractor.get_race_features(race_id)
            
            if race_features:
                # 予測実行
                prediction = self.prediction_model.predict_race(race_features)
                predictions[race_id] = prediction
        
        # 予測結果を保存
        self.current_predictions.update(predictions)
        
        logger.info(f"日次予測完了: {len(predictions)}レース")
        return predictions
    
    def evaluate_daily_results(self, date=None):
        """指定日のレース結果を評価"""
        if date is None:
            date = datetime.datetime.now().strftime("%Y%m%d")
            
        logger.info(f"日次評価開始: {date}")
        
        # レース予定取得
        races = self.data_collector.get_race_schedule(date)
        evaluations = {}
        
        # 各レースの評価
        for race in races:
            race_id = race["race_id"]
            
            if race_id in self.current_predictions:
                prediction = self.current_predictions[race_id]
                
                # レース結果取得
                results = self.data_collector.get_race_results(race_id)
                
                if results:
                    # 予測評価
                    evaluation = self.prediction_model.evaluate_prediction(prediction, results)
                    evaluations[race_id] = evaluation
        
        logger.info(f"日次評価完了: {len(evaluations)}レース")
        return evaluations
    
    def get_performance_report(self, days=30):
        """成績レポート作成"""
        logger.info(f"成績レポート作成: 過去{days}日間")
        
        # 予測モデルの成績統計取得
        stats = self.prediction_model.get_performance_stats(days)
        
        # レポート作成
        report = {
            "period": stats["period"],
            "race_count": stats["race_count"],
            "hit_rates": {
                "average": stats["avg_hit_rate"],
                "win": stats["win_hit_rate"],
                "exacta": stats["exacta_hit_rate"],
                "quinella": stats["quinella_hit_rate"],
                "trio": stats["trio_hit_rate"]
            },
            "recent_predictions": {}
        }
        
        # 直近の予測
        current_date = datetime.datetime.now().strftime("%Y%m%d")
        for race_id, prediction in self.current_predictions.items():
            if race_id.startswith(current_date):
                report["recent_predictions"][race_id] = prediction
        
        return report
    
    def daily_update_routine(self):
        """日次更新ルーチン"""
        logger.info("日次更新ルーチン開始")
        
        today = datetime.datetime.now().strftime("%Y%m%d")
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y%m%d")
        
        # 1. 今日のデータ収集
        self.data_collector.collect_daily_data(today)
        
        # 2. 昨日のレース結果収集
        self.data_collector.collect_race_results(yesterday)
        
        # 3. 昨日の予測評価
        self.evaluate_daily_results(yesterday)
        
        # 4. 今日のレース予測
        self.predict_daily_races(today)
        
        # 5. モデルの定期再学習（週に1回など）
        current_weekday = datetime.datetime.now().weekday()
        if current_weekday == 0:  # 月曜日に再学習
            collected_data = self.collect_historical_data(days=30)
            training_data = self.prepare_training_data(collected_data)
            self.train_prediction_model(training_data)
        
        logger.info("日次更新ルーチン完了")
    

    def start_scheduled_tasks(self):
        """スケジュールされたタスクを開始"""
        logger.info("スケジュールタスク開始")
        
        # 毎日朝6時にデータ収集と予測実行
        schedule.every().day.at("06:00").do(self.daily_update_routine)
        
        # 毎時0分にレース結果をチェック
        schedule.every().hour.at(":00").do(self.check_race_results)
        
        # 毎時30分に直近レースの予測を更新
        schedule.every().hour.at(":30").do(self.update_upcoming_predictions)
        
        # スケジュールタスクの実行
        while True:
            schedule.run_pending()
            time.sleep(60)  # 1分ごとにスケジュールをチェック
    
    def check_race_results(self):
        """直近のレース結果をチェックして評価"""
        logger.info("レース結果チェック実行")
        
        current_datetime = datetime.datetime.now()
        current_date = current_datetime.strftime("%Y%m%d")
        current_hour = current_datetime.hour
        
        # 現在時刻より前のレースを対象
        races = self.data_collector.get_race_schedule(current_date)
        target_races = []
        
        for race in races:
            race_number = int(race["race_id"][10:12])
            # 競艇は通常1レース30分間隔で進行、レースは12時から開始と仮定
            race_hour = 12 + (race_number - 1) // 2
            if race_hour < current_hour:
                target_races.append(race)
        
        # 結果取得と評価
        for race in target_races:
            race_id = race["race_id"]
            
            # 既に評価済みかチェック
            if race_id in self.prediction_model.race_history:
                continue
            
            # レース結果取得
            results = self.data_collector.get_race_results(race_id)
            
            if race_id in self.current_predictions and results:
                # 予測評価
                evaluation = self.prediction_model.evaluate_prediction(
                    self.current_predictions[race_id], 
                    results
                )
                logger.info(f"レース評価完了: {race_id}, 的中率: {evaluation['hit_rate']:.2f}")
        
        return True
    
    def update_upcoming_predictions(self):
        """直近のレース予測を更新"""
        logger.info("直近レース予測更新実行")
        
        current_datetime = datetime.datetime.now()
        current_date = current_datetime.strftime("%Y%m%d")
        current_hour = current_datetime.hour
        
        # 現在時刻以降のレースを対象
        races = self.data_collector.get_race_schedule(current_date)
        upcoming_races = []
        
        for race in races:
            race_number = int(race["race_id"][10:12])
            # 競艇は通常1レース30分間隔で進行、レースは12時から開始と仮定
            race_hour = 12 + (race_number - 1) // 2
            if race_hour >= current_hour and race_hour <= current_hour + 2:
                upcoming_races.append(race)
        
        # 最新データで予測更新
        for race in upcoming_races:
            race_id = race["race_id"]
            
            # 最新のデータを取得
            self.data_collector.get_race_entries(race_id)
            self.data_collector.get_water_condition(race_id)
            self.data_collector.get_racer_comments(race_id)
            
            # 特徴量抽出
            race_features = self.feature_extractor.get_race_features(race_id)
            
            if race_features:
                # 予測更新
                prediction = self.prediction_model.predict_race(race_features)
                self.current_predictions[race_id] = prediction
                logger.info(f"レース予測更新: {race_id}")
        
        return True
    
    def get_race_prediction(self, race_id):
        """特定レースの予測を取得"""
        logger.info(f"レース予測取得: {race_id}")
        
        # 予測が既にある場合は返す
        if race_id in self.current_predictions:
            return self.current_predictions[race_id]
        
        # ない場合は新規予測
        race_features = self.feature_extractor.get_race_features(race_id)
        
        if race_features:
            prediction = self.prediction_model.predict_race(race_features)
            self.current_predictions[race_id] = prediction
            return prediction
        
        return None
    
    def generate_daily_report(self, date=None):
        """日次レポート生成"""
        if date is None:
            date = datetime.datetime.now().strftime("%Y%m%d")
            
        logger.info(f"日次レポート生成: {date}")
        
        # レース結果の取得
        races = self.data_collector.get_race_schedule(date)
        race_results = {}
        
        for race in races:
            race_id = race["race_id"]
            results = self.data_collector.get_race_results(race_id)
            if results:
                race_results[race_id] = results
        
        # 予測と実績の比較
        predictions = {}
        evaluations = {}
        
        for race_id, results in race_results.items():
            if race_id in self.current_predictions:
                predictions[race_id] = self.current_predictions[race_id]
                
                # 予測評価
                evaluation = self.prediction_model.evaluate_prediction(
                    self.current_predictions[race_id], 
                    results
                )
                evaluations[race_id] = evaluation
        
        # 的中率集計
        hit_rates = {
            "win": sum(1 for e in evaluations.values() if e["win_hit"]) / len(evaluations) if evaluations else 0,
            "exacta": sum(1 for e in evaluations.values() if e["exacta_hit"]) / len(evaluations) if evaluations else 0,
            "quinella": sum(1 for e in evaluations.values() if e["quinella_hit"]) / len(evaluations) if evaluations else 0,
            "trio": sum(1 for e in evaluations.values() if e["trio_hit"]) / len(evaluations) if evaluations else 0
        }
        
        # レポート作成
        report = {
            "date": date,
            "total_races": len(races),
            "finished_races": len(race_results),
            "predicted_races": len(predictions),
            "hit_rates": hit_rates,
            "race_details": {
                race_id: {
                    "venue": race["venue"],
                    "race_number": race["race_number"],
                    "prediction": predictions.get(race_id),
                    "result": race_results.get(race_id),
                    "evaluation": evaluations.get(race_id)
                } for race_id, race in [(r["race_id"], r) for r in races]
            }
        }
        
        return report
    
    def export_report_to_json(self, report, file_path=None):
        """レポートをJSONファイルにエクスポート"""
        if file_path is None:
            file_path = f"report_{report['date']}.json"
            
        logger.info(f"レポートエクスポート: {file_path}")
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            logger.info(f"レポートエクスポート完了: {file_path}")
            return True
        except Exception as e:
            logger.error(f"レポートエクスポートエラー: {str(e)}")
            return False
    
    def generate_web_report(self, date=None):
        """Web表示用レポート生成"""
        report = self.generate_daily_report(date)
        
        # HTML形式のレポート作成（実際はテンプレートエンジンを使用）
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>競艇AI予測レポート {report['date']}</title>
            <style>
                body {{ font-family: 'Hiragino Sans', 'Meiryo', sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                h1, h2, h3 {{ color: #0056b3; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th, td {{ padding: 10px; border: 1px solid #ddd; text-align: center; }}
                th {{ background-color: #0056b3; color: white; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
                .win {{ background-color: #d4edda; }}
                .lose {{ background-color: #f8d7da; }}
                .summary {{ display: flex; justify-content: space-around; margin-bottom: 20px; }}
                .summary-box {{ padding: 15px; background: #e9f2fb; border-radius: 5px; width: 22%; text-align: center; }}
                .summary-box h3 {{ margin-top: 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>競艇AI予測レポート {report['date']}</h1>
                
                <div class="summary">
                    <div class="summary-box">
                        <h3>総レース数</h3>
                        <p>{report['total_races']}</p>
                    </div>
                    <div class="summary-box">
                        <h3>終了レース</h3>
                        <p>{report['finished_races']}</p>
                    </div>
                    <div class="summary-box">
                        <h3>予測レース</h3>
                        <p>{report['predicted_races']}</p>
                    </div>
                    <div class="summary-box">
                        <h3>的中率（3連複）</h3>
                        <p>{report['hit_rates']['trio']:.2%}</p>
                    </div>
                </div>
                
                <h2>的中率サマリー</h2>
                <table>
                    <tr>
                        <th>単勝</th>
                        <th>2連単</th>
                        <th>2連複</th>
                        <th>3連複</th>
                    </tr>
                    <tr>
                        <td>{report['hit_rates']['win']:.2%}</td>
                        <td>{report['hit_rates']['exacta']:.2%}</td>
                        <td>{report['hit_rates']['quinella']:.2%}</td>
                        <td>{report['hit_rates']['trio']:.2%}</td>
                    </tr>
                </table>
                
                <h2>レース詳細</h2>
                <table>
                    <tr>
                        <th>会場</th>
                        <th>レース</th>
                        <th>予測1着</th>
                        <th>実際1着</th>
                        <th>予測2着</th>
                        <th>実際2着</th>
                        <th>予測3着</th>
                        <th>実際3着</th>
                        <th>単勝的中</th>
                        <th>3連複的中</th>
                    </tr>
        """
        
        # レース詳細行の追加
        for race_id, detail in report['race_details'].items():
            if detail['prediction'] and detail['result']:
                prediction = detail['prediction']
                # 予測順位別にソート
                predicted_boats = sorted(prediction['predictions'], key=lambda x: x['expected_value'])
                predicted_top3 = [p['boat_number'] for p in predicted_boats[:3]]
                
                # 実際の順位を取得
                actual_results = {r['boat_number']: r['rank'] for r in detail['result']}
                actual_top3 = sorted([(boat, rank) for boat, rank in actual_results.items() if rank <= 3], key=lambda x: x[1])
                actual_top3 = [boat for boat, _ in actual_top3]
                
                # 的中判定
                win_hit = actual_top3[0] == predicted_top3[0] if actual_top3 else False
                trio_hit = set(actual_top3) == set(predicted_top3) if actual_top3 and len(actual_top3) == 3 else False
                
                html_content += f"""
                <tr>
                    <td>{detail['venue']}</td>
                    <td>{detail['race_number']}</td>
                    <td>{predicted_top3[0]}</td>
                    <td>{actual_top3[0] if actual_top3 else '-'}</td>
                    <td>{predicted_top3[1]}</td>
                    <td>{actual_top3[1] if actual_top3 and len(actual_top3) > 1 else '-'}</td>
                    <td>{predicted_top3[2]}</td>
                    <td>{actual_top3[2] if actual_top3 and len(actual_top3) > 2 else '-'}</td>
                    <td class="{'win' if win_hit else 'lose'}">{win_hit}</td>
                    <td class="{'win' if trio_hit else 'lose'}">{trio_hit}</td>
                </tr>
                """
        
        html_content += """
                </table>
            </div>
        </body>
        </html>
        """
        
        return html_content
    
    def save_web_report(self, html_content, file_path=None, date=None):
        """Web表示用レポートの保存"""
        if date is None:
            date = datetime.datetime.now().strftime("%Y%m%d")
            
        if file_path is None:
            file_path = f"report_{date}.html"
            
        logger.info(f"Webレポート保存: {file_path}")
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logger.info(f"Webレポート保存完了: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Webレポート保存エラー: {str(e)}")
            return False

    def run_flask_api(self, host='0.0.0.0', port=5000):
        """Flask APIサーバーの実行"""
        from flask import Flask, jsonify, request, render_template_string
        
        app = Flask(__name__)
        
        @app.route('/api/races/today', methods=['GET'])
        def api_today_races():
            races = self.get_today_races()
            return jsonify(races)
        
        @app.route('/api/prediction/<race_id>', methods=['GET'])
        def api_race_prediction(race_id):
            prediction = self.get_race_prediction(race_id)
            if prediction:
                return jsonify(prediction)
            else:
                return jsonify({"error": "Prediction not available"}), 404
        
        @app.route('/api/report/<date>', methods=['GET'])
        def api_daily_report(date):
            report = self.get_daily_report(date)
            if report:
                return jsonify(report)
            else:
                return jsonify({"error": "Report not available"}), 404
        
        @app.route('/api/stats', methods=['GET'])
        def api_performance_stats():
            days = request.args.get('days', default=30, type=int)
            stats = self.get_performance_stats(days)
            return jsonify(stats)
        
        @app.route('/web/report/<date>', methods=['GET'])
        def web_report(date):
            web_report = self.get_web_report(date)
            return render_template_string(web_report)
        
        @app.route('/', methods=['GET'])
        def home():
            today = datetime.datetime.now().strftime("%Y%m%d")
            return f'<html><head><meta http-equiv="refresh" content="0; URL=/web/report/{today}" /></head></html>'
        
        # API サーバー起動
        logger.info(f"Flask API サーバー起動: {host}:{port}")
        app.run(host=host, port=port, debug=False)

if __name__ == "__main__":
    main()
