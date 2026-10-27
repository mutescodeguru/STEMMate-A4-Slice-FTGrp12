# Start App: python run.py
# Simple way to start server on personal computer

from stemmate import create_app

app = create_app()  #builds the app (real db in instance/)

if __name__ == "__main__":
    # 127.0.0.1 means this computer can reach it only (P1's rule AC-5)
    app.run(host="127.0.0.1", port=5000)