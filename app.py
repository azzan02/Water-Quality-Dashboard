from flask import Flask, request, jsonify, render_template, Response, g, redirect, url_for, send_file
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
import io
import csv
import pandas as pd

app = Flask(__name__, static_folder='static')

# Enable CORS if needed
# from flask_cors import CORS
# CORS(app)

DATABASE = 'database.db'
latest_data = {}
clients = []
data_lock = threading.Lock()

# Variable to track active data collection period
current_period_id = None
period_lock = threading.Lock()

# Load the arsenic prediction model
MODEL_PATH = 'Random_Forest_(Dissolved_Arsenic).joblib'
arsenic_model = None

# Load the barium prediction model
BARIUM_MODEL_PATH = 'BARIUM_DISSOLVED_µG_L_model.pkl'
barium_model = None

def load_models():
    global arsenic_model, barium_model
    try:
        print(f"Attempting to load arsenic model from {os.path.abspath(MODEL_PATH)}")
        if os.path.exists(MODEL_PATH):
            arsenic_model = joblib.load(MODEL_PATH)
            print(f"Successfully loaded arsenic prediction model from {MODEL_PATH}")
        else:
            print(f"Warning: Arsenic model file {MODEL_PATH} not found at path: {os.path.abspath(MODEL_PATH)}")
            
        print(f"Attempting to load barium model from {os.path.abspath(BARIUM_MODEL_PATH)}")
        if os.path.exists(BARIUM_MODEL_PATH):
            barium_model = joblib.load(BARIUM_MODEL_PATH)
            print(f"Successfully loaded barium prediction model from {BARIUM_MODEL_PATH}")
        else:
            print(f"Warning: Barium model file {BARIUM_MODEL_PATH} not found at path: {os.path.abspath(BARIUM_MODEL_PATH)}")
    except Exception as e:
        print(f"Error loading models: {str(e)}")
        print(traceback.format_exc())  # More detailed error info

# Load the models when app starts
load_models()

# Function to predict arsenic concentration
def predict_arsenic(tds, ec, temp):
    try:
        if arsenic_model is None:
            print("Warning: No arsenic model loaded, cannot predict arsenic")
            return None
            
        # Create DataFrame with correct feature names matching training data
        features = pd.DataFrame([[tds, ec, temp]], 
                              columns=['TOTAL DISSOLVED SOLIDS MERGED (MG/L)',
                                     'ELECTRICAL CONDUCTIVITY (µS/CM)',
                                     'TEMPERATURE WATER MERGED (DEG C)'])
        
        prediction = arsenic_model.predict(features)[0]
        return round(float(prediction), 3)
    except Exception as e:
        print(f"Error predicting arsenic: {str(e)}")
        return None

