import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config(object):
    DEBUG = False
    TESTING = False
    CSRF_ENABLED = True
    SECRET_KEY = 'this-really-needs-to-be-changed'
    # disable warning 'SQLALCHEMY_TRACK_MODIFICATIONS adds significant overhead and will be disabled by default in the future.  Set it to True to suppress this warning'
    # this is needed in order to detect delete cascades and execute some code when that happens, such as deleting files when experiment gets deleted
    SQLALCHEMY_TRACK_MODIFICATIONS = True
    # This is the path to the directory where files will be uploaded to
    UPLOAD_FOLDER = './uploads'
    # These are the extension that we are accepting to be uploaded
    ALLOWED_EXTENSIONS = set(['txt'])

    @staticmethod
    def init_app(app):
        pass


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = 'postgresql://localhost/butler'

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)


class DevelopmentConfig(Config):
    DEVELOPMENT = True
    DEBUG = True
    ERROR_404_HELP = False
    SQLALCHEMY_DATABASE_URI = 'postgresql://localhost/butler_dev'


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'postgresql://localhost/butler_test'


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
