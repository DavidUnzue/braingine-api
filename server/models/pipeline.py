from marshmallow_jsonapi import Schema, fields


class PipelineSchema(Schema):
    id = fields.Str()
    name = fields.Str()
    description = fields.Str()
    command = fields.Str()
    parameters = fields.List(fields.Dict())

    class Meta:
        type_ = 'pipelines'
        strict = True
        self_url = '/api/pipelines/{id}'
        self_url_kwargs = {'id': '<id>'}
