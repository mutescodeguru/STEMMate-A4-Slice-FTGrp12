# START THE SIMULATED central store:  python run_central.py   (port 5001)

from central.app import create_central_app

app = create_central_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001)