# Function to predict barium concentration
def predict_barium(ph, tds, ec, do, temp):
    try:
        if barium_model is None:
            print("Warning: No barium model loaded, cannot predict barium")
            return None
            
        # Create DataFrame with named features
        features = pd.DataFrame([[ph, tds, ec, do, temp]], 
                              columns=['ELECTRICAL CONDUCTIVITY (µS/CM)',
                                     'PH MERGED (PH)', 
                                     'TEMPERATURE WATER MERGED (DEG C)',
                                     'OXYGEN DISSOLVED MERGED (MG/L)',
                                     'TOTAL DISSOLVED SOLIDS MERGED (MG/L)'])
        
        prediction = barium_model.predict(features)[0]
        
        # Return the prediction rounded to 3 decimal places
        return round(float(prediction), 3)
    except Exception as e:
        print(f"Error predicting barium: {str(e)}")
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
            Barium REAL,
            Lat TEXT,
            Lon TEXT,
            period_id INTEGER
        )''')
        
        # Create periods table for tracking data collection periods
        db.execute('''CREATE TABLE IF NOT EXISTS data_periods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            start_time TEXT,
            end_time TEXT,
            notes TEXT
        )''')
        
        # Check if period_id column exists in sensor_data, if not add it
        try:
            db.execute('ALTER TABLE sensor_data ADD COLUMN period_id INTEGER')
            print("Added period_id column to existing database")
        except sqlite3.OperationalError as e:
            # Column might already exist, which will cause an error
            if "duplicate column name" not in str(e):
                print(f"Note: {e}")
        
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
                
        # Check if Barium column exists, if not add it
        try:
            db.execute('ALTER TABLE sensor_data ADD COLUMN Barium REAL')
            print("Added Barium column to existing database")
        except sqlite3.OperationalError as e:
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

def get_periods():
    db = get_db()
    db.row_factory = dict_factory
    cursor = db.cursor()
    cursor.execute('SELECT * FROM data_periods ORDER BY id DESC')
    return cursor.fetchall()

def get_period_data(period_id):
    db = get_db()
    db.row_factory = dict_factory
    cursor = db.cursor()
    cursor.execute('SELECT * FROM sensor_data WHERE period_id = ? ORDER BY id ASC', (period_id,))
    return cursor.fetchall()

def get_period_info(period_id):
    db = get_db()
    db.row_factory = dict_factory
    cursor = db.cursor()
    cursor.execute('SELECT * FROM data_periods WHERE id = ?', (period_id,))
    return cursor.fetchone()

# ---------- SSE Broadcaster ----------
def notify_clients(event_type="update"):
    print(f"Notifying {len(clients)} clients with event: {event_type}")
    for client_queue in clients[:]:  # Copy the list to avoid modification during iteration
        try:
            client_queue.put(f"data: {event_type}\n\n")
            print(f"Notification '{event_type}' sent to client")
        except Exception as e:
            print(f"Error notifying client: {str(e)}")
            if client_queue in clients:
                clients.remove(client_queue)

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

# ---------- Routes ----------
@app.route('/')
def dashboard():
    print("Serving dashboard")
    return render_template('index.html')

@app.route('/lora', methods=['POST'])
def receive_data():
    global latest_data, current_period_id
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
                
        # Predict barium concentration if we have all required parameters
        if all(k in data and data[k] is not None for k in ['pH', 'TDS', 'EC', 'DO', 'Temp']):
            barium_prediction = predict_barium(
                data['pH'],
                data['TDS'], 
                data['EC'],
                data['DO'],
                data['Temp']
            )
            if barium_prediction is not None:
                data['Barium'] = barium_prediction
                print(f"Predicted barium concentration: {barium_prediction}")
        else:
            print("Missing one or more parameters required for barium prediction")
                
        with data_lock:
            latest_data = data.copy()
            print(f"Updated latest_data: {latest_data}")

        # Get current period_id if we're in a data collection period
        with period_lock:
            period_id = current_period_id

        # Save to database
        db = get_db()
        db.execute('''INSERT INTO sensor_data (timestamp, pH, EC, TDS, DO, Temp, Arsenic, Barium, Lat, Lon, period_id)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                          timestamp,
                          data.get('pH'),
                          data.get('EC'),
                          data.get('TDS'),
                          data.get('DO'),
                          data.get('Temp'),
                          data.get('Arsenic'),
                          data.get('Barium'),
                          data.get('Lat'),
                          data.get('Lon'),
                          period_id
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

