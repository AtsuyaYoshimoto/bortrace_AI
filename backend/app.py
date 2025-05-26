from flask import Flask, jsonify, request
import os
import requests
from bs4 import BeautifulSoup
import sqlite3
import datetime
import time
import random
import re

app = Flask(__name__)

# CORSの設定
@app.after_request
def add_cors_headers(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response

@app.route('/')
def index():
    return "競艇予想AI API サーバー"

@app.route('/api/test', methods=['GET'])
def test():
    return jsonify({"status": "success", "message": "API is working!"})

@app.route('/api/races/today', methods=['GET'])
def get_today_races():
    races = [
        {"race_id": "202505251201", "venue": "住之江", "race_number": 12}
    ]
    return jsonify(races)

# 既存のエンドポイント（残す）
@app.route('/api/prediction/<race_id>', methods=['GET', 'POST'])
def get_race_prediction(race_id):
    # モックデータを返す
    prediction = {
        "race_id": race_id,
        "predictions": [
            {"racer_id": 1, "boat_number": 1, "predicted_rank": 1, "rank_probabilities": [0.8, 0.1, 0.05, 0.03, 0.01, 0.01], "expected_value": 1.2},
            {"racer_id": 2, "boat_number": 2, "predicted_rank": 3, "rank_probabilities": [0.1, 0.2, 0.4, 0.2, 0.08, 0.02], "expected_value": 2.8},
            {"racer_id": 3, "boat_number": 3, "predicted_rank": 2, "rank_probabilities": [0.15, 0.5, 0.25, 0.08, 0.01, 0.01], "expected_value": 2.3},
            {"racer_id": 4, "boat_number": 4, "predicted_rank": 5, "rank_probabilities": [0.02, 0.05, 0.1, 0.2, 0.4, 0.23], "expected_value": 4.8},
            {"racer_id": 5, "boat_number": 5, "predicted_rank": 4, "rank_probabilities": [0.03, 0.08, 0.15, 0.35, 0.3, 0.09], "expected_value": 4.2},
            {"racer_id": 6, "boat_number": 6, "predicted_rank": 6, "rank_probabilities": [0.01, 0.02, 0.05, 0.12, 0.2, 0.6], "expected_value": 5.4}
        ],
        "forecast": {
            "win": 1,
            "quinella": [1, 3],
            "exacta": [1, 3],
            "trio": [1, 3, 2]
        }
    }
    return jsonify(prediction)

# 既存のエンドポイント（残す）
@app.route('/api/stats', methods=['GET'])
def get_performance_stats():
    stats = {
        "period": "過去30日間",
        "race_count": 150,
        "avg_hit_rate": 0.75,
        "win_hit_rate": 0.945,
        "exacta_hit_rate": 0.823,
        "quinella_hit_rate": 0.887,
        "trio_hit_rate": 0.678
    }
    return jsonify(stats)

# 会場コード一覧エンドポイント
@app.route('/api/venues', methods=['GET'])
def get_venues():
    venues = {
        "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島",
        "05": "多摩川", "06": "浜名湖", "07": "蒲郡", "08": "常滑",
        "09": "津", "10": "三国", "11": "びわこ", "12": "住之江",
        "13": "尼崎", "14": "鳴門", "15": "丸亀", "16": "児島",
        "17": "宮島", "18": "徳山", "19": "下関", "20": "若松",
        "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村"
    }
    return jsonify(venues)

# 新しい /api/kyotei/<venue_code> エンドポイント
@app.route('/api/kyotei/<venue_code>', methods=['GET'])
def get_kyotei_data(venue_code):
    """指定された競艇場のデータを取得"""
    try:
        # 今日の日付を取得
        today = datetime.datetime.now().strftime("%Y%m%d")
        
        # 動的なURL生成（venue_codeを使用）
        race_url = f"https://boatrace.jp/owpc/pc/race/racelist?rno=1&jcd={venue_code}&hd={today}"
        
        print(f"データ取得開始... 会場コード: {venue_code}")
        race_data = get_race_info_improved(race_url)

         # 会場名取得用（新しいエンドポイント内で定義）
        venues = {
            "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島",
            "05": "多摩川", "06": "浜名湖", "07": "蒲郡", "08": "常滑",
            "09": "津", "10": "三国", "11": "びわこ", "12": "住之江",
            "13": "尼崎", "14": "鳴門", "15": "丸亀", "16": "児島",
            "17": "宮島", "18": "徳山", "19": "下関", "20": "若松",
            "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村"
        }
        venue_name = venues.get(venue_code, "不明")
        
        if race_data["status"] == "error":
            return jsonify({
                "error": "データ取得失敗",
                "venue_code": venue_code,
                "message": race_data["message"],
                "suggestion": "30分後に再試行してください"
            })
        
        print("選手データ抽出開始...")
        racer_data = extract_racer_data_final(race_data["content"])
        
        # 定数から会場名を取得（重複解消）
        venue_name = VENUES.get(venue_code, "不明")
        
        return jsonify({
            "venue_code": venue_code,
            "venue_name": venue_name,
            "data_acquisition": {
                "status": race_data["status"],
                "length": race_data["length"],
                "encoding": race_data["encoding"]
            },
            "racer_extraction": racer_data,
            "timestamp": datetime.datetime.now().isoformat(),
            "race_url": race_url
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "venue_code": venue_code,
            "suggestion": "システム側の問題です。後ほど再試行してください。"
        })

# データベース関連
def initialize_database():
    conn = sqlite3.connect('boatrace_data.db')
    cursor = conn.cursor()
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
    conn.commit()
    conn.close()

@app.route('/api/init-db', methods=['POST'])
def init_database():
    initialize_database()
    return jsonify({"status": "Database initialized"})

# スクレイピング関連の関数
def get_race_info_improved(race_url):
    """改良版のレース情報取得（基本版）"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate',
        'Referer': 'https://boatrace.jp/',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0'
    }
    
    try:
        # 固定の遅延（2秒）
        time.sleep(2)
        
        response = requests.get(race_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        return {
            "status": "success",
            "content": response.content,
            "text": response.text,
            "length": len(response.content),
            "encoding": response.encoding
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

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
        return {"status": "error", "message": str(e)}

# メインのスクレイピングエンドポイント
@app.route('/api/real-data-test', methods=['GET'])  
def real_data_test():
    """改良版のリアルデータテスト"""
    try:
        race_url = "https://boatrace.jp/owpc/pc/race/racelist?rno=1&jcd=01&hd=20250525"
        
        print("データ取得開始...")
        race_data = get_race_info_improved(race_url)
        
        if race_data["status"] == "error":
            return jsonify({
                "error": "データ取得失敗",
                "message": race_data["message"],
                "suggestion": "30分後に再試行してください"
            })
        
        print("選手データ抽出開始...")
        racer_data = extract_racer_data_final(race_data["content"])
        
        return jsonify({
            "data_acquisition": {
                "status": race_data["status"],
                "length": race_data["length"],
                "encoding": race_data["encoding"]
            },
            "racer_extraction": racer_data,
            "timestamp": datetime.datetime.now().isoformat(),
            "html_sample": str(race_data["content"][:500])
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "suggestion": "システム側の問題です。後ほど再試行してください。"
        })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
