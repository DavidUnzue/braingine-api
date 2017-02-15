import os

from celery import Celery
from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
# from flask_simpleldap import LDAP

from config import config

db = SQLAlchemy()
# ldap = LDAP()

def create_app(config_name, register_blueprints=True):
    app = Flask(__name__, instance_relative_config=True)
    # load the config class defined in env var from config.py
    app.config.from_object(config[config_name])
    # load the configuration file from the instance folder.
    # silent=True is optional and used to suppress the error in case config.cfg is not found
    app.config.from_pyfile('config.cfg', silent=True)

    config[config_name].init_app(app)
    db.init_app(app)
    # ldap.init_app(app)

    if not app.debug:
        # Configure logging
        import logging
        handler = logging.FileHandler(app.config['LOGGING_LOCATION'])
        handler.setLevel(app.config['LOGGING_LEVEL'])
        formatter = logging.Formatter(app.config['LOGGING_FORMAT'])
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)

    if register_blueprints:
        # Import blueprints
        from .api_1_0 import api_blueprint as api_v1
        from .views.index import index_view
        # Register blueprint(s)
        app.register_blueprint(api_v1, url_prefix='/api')
        app.register_blueprint(index_view)

    return app


def create_celery_app(app=None):
    """
    Create celery instance with app context bound to it, so we can use things like DB within a celery task.
    """
    app = app or create_app(os.getenv('APP_SETTINGS') or 'default', register_blueprints=False)
    celery = Celery(__name__, backend=app.config['CELERY_RESULT_BACKEND'], broker=app.config['CELERY_BROKER_URL'])
    celery.conf.update(app.config)
    TaskBase = celery.Task

    class ContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)

    celery.Task = ContextTask
    return celery
