from flask import current_app
from . import db
import os
from utils import silent_remove, sha1_string

# Define a base model for other models to inherit
class Base(db.Model):

    __abstract__  = True

    id            = db.Column(db.Integer, primary_key=True)
    date_created  = db.Column(db.DateTime(timezone=True),  default=db.func.current_timestamp())
    date_modified = db.Column(db.DateTime(timezone=True),  default=db.func.current_timestamp(),
                                           onupdate=db.func.current_timestamp())


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


# Define Experiment files model
class ExperimentFile(Base):

    __tablename__ = "experiment_files"

    # Attributes
    uid = db.Column(db.String(40), nullable=True, default='')
    experiment_id = db.Column(db.Integer, db.ForeignKey("experiments.id", ondelete="CASCADE"))
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
    Create a hash out of the filename for use as unique identifier
    """
    filename_hash = sha1_string(target.file_name)
    target.uid = filename_hash
