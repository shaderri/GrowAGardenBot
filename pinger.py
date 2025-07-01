import time
import requests

# URL вашего Render Web Service, полученный после деплоя
URL = "https://your-service-name.onrender.com/"

# Интервал между запросами (в секундах)
PING_INTERVAL = 15 * 60  # 15 минут


def ping():
    try:
        resp = requests.get(URL, timeout=10)
        print(f"Ping {URL} — {resp.status_code}")
    except Exception as e:
        print(f"Ping error: {e}")


if __name__ == "__main__":
    print(f"Starting pinger for {URL} every {PING_INTERVAL} seconds...")
    while True:
        ping()
        time.sleep(PING_INTERVAL)