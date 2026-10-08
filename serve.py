import os
from app import create_app
from waitress import serve

if __name__ == "__main__":
    app = create_app()
    serve(app, host=os.getenv("APP_HOST", "127.0.0.1"), port=int(os.getenv("APP_PORT", "8088")), threads=4)
