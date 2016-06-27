from flask import current_app
from . import db
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
    date_created  = db.Column(db.DateTime(timezone=True),  default=db.func.current_timestamp())
    date_modified = db.Column(db.DateTime(timezone=True),  default=db.func.current_timestamp(),
                                           onupdate=db.func.current_timestamp())


# Marshmallow schema for base model
class BaseSchema(Schema):
    id = fields.Integer(dump_only=True)
    date_created = fields.DateTime()
    date_modified = fields.DateTime()


# Define Experiment model
class Experiment(Base):

    __tablename__ = "experiments"

    # Attributes
    exp_type = db.Column(db.String(255))
    name = db.Column(db.String(255))
    date = db.Column(db.Date)
    experimenter = db.Column(db.String(255))
    species = db.Column(db.String(255))
    tissue = db.Column(db.String(255))

    # one-to-many relationship to ExperimentFile
    # one experiments can contain many files, one file belongs only to one experiment
    files = db.relationship('ExperimentFile', backref='experiments',
                                lazy='select', cascade="all, delete-orphan")

    # constructor
    def __init__(self, exp_type, name, date, experimenter, species, tissue):
        self.exp_type = exp_type
        self.name = name
        self.date = date
        self.experimenter = experimenter
        self.species = species
        self.tissue = tissue

    def __repr__(self):
        return '<Experiment %d>' % self.id


# Marshmallow schema for experiments
class ExperimentSchema(BaseSchema):
    name = fields.Str()
    exp_type = fields.Str()
    date = fields.Date()
    experimenter = fields.Str()
    species = fields.Str()
    tissue = fields.Str()

    files = fields.Relationship(
        related_url='/experiments/{experiment_id}/files',
        related_url_kwargs={'experiment_id': '<id>'},
        # Include resource linkage
        many=True, include_resource_linkage=True,
        type_='files'
    )

    class Meta:
        type_ = 'experiments'
        strict = True


# Define Experiment files model
class ExperimentFile(Base):

    __tablename__ = "experiment_files"

    # Attributes
    # filename hash string will be generated from file name using SHA1 hashing, see event "hash_before_insert"
    filename_hash = db.Column(db.String(40), nullable=True, default='')
    experiment_id = db.Column(db.Integer(), db.ForeignKey("experiments.id", ondelete="CASCADE"))
    file_name = db.Column(db.String(255), nullable=False, default='')
    file_path = db.Column(db.String(255), nullable=False, default='')
    # filesize stored as amount of Bytes
    # because of huge files (>1TB) possible, we need BigInteger to store it
    # PostgreSQL: http://www.postgresql.org/docs/current/static/datatype-numeric.html
    # bigint(8 bytes storage size). Range: -9223372036854775808 to +9223372036854775807
    file_size = db.Column(db.BigInteger)
    file_group = db.Column(db.String(40), default='raw')

    # constructor
    def __init__(self, experiment_id, file_name, file_path, file_size, file_group='raw'):
        self.experiment_id = experiment_id
        self.file_name = file_name
        self.file_path = file_path
        self.file_size = file_size
        self.file_group = file_group

    def __repr__(self):
        return '<Experiment file %d>' % self.id


# Marshmallow schema for experiments
class ExperimentFileSchema(BaseSchema):
    file_name = fields.Str()
    filename_hash = fields.Str()
    experiment_id = fields.Int()
    file_path = fields.Str()
    # python integer type can store very large numbers, there is no toher data type like bigint
    file_size = fields.Int()
    file_group = fields.Str()

    class Meta:
        type_ = 'files'
        strict = True


@db.event.listens_for(ExperimentFile, 'after_delete')
def remove_file_after_delete(mapper, connection, target):
    """
    Remove file from filesystem after row gets deleted in database
    """
    silent_remove(target.file_path)


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
    filename_hash = sha1_string(target.file_name)
    target.filename_hash = filename_hash
