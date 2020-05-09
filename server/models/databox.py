from .. import db
from .base import Base, BaseSchema
from .file import ExperimentFile
from marshmallow import fields


association_databox_to_file = db.Table('databoxes_to_files', Base.metadata,
    db.Column('databox_id', db.Integer, db.ForeignKey('databoxes.id', ondelete="CASCADE")),
    db.Column('file_id', db.Integer, db.ForeignKey('files.id', ondelete="CASCADE"))
)

class DataBox(Base):

    __tablename__ = "databoxes"

    # Attributes
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    files = db.relationship(
        "ExperimentFile",
        secondary=association_databox_to_file,
        backref="databox",
        lazy='dynamic')

    # constructor
    def __init__(self, user_id):
        self.user_id = user_id

    def __repr__(self):
        return '<DataBox {}>'.format(self.id)


# Marshmallow schema for collection
class DataBoxSchema(BaseSchema):
    user_id = fields.Int(dump_only=True)
    files = fields.List(fields.Int(), load_only=True) # list of file ids

    class Meta:
        strict = True
