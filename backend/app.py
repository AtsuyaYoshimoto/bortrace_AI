from flask import Flask, jsonify, request, make_response
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
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

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

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return "競艇予想AI API サーバー - 全競艇場対応版"

@app.route('/api/test', methods=['GET'])
def test():
    return jsonify({"status": "success", "message": "API is working!"})

@app.route('/api/races/today', methods=['GET'])
def get_today_races():
    races = [
        {"race_id": "202505251201", "venue": "住之江", "race_number": 12}
    ]
    return jsonify(races)

@app.route('/api/prediction/<race_id>', methods=['GET', 'POST'])
def get_race_prediction(race_id):
    try:
        if not AI_AVAILABLE:
            return jsonify(get_mock_prediction(race_id))
            
        prediction = ai_model.get_race_prediction(race_id)
        return jsonify(prediction)
        
    except Exception as e:
        print(f"AI予想エラー: {str(e)}")
        return jsonify(get_mock_prediction(race_id))

def get_mock_prediction(race_id):
    # 既存のモックデータをここに移動
    return {
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

# 会場コード一覧エンドポイント（拡張版）
@app.route('/api/venues', methods=['GET'])
def get_venues():
    venues = {
        "01": {"name": "桐生", "location": "群馬県", "region": "関東"},
        "02": {"name": "戸田", "location": "埼玉県", "region": "関東"},
        "03": {"name": "江戸川", "location": "東京都", "region": "関東"},
        "04": {"name": "平和島", "location": "東京都", "region": "関東"},
        "05": {"name": "多摩川", "location": "東京都", "region": "関東"},
        "06": {"name": "浜名湖", "location": "静岡県", "region": "中部"},
        "07": {"name": "蒲郡", "location": "愛知県", "region": "中部"},
        "08": {"name": "常滑", "location": "愛知県", "region": "中部"},
        "09": {"name": "津", "location": "三重県", "region": "中部"},
        "10": {"name": "三国", "location": "福井県", "region": "中部"},
        "11": {"name": "びわこ", "location": "滋賀県", "region": "関西"},
        "12": {"name": "住之江", "location": "大阪府", "region": "関西"},
        "13": {"name": "尼崎", "location": "兵庫県", "region": "関西"},
        "14": {"name": "鳴門", "location": "徳島県", "region": "中国・四国"},
        "15": {"name": "丸亀", "location": "香川県", "region": "中国・四国"},
        "16": {"name": "児島", "location": "岡山県", "region": "中国・四国"},
        "17": {"name": "宮島", "location": "広島県", "region": "中国・四国"},
        "18": {"name": "徳山", "location": "山口県", "region": "中国・四国"},
        "19": {"name": "下関", "location": "山口県", "region": "中国・四国"},
        "20": {"name": "若松", "location": "福岡県", "region": "九州"},
        "21": {"name": "芦屋", "location": "福岡県", "region": "九州"},
        "22": {"name": "福岡", "location": "福岡県", "region": "九州"},
        "23": {"name": "唐津", "location": "佐賀県", "region": "九州"},
        "24": {"name": "大村", "location": "長崎県", "region": "九州"}
    }
    return jsonify(venues)

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
    
    # レース履歴テーブルも追加
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
        time.sleep(0.5)
        
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

def build_race_url(venue_code, race_number, date_str):
    """レースURLを構築"""
    base_url = "https://boatrace.jp/owpc/pc/race/racelist"
    url = f"{base_url}?rno={race_number}&jcd={venue_code}&hd={date_str}"
    return url

def get_today_date():
    """今日の日付を取得（YYYYMMDD形式）"""
    return datetime.now().strftime("%Y%m%d")

# 拡張版のスクレイピングエンドポイント
@app.route('/api/race-data', methods=['GET'])
def get_race_data():
    """拡張版：任意の会場・レースのデータ取得"""
    try:
        # パラメータ取得
        venue_code = request.args.get('venue', '01')  # デフォルト：桐生
        race_number = request.args.get('race', '1')   # デフォルト：1R
        date_str = request.args.get('date', get_today_date())  # デフォルト：今日
        
        # バリデーション
        if venue_code not in [f"{i:02d}" for i in range(1, 25)]:
            return jsonify({
                "error": "無効な会場コードです",
                "valid_codes": "01-24"
            }), 400
            
        if not race_number.isdigit() or not (1 <= int(race_number) <= 12):
            return jsonify({
                "error": "無効なレース番号です",
                "valid_range": "1-12"
            }), 400
        
        # URLを構築
        race_url = build_race_url(venue_code, race_number, date_str)
        
        print(f"データ取得開始... URL: {race_url}")
        race_data = get_race_info_improved(race_url)
        
        if race_data["status"] == "error":
            return jsonify({
                "error": "データ取得失敗",
                "message": race_data["message"],
                "suggestion": "30分後に再試行してください",
                "url": race_url
            }), 500
        
        print("選手データ抽出開始...")
        racer_data = extract_racer_data_final(race_data["content"])
        
        # 会場情報を取得
        venues = get_venues().get_json()
        venue_info = venues.get(venue_code, {"name": "不明", "location": "不明"})
        
        return jsonify({
            "data_acquisition": {
                "status": race_data["status"],
                "length": race_data["length"],
                "encoding": race_data["encoding"],
                "url": race_url
            },
            "race_info": {
                "venue_code": venue_code,
                "venue_name": venue_info["name"],
                "venue_location": venue_info["location"],
                "race_number": race_number,
                "date": date_str
            },
            "racer_extraction": racer_data,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "suggestion": "システム側の問題です。後ほど再試行してください。"
        }), 500

@app.route('/api/real-data-test', methods=['GET'])  
def real_data_test():
    """既存エンドポイント（桐生1R・キャッシュ対応版）"""
    cache_key = "real_data_test_01"
    
    # キャッシュ確認
    cached_result = get_cached_data(cache_key, 30)  # 30分キャッシュ
    if cached_result:
        print("キャッシュからデータを返却")
        return jsonify(cached_result)
    
    try:
        venue_code = '01'
        race_number = '1'
        date_str = get_today_date()
        
        race_url = build_race_url(venue_code, race_number, date_str)
        
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
        
        result = {
            "data_acquisition": {
                "status": race_data["status"],
                "length": race_data["length"],
                "encoding": race_data["encoding"]
            },
            "racer_extraction": racer_data,
            "timestamp": datetime.now().isoformat(),
            "html_sample": str(race_data["content"][:500])
        }
        
        # キャッシュに保存
        set_cached_data(cache_key, result)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "suggestion": "システム側の問題です。後ほど再試行してください。"
        })
        