# ---------- New Period Data Routes ----------
@app.route('/start', methods=['POST'])
def start_period():
    global current_period_id
    
    try:
        data = request.get_json() or {}
        name = data.get('name', f'Period {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        notes = data.get('notes', '')
        
        with period_lock:
            # Check if we're already in a period
            if current_period_id is not None:
                return jsonify({
                    'status': 'error', 
                    'message': 'A data collection period is already in progress', 
                    'period_id': current_period_id
                }), 400
            
            # Create new period
            db = get_db()
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor = db.execute(
                'INSERT INTO data_periods (name, start_time, notes) VALUES (?, ?, ?)',
                (name, timestamp, notes)
            )
            db.commit()
            
            # Get the ID of the inserted period
            current_period_id = cursor.lastrowid
            
        print(f"Started new data collection period: {current_period_id} - {name}")
        notify_clients("period_started")
        
        return jsonify({
            'status': 'success', 
            'message': 'Data collection period started', 
            'period_id': current_period_id,
            'name': name,
            'start_time': timestamp
        })
    
    except Exception as e:
        print(f"Error starting data period: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/stop', methods=['POST'])
def stop_period():
    global current_period_id
    
    try:
        with period_lock:
            # Check if we're actually in a period
            if current_period_id is None:
                return jsonify({
                    'status': 'error', 
                    'message': 'No data collection period is currently active'
                }), 400
            
            # Update the period record to mark it as ended
            db = get_db()
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            db.execute(
                'UPDATE data_periods SET end_time = ? WHERE id = ?',
                (timestamp, current_period_id)
            )
            db.commit()
            
            period_id = current_period_id
            current_period_id = None
            
        print(f"Stopped data collection period: {period_id}")
        notify_clients("period_stopped")
        
        return jsonify({
            'status': 'success', 
            'message': 'Data collection period stopped', 
            'period_id': period_id,
            'end_time': timestamp
        })
    
    except Exception as e:
        print(f"Error stopping data period: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/period-status')
def period_status():
    global current_period_id
    
    with period_lock:
        if current_period_id is not None:
            db = get_db()
            db.row_factory = dict_factory
            cursor = db.cursor()
            cursor.execute('SELECT * FROM data_periods WHERE id = ?', (current_period_id,))
            period = cursor.fetchone()
            
            return jsonify({
                'active': True,
                'period_id': current_period_id,
                'name': period['name'],
                'start_time': period['start_time']
            })
        else:
            return jsonify({'active': False})

@app.route('/periods')
def list_periods():
    try:
        periods = get_periods()
        return render_template('periods.html', periods=periods)
    except Exception as e:
        print(f"Error listing periods: {str(e)}")
        print(traceback.format_exc())
        return f"Error: {str(e)}", 500

@app.route('/period/<int:period_id>')
def view_period(period_id):
    try:
        period_info = get_period_info(period_id)
        if not period_info:
            return "Period not found", 404
        
        data = get_period_data(period_id)
        
        # Check if any data point has GPS coordinates
        has_gps_data = any(item.get('Lat') and item.get('Lon') for item in data)
        
        return render_template('period_data.html', 
                              period=period_info, 
                              data=data, 
                              has_gps_data=has_gps_data)
    except Exception as e:
        print(f"Error viewing period: {str(e)}")
        print(traceback.format_exc())
        return f"Error: {str(e)}", 500

@app.route('/period/<int:period_id>/download')
def download_period_data(period_id):
    try:
        format_type = request.args.get('format', 'csv')
        period_info = get_period_info(period_id)
        if not period_info:
            return "Period not found", 404
        
        data = get_period_data(period_id)
        
        if format_type == 'csv':
            # Create in-memory CSV file
            output = io.StringIO()
            if data and len(data) > 0:
                fieldnames = data[0].keys()
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                for row in data:
                    writer.writerow(row)
                
            # Convert to bytes for sending
            output_bytes = io.BytesIO(output.getvalue().encode('utf-8'))
            output.close()
            
            return send_file(
                output_bytes,
                as_attachment=True,
                download_name=f"period_{period_id}_{period_info['name']}.csv",
                mimetype='text/csv'
            )
        else:
            return f"Unsupported format: {format_type}", 400
            
    except Exception as e:
        print(f"Error downloading period data: {str(e)}")
        print(traceback.format_exc())
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    init_db()
    # Start heartbeat thread
    threading.Thread(target=heartbeat, daemon=True).start()
    print("Server starting...")
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)