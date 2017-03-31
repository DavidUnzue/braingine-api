from server import db
from .base import Base, BaseSchema
from marshmallow import fields


class PlotInput(Base):
    __tablename__ = "plot_inputs"

    plot_id = db.Column(db.Integer, db.ForeignKey('plots.id', ondelete="CASCADE"))
    name = db.Column(db.String(40))
    label = db.Column(db.String(255))
    help = db.Column(db.String(255))
    type = db.Column(db.String(40))
    multiple = db.Column(db.Boolean())
    format = db.Column(db.String(35))
    plot = db.relationship("Plot", back_populates="inputs")


class PlotInputSchema(BaseSchema):
    plot_id = fields.Int(dump_only=True)
    name = fields.Str()
    label = fields.Str()
    help = fields.Str()
    type = fields.Str()
    multiple = fields.Bool()
    format = fields.Str()

    class Meta:
        strict = True


class Plot(Base):
    __tablename__ = "plots"

    uid = db.Column(db.String(40))
    filename = db.Column(db.String(40))
    name = db.Column(db.String(40))
    description = db.Column(db.Text())
    executor = db.Column(db.String(35))
    command = db.Column(db.Text())
    checksum = db.Column(db.String(255))
    inputs = db.relationship("PlotInputs", back_populates="plot", lazy='select', cascade="all, delete-orphan")
    output_file = db.Column(db.Integer, db.ForeignKey('files.id'))

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


class PlotSchema(BaseSchema):
    uid = fields.Str()
    filename = fields.Str()
    name = fields.Str()
    description = fields.Str()
    executor = fields.Str()
    command = fields.Str()
    checksum = fields.Str()
    inputs = fields.Nested('PipelineInputSchema', many=True)
    output_file = fields.Int()

    class Meta:
        strict = True
