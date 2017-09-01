import os
from .. import db
from .base import Base, BaseSchema
from marshmallow import fields
from flask import abort, current_app
from ..utils import create_folder, silent_remove


association_user_to_user_group = db.Table('users_to_user_groups', Base.metadata,
    db.Column('user_id', db.Integer, db.ForeignKey('users.id', ondelete="CASCADE")),
    db.Column('group_id', db.Integer, db.ForeignKey('user_groups.id', ondelete="CASCADE"))
)

class User(Base):

    __tablename__ = 'users'

    username = db.Column(db.String(32), index=True, unique=True, nullable=False)
    fullname = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    groups = db.relationship("UserGroup",
                    secondary=association_user_to_user_group)

    def __init__(self, username, fullname, email):
        self.username = username
        self.fullname = fullname
        self.email = email

    def __repr__(self):
        return '<User {}>'.format(self.username)


class UserSchema(BaseSchema):
    username = fields.Str()
    email = fields.Str()
    fullname = fields.Str()


@db.event.listens_for(User, 'after_insert')
def create_user_directory(mapper, connection, target):
    """
    Create user directory in storage after new entry created in DB
    """
    # setup folders for project data
    user_folder = os.path.join(current_app.config.get('SYMLINK_TO_DATA_STORAGE'), target.username)
    uploads_folder = os.path.join(user_folder, current_app.config.get('UPLOADS_FOLDER'))
    analyses_folder = os.path.join(user_folder, current_app.config.get('ANALYSES_FOLDER'))

    try:
        create_folder(user_folder)
        create_folder(uploads_folder)
        create_folder(analyses_folder)
    except OSError as err:
        try:
            db.session.delete(target)
            db.session.commit()
            silent_remove(user_folder)
        finally:
            abort(404, "Error creating user directory structure on storage service: {}".format(err))


class UserGroup(Base):
    __tablename__ = 'user_groups'

    group_id = db.Column(db.String(250), index=True, unique=True, nullable=False)

    def __init__(self, group_id):
        self.group_id = group_id

    def __repr__(self):
        return '<User group {}>'.format(self.group_id)


class UserGroupSchema(BaseSchema):
    group_id = fields.Int()
