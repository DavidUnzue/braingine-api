from .base import Base, BaseSchema
from marshmallow import fields
from passlib.apps import custom_app_context as pwd_context


class User(Base):

    __tablename__ = 'users'

    username = db.Column(db.String(32), index = True)
    password_hash = db.Column(db.String(128))

    def __init__(self, username, password):
        self.script = script
        hash_password(password)

    def __repr__(self):
        return '<User {}>'.format(self.id)

    def hash_password(self, password):
        self.password_hash = pwd_context.encrypt(password)

    def verify_password(self, password):
        return pwd_context.verify(password, self.password_hash)


class UserSchema(BaseSchema):
    username = fields.Str()
    password_hash = fields.Str(dump_only=True)