@app.route('/api/kyotei/<venue_code>', methods=['GET'])
def get_kyotei_data(venue_code):
    """指定された競艇場のデータを取得（キャッシュ対応版）"""
    cache_key = f"kyotei_data_{venue_code}"
    
    # キャッシュ確認
    cached_result = get_cached_data(cache_key, 30)  # 30分キャッシュ
    if cached_result:
        print(f"キャッシュからデータを返却: {venue_code}")
        return jsonify(cached_result)
    
    try:
        # 今日の日付を取得
        today = datetime.datetime.now().strftime("%Y%m%d")
        
        # 動的なURL生成（venue_codeを使用）
        race_url = f"https://boatrace.jp/owpc/pc/race/racelist?rno=1&jcd={venue_code}&hd={today}"
        
        print(f"データ取得開始... 会場コード: {venue_code}")
        race_data = get_race_info_improved(race_url)
        
        if race_data["status"] == "error":
            return jsonify({
                "error": "データ取得失敗",
                "venue_code": venue_code,
                "message": race_data["message"],
                "suggestion": "30分後に再試行してください"
            })
        
        print("選手データ抽出開始...")
        racer_data = extract_racer_data_final(race_data["content"])
        
        # 会場名を取得
        venues = get_venues().get_json()
        venue_info = venues.get(venue_code, {"name": "不明", "location": "不明"})
        
        result = {
            "venue_code": venue_code,
            "venue_name": venue_info["name"],
            "data_acquisition": {
                "status": race_data["status"],
                "length": race_data["length"],
                "encoding": race_data["encoding"]
            },
            "racer_extraction": racer_data,
            "timestamp": datetime.now().isoformat(),
            "race_url": race_url
        }
        
        # キャッシュに保存
        set_cached_data(cache_key, result)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "venue_code": venue_code,
            "suggestion": "システム側の問題です。後ほど再試行してください。"
        })

