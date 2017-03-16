from flask import current_app, url_for, json
from server import db
from server.api_1_0 import api
import os
from server.utils import silent_remove, sha1_string
from .base import Base, BaseSchema
from marshmallow import fields


# Define Experiment model
class Experiment(Base):

    __tablename__ = "experiments"

    # Attributes
    exp_type = db.Column(db.String(255))
    name = db.Column(db.String(255))
    date = db.Column(db.String(255)) #TODO use Date type here
    experimenter = db.Column(db.String(255))
    species = db.Column(db.String(255))
    tissue = db.Column(db.String(255))
    information = db.Column(db.Text)
    sha = db.Column(db.String(40), nullable=True, default='')

    # one-to-many relationship to ExperimentFile
    # one experiments can contain many files, one file belongs only to one experiment
    files = db.relationship('ExperimentFile', backref='experiment',
                                lazy='select', cascade="all, delete-orphan")

    # one-to-many relationship to Analysis
    # one experiments can contain many analyses, one analysis belongs only to one experiment
    analyses = db.relationship('Analysis', backref='experiment',
                                lazy='select', cascade="all, delete-orphan")

    # constructor
    def __init__(self, exp_type, name, date, experimenter, species, tissue, information):
        self.exp_type = exp_type
        self.name = name
        self.date = date
        self.experimenter = experimenter
        self.species = species
        self.tissue = tissue
        self.information = information

    def __repr__(self):
        return '<Experiment {}>'.format(self.id)


# Marshmallow schema for experiments
class ExperimentSchema(BaseSchema):
    name = fields.Str()
    exp_type = fields.Str()
    date = fields.Str()
    experimenter = fields.Str()
    species = fields.Str()
    tissue = fields.Str()
    information = fields.Str()
    sha = fields.Str()
    files = fields.Nested('ExperimentFileSchema', many=True)
    analyses = fields.Nested('AnalysisSchema', many=True)

    class Meta:
        strict = True


@db.event.listens_for(Experiment, 'before_insert')
def hash_before_insert(mapper, connection, target):
    """
    Create a hash string out of the filename for use as file unique identifier
    """
    experiment_name_hash = sha1_string(target.name)
    target.sha = experiment_name_hash

@db.event.listens_for(Experiment.name, 'set')
def hash_after_update(target, value, oldvalue, initiator):
    """
    Update the hash string after a filename gets updated
    """
    experiment_name_hash = sha1_string(value)
    target.sha = experiment_name_hash


# Define Experiment file model. File can actually be a file or a directory
class ExperimentFile(Base):

    __tablename__ = "files"

    # Attributes
    # id of experiment this file belongs to
    experiment_id = db.Column(db.Integer(), db.ForeignKey("experiments.id", ondelete="CASCADE"))
    # filesize stored as amount of Bytes
    # because of huge files (>1TB) possible, we need BigInteger to store it
    # PostgreSQL: http://www.postgresql.org/docs/current/static/datatype-numeric.html
    # bigint(8 bytes storage size). Range: -9223372036854775808 to +9223372036854775807
    size_in_bytes = db.Column(db.BigInteger)
    name = db.Column(db.String(255), nullable=False, default='')
    path = db.Column(db.String(255), nullable=False, default='')
    folder = db.Column(db.String(255), nullable=False, default='')
    # a file within a directory has the parent set to that directory's id
    parent = db.Column(db.Integer, nullable=True)
    # hash string will be generated from file name using SHA1 hashing, see event "hash_before_insert"
    sha = db.Column(db.String(40), nullable=True, default='')
    # for a folder, use mime type "application/vnd.mpi-apps.folder"
    # a folder will essentially be a file with that mime type
    mime_type = db.Column(db.String(255))
    file_type = db.Column(db.String(255))
    is_upload = db.Column(db.Boolean, nullable=False, default=False)

    output_of_analysis_id = db.Column(db.Integer(), db.ForeignKey("analyses.id", ondelete="CASCADE"))

    # constructor
    def __init__(self, experiment_id, size_in_bytes, name, path, folder, mime_type, file_type, is_upload=False, parent=None):
        self.experiment_id = experiment_id
        self.size_in_bytes = size_in_bytes
        self.name = name
        self.path = path
        self.folder = folder
        self.parent = parent
        self.mime_type = mime_type
        self.file_type = file_type
        self.is_upload = is_upload

    def __repr__(self):
        return '<Experiment file {}>'.format(self.id)


# Marshmallow schema for experiment file
class ExperimentFileSchema(BaseSchema):
    experiment_id = fields.Int(dump_only=True)
    # python integer type can store very large numbers, there is no other data type like bigint
    size_in_bytes = fields.Int(dump_only=True)
    name = fields.Str()
    path = fields.Str(dump_only=True)
    folder = fields.Str(dump_only=True)
    parent = fields.Str(missing=None)
    sha = fields.Str()
    mime_type = fields.Str(dump_only=True)
    file_type = fields.Str()
    is_upload = fields.Bool()

    class Meta:
        strict = True


