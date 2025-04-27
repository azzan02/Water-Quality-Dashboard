// Debug logging function
function log(message) {
  const debugPanel = document.getElementById('debug');
  const timestamp = new Date().toLocaleTimeString();
  debugPanel.innerHTML += `<div>[${timestamp}] ${message}</div>`;
  debugPanel.scrollTop = debugPanel.scrollHeight;
  console.log(`[${timestamp}] ${message}`);
}

log("Dashboard initializing...");

// Initialize map
log("Initializing map...");
const map = L.map('map').setView([0, 0], 2); // Default view of the world

// Add tile layer (you can change this to a different map style if desired)
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);

// Create marker for the current location (we'll update its position later)
let marker = null;
// Create a line to track path of the USV
let pathLine = L.polyline([], {color: '#00ffff', weight: 3}).addTo(map);
let pathCoordinates = [];

// Initialize charts
// Update the createLineChart function in main.js file to have more visible grids:

// Update the createLineChart function in main.js to include full grid

function createLineChart(ctx, label, color) {
  return new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: label,
        data: [],
        borderColor: color,
        backgroundColor: color + '33', // Semi-transparent fill
        fill: true,
        tension: 0.3,
        borderWidth: 3,
        pointRadius: 3,
        pointHoverRadius: 5
      }]
    },
    options: {
      scales: {
        x: {
          ticks: { 
            color: 'white',
            font: {
              size: 11
            }
          },
          grid: {
            color: 'rgba(255, 255, 255, 0.25)',
            tickLength: 8,
            lineWidth: 1,
            display: true,
            drawBorder: true,
            drawOnChartArea: true,
            drawTicks: true
          },
          border: {
            color: 'rgba(255, 255, 255, 0.5)',
            width: 1
          }
        },
        y: {
          beginAtZero: false,
          ticks: { 
            color: 'white',
            font: {
              size: 11
            },
            padding: 8
          },
          grid: {
            color: 'rgba(255, 255, 255, 0.25)',
            tickLength: 8,
            lineWidth: 1,
            display: true,
            drawBorder: true,
            drawOnChartArea: true,
            drawTicks: true
          },
          border: {
            color: 'rgba(255, 255, 255, 0.5)',
            width: 1
          }
        }
      },
      plugins: {
        legend: {
          display: false // Hide legend
        },
        tooltip: {
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          titleColor: '#fff',
          bodyColor: '#fff',
          borderColor: '#555',
          borderWidth: 1,
          padding: 10,
          displayColors: true
        }
      },
      responsive: true,
      maintainAspectRatio: false,
      animation: {
        duration: 1000
      },
      elements: {
        line: {
          borderWidth: 3,
          tension: 0.3
        },
        point: {
          radius: 3,
          hoverRadius: 5,
          borderWidth: 2
        }
      }
    }
  });
}

log("Creating charts...");
const phChart = createLineChart(document.getElementById('phChart'), 'pH', '#ffd700'); // Gold
const doChart = createLineChart(document.getElementById('doChart'), 'DO', '#cc33cc'); // Magenta
const ecChart = createLineChart(document.getElementById('ecChart'), 'Conductivity', '#00bfff'); // DeepSkyBlue
const tdsChart = createLineChart(document.getElementById('tdsChart'), 'TDS', '#66cc66'); // Light Green
const tempChart = createLineChart(document.getElementById('tempChart'), 'Temperature', '#ff6347'); // Tomato
const arsenicChart = createLineChart(document.getElementById('arsenicChart'), 'Arsenic', '#e91e63'); // Pink
const bariumChart = createLineChart(document.getElementById('bariumChart'), 'Barium', '#ff6b6b'); // Coral red
log("Charts created");

