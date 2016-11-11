#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import abort, current_app
from flask.ext.restful import Resource, reqparse, fields

from server import db
from server.models.pipeline import PipelineSchema
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

        pipeline_definition_list = list()
        for pipleine_file in pipeline_files:
            with open('{}/{}'.format(current_app.config.get('PIPELINES_FOLDER'), pipleine_file)) as pipeline_definition_file:
                pipeline_definition = json.load(pipeline_definition_file)
                pipeline_definition_list.append(pipeline_definition)

        result = pipeline_schema.dump(pipeline_definition_list, many=True).data
        return result, 200


class PipelineController(Resource):
    def get(self, pipeline_filename):

        with open('{}/{}.json'.format(current_app.config.get('PIPELINES_FOLDER'), pipeline_filename)) as pipeline_definition_file:
            pipeline_definition = json.load(pipeline_definition_file)

        result = pipeline_schema.dump(pipeline_definition).data
        return result, 200
