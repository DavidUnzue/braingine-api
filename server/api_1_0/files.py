#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import abort, current_app
from flask.ext.restful import Resource

from ..models.experiment import ExperimentFile, ExperimentFileSchema
import json
from . import api
from webargs import fields
from webargs.flaskparser import use_args

experiment_file_schema = ExperimentFileSchema()


class FileListController(Resource):
    @use_args({
        'page': fields.Int(missing=1)
    })
    def get(self, args):
        # pagination
        page = args['page']
        pagination = ExperimentFile.query.paginate(page, 5, False)
        files = pagination.items
        #experiments = Experiment.query.all()
        page_prev = None
        if pagination.has_prev:
            page_prev = api.url_for(self, page=page-1, _external=True)
        page_next = None
        if pagination.has_next:
            page_next = api.url_for(self, page=page+1, _external=True)

        result = experiment_file_schema.dump(files, many=True).data

        return result, 200


class FileController(Resource):
    def get(self, file_id):
        single_file = ExperimentFile.query.get(file_id)
        if not single_file:
            abort(404, "File {} doesn't exist".format(file_id))
        result = experiment_file_schema.dump(single_file).data
        return result, 200
