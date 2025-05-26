from flask import Flask, jsonify, request
import os
import requests
from bs4 import BeautifulSoup
import sqlite3
import datetime
import time
import random

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

# 新規追加
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

# 新規エンドポイント
@app.route('/api/init-db', methods=['POST'])
def init_database():
    initialize_database()
    return jsonify({"status": "Database initialized"})

@app.route('/api/real-data-test-improved', methods=['GET'])
def real_data_test_improved():
    """改良版のリアルデータテスト"""
    try:
        race_url = "https://boatrace.jp/owpc/pc/race/racelist?rno=1&jcd=01&hd=20250525"
        
        # 段階的にアクセス
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
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "suggestion": "システム側の問題です。後ほど再試行してください。"
        })
        
def extract_racer_data_final(html_content):
    """最終版：選手情報抽出"""
    try:
        import re
        
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
        
# テスト用エンドポイント追加
@app.route('/api/scrape-test', methods=['GET'])
def test_scraping():
    result = get_race_info_basic("01", "20250525")  # 桐生、今日の日付
    return jsonify(result)

@app.route('/api/real-data-test', methods=['GET'])  
def real_data_test():
    race_data = get_race_info_improved(race_url)  # ← 修正
    racer_data = extract_racer_data_final(race_data["content"])  # ← 修正
    
    if result["status"] == "success":
        # 実際に取得したHTMLを使用
        url = result["url"]
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        
        # 実際のHTMLを解析
        racers = extract_racer_data(response.content)
        return jsonify({
            "data_acquisition": result,
            "racer_extraction": racers,
            "html_sample": str(response.content[:500])  # 最初の500文字をサンプル表示
        })
    else:
        return jsonify(result)
        
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
