from flask import current_app, url_for, json
from . import db
from api_1_0 import api
import os
from utils import silent_remove, sha1_string
from marshmallow_jsonapi import Schema, fields


# Define a base model for other models to inherit
class Base(db.Model):
    """
    Base model with attributes common to every model. Other models will inherit from this one.
    """

    # tell SQLAlchemy not to create a table for a this model
    __abstract__  = True

    id            = db.Column(db.Integer, primary_key=True)
    created_at  = db.Column(db.DateTime(timezone=True),  default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime(timezone=True),  default=db.func.current_timestamp(),
                                           onupdate=db.func.current_timestamp())


# Marshmallow schema for base model
class BaseSchema(Schema):
    id = fields.Integer(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


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

    # one-to-many relationship to ExperimentFile
    # one experiments can contain many files, one file belongs only to one experiment
    files = db.relationship('ExperimentFile', backref='experiments',
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

    files = fields.Relationship(
        related_url='/api/experiments/{experiment_id}/files',
        related_url_kwargs={'experiment_id': '<id>'},
        # Include resource linkage
        many=True, include_resource_linkage=True,
        type_='files'
    )

    analyses = fields.Relationship(
        related_url='/api/experiments/{experiment_id}/analyses',
        related_url_kwargs={'experiment_id': '<id>'},
        # Include resource linkage
        many=True, include_resource_linkage=True,
        type_='analyses'
    )

    # extend get_top_level_links method from parent class to output further link objects (pagination, etc...)
    def get_top_level_links(self, data, many):
        top_level_links = super(ExperimentSchema, self).get_top_level_links(data, many) # call parent class' method
        if many:
            next_link = url_for('api.experimentlistcontroller', page=2, _external=True) #TODO get page number from controller
            prev_link = url_for('api.experimentlistcontroller', page=1, _external=True)
            top_level_links.update({'next': next_link, 'prev': prev_link})
        return top_level_links

    class Meta:
        type_ = 'experiments'
        strict = True
        self_url = '/api/experiments/{id}'
        self_url_kwargs = {'id': '<id>'}
        self_url_many = '/api/experiments/'


# Define Experiment file model. File can actually be a file or a directory
class ExperimentFile(Base):

    __tablename__ = "experiment_files"

    # Attributes
    # id of experiment this file belongs to
    experiment_id = db.Column(db.Integer(), db.ForeignKey("experiments.id", ondelete="CASCADE"))
    # filesize stored as amount of Bytes
    # because of huge files (>1TB) possible, we need BigInteger to store it
    # PostgreSQL: http://www.postgresql.org/docs/current/static/datatype-numeric.html
    # bigint(8 bytes storage size). Range: -9223372036854775808 to +9223372036854775807
    size = db.Column(db.BigInteger)
    name = db.Column(db.String(255), nullable=False, default='')
    path = db.Column(db.String(255), nullable=False, default='')
    # a file within a directory has the parent set to that directory's id
    parent = db.Column(db.Integer, nullable=True)
    # hash string will be generated from file name using SHA1 hashing, see event "hash_before_insert"
    sha = db.Column(db.String(40), nullable=True, default='')
    # for a folder, use mime type "application/vnd.mpi-apps.folder"
    # a folder will essentially be a file with that mime type
    mime_type = db.Column(db.String(255))
    file_type = db.Column(db.String(255))
    # a file belongs either to the  uploaded files group ('upload') or to analysis files group ('analysis')
    group = db.Column(db.String(40), default='upload')

    # constructor
    def __init__(self, experiment_id, size, name, path, mime_type, file_type, parent=None, group='upload'):
        self.experiment_id = experiment_id
        self.size = size
        self.name = name
        self.path = path
        self.parent = parent
        self.mime_type = mime_type
        self.file_type = file_type
        self.group = group

    def __repr__(self):
        return '<Experiment file {}>'.format(self.id)


# Marshmallow schema for experiment file
class ExperimentFileSchema(BaseSchema):
    type = fields.Str(dump_only=True)
    experiment_id = fields.Int(dump_only=True)
    # python integer type can store very large numbers, there is no other data type like bigint
    size = fields.Int(dump_only=True)
    name = fields.Str()
    path = fields.Str(dump_only=True)
    parent = fields.Str()
    sha = fields.Str()
    mime_type = fields.Str(dump_only=True)
    file_type = fields.Str()
    group = fields.Str()

    class Meta:
        type_ = 'files'
        strict = True
        self_url = '/api/experiments/{experiment_id}/files/{id}'
        self_url_kwargs = {'experiment_id': '<experiment_id>', 'id': '<id>'}


@db.event.listens_for(ExperimentFile, 'after_delete')
def remove_file_after_delete(mapper, connection, target):
    """
    Remove file from filesystem after row gets deleted in database
    """
    silent_remove(target.path)


@db.event.listens_for(Experiment, 'after_delete')
def remove_directory_after_delete(mapper, connection, target):
    """
    Remove experiment files directory from filesystem after experiment row gets deleted in database
    """
    files_folder = os.path.join(current_app.config.get('UPLOAD_FOLDER'), sha1_string(target.name))
    silent_remove(files_folder)


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


class ExperimentAnalysisParameter(Base):

    __tablename__ = 'experiment_analysis_parameters'

    experiment_analysis_id = db.Column(db.Integer(), db.ForeignKey("experiment_analyses.id", ondelete="CASCADE"))
    parameter_name = db.Column(db.String(255), nullable=False, default='')
    parameter_value = db.Column(db.String(255), nullable=False, default='')

    def __init__(self, experiment_analysis_id, parameter_name, parameter_value):
        self.experiment_analysis_id = experiment_analysis_id
        self.parameter_name = parameter_name
        self.parameter_value = parameter_value

    def __repr__(self):
        return '<Experiment analysis parameter {}>'.format(self.id)


class ExperimentAnalysisParameterSchema(BaseSchema):
    experiment_analysis_id = fields.Int(dump_only=True)
    parameter_name = fields.Str()
    parameter_value = fields.Str()

    class Meta:
        type_ = 'analysis_parameters'
        strict = True


# Experiment contains analyses with programs/parameters/input&output workflows
class ExperimentAnalysis(Base):

    __tablename__ = 'experiment_analyses'

    # id of experiment this analysis belongs to
    experiment_id = db.Column(db.Integer(), db.ForeignKey("experiments.id", ondelete="CASCADE"))
    pipeline_id = db.Column(db.String(255), nullable=False, default='')
    # inputs = db.Column(db.String(255), nullable=False, default='')
    # outputs = db.Column(db.String(255), nullable=False, default='')

    # one-to-many relationship to experiment analysis parameters
    # An experiment analysis contains one or more parameters
    parameters = db.relationship('ExperimentAnalysisParameter', backref='experiment_analyses',
                                lazy='select', cascade="all, delete-orphan")

    def __init__(self, experiment_id, pipeline_id, parameters):
        self.experiment_id = experiment_id
        self.pipeline_id = pipeline_id
        self.parameters = parameters
        # self.inputs = inputs
        # self.outputs = outputs

    def __repr__(self):
        return '<Experiment analysis {}>'.format(self.id)


class ExperimentAnalysisSchema(BaseSchema):
    experiment_id = fields.Int(dump_only=True)
    pipeline_id = fields.Int()
    inputs = fields.Nested(ExperimentAnalysisParameterSchema, many=True)
    outputs = fields.Nested(ExperimentAnalysisParameterSchema, many=True)

    class Meta:
        type_ = 'analyses'
        strict = True
        self_url = '/api/experiments/{experiment_id}/analyses/{id}'
        self_url_kwargs = {'experiment_id': '<experiment_id>', 'id': '<id>'}


class Pipeline(Base):

    __tablename__ = 'pipelines'

    script = db.Column(db.String(255), nullable=False, default='')
    definition = db.Column(db.String(255), nullable=False, default='')

    def __init__(self, script, definition):
        self.script = script
        self.definition = definition

    def __repr__(self):
        return '<Pipeline {}>'.format(self.id)


class PipelineSchema(BaseSchema):
    script = fields.Str()
    definition = fields.Str()

    class Meta:
        type_ = 'pipelines'
        strict = True
        self_url = '/api/pipelines/{id}'
        self_url_kwargs = {'id': '<id>'}
