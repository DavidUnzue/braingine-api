#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import abort, current_app
from flask.ext.restful import Resource, reqparse, fields

from server import db
from server.models import Pipeline, PipelineSchema
from . import api
import json


pipeline_schema = PipelineSchema()

parser = reqparse.RequestParser()

class PipelineListController(Resource):
    def get(self):
        from os import listdir
        from os.path import isfile, join
        # get json files (pipeline definition files) from pipelines folder
        pipeline_files = [f for f in listdir(current_app.config.get('PIPELINES_FOLDER')) if isfile(join(current_app.config.get('PIPELINES_FOLDER'), f)) and f.endswith(".json")]

        # parser.add_argument('page', type=int, default=1, location=['args'])
        # parsed_args = parser.parse_args()
        # page = parsed_args['page']

        # pagination = Pipeline.query.paginate(page, 5)
        # pipelines = pagination.items
        # page_prev = None
        # if pagination.has_prev:
        #     page_prev = api.url_for(self, page=page-1, _external=True)
        # page_next = None
        # if pagination.has_next:
        #     page_next = api.url_for(self, page=page+1, _external=True)
        #
        # result = pipeline_schema.dump(pipelines, many=True).data
        result = pipeline_files
        return result, 200


class PipelineController(Resource):
    def get(self, pipeline_filename):
        # parser.add_argument('pipeline_filename', type=int, default=1, location=['form, json'])
        # parsed_args = parser.parse_args()
        # pipeline_filename = parsed_args['pipeline_filename']

        with open('{}/{}.json'.format(current_app.config.get('PIPELINES_FOLDER'), pipeline_filename)) as pipeline_definition_file:
            pipeline_definition = json.load(pipeline_definition_file)

        # pipeline_input = pipeline_definition["inputs"][0]
        # pipeline_output = pipeline_definition["outputs"][0]

        # pipeline = Pipeline.query.get(pipeline_id)
        # if not pipeline:
        #     abort(404, "Pipeline {} doesn't exist".format(pipeline_id))
        # result = pipeline_schema.dump(pipeline_definition).data
        result = pipeline_definition
        return result, 200
