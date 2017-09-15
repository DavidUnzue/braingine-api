from flask import current_app
from .. import db
import os
from ..utils import silent_remove
from .base import Base, BaseSchema
from .user import User
from .file import ExperimentFile
from marshmallow import fields


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
    input_file = db.relationship('ExperimentFile')


class AnalysisInputFileSchema(BaseSchema):
    analysis_id = fields.Int(dump_only=True)
    file_id = fields.Int(dump_only=True)
    pipeline_fieldname = fields.Str()

    class Meta:
        strict = True


class AssociationAnalysesOutputFiles(Base):

    __tablename__ = 'analyses_output_files'

    analysis_id = db.Column(db.Integer, db.ForeignKey('analyses.id'), primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey('files.id'), primary_key=True)
    pipeline_fieldname = db.Column(db.String(35), nullable=False, default='')
    output_file = db.relationship('ExperimentFile')


class AnalysisOutputFileSchema(BaseSchema):
    analysis_id = fields.Int(dump_only=True)
    file_id = fields.Int(dump_only=True)
    pipeline_fieldname = fields.Str()

    class Meta:
        strict = True


class Analysis(Base):

    __tablename__ = 'analyses'

    user_id = db.Column(db.Integer(), db.ForeignKey("users.id", ondelete="CASCADE"))
    pipeline_id = db.Column(db.Integer(), db.ForeignKey("pipelines.id"))
    pipeline_uid = db.Column(db.String(), nullable=False, default='')
    state = db.Column(db.String(15), nullable=False, default='PENDING')

    # one-to-many relationship to experiment analysis parameters
    # An experiment analysis contains one or more parameters
    parameters = db.relationship('AnalysisParameter', backref='analysis', lazy='dynamic', cascade="all, delete-orphan")

    # many-to-many relationship
    # one analysis can contain many input file, one file can be input of many analyses
    input_files = db.relationship('AssociationAnalysesInputFiles', lazy='dynamic', cascade="all, delete-orphan")

    # many-to-one relationship
    # one analysis can contain many output file, one file can only be output of one analysis
    output_files = db.relationship('AssociationAnalysesOutputFiles', lazy='dynamic', cascade="all, delete-orphan")

    def __init__(self, user_id, pipeline_id, pipeline_uid):
        self.user_id = user_id
        self.pipeline_id = pipeline_id
        self.pipeline_uid = pipeline_uid

    def __repr__(self):
        return '<Analysis {}>'.format(self.id)


class AnalysisSchema(BaseSchema):
    user_id = fields.Int(dump_only=True)
    pipeline_id = fields.Int(dump_only=True)
    pipeline_uid = fields.Str()
    state = fields.Str()
    parameters = fields.Nested('AnalysisParameterSchema', many=True)
    input_files = fields.Nested('AnalysisInputFileSchema', many=True)
    output_files = fields.Nested('AnalysisOutputFileSchema', many=True)

    class Meta:
        strict = True


@db.event.listens_for(Analysis, 'after_delete')
def remove_directory_after_delete(mapper, connection, target):
    """
    Remove analysis directory from filesystem after analysis row gets deleted in database
    """
    user = User.query.get(target.user_id)
    user_folder = os.path.join(current_app.config.get('SYMLINK_TO_DATA_STORAGE'), user.username)
    analysis_folder = os.path.join(user_folder, current_app.config.get('ANALYSES_FOLDER'), str(target.id))
    silent_remove(analysis_folder)
