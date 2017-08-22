#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os, json, werkzeug, shutil
from flask import abort, current_app
from flask.ext.restful import Resource

from .. import db
from ..models.experiment import Experiment, ExperimentFile, ExperimentFileSchema
from .auth import auth
from . import api
from webargs import fields
from webargs.flaskparser import use_args
from ..utils import sha1_string

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
        'experiment_id': fields.Str(load_from='X-Experiment-Id', location='headers'),
        'content-range': fields.Str(load_from='Content-Range', location='headers', missing=None),
        'content-length': fields.Int(load_from='Content-Length', location='headers', missing=0),
    })
    def post(self, args):
        from .api_utils import store_file_upload

        # Make the filename safe, remove unsupported chars
        filename = werkzeug.secure_filename(args['filename'])
        # get experiment
        experiment = Experiment.query.get(args['experiment_id'])
        experiment_folder = sha1_string(experiment.name)

        input_file_path = os.path.join(current_app.config.get('SYMLINK_TO_DATA_STORAGE_PREUPLOADS'), args['temp_filename'])

        output_file_path = os.path.join(current_app.config.get('DATA_ROOT_INTERNAL'), current_app.config.get('EXPERIMENTS_FOLDER'), experiment_folder, current_app.config.get('UPLOADS_FOLDER'), filename)

        # handle chunked file upload
        if args['content-range']:

            # extract byte numbers from Content-Range header string
            content_range = args['content-range']
            range_str = content_range.split(' ')[1]
            start_bytes = int(range_str.split('-')[0])
            end_bytes = int(range_str.split('-')[1].split('/')[0])
            total_bytes = int(range_str.split('/')[1])


            # append chunk to the file on server, or create new
            with open(output_file_path, "ab") as output_file, open(input_file_path, "rb") as input_file:
                output_file.write(input_file.read())
            # remove temp file after copying contents
            try:
                os.remove(input_file_path)
            except OSError:
                print('Not able to remove file under {}'.format(input_file_path))

            # check if these are the last bytes
            # if so, create file model
            if end_bytes >= (total_bytes - 1):
                experimentFile = store_file_upload(filename, experiment)
                result = experiment_file_schema.dump(experimentFile, many=False).data
                return result, 200
            # otherwise, return range as string
            else:
                return range_str, 201

        # handle small/non-chunked file upload
        else:
            # move file from preuploads to corresponding uploads folder
            shutil.move(input_file_path, output_file_path)
            experimentFile = store_file_upload(filename, experiment)
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
