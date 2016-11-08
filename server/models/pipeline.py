from .base import Base, BaseSchema
from server import db
from marshmallow_jsonapi import fields


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