@db.event.listens_for(ExperimentFile, 'after_delete')
def remove_file_after_delete(mapper, connection, target):
    """
    Remove file from filesystem after row gets deleted in database
    """
    file_path = os.path.join(current_app.config.get('SYMLINK_TO_DATA_STORAGE'), target.folder, current_app.config.get('UPLOADS_FOLDER'), target.name)
    silent_remove(file_path)


@db.event.listens_for(Experiment, 'after_delete')
def remove_directory_after_delete(mapper, connection, target):
    """
    Remove experiment directory from filesystem after experiment row gets deleted in database
    """
    project_folder = os.path.join(current_app.config.get('SYMLINK_TO_DATA_STORAGE'), target.sha)
    silent_remove(project_folder)


@db.event.listens_for(ExperimentFile, 'before_insert')
def hash_before_insert(mapper, connection, target):
    """
    Create a hash string out of the filename for use as file unique identifier
    """
    filename_hash = sha1_string(target.name)
    target.sha = filename_hash

@db.event.listens_for(ExperimentFile.name, 'set')
def hash_after_update(target, value, oldvalue, initiator):
    """
    Update the hash string after a filename gets updated
    """
    filename_hash = sha1_string(value)
    target.sha = filename_hash


# class Upload(Base):
#
#     __tablename__ = 'uploads'
#
#     experiment_id = db.Column(db.Integer(), db.ForeignKey("experiments.id", ondelete="CASCADE"))
#     file_id = db.Column(db.Integer(), db.ForeignKey("files.id", ondelete="CASCADE"))
#
#
# class UploadSchema(BaseSchema):
#     experiment_id = fields.Int(dump_only=True)
#     file_id = fields.Int(dump_only=True)
#
#     class Meta:
#         strict = True


class AnalysisParameter(Base):

    __tablename__ = 'analyses_parameters'

    analysis_id = db.Column(db.Integer(), db.ForeignKey("analyses.id", ondelete="CASCADE"))
    name = db.Column(db.String(255), nullable=False, default='')
    value = db.Column(db.Text, nullable=False, default='')

    def __init__(self, analysis_id, name, value):
        self.analysis_id = analysis_id
        self.name = name
        self.value = value

    def __repr__(self):
        return '<Experiment analysis parameter {}>'.format(self.id)


class AnalysisParameterSchema(BaseSchema):
    analysis_id = fields.Int(dump_only=True)
    name = fields.Str()
    value = fields.Str()

    class Meta:
        strict = True


class AssociationAnalysesInputFiles(Base):

    __tablename__ = 'analyses_input_files'

    analysis_id = db.Column(db.Integer, db.ForeignKey('analyses.id'), primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey('files.id'), primary_key=True)
    pipeline_fieldname = db.Column(db.String(35), nullable=False, default='')
    input_files = db.relationship('ExperimentFile')


class Analysis(Base):

    __tablename__ = 'analyses'

    # id of experiment this analysis belongs to
    experiment_id = db.Column(db.Integer(), db.ForeignKey("experiments.id", ondelete="CASCADE"))
    pipeline_id = db.Column(db.String(255), nullable=False, default='')
    state = db.Column(db.String(15), nullable=False, default='PENDING')

    # one-to-many relationship to experiment analysis parameters
    # An experiment analysis contains one or more parameters
    parameters = db.relationship('AnalysisParameter', backref='experiment_analyses', lazy='select', cascade="all, delete-orphan")

    # many-to-many relationship
    # one analysis can contain many input file, one file can be input of many analyses
    input_files = db.relationship('AssociationAnalysesInputFiles')

    # many-to-one relationship
    # one analysis can contain many output file, one file can only be output of one analysis
    output_files = db.relationship('ExperimentFile', backref="output_of_analysis")

    def __init__(self, experiment_id, pipeline_id):
        self.experiment_id = experiment_id
        self.pipeline_id = pipeline_id

    def __repr__(self):
        return '<Experiment analysis {}>'.format(self.id)


class AnalysisSchema(BaseSchema):
    experiment_id = fields.Int(dump_only=True)
    pipeline_id = fields.Str() # pipeline id is a unique String, usually the pipeline file name wihtout extension
    state = fields.Str()
    parameters = fields.Nested('AnalysisParameterSchema', many=True)

    class Meta:
        strict = True


@db.event.listens_for(Analysis, 'after_delete')
def remove_directory_after_delete(mapper, connection, target):
    """
    Remove analysis directory from filesystem after analysis row gets deleted in database
    """
    experiment = Experiment.query.get(target.experiment_id)
    project_folder = os.path.join(current_app.config.get('SYMLINK_TO_DATA_STORAGE'), experiment.sha)
    analysis_folder = os.path.join(project_folder, current_app.config.get('ANALYSES_FOLDER'), str(target.id))
    silent_remove(analysis_folder)
