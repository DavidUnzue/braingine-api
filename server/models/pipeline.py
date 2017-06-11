from server import db
from .base import Base, BaseSchema
from marshmallow import fields


class PipelineInput(Base):
    __tablename__ = "pipeline_inputs"

    pipeline_id = db.Column(db.Integer, db.ForeignKey('pipelines.id', ondelete="CASCADE"))
    pipeline = db.relationship("Pipeline", back_populates="inputs")
    name = db.Column(db.String(255))
    label = db.Column(db.String(255))
    help = db.Column(db.String(255))
    type = db.Column(db.String(40))
    multiple = db.Column(db.Boolean(), default=False)
    format = db.Column(db.String(255), default='')


class PipelineInputSchema(BaseSchema):
    pipeline_id = fields.Int(dump_only=True)
    name = fields.Str()
    label = fields.Str()
    help = fields.Str()
    type = fields.Str()
    multiple = fields.Bool()
    format = fields.Str()

    class Meta:
        strict = True


class PipelineOutput(Base):
    __tablename__ = "pipeline_outputs"

    pipeline_id = db.Column(db.Integer, db.ForeignKey('pipelines.id', ondelete="CASCADE"))
    pipeline = db.relationship("Pipeline", back_populates="outputs")
    name = db.Column(db.String(255))
    label = db.Column(db.String(255))
    type = db.Column(db.String(40))
    value = db.Column(db.String(255))
    format = db.Column(db.String(255))


class PipelineOutputSchema(BaseSchema):
    pipeline_id = fields.Int(dump_only=True)
    name = fields.Str()
    label = fields.Str()
    type = fields.Str()
    value = fields.Str()
    format = fields.Str()

    class Meta:
        strict = True


class Pipeline(Base):
    __tablename__ = "pipelines"

    uid = db.Column(db.String(255))
    filename = db.Column(db.String(255))
    name = db.Column(db.String(255))
    description = db.Column(db.Text())
    executor = db.Column(db.String(35))
    command = db.Column(db.Text())
    checksum = db.Column(db.String(255))
    inputs = db.relationship("PipelineInput", back_populates="pipeline", lazy='select', cascade="all, delete-orphan")
    outputs = db.relationship("PipelineOutput", back_populates="pipeline", lazy='select', cascade="all, delete-orphan")

    def __init__(self, uid, filename, name, description, executor, command, checksum):
        self.uid = uid
        self.filename = filename
        self.name = name
        self.description = description
        self.executor = executor
        self.command = command
        self.checksum = checksum

    def __repr__(self):
        return '<Pipeline {}>'.format(self.id)


class PipelineSchema(BaseSchema):
    uid = fields.Str()
    filename = fields.Str()
    name = fields.Str()
    description = fields.Str()
    executor = fields.Str()
    command = fields.Str()
    checksum = fields.Str()
    inputs = fields.Nested('PipelineInputSchema', many=True)
    outputs = fields.Nested('PipelineOutputSchema', many=True)

    class Meta:
        strict = True
