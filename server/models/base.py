from server import db
from marshmallow import Schema, fields


def same_as(column_name):
    """
    Helper function to set one column's default as the value of another column

    this could be implemented as lambda function:
    same_as = lambda col: lambda ctx: ctx.current_parameters.get(col)
    """
    def set_default(context):
        return context.current_parameters.get(column_name)
    return set_default

# Define a base model for other models to inherit
class Base(db.Model):
    """
    Base model with attributes common to every model. Other models will inherit from this one.
    """

    # tell SQLAlchemy not to create a table for a this model
    __abstract__  = True

    id = db.Column(db.Integer, primary_key=True)
    created_at  = db.Column(db.DateTime(timezone=True),  default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime(timezone=True),  default=db.func.current_timestamp(),
                                           onupdate=db.func.current_timestamp())


# Marshmallow schema for base model
class BaseSchema(Schema):
    id = fields.Integer(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
