import marshmallow as ma
from marshmallow import fields as ma_fields
import marshmallow_jsonapi as majapi
import webargs.core
import webargs.flaskparser


class JsonApiNested(ma.Schema):
    """ Placeholder wrapper for webargs to marshmallow-jsonapi handling. """
    # webargs.flaskparser.FlaskParser specifically returns missing if there is no json
    # at all instead of returning the field default
    data = ma_fields.Dict(required=True)  #, missing={}, default={})
    class Meta:  # pylint: disable=too-few-public-methods
        """ Sets strict so an error will be raised when invalid data is passed in. """
        strict = True


class JsonApiParser(webargs.flaskparser.FlaskParser):
    """ Special case handling for marshmallow-jsonapi.Schema's """
    def _parse_request(self, schema, req, locations):
        if isinstance(schema, majapi.Schema):
            jsonapi = JsonApiNested()
            data = super(JsonApiParser, self)._parse_request(jsonapi, req, locations)
            if data['data'] == webargs.core.missing:
                data = {}
        else:
            data = super(JsonApiParser, self)._parse_request(schema, req, locations)

        return data or {}
