from asgiref.wsgi import WsgiToAsgi
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from logging.handlers import RotatingFileHandler
import os
import traceback
import platform
import multiprocessing
import subprocess
import sys

from api.routes import api_bp
from services.constant_service import HTTP_PORT

load_dotenv()
app = Flask(__name__)
CORS(app)

# Configure file upload settings
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))

# Optional local logging for development / Windows
def setup_logging():
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    log_path = os.path.join(log_dir, 'mockplant.log')

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=10485760,
        backupCount=10
    )
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers = []
    root_logger.addHandler(file_handler)

    app.logger.setLevel(logging.DEBUG)
    app.logger.handlers = []
    app.logger.propagate = False
    app.logger.addHandler(file_handler)

    # Log messages from Waitress
    waitress_logger = logging.getLogger('waitress')
    waitress_logger.setLevel(logging.DEBUG)
    for handler in app.logger.handlers:
        waitress_logger.addHandler(handler)

    app.logger.info('Logging initialized to mockplant.log')

@app.before_request
def log_request_info():
    app.logger.info('Request: %s %s', request.method, request.url)

@app.after_request
def log_response_info(response):
    app.logger.info('Response: %s %s - %s', request.method, request.url, response.status)
    return response

@app.errorhandler(Exception)
def unhandled_exception(e):
    app.logger.error('Unhandled Exception: %s', str(e))
    app.logger.error('Traceback: %s', traceback.format_exc())
    return jsonify({'error': 'Internal server error'}), 500


# Register the API blueprint
app.register_blueprint(api_bp)

def get_thread_count():
    return (multiprocessing.cpu_count() * 4) + 1

def run_server():
    system = platform.system().lower()
    system = "windows"
    app.logger.info('Starting server on %s platform', system)

    current_dir = os.path.dirname(os.path.abspath(__file__))
    log_file_path = os.path.join(current_dir, 'logs', 'mockplant.log')

    if system == 'linux':
        # Use Gunicorn on Linux
        threads = get_thread_count()
        os.environ['PYTHONPATH'] = current_dir

        cmd = [
            'gunicorn',
            '--config', os.path.join(current_dir, 'gunicorn_conf.py'),
            '--bind', f'0.0.0.0:{HTTP_PORT}',
            '--threads', str(threads),
            '--worker-class', 'gthread',
            '--timeout', '120',
            '--log-level', 'debug',
            'mockplant_http:app'
        ]
        app.logger.info('Starting Gunicorn: %s', ' '.join(cmd))
        subprocess.run(cmd)

    elif system == 'windows':
        # Use Uvicorn on Windows
        import uvicorn
        asgi_app = WsgiToAsgi(app)
        uvicorn.run(
            asgi_app,  # Replace with actual import path, e.g. main:app
            host="0.0.0.0",
            port=HTTP_PORT,
            log_level="debug",
            workers=1,  # Uvicorn uses async workers by default, increase for multi-process
            timeout_keep_alive=120,
            limit_concurrency=1000,
            limit_max_requests=1000,
            headers=[("Server", "MockPlant")],
        )
    else:
        app.logger.error(f"Unsupported OS: {system}")
        sys.exit(1)

if __name__ == '__main__':
    if platform.system().lower() == 'windows':
        setup_logging()
    run_server()
