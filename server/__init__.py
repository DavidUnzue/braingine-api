from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from config import config

db = SQLAlchemy()

def create_app(config_name):
    app = Flask(__name__, instance_relative_config=True)
    # load the config class defined in env var from config.py
    app.config.from_object(config[config_name])
    # load the configuration file from the instance folder.
    # silent=True is optional and used to suppress the error in case config.cfg is not found
    app.config.from_pyfile('config.cfg', silent=True)
    config[config_name].init_app(app)

    db.init_app(app)

    # Import blueprints
    from api_1_0 import api_blueprint as api_v1
    from views.index import index_view
    # Register blueprint(s)
    app.register_blueprint(api_v1, url_prefix='/api')
    app.register_blueprint(index_view)

    return app


# import models so that Alembic knows about them when creating DB migrations
#from .models import *
