import time
from datetime import datetime

print("Timestamp Logger started.", flush=True)

while True:
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    print(timestamp, flush=True)
    time.sleep(60)
