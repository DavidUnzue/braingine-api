import os
import logging
basedir = os.path.abspath(os.path.dirname(__file__))

class Config(object):
    DEBUG = False
    TESTING = False
    CSRF_ENABLED = True
    SECRET_KEY = 'this-really-needs-to-be-changed'
    LOGGING_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOGGING_LOCATION = 'butler-api.log'
    LOGGING_LEVEL = logging.DEBUG
    # disable warning 'SQLALCHEMY_TRACK_MODIFICATIONS adds significant overhead and will be disabled by default in the future.  Set it to True to suppress this warning'
    # this is needed in order to detect delete cascades and execute some code when that happens, such as deleting files when experiment gets deleted
    SQLALCHEMY_TRACK_MODIFICATIONS = True
    # max. file size for uploaded file chunks per request
    #MAX_CONTENT_LENGTH = 8 * 1024 * 1024 # 8 MB
    SYMLINK_TO_DATA_STORAGE = './data/projects'
    # This is the path to the directory in the storage server where files will be uploaded to
    DATA_STORAGE = '/storage/scic/Data/External/butler/projects'
    # this is the path the webapp uses internally to move the files to. this is a symlink
    UPLOAD_FOLDER = '/Users/davidunzue/Projects/butler-api/data/projects'
    PIPELINES_FOLDER = './data/pipelines' # without trailing slash
    CELERY_RESULT_BACKEND = 'redis://'
    CELERY_BROKER_URL = 'redis://localhost:6379/0'
    # These are the extension that we are accepting to be uploaded
    ALLOWED_EXTENSIONS = set(['txt','bam','bed','fasta','fa', 'fastq', 'fq', 'bz2'])
    BIOINFO_MAGIC_FILE = './resources/magic/bioinformatics'

    @staticmethod
    def init_app(app):
        pass


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = 'postgresql://localhost/butler'
    USE_X_SENDFILE = True

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
