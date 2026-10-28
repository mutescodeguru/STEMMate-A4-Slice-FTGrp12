# Start the app:  python run.py

from stemmate import create_app
from stemmate.services import sync_service

app = create_app()

if __name__ == "__main__":
    sync_service.start_scheduler(app) # background sync every 60 s
    # 127.0.0.1 = this computer only (P1's rule AC-5)
    app.run(host="127.0.0.1", port=5000)