// Function to update risk level indicator based on arsenic concentration
function updateArsenicRiskLevel(arsenicValue) {
  const currentArsenicEl = document.getElementById('currentArsenic');
  const riskLevelEl = document.getElementById('riskLevel');
  
  // Update the current value
  currentArsenicEl.textContent = arsenicValue !== null && arsenicValue !== undefined ? 
                                arsenicValue.toFixed(3) : 'N/A';
  
  // Clear previous risk classes
  riskLevelEl.classList.remove('risk-low', 'risk-medium', 'risk-high', 'risk-veryhigh');
  
  // Set risk level based on WHO standards for arsenic in drinking water
  if (arsenicValue === null || arsenicValue === undefined) {
    riskLevelEl.textContent = 'Unknown';
    riskLevelEl.style.backgroundColor = '#888'; // Grey for unknown
  } 
  else if (arsenicValue <= 10) { // 10 ppb is WHO recommended limit
    riskLevelEl.textContent = 'Low';
    riskLevelEl.classList.add('risk-low');
  }
  else if (arsenicValue <= 50) { // 50 ppb is limit in many developing countries
    riskLevelEl.textContent = 'Medium';
    riskLevelEl.classList.add('risk-medium');
  }
  else if (arsenicValue <= 100) {
    riskLevelEl.textContent = 'High';
    riskLevelEl.classList.add('risk-high');
  }
  else {
    riskLevelEl.textContent = 'Very High';
    riskLevelEl.classList.add('risk-veryhigh');
  }
}

// Function to update barium risk level indicator
function updateBariumRiskLevel(bariumValue) {
  const currentBariumEl = document.getElementById('currentBarium');
  const riskLevelEl = document.getElementById('bariumRiskLevel');
  
  if (!currentBariumEl || !riskLevelEl) {
    return; // Elements not found, possibly on a different page
  }
  
  // Update the current value
  currentBariumEl.textContent = bariumValue !== null && bariumValue !== undefined ? 
                              bariumValue.toFixed(3) : 'N/A';
  
  // Clear previous risk classes
  riskLevelEl.classList.remove('risk-low', 'risk-medium', 'risk-high', 'risk-veryhigh');
  
  // Set risk level based on EPA standards for barium in drinking water
  // EPA Maximum Contaminant Level (MCL) for Barium is 2000 ppb (2 mg/L)
  if (bariumValue === null || bariumValue === undefined) {
    riskLevelEl.textContent = 'Unknown';
    riskLevelEl.style.backgroundColor = '#888'; // Grey for unknown
  } 
  else if (bariumValue <= 500) { // Very conservative limit
    riskLevelEl.textContent = 'Low';
    riskLevelEl.classList.add('risk-low');
  }
  else if (bariumValue <= 1000) { // Half the EPA limit
    riskLevelEl.textContent = 'Medium';
    riskLevelEl.classList.add('risk-medium');
  }
  else if (bariumValue <= 2000) { // EPA limit
    riskLevelEl.textContent = 'High';
    riskLevelEl.classList.add('risk-high');
  }
  else {
    riskLevelEl.textContent = 'Very High';
    riskLevelEl.classList.add('risk-veryhigh');
  }
}

const maxData = 20; // Max number of data points to show on charts
let sensorData = []; // Array to hold historical data

// Handle failures by reconnecting
let failedAttempts = 0;
let eventSource = null;
let pollInterval = null;

// Update GPS display and map
function updateGPSLocation(lat, lon) {
  try {
    // Parse coordinates as floats to ensure proper formatting
    const latitude = parseFloat(lat);
    const longitude = parseFloat(lon);
    
    // Update text display
    document.getElementById('gpsInfo').textContent = `Latitude: ${latitude.toFixed(6)}, Longitude: ${longitude.toFixed(6)}`;
    
    // Update map
    const newLatLng = [latitude, longitude];
    
    // Add to path coordinates and update polyline
    pathCoordinates.push(newLatLng);
    pathLine.setLatLngs(pathCoordinates);
    
    // If it's the first point or we need to create a new marker
    if (!marker) {
      marker = L.marker(newLatLng).addTo(map);
      map.setView(newLatLng, 14); // Zoom to location
    } else {
      // Update existing marker position
      marker.setLatLng(newLatLng);
      map.panTo(newLatLng); // Pan map to follow the marker
    }
    
    log(`Updated GPS: ${latitude.toFixed(6)}, ${longitude.toFixed(6)}`);
  } catch (error) {
    log(`Error updating GPS: ${error.message}`);
  }
}

