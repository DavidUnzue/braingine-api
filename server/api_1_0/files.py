#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import abort, current_app
from flask.ext.restful import Resource

from ..models.experiment import ExperimentFile, ExperimentFileSchema
import json

experiment_file_schema = ExperimentFileSchema()


class FileListController(Resource):
    def get(self):
        files = ExperimentFile.query.all()
        result = experiment_file_schema.dump(files, many=True).data

        return result, 200


class FileController(Resource):
    def get(self, file_id):
        single_file = ExperimentFile.query.get(file_id)
        if not single_file:
            abort(404, "File {} doesn't exist".format(file_id))
        result = experiment_file_schema.dump(single_file).data
        return result, 200
