import requests
import os

# --- Configuration ---
NEON_API_KEY = "your_neon_api_key"
PROJECT_ID = "your_project_id"
THRESHOLD_SECONDS = 342000  # 95 Hours


def monitor_quota():
    url = f"https://console.neon.tech/api/v2/projects/{PROJECT_ID}/consumption"
    headers = {"Authorization": f"Bearer {NEON_API_KEY}"}

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        usage = response.json().get('active_time_seconds', 0)

        if usage >= THRESHOLD_SECONDS:
            print("⚠️ QUOTA LIMIT NEAR: Switching to Backup DB...")
            # Here you would trigger your logic to switch URLs
            # or send yourself a notification.
        else:
            print(f"✅ Quota Safe: {usage / 3600:.2f} hours used.")
    else:
        print("Failed to fetch Neon metrics.")


if __name__ == "__main__":
    monitor_quota()