# 複数レースの一括取得エンドポイント
@app.route('/api/venue-races', methods=['GET'])
def get_venue_races():
    """指定会場の全レース情報を取得"""
    try:
        venue_code = request.args.get('venue', '01')
        date_str = request.args.get('date', get_today_date())
        max_races = int(request.args.get('max_races', '3'))  # 負荷軽減のため最大3レースまで
        
        results = []
        
        for race_num in range(1, min(max_races + 1, 13)):  # 1Rから指定レース数まで
            try:
                race_url = build_race_url(venue_code, str(race_num), date_str)
                race_data = get_race_info_improved(race_url)
                
                if race_data["status"] == "success":
                    racer_data = extract_racer_data_final(race_data["content"])
                    
                    if racer_data["status"] == "success" and racer_data["found_count"] > 0:
                        results.append({
                            "race_number": race_num,
                            "racers": racer_data["racers"],
                            "status": "success"
                        })
                    else:
                        results.append({
                            "race_number": race_num,
                            "status": "no_data",
                            "message": "選手データが見つかりません"
                        })
                else:
                    results.append({
                        "race_number": race_num,
                        "status": "error",
                        "message": race_data["message"]
                    })
                    
                # レース間の遅延
                time.sleep(1)
                
            except Exception as e:
                results.append({
                    "race_number": race_num,
                    "status": "error", 
                    "message": str(e)
                })
        
        # 会場情報を取得
        venues = get_venues().get_json()
        venue_info = venues.get(venue_code, {"name": "不明", "location": "不明"})
        
        return jsonify({
            "venue_info": {
                "code": venue_code,
                "name": venue_info["name"],
                "location": venue_info["location"]
            },
            "date": date_str,
            "races": results,
            "total_races": len(results),
            "successful_races": len([r for r in results if r["status"] == "success"]),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "suggestion": "システム側の問題です。後ほど再試行してください。"
        }), 500

cache_data = {}
cache_lock = threading.Lock()

def get_cached_data(cache_key, expiry_minutes=30):
    """キャッシュからデータを取得"""
    with cache_lock:
        if cache_key in cache_data:
            data, timestamp = cache_data[cache_key]
            if datetime.now() - timestamp < timedelta(minutes=expiry_minutes):
                return data
    return None

def set_cached_data(cache_key, data):
    """キャッシュにデータを保存"""
    with cache_lock:
        cache_data[cache_key] = (data, datetime.now())

@app.route('/api/race-features/<race_id>', methods=['GET'])
def get_race_features(race_id):
    try:
        if not AI_AVAILABLE:
            return jsonify({"error": "AI model not available"}), 503
            
        features = ai_model.feature_extractor.get_race_features(race_id)
        return jsonify(features)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/ai-predict', methods=['POST'])
def ai_predict():
    if not AI_AVAILABLE:
        return jsonify({"error": "AI model not available"}), 503
    
    data = request.get_json()
    try:
        prediction = ai_model.predict(data['racers'])
        return jsonify({"prediction": prediction})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/ai-status')
def ai_status():
    return jsonify({
        "ai_available": AI_AVAILABLE,
        "status": "ok",
        "model_type": "deep_learning" if AI_AVAILABLE else "mock"
    })

@app.route('/api/ai-debug')
def ai_debug():
    import traceback
    try:
        from boat_race_prediction_system import BoatRaceAI
        model = BoatRaceAI()
        return jsonify({"status": "success", "message": "AI model loaded"})
    except Exception as e:
        return jsonify({
            "status": "failed",
            "error": str(e),
            "traceback": traceback.format_exc().split('\n')
        })

@app.route('/api/ai-prediction-simple', methods=['POST'])
def ai_prediction_simple():
    data = request.get_json()
    try:
        if AI_AVAILABLE:
            racers = data.get('racers', [])
            venue_code = data.get('venue_code', '01')
            
            # AIクラスに処理を委譲
            result = ai_model.get_comprehensive_prediction(racers, venue_code)
            return jsonify(result)
        else:
            return jsonify({"error": "AI not available"})
            
    except Exception as e:
        print(f"AI予想エラー: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/train-daily', methods=['GET', 'POST'])
def train_daily():
    try:
        if AI_AVAILABLE:
            # 過去3日分のデータで学習
            ai_model.train_prediction_model(epochs=5)
            return jsonify({"status": "success", "message": "Daily training completed"})
        else:
            return jsonify({"error": "AI not available"}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# バックグラウンドでデータ収集開始
import threading
#scheduler_thread = threading.Thread(target=ai_model.start_scheduled_tasks)
#scheduler_thread.daemon = True
#scheduler_thread.start()
#logger.info("データ収集スケジューラー開始")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
    
