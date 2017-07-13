#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
from flask import abort, current_app
from flask.ext.restful import Resource

from .. import db
from ..models.experiment import ExperimentFile, ExperimentFileSchema
import json
from . import api
from webargs import fields
from webargs.flaskparser import use_args

experiment_file_schema = ExperimentFileSchema()


class FileListController(Resource):
    decorators = [auth.login_required]

    @use_args({
        'page': fields.Int(missing=1)
    })
    def get(self, args):
        # pagination
        page = args['page']
        pagination = ExperimentFile.query.paginate(page, current_app.config.get('ITEMS_PER_PAGE'), False)
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

    @use_args({
        'temp_filename': fields.Str(load_from='X-Temp-File-Name', location='headers'),
        'filename': fields.Str(load_from='X-File-Name', location='headers'),
        'experiment_id': fields.Str(load_from='X-Experiment-Id', location='headers')
    })
    def post(self, args):
        from .api_utils import file_upload
        experimentFile = file_upload(args['temp_filename'], args['filename'], args['experiment_id'])

        result = experiment_file_schema.dump(experimentFile, many=False).data
        return result, 201

class FileController(Resource):
    decorators = [auth.login_required]
    
    def request_wants_json(self):
        from flask import request
        best = request.accept_mimetypes \
            .best_match(['application/json', 'text/html'])
        return best == 'application/json' and \
            request.accept_mimetypes[best] > \
            request.accept_mimetypes['text/html']

    def download_file(self, experiment_file, attachment=False):
        """Makes a Flask response with the corresponding content-type encoded body"""
        from flask import send_from_directory
        data_path = os.path.abspath(current_app.config.get('DATA_ROOT_INTERNAL'))
        return send_from_directory(data_path, experiment_file.path, mimetype=experiment_file.mime_type, as_attachment=attachment)

    @use_args({
        'accept': fields.Str(load_from='Accept', location='headers'), # default is */* for accepting everything
        'download': fields.Boolean(location='querystring', missing=False) # force download or not
    })
    def get(self, args, file_id):
        print(args['accept'])
        single_file = ExperimentFile.query.get(file_id)
        if not single_file:
            abort(404, "File {} doesn't exist".format(file_id))
        # metadata as json requested
        if self.request_wants_json():
        # if (args['accept'] == 'application/json'):
            result = experiment_file_schema.dump(single_file).data
            return result, 200
        # otherwise send file contents
        # elif (args['accept'] == single_file.mime_type or args['accept'] == '*/*'):
        else:
            return self.download_file(single_file, args['download'])
        # not acceptable content-type requested
        # else:
        #     abort(406, "The resource identified by the request is only capable of generating response entities which have content characteristics not acceptable according to the accept headers sent in the request.")

    def delete(self, file_id):
        experiment_file = ExperimentFile.query.get(file_id)
        if not experiment_file:
            abort(404, "Experiment file {} doesn't exist".format(file_id))
        db.session.delete(experiment_file)
        db.session.commit()
        return {}, 204
