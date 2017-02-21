from marshmallow import Schema, fields


class StorageFileSchema(Schema):
    id = fields.Str()
    name = fields.Str()
