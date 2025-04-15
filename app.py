from flask import Flask, request, jsonify, render_template, Response, g
import sqlite3
import datetime
import threading

app = Flask(__name__)

DATABASE = 'database.db'
latest_data = {}
clients = []

# ---------- Database Helpers ----------
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE, check_same_thread=False)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            pH TEXT,
            EC TEXT,
            TDS TEXT,
            DO TEXT,
            Lat TEXT,
            Lon TEXT
        )''')
        db.commit()

# ---------- SSE Broadcaster ----------
def notify_clients():
    for queue in clients:
        queue.put("data: update\n\n")

# ---------- Routes ----------
@app.route('/')
def dashboard():
    return render_template('index.html')

@app.route('/lora', methods=['POST'])
def receive_data():
    global latest_data
    try:
        raw = request.get_data(as_text=True)
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] Received: {raw}")

        # Parse key:value,key:value,...
        parts = raw.split(',')
        latest_data = {k.strip(): v.strip() for k, v in (pair.split(':') for pair in parts if ':' in pair)}
        latest_data["timestamp"] = timestamp

        # Save to database
        db = get_db()
        db.execute('''INSERT INTO sensor_data (timestamp, pH, EC, TDS, DO, Lat, Lon)
                      VALUES (?, ?, ?, ?, ?, ?, ?)''', (
                          timestamp,
                          latest_data.get('pH'),
                          latest_data.get('EC'),
                          latest_data.get('TDS'),
                          latest_data.get('DO'),
                          latest_data.get('Lat'),
                          latest_data.get('Lon')
                      ))
        db.commit()

        notify_clients()
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/lora/latest')
def get_latest():
    return jsonify(latest_data)

@app.route('/stream')
def stream():
    def event_stream():
        import queue
        q = queue.Queue()
        clients.append(q)
        try:
            while True:
                yield q.get()
        except GeneratorExit:
            clients.remove(q)
    return Response(event_stream(), mimetype="text/event-stream")

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
