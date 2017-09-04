from flask import current_app
from .. import db
import os
from ..utils import silent_remove
from .base import Base, BaseSchema
from .user import User
from .file import ExperimentFile
from marshmallow import fields


class VisualizationParameter(Base):

    __tablename__ = 'visualizations_parameters'

    visualization_id = db.Column(db.Integer(), db.ForeignKey("visualizations.id", ondelete="CASCADE"))
    name = db.Column(db.String(255), nullable=False, default='')
    value = db.Column(db.Text, nullable=False, default='')

    def __init__(self, visualization_id, name, value):
        self.visualization_id = visualization_id
        self.name = name
        self.value = value

    def __repr__(self):
        return '<Experiment visualization parameter {}>'.format(self.id)


class VisualizationParameterSchema(BaseSchema):
    visualization_id = fields.Int(dump_only=True)
    name = fields.Str()
    value = fields.Str()

    class Meta:
        strict = True


class AssociationVisualizationsInputFiles(Base):

    __tablename__ = 'visualizations_input_files'

    visualization_id = db.Column(db.Integer, db.ForeignKey('visualizations.id'), primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey('files.id'), primary_key=True)
    plot_fieldname = db.Column(db.String(35), nullable=False, default='')
    input_file = db.relationship('ExperimentFile')


class VisualizationInputFileSchema(BaseSchema):
    visualization_id = fields.Int(dump_only=True)
    file_id = fields.Int(dump_only=True)
    plot_fieldname = fields.Str()

    class Meta:
        strict = True


class Visualization(Base):
    __tablename__ = "visualizations"

    user_id = db.Column(db.Integer(), db.ForeignKey("users.id", ondelete="CASCADE"))
    # id of plotting script the visualization uses
    plot_id = db.Column(db.Integer(), db.ForeignKey("plots.id"))
    plot_uid = db.Column(db.String(), nullable=False, default='')
    state = db.Column(db.String(15), nullable=False, default='PENDING')

    # one-to-many relationship to visualization parameters
    # A visualization contains one or more parameters
    parameters = db.relationship('VisualizationParameter', backref='visualization', lazy='select', cascade="all, delete-orphan")

    # many-to-many relationship
    # one visualization can contain many input file, one file can be input of many visualizations
    input_files = db.relationship('AssociationVisualizationsInputFiles', lazy='select', cascade="all, delete-orphan")

    # one-to-one relationship
    # one visualization contains a single output file, one output file corresponds to a single visualization
    output_file_id = db.Column(db.Integer(), db.ForeignKey("files.id", ondelete="CASCADE"))

    def __init__(self, user_id, plot_id, plot_uid):
        self.user_id = user_id
        self.plot_id = plot_id
        self.plot_uid = plot_uid

    def __repr__(self):
        return '<Visualization {}>'.format(self.id)


class VisualizationSchema(BaseSchema):
    user_id = fields.Int(dump_only=True)
    plot_id = fields.Int(dump_only=True)
    plot_uid = fields.Str()
    state = fields.Str()
    parameters = fields.Nested('VisualizationParameterSchema', many=True)
    input_files = fields.Nested('VisualizationInputFileSchema', many=True)
    output_file_id = fields.Int()

    class Meta:
        strict = True


@db.event.listens_for(Visualization, 'after_delete')
def remove_directory_after_delete(mapper, connection, target):
    """
    Remove visualization directory from filesystem after visualization row gets deleted in database
    """
    user = User.query.get(target.user_id)
    user_folder = os.path.join(current_app.config.get('SYMLINK_TO_DATA_STORAGE'), user.username)
    visualization_folder = os.path.join(user_folder, current_app.config.get('VISUALIZATIONS_FOLDER'), str(target.id))
    silent_remove(visualization_folder)
