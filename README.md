# 🌊 Water Quality Dashboard — Real-Time Monitoring & Heavy Metal Prediction

This is the **web-based monitoring system** for the **BlueShield-USV** project — a smart unmanned surface vehicle designed to assess water quality and predict the presence of harmful **heavy metals** such as **Arsenic, Barium, and Lithium** using real-time sensor data and machine learning.

The dashboard provides a user-friendly interface to:
- 📡 View live water parameter readings
- 🧠 See AI-predicted metal concentrations
- 📍 Track the drone’s real-time GPS location
- 🕒 Analyze historical water quality trends

---

## 🚀 Features

✅ Real-time updates from on-field drone sensors  
✅ REST API integration with the hardware receiver (ESP32 + LoRa)  
✅ ML-based prediction of heavy metal concentrations  
✅ Dynamic dashboard with data tables, graphs, and maps  
✅ Interactive map with drone location tracking (via GPS)

---

## 🧠 Technologies Used

| Component          | Stack/Tool                             |
|--------------------|----------------------------------------|
| Backend            | Python, Flask                          |
| Frontend           | HTML, CSS, JavaScript, Jinja2          |
| Charts             | Chart.js                               |
| Maps               | Leaflet.js                             |
| Communication      | REST API                               |
| ML Models          | Random Forest (trained separately)     |
| Deployment (local) | Flask dev server                       |

---

## 📂 Project Structure

```bash
Water-Quality-Dashboard/
│
├── static/               # CSS, JS, images
├── templates/            # HTML templates for Flask rendering
├── app.py                # Main Flask server file
├── api_handler.py        # Handles data reception from ESP32
├── ml_predictor.py       # Predicts heavy metal concentrations
├── requirements.txt      # Required Python packages
└── README.md             # This file
