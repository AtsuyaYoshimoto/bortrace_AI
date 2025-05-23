from flask import Flask, jsonify, request
import os
import sys

# AIモデルのインポート
from boat_race_prediction_system import BoatRaceAI, BoatRaceWebAPI

app = Flask(__name__)

# CORSの設定
@app.after_request
def add_cors_headers(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response

# AIシステム初期化
boat_race_ai = BoatRaceAI()
api = BoatRaceWebAPI(boat_race_ai)

@app.route('/')
def index():
    return "競艇予想AI API サーバー"

@app.route('/api/test', methods=['GET'])
def test():
    return jsonify({"status": "success", "message": "API is working!"})

@app.route('/api/races/today', methods=['GET'])
def get_today_races():
    races = api.get_today_races()
    return jsonify(races)

@app.route('/api/prediction/<race_id>', methods=['POST', 'GET'])
def get_race_prediction(race_id):
    prediction = api.get_race_prediction(race_id)
    if prediction:
        return jsonify(prediction)
    else:
        return jsonify({"error": "Prediction not available"}), 404

@app.route('/api/stats', methods=['GET'])
def get_performance_stats():
    days = request.args.get('days', default=30, type=int)
    stats = api.get_performance_stats(days)
    return jsonify(stats)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