// Updated updateCharts function with arsenic and barium handling
function updateCharts(data) {
  try {
    if (!data || Object.keys(data).length === 0) {
      log("No data to update");
      return;
    }

    // If we received a successful update, reset failure counter
    failedAttempts = 0;

    log(`Updating charts with data: ${JSON.stringify(data)}`);

    // Add new data if it has a timestamp
    if (data.timestamp) {
      // Check if we already have this timestamp to prevent duplicates
      const existingIndex = sensorData.findIndex(item => item.timestamp === data.timestamp);
      if (existingIndex === -1) {
        sensorData.push(data);
        if (sensorData.length > maxData) {
          sensorData.shift(); // Remove the oldest data point
        }
      } else {
        // Optionally update existing data point if needed
        // sensorData[existingIndex] = data;
        log(`Data with timestamp ${data.timestamp} already exists. Skipping add.`);
      }
    }

    // Clear existing chart data before repopulating
    phChart.data.labels = [];
    phChart.data.datasets[0].data = [];
    doChart.data.labels = [];
    doChart.data.datasets[0].data = [];
    ecChart.data.labels = [];
    ecChart.data.datasets[0].data = [];
    tdsChart.data.labels = [];
    tdsChart.data.datasets[0].data = [];
    tempChart.data.labels = [];
    tempChart.data.datasets[0].data = [];
    arsenicChart.data.labels = [];
    arsenicChart.data.datasets[0].data = [];
    bariumChart.data.labels = []; 
    bariumChart.data.datasets[0].data = [];

    log(`Processing ${sensorData.length} data points`);

    // Update with all available data
    sensorData.forEach(item => {
      // Ensure timestamp exists before trying to format it
      const time = item.timestamp ? new Date(item.timestamp).toLocaleTimeString() : 'Unknown Time';

      // Only add valid numeric values
      if (item.pH !== undefined && item.pH !== null) { // Allow 0 as a valid value
        phChart.data.labels.push(time);
        phChart.data.datasets[0].data.push(parseFloat(item.pH));
      }

      if (item.DO !== undefined && item.DO !== null) {
        doChart.data.labels.push(time);
        doChart.data.datasets[0].data.push(parseFloat(item.DO));
      }

      if (item.EC !== undefined && item.EC !== null) {
        ecChart.data.labels.push(time);
        ecChart.data.datasets[0].data.push(parseFloat(item.EC));
      }

      if (item.TDS !== undefined && item.TDS !== null) {
        tdsChart.data.labels.push(time);
        tdsChart.data.datasets[0].data.push(parseFloat(item.TDS));
      }
      
      if (item.Temp !== undefined && item.Temp !== null) {
        tempChart.data.labels.push(time);
        tempChart.data.datasets[0].data.push(parseFloat(item.Temp));
      }
      
      if (item.Arsenic !== undefined && item.Arsenic !== null) {
        arsenicChart.data.labels.push(time);
        arsenicChart.data.datasets[0].data.push(parseFloat(item.Arsenic));
      }
      
      // Add Barium data processing
      if (item.Barium !== undefined && item.Barium !== null) {
        bariumChart.data.labels.push(time);
        bariumChart.data.datasets[0].data.push(parseFloat(item.Barium));
      }
    });
    
    // Update GPS info if available (use latest data from the main 'data' object received)
    if (data.Lat && data.Lon) {
      updateGPSLocation(data.Lat, data.Lon);
    }

    // Update last updated time (use timestamp from the main 'data' object)
    if (data.timestamp) {
      document.getElementById('lastUpdated').textContent = `Last updated: ${new Date(data.timestamp).toLocaleString()}`;
    }
    
    // Update arsenic risk level indicator (use latest data)
    if (data.Arsenic !== undefined && data.Arsenic !== null) {
      updateArsenicRiskLevel(parseFloat(data.Arsenic));
    }
    
    // Update barium risk level indicator (use latest data)
    if (data.Barium !== undefined && data.Barium !== null) {
      updateBariumRiskLevel(parseFloat(data.Barium));
    }

    // Update all charts
    phChart.update();
    doChart.update();
    ecChart.update();
    tdsChart.update();
    tempChart.update();
    arsenicChart.update();
    bariumChart.update();

    log("Charts updated successfully");
  } catch (error) {
    log(`Error updating charts: ${error.message} \nStack: ${error.stack}`); // Added stack trace for better debugging
  }
}

