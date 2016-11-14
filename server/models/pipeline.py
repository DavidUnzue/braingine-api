from marshmallow import Schema, fields


class PipelineSchema(Schema):
    id = fields.Str()
    name = fields.Str()
    description = fields.Str()
    command = fields.Str()
    parameters = fields.List(fields.Dict())
