import logging
import os
import threading
import webbrowser
from datetime import timedelta
from flask import Flask
from Backend.Routers.router import register_routes

PORT = 8000
app = Flask(
    __name__,
    static_folder="Frontend",
    static_url_path="/static",
)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "local-dev-secret-key")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
register_routes(app)

def open_browser() -> None:
    webbrowser.open(f"http://localhost:{PORT}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    url = f"http://localhost:{PORT}"
    print(f"Server running at {url}")
    threading.Timer(1, open_browser).start()
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
