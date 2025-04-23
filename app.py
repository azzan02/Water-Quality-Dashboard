from flask import Flask, request, jsonify, render_template, Response, g
import sqlite3
import datetime
import json
import queue
import threading
import time
import traceback
import joblib
import os
import numpy as np

app = Flask(__name__, static_folder='static')

# Enable CORS if needed
# from flask_cors import CORS
# CORS(app)

DATABASE = 'database.db'
latest_data = {}
clients = []
data_lock = threading.Lock()

# Load the arsenic prediction model
MODEL_PATH = 'Random_Forest_(Dissolved_Arsenic).joblib'
arsenic_model = None

def load_model():
    global arsenic_model
    try:
        print(f"Attempting to load model from {os.path.abspath(MODEL_PATH)}")
        if os.path.exists(MODEL_PATH):
            arsenic_model = joblib.load(MODEL_PATH)
            print(f"Successfully loaded arsenic prediction model from {MODEL_PATH}")
        else:
            print(f"Warning: Model file {MODEL_PATH} not found at path: {os.path.abspath(MODEL_PATH)}")
    except Exception as e:
        print(f"Error loading model: {str(e)}")
        print(traceback.format_exc())  # More detailed error info

# Load the model when app starts
load_model()

# Function to predict arsenic concentration
def predict_arsenic(tds, ec, temp):
    try:
        if arsenic_model is None:
            print("Warning: No model loaded, cannot predict arsenic")
            return None
            
        # Prepare input features as expected by the model
        features = np.array([[tds, ec, temp]])
        
        # Make prediction
        prediction = arsenic_model.predict(features)[0]
        
        # Return the prediction rounded to 3 decimal places
        return round(float(prediction), 3)
    except Exception as e:
        print(f"Error predicting arsenic: {str(e)}")
        return None