// Function to set up SSE (Server-Sent Events)
function setupEventSource() {
  if (eventSource) {
    eventSource.close(); // Close existing connection if any
  }

  log("Setting up EventSource...");
  eventSource = new EventSource('/stream'); // Endpoint for SSE

  eventSource.onopen = function() {
    log("SSE connection opened");
    document.getElementById('connectionStatus').classList.add('status-connected');
    document.getElementById('connectionStatus').classList.remove('status-disconnected');
    failedAttempts = 0; // Reset counter on successful connection
    if (pollInterval) { // If polling was active, stop it
      clearInterval(pollInterval);
      pollInterval = null;
      log("Stopped polling fallback.");
    }
  };

  eventSource.onerror = function(event) {
    log("SSE connection error");
    document.getElementById('connectionStatus').classList.add('status-disconnected');
    document.getElementById('connectionStatus').classList.remove('status-connected');
    eventSource.close(); // Close the connection on error

    failedAttempts++;
    log(`Connection failed (attempt ${failedAttempts})`);

    if (failedAttempts < 5) {
      // Try to reconnect after a delay (exponential backoff)
      const delay = Math.min(30000, 1000 * Math.pow(2, failedAttempts)); // Max 30 seconds
      log(`Attempting to reconnect SSE in ${delay/1000} seconds...`);

      setTimeout(() => {
        setupEventSource(); // Retry SSE setup
      }, delay);
    } else {
      log("Too many SSE connection failures. Switching to polling mode.");
      setupPollingFallback(); // Switch to polling after multiple failures
    }
  };

  eventSource.onmessage = function(event) {
    log(`SSE message received: ${event.data}`);
    // Expecting a simple 'update' message to trigger fetch
    if (event.data === 'update') {
      log("Fetching updated data via SSE trigger...");
      fetch('/lora/latest')
        .then(response => {
          if (!response.ok) {
            throw new Error(`HTTP error ${response.status}`);
          }
          return response.json();
        })
        .then(data => {
          log(`Received updated data: ${JSON.stringify(data)}`);
          if (Object.keys(data).length > 0) {
            updateCharts(data); // Pass the single latest data point object
          } else {
            log("Received empty data object from /lora/latest");
          }
        })
        .catch(error => {
          log(`Error fetching updated data after SSE trigger: ${error}`);
          // Don't increment failedAttempts here, SSE connection itself is fine
        });
    } else {
      log(`Received unexpected SSE message: ${event.data}`);
      // Optionally try to parse event.data directly if backend sends full JSON
      try {
        const jsonData = JSON.parse(event.data);
        if (Object.keys(jsonData).length > 0) {
          updateCharts(jsonData);
        }
      } catch(e) {
        // Ignore if it's not JSON or the 'update' string
      }
    }
  };
}

// Polling fallback for environments where SSE doesn't work or fails repeatedly
function setupPollingFallback() {
  log("Setting up polling fallback...");

  // Ensure SSE is closed if we switch to polling
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }

  // Clear any existing polling interval
  if (pollInterval) {
    clearInterval(pollInterval);
  }

  const pollFrequency = 5000; // Poll every 5 seconds
  log(`Polling /lora/latest every ${pollFrequency / 1000} seconds`);

  // Initial fetch for polling
  fetchLatestDataPolling();

  // Set interval for subsequent polls
  pollInterval = setInterval(fetchLatestDataPolling, pollFrequency);
}

