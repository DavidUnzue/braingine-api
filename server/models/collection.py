from flask import current_app
from .. import db
import os
from ..utils import silent_remove
from .base import Base, BaseSchema
from .user import User
from .file import ExperimentFile
from marshmallow import fields


association_collection_to_file = db.Table('collections_to_files', Base.metadata,
    db.Column('collection_id', db.Integer, db.ForeignKey('collections.id', ondelete="CASCADE")),
    db.Column('file_id', db.Integer, db.ForeignKey('files.id', ondelete="CASCADE"))
)

class Collection(Base):

    __tablename__ = "collections"

    # Attributes
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    name = db.Column(db.String(255))
    description = db.Column(db.Text)
    files = db.relationship(
        "ExperimentFile",
        secondary=association_collection_to_file,
        backref="collections")

    # constructor
    def __init__(self, user_id, name, description):
        self.user_id = user_id
        self.name = name
        self.description = description

    def __repr__(self):
        return '<Collection {}>'.format(self.id)


# Marshmallow schema for collection
class CollectionSchema(BaseSchema):
    user_id = fields.Int(dump_only=True)
    name = fields.Str()
    description = fields.Str(allow_none=True)
    # a collection that contains files which are all within the same directory will contain the path to that dir
    path = fields.Str(allow_none=True)

    class Meta:
        strict = True
