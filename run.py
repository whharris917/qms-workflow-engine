"""Entry point — run from the repo root: python run.py"""

from app.app import app

if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True)
