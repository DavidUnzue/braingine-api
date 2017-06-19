#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import current_app
from flask.ext.restful import Resource

from server.models.pipeline import PipelineSchema
import json


pipeline_schema = PipelineSchema()

class PipelineListController(Resource):
    def get(self):
        import glob
        from os import listdir
        from os.path import isfile, join

        pipelines_folder = current_app.config.get('PIPELINES_FOLDER')
        # get json files (pipeline definition files) from pipelines folders
        pipeline_files = glob.glob(join(pipelines_folder, '**/*.json'), recursive=True)

        pipeline_definition_list = list()
        for pipeline_file in pipeline_files:
            with open(pipeline_file) as pipeline_definition_file:
                pipeline_definition = json.load(pipeline_definition_file)
                pipeline_definition_list.append(pipeline_definition)

        result = pipeline_schema.dump(pipeline_definition_list, many=True).data
        return result, 200


class PipelineController(Resource):
    def get(self, pipeline_filename):

        pipelines_folder = current_app.config.get('PIPELINES_FOLDER')

        with open('{}/{}/{}.json'.format(pipelines_folder, pipeline_filename, pipeline_filename)) as pipeline_definition_file:
            pipeline_definition = json.load(pipeline_definition_file)

        result = pipeline_schema.dump(pipeline_definition).data
        return result, 200
