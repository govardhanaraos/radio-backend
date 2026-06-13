import requests
import time
from datetime import datetime

# Configuration
URL = "http://127.0.0.1:8000/hindiflacs-song-download/process-pending-uploads"
PARAMS = {"limit": 2}
INTERVAL_SECONDS = 2  # 5 Seconds

def trigger_batch():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        print(f"[{datetime.now()}] 🚀 Triggering batch upload...")
        response = requests.get(URL, params=PARAMS, timeout=600) # 10 min timeout for uploads
        
        if response.status_code == 200:
            print(f"[{datetime.now()}] ✅ Success: {response.json()}")
        else:
            print(f"[{datetime.now()}] ⚠️ Server responded with {response.status_code}: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now()}] ❌ Connection Error: Is your local FastAPI server running? {e}")

import subprocess

def is_on_correct_wifi(target_ssid):
    try:
        print(target_ssid)
        results = subprocess.check_output(["netsh", "wlan", "show", "interfaces"]).decode("utf-8")
        print(results)
        return target_ssid in results
    except:
        return False

# In your loop:
# if is_on_correct_wifi("Your_Home_Wifi_Name"):
#     trigger_batch()

if __name__ == "__main__":
    print(f"Starting trigger script for {URL}")
    print(f"Processing 2 songs every {INTERVAL_SECONDS} Seconds.")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    while True:
        trigger_batch()
        print(f"[{datetime.now()}]Waiting {INTERVAL_SECONDS/60} minutes for next batch...\n")
        time.sleep(INTERVAL_SECONDS)
