import os
import logging
basedir = os.path.abspath(os.path.dirname(__file__))

class Config(object):
    DEBUG = False
    TESTING = False
    CSRF_ENABLED = True
    SECRET_KEY = 'this-really-needs-to-be-changed' #TODO change this
    LOGGING_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOGGING_LOCATION = 'braingine-api.log'
    LOGGING_LEVEL = logging.WARNING
    # disable warning 'SQLALCHEMY_TRACK_MODIFICATIONS adds significant overhead and will be disabled by default in the future.  Set it to True to suppress this warning'
    # this is needed in order to detect delete cascades and execute some code when that happens, such as deleting files when experiment gets deleted
    SQLALCHEMY_TRACK_MODIFICATIONS = True
    # max. file size for uploaded file chunks per request
    #MAX_CONTENT_LENGTH = 8 * 1024 * 1024 # 8 MB
    SYMLINK_TO_DATA_STORAGE = './data/projects'
    # This is the path to the directory in the storage server where files will be uploaded to
    DATA_STORAGE = '/storage/scic/Data/External/braingine/projects'
    # path to directory within storage server where user files are located for alternative upload
    DATA_STORAGE_PREUPLOADS = '/storage/scic/Data/External/braingine/preuploads'
    SYMLINK_TO_DATA_STORAGE_PREUPLOADS = './data/preuploads'
    # the folder within a project folder where the uploaded files will be stored
    UPLOADS_FOLDER = 'uploads'
    # the folder within a project folder where the results of an analysis will be stored
    ANALYSES_FOLDER = 'analyses'
    # the folder within a project folder where the visualization figures will be stored
    VISUALIZATIONS_FOLDER = 'visualizations'
    # pipelines location
    PIPELINES_STORAGE = '/storage/scic/Data/External/braingine/pipelines'
    PIPELINES_FOLDER = './data/pipelines' # without trailing slash
    # plots location
    PLOTS_STORAGE = '/storage/scic/Data/External/braingine/plots'
    PLOTS_FOLDER = './data/plots' # without trailing slash
    # These are the extension that we are accepting to be uploaded
    ALLOWED_EXTENSIONS = set(['txt','bam','bed','fasta','fa', 'fastq', 'fq', 'bz2'])
    BIOINFO_MAGIC_FILE = './resources/magic/bioinformatics'
    # celery configuration
    CELERY_RESULT_BACKEND = 'redis://'
    CELERY_BROKER_URL = 'redis://localhost:6379/0'
    CELERY_ACCEPT_CONTENT = ['pickle', 'json', 'msgpack', 'yaml']
    # LDAP config
    LDAP_SERVER = 'ldap://mpibr.local:3268'
    LDAP_USERNAME = 'ldap_read@MPIBR'
    LDAP_PASSWORD = 'OPpgs7s1'
    LDAP_BASE_DN = 'OU=MPIBR,DC=mpibr,DC=local'


    @staticmethod
    def init_app(app):
        pass


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = 'postgresql:///braingine'
    LOGGING_LOCATION = '/var/log/braingine/braingine-api.log'
    USE_X_SENDFILE = True

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)


class DevelopmentConfig(Config):
    DEVELOPMENT = True
    DEBUG = True
    ERROR_404_HELP = False
    SQLALCHEMY_DATABASE_URI = 'postgresql://localhost/braingine_dev'


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'postgresql://localhost/braingine_test'


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
