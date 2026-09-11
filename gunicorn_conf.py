import os
import logging
from logging.handlers import RotatingFileHandler

def post_fork(server, worker):
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
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

    logging.getLogger('gunicorn.error').addHandler(file_handler)
    logging.getLogger('gunicorn.access').addHandler(file_handler)

    try:
        from mockplant_http import app
        app.logger.handlers = []
        app.logger.setLevel(logging.DEBUG)
        app.logger.propagate = False
        app.logger.addHandler(file_handler)
        app.logger.info("Logging initialized in Gunicorn worker")
    except Exception as e:
        logging.error(f"Error initializing Flask logger in worker: {e}")
