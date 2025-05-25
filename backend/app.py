from flask import Flask, jsonify, request
import os
import requests
from bs4 import BeautifulSoup
import sqlite3
import datetime

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

# 競艇公式サイトからデータ取得（基本版）
def get_race_info_basic(venue_code, date):
    """基本的なレース情報取得"""
    try:
        # 競艇公式サイトの構造に合わせてスクレイピング
        url = f"https://boatrace.jp/owpc/pc/race/racelist?rno=1&jcd={venue_code}&hd={date}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            # 基本的な情報取得テスト
            title = soup.find('title')
            return {
                "status": "success", 
                "message": "データ取得成功",
                "url": url,
                "title": title.text if title else "タイトル不明",
                "response_length": len(response.content)
            }
        else:
            return {"status": "error", "message": f"HTTPエラー: {response.status_code}"}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}

def extract_racer_data(html_content):
    """出走表HTMLから選手情報を抽出"""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 選手データの抽出（基本版）
        racers = []
        
        # 実際のHTML構造に合わせて要素を取得
        # ※ 実際の構造解析が必要
        racer_elements = soup.find_all('td', class_='racer-name')  # 仮の要素名
        
        for i, element in enumerate(racer_elements[:6]):  # 6艇分
            racers.append({
                "boat_number": i + 1,
                "name": element.get_text().strip() if element else f"選手{i+1}",
                "racer_id": f"test_{i+1}",
                "grade": "A1"  # 仮データ
            })
            
        return {"status": "success", "racers": racers}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

# テスト用エンドポイント追加
@app.route('/api/scrape-test', methods=['GET'])
def test_scraping():
    result = get_race_info_basic("01", "20250525")  # 桐生、今日の日付
    return jsonify(result)

@app.route('/api/real-data-test', methods=['GET'])
def test_real_data():
    # HTMLデータ取得
    result = get_race_info_basic("01", "20250525")
    
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
