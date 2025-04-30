from app import app

# This is for WSGI servers (Gunicorn)
if __name__ == "__main__":
    app.run() 