// Function to fetch data during polling
function fetchLatestDataPolling() {
  log("Polling for updates...");
  fetch('/lora/latest')
    .then(response => {
      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`);
      }
      return response.json();
    })
    .then(data => {
      if (Object.keys(data).length > 0) {
        updateCharts(data); // Update charts with the latest data
        document.getElementById('connectionStatus').classList.add('status-connected');
        document.getElementById('connectionStatus').classList.remove('status-disconnected');
      } else {
        log("Polling received empty data object.");
      }
    })
    .catch(error => {
      log(`Polling error: ${error}`);
      document.getElementById('connectionStatus').classList.add('status-disconnected');
      document.getElementById('connectionStatus').classList.remove('status-connected');
      // Consider stopping polling after too many errors?
    });
}

// Handle window resize events to update the map
window.addEventListener('resize', function() {
  // Wait a bit for the layout to stabilize
  setTimeout(function() {
    map.invalidateSize();
  }, 100);
});

// Load initial historical data
log("Fetching historical data...");
fetch('/lora/history') // Endpoint for historical data
  .then(response => {
    if (!response.ok) {
      throw new Error(`HTTP error ${response.status}`);
    }
    return response.json();
  })
  .then(data => {
    log(`Received ${data.length} historical records`);
    if (Array.isArray(data) && data.length > 0) {
      // Sort data by timestamp ascending just in case it's not ordered
      data.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

      // Limit initial data to maxData points
      sensorData = data.slice(-maxData);
      
      // Update arsenic risk level with the most recent reading
      const latestReading = sensorData[sensorData.length - 1];
      if (latestReading && latestReading.Arsenic !== undefined && latestReading.Arsenic !== null) {
        updateArsenicRiskLevel(parseFloat(latestReading.Arsenic));
      }
      
      // Update barium risk level with the most recent reading
      if (latestReading && latestReading.Barium !== undefined && latestReading.Barium !== null) {
        updateBariumRiskLevel(parseFloat(latestReading.Barium));
      }

      // Process GPS data from all historical points to create the path
      pathCoordinates = [];
      sensorData.forEach(point => {
        if (point.Lat && point.Lon) {
          const lat = parseFloat(point.Lat);
          const lon = parseFloat(point.Lon);
          if (!isNaN(lat) && !isNaN(lon)) {
            pathCoordinates.push([lat, lon]);
          }
        }
      });

      // Update path on map if we have coordinates
      if (pathCoordinates.length > 0) {
        pathLine.setLatLngs(pathCoordinates);
        
        // Set view to the most recent coordinate
        const lastPoint = pathCoordinates[pathCoordinates.length - 1];
        map.setView(lastPoint, 14);
        
        // Create marker at the latest position
        if (!marker) {
          marker = L.marker(lastPoint).addTo(map);
        } else {
          marker.setLatLng(lastPoint);
        }
      }

      // Update charts with the most recent historical point as the initial state
      if (sensorData.length > 0) {
        updateCharts(sensorData[sensorData.length - 1]);
      }

    } else {
      log("No valid historical data received or array is empty.");
    }

    // Invalid size and refresh map after data is loaded
    setTimeout(() => map.invalidateSize(), 100);
  })
  .catch(error => {
    log(`Error fetching historical data: ${error}`);
  })
  .finally(() => {
    // Set up real-time updates after attempting to load history
    log("Setting up real-time updates (SSE or Polling)...");
    setupEventSource(); // Start with SSE
  });


// Set up controls
document.getElementById('testDataBtn').addEventListener('click', function() {
  log("Generating test data...");
  fetch('/test-data') // Endpoint to trigger test data generation on the server
    .then(response => response.json())
    .then(result => {
      // The backend should ideally send an SSE 'update' message after generating test data.
      // If not, we might need to manually call fetch or updateCharts here.
      log(`Test data request sent. Result: ${JSON.stringify(result)}`);
      // Assuming the backend SSE notifies of the new data, no direct update needed here.
    })
    .catch(error => {
      log(`Error requesting test data generation: ${error}`);
    });
});

document.getElementById('toggleDebugBtn').addEventListener('click', function() {
  const debugPanel = document.getElementById('debug');
  if (debugPanel.style.display === 'none') {
    debugPanel.style.display = 'block';
    this.textContent = 'Hide Debug';
  } else {
    debugPanel.style.display = 'none';
    this.textContent = 'Show Debug';
  }
  
  // Refresh map when debug panel is toggled (helps with layout issues)
  setTimeout(() => map.invalidateSize(), 100);
});

log("Dashboard initialization complete");

// Initialize the arsenic risk level indicator
updateArsenicRiskLevel(null);

// Initialize the barium risk level indicator
updateBariumRiskLevel(null);