# ---------- Database Helpers ----------
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
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
        # Create table if it doesn't exist
        db.execute('''CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            pH REAL,
            EC REAL,
            TDS REAL,
            DO REAL,
            Temp REAL,
            Arsenic REAL,
            Lat TEXT,
            Lon TEXT
        )''')
        
        # Check if Temp column exists, if not add it
        try:
            db.execute('ALTER TABLE sensor_data ADD COLUMN Temp REAL')
            print("Added Temp column to existing database")
        except sqlite3.OperationalError as e:
            # Column might already exist, which will cause an error
            if "duplicate column name" not in str(e):
                print(f"Note: {e}")
        
        # Check if Arsenic column exists, if not add it
        try:
            db.execute('ALTER TABLE sensor_data ADD COLUMN Arsenic REAL')
            print("Added Arsenic column to existing database")
        except sqlite3.OperationalError as e:
            # Column might already exist, which will cause an error
            if "duplicate column name" not in str(e):
                print(f"Note: {e}")
            
        db.commit()
        print("Database initialized")

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def get_recent_data(limit=20):
    db = get_db()
    db.row_factory = dict_factory
    cursor = db.cursor()
    cursor.execute('SELECT * FROM sensor_data ORDER BY id DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()
    return rows[::-1]  # Reverse to get chronological order

# ---------- SSE Broadcaster ----------
def notify_clients():
    print(f"Notifying {len(clients)} clients")
    for client_queue in clients[:]:  # Copy the list to avoid modification during iteration
        try:
            client_queue.put("data: update\n\n")
            print("Notification sent to client")
        except Exception as e:
            print(f"Error notifying client: {str(e)}")
            if client_queue in clients:
                clients.remove(client_queue)

# ---------- Routes ----------
@app.route('/')
def dashboard():
    print("Serving dashboard")
    return render_template('index.html')

@app.route('/lora', methods=['POST'])
def receive_data():
    global latest_data
    try:
        raw = request.get_data(as_text=True)
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] Received: {raw}")

        # Parse the raw data as JSON
        try:
            json_data = json.loads(raw)
            message = json_data.get("message", "")
        except json.JSONDecodeError:
            print("Error: Received data is not valid JSON")
            return jsonify({'status': 'error', 'message': 'Invalid JSON format'}), 400    

        # Parse key:value,key:value,...
        print("RAW", raw)
        parts = message.split(",")
        data = {}
        
        for part in parts:
            if ':' in part:
                key_value = part.split(':', 1)  # Split only on first colon
                if len(key_value) == 2:
                    key, value = key_value
                    data[key.strip()] = value.strip()
                    print(f"Parsed key: {key.strip()}, value: {value.strip()}")  # Debugging
        

        data["timestamp"] = timestamp
        
        # Convert numeric values to float where appropriate
        for key in ['pH', 'EC', 'TDS', 'DO', 'Temp']:
            if key in data:
                try:
                    data[key] = float(data[key])
                    print(f"Converted {key} to float: {data[key]}")
                except ValueError:
                    print(f"Could not convert {key} value '{data[key]}' to float")
                    data[key] = None  # Keep as string if conversion fails
        
        # Handle GPS data specially
        if 'GPS' in data:
            if data['GPS'] != 'NoFix':
                # If GPS has coordinates, parse them
                try:
                    lat_lon = data['GPS'].split(',')
                    if len(lat_lon) == 2:
                        data['Lat'] = lat_lon[0]
                        data['Lon'] = lat_lon[1]
                except:
                    pass
            # Remove the raw GPS field to avoid confusion
            del data['GPS']
        
        # Predict arsenic concentration if we have the required parameters
        if all(k in data and data[k] is not None for k in ['TDS', 'EC', 'Temp']):
            arsenic_prediction = predict_arsenic(data['TDS'], data['EC'], data['Temp'])
            if arsenic_prediction is not None:
                data['Arsenic'] = arsenic_prediction
                print(f"Predicted arsenic concentration: {arsenic_prediction}")
        else:
            print("Missing one or more parameters required for arsenic prediction")
                
        with data_lock:
            latest_data = data.copy()
            print(f"Updated latest_data: {latest_data}")

        # Save to database
        db = get_db()
        db.execute('''INSERT INTO sensor_data (timestamp, pH, EC, TDS, DO, Temp, Arsenic, Lat, Lon)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                          timestamp,
                          data.get('pH'),
                          data.get('EC'),
                          data.get('TDS'),
                          data.get('DO'),
                          data.get('Temp'),
                          data.get('Arsenic'),
                          data.get('Lat'),
                          data.get('Lon')
                      ))
        db.commit()
        print("Data saved to database")

        # Notify all connected clients
        notify_clients()
        
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        print(f"Error processing data: {str(e)}")
        print(traceback.format_exc())  # Print detailed error info
        
        # If it's a database schema error related to Temp column, provide hint
        if "no column named" in str(e):
            hint = "Please recreate your database or update schema to include all required columns"
            print(hint)
            return jsonify({'status': 'error', 'message': str(e), 'hint': hint}), 500
            
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/lora/latest')
def get_latest():
    with data_lock:
        # Ensure timestamp exists
        if latest_data and 'timestamp' not in latest_data:
            latest_data['timestamp'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"Returning latest data: {latest_data}")
        return jsonify(latest_data)

@app.route('/lora/history')
def get_history():
    try:
        limit = int(request.args.get('limit', 20))
        data = get_recent_data(limit)
        print(f"Returning {len(data)} history records")
        return jsonify(data)
    except Exception as e:
        print(f"Error getting history: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/stream')
def stream():
    def event_stream():
        q = queue.Queue()
        clients.append(q)
        print(f"New client connected. Total clients: {len(clients)}")
        
        try:
            # Send initial notification to trigger data fetch
            q.put("data: update\n\n")
            print("Sent initial update notification")
            
            while True:
                message = q.get()
                print(f"Sending to client: {message.strip()}")
                yield message
        except GeneratorExit:
            print("Client disconnected")
            if q in clients:
                clients.remove(q)
                print(f"Client removed. Remaining clients: {len(clients)}")
    
    return Response(event_stream(), mimetype="text/event-stream")

# Setup heartbeat to keep connections alive
def heartbeat():
    while True:
        time.sleep(15)  # Send a heartbeat every 15 seconds
        print(f"Sending heartbeat to {len(clients)} clients")
        for client_queue in clients[:]:
            try:
                client_queue.put(": heartbeat\n\n")
            except:
                if client_queue in clients:
                    clients.remove(client_queue)
                    print("Removed disconnected client during heartbeat")

# Add a test data endpoint for debugging
@app.route('/test-data')
def add_test_data():
    """Generate and add test data for debugging purposes"""
    import random
    
    # Generate random data
    test_data = {
        'pH': round(random.uniform(6.0, 9.0), 2),
        'EC': round(random.uniform(0.5, 1.5), 2),
        'TDS': round(random.uniform(0.1, 0.5), 2),
        'DO': round(random.uniform(-2.0, 2.0), 2),
        'Temp': round(random.uniform(15.0, 30.0), 2),
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Add random GPS if desired
    if random.choice([True, False]):
        test_data['Lat'] = str(round(random.uniform(30, 45), 6))
        test_data['Lon'] = str(round(random.uniform(-120, -70), 6))
    
    # Predict arsenic concentration based on the test data
    if arsenic_model is not None:
        test_data['Arsenic'] = predict_arsenic(test_data['TDS'], test_data['EC'], test_data['Temp'])
    
    # Save to latest_data and database
    with data_lock:
        global latest_data
        latest_data = test_data.copy()
        print(f"Generated test data: {latest_data}")
    
    # Save to database
    db = get_db()
    db.execute('''INSERT INTO sensor_data (timestamp, pH, EC, TDS, DO, Temp, Arsenic, Lat, Lon)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                      test_data.get('timestamp'),
                      test_data.get('pH'),
                      test_data.get('EC'),
                      test_data.get('TDS'),
                      test_data.get('DO'),
                      test_data.get('Temp'),
                      test_data.get('Arsenic'),
                      test_data.get('Lat'),
                      test_data.get('Lon')
                  ))
    db.commit()
    
    # Notify clients
    notify_clients()
    
    return jsonify({'status': 'success', 'data': test_data})

if __name__ == '__main__':
    init_db()
    # Start heartbeat thread
    threading.Thread(target=heartbeat, daemon=True).start()
    print("Server starting...")
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)