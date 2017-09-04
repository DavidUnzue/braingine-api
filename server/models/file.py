from flask import current_app
from .. import db
import os
from ..utils import silent_remove, sha1_string
from .base import Base, BaseSchema, same_as
from marshmallow import fields
from sqlalchemy.dialects.postgresql import JSON

class ExperimentFile(Base):

    __tablename__ = "files"

    # Attributes
    user_id = db.Column(db.Integer(), db.ForeignKey("users.id", ondelete="CASCADE"))
    # filesize stored as amount of Bytes
    # because of huge files (>1TB) possible, we need BigInteger to store it
    # PostgreSQL: http://www.postgresql.org/docs/current/static/datatype-numeric.html
    # bigint(8 bytes storage size). Range: -9223372036854775808 to +9223372036854775807
    size_in_bytes = db.Column(db.BigInteger)
    name = db.Column(db.String(255), nullable=False, default='')
    display_name = db.Column(db.String(255), default=same_as('name'))
    path = db.Column(db.String(255), nullable=False, default='')
    folder = db.Column(db.String(255), nullable=False, default='')
    # a file within a directory has the parent set to that directory's id
    parent = db.Column(db.Integer, nullable=True)
    # hash string will be generated from file name using SHA1 hashing, see event "hash_before_insert"
    sha = db.Column(db.String(40), nullable=True, default='')
    # for a folder, use mime type "application/vnd.mpi-apps.folder"
    # a folder will essentially be a file with that mime type
    mime_type = db.Column(db.String(255))
    file_format = db.Column(db.String(35))
    file_format_full = db.Column(db.String(255))
    is_upload = db.Column(db.Boolean, nullable=False, default=False)

    # annotation
    experimenter = db.Column(db.String(255))
    organism = db.Column(db.String(40))
    age = db.Column(db.String(40))
    gender = db.Column(db.String(40))
    custom_fields = db.Column(JSON)

    # constructor
    def __init__(self, user_id, size_in_bytes, name, path, folder, mime_type, file_format_full, is_upload=False, parent=None, display_name=None):
        self.user_id = user_id
        self.size_in_bytes = size_in_bytes
        self.name = name
        self.display_name = display_name
        self.path = path
        self.folder = folder
        self.parent = parent
        self.mime_type = mime_type
        self.file_format_full = file_format_full
        self.file_format = self.get_file_format(self.file_format_full, self.name)
        self.is_upload = is_upload

    def __repr__(self):
        return '<Experiment file {}>'.format(self.id)

    def get_file_format(self, file_format_full, filename):
        """
        Get the short file format name using the full file format returned by magic
        """
        import json, re
        with open(current_app.config.get('FILE_FORMATS')) as formats_file:
            matching = json.load(formats_file)
        # try using the full file format detected by magic
        for regex, file_format in matching.items():
            if (re.search(regex, file_format_full)):
                return file_format
        # fall back to file extension
        file_extension = os.path.splitext(filename)[1][1:]
        return file_extension


# Marshmallow schema for experiment file
class ExperimentFileSchema(BaseSchema):
    user_id = fields.Int(dump_only=True)
    # python integer type can store very large numbers, there is no other data type like bigint
    size_in_bytes = fields.Int(dump_only=True)
    name = fields.Str()
    display_name = fields.Str()
    path = fields.Str(dump_only=True)
    folder = fields.Str(dump_only=True)
    parent = fields.Str(missing=None)
    sha = fields.Str()
    mime_type = fields.Str(dump_only=True)
    file_format = fields.Str()
    file_format_full = fields.Str()
    is_upload = fields.Bool()

    class Meta:
        strict = True


@db.event.listens_for(ExperimentFile, 'after_delete')
def remove_file_after_delete(mapper, connection, target):
    """
    Remove file from filesystem after row gets deleted in database
    """
    file_path = os.path.join(current_app.config.get('SYMLINK_TO_DATA_STORAGE'), target.folder, current_app.config.get('UPLOADS_FOLDER'), target.name)
    silent_remove(file_path)


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
