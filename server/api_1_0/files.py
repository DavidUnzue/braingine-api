#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os, json, werkzeug, shutil
from flask import abort, current_app, g
from flask.ext.restful import Resource

from .. import db
from sqlalchemy import text
from ..models.file import ExperimentFile, ExperimentFileSchema
from ..models.user import User
from .auth import auth
from . import api
from webargs import fields
from webargs.flaskparser import use_args
from ..utils import sha1_string
from .api_utils import create_pagination_header, create_projection, store_file_upload

experiment_file_schema = ExperimentFileSchema()


class FileListController(Resource):
    decorators = [auth.login_required]

    @use_args({
        # access querystring arguments to filter files by is_upload
        'is_upload': fields.Bool(location='query', missing=None),
        'page': fields.Int(location='query', missing=1),
        'per_page': fields.Int(location='query', missing=None),
        'projection': fields.Str(location='query', missing=None),
        'merge': fields.Bool(location='query', missing=False),
        'sort_by': fields.Str(location='query', missing=None),
        'order': fields.Str(location='query', missing=None),
        'where': fields.Str(location='query', missing=None)
    })
    def get(self, args):
        # pagination
        page = args['page']
        user = g.user
        # filtering
        filters = {}
        filters['user_id'] = user.id
        if args['is_upload']:
            filters['is_upload'] = args['is_upload']
        if args['where']:
            filters.update(json.loads(args['where']))

        experiment_files_query = ExperimentFile.query.filter_by(**filters)

        if args['projection']:
            projection = json.loads(args['projection'])
            experiment_files_query = create_projection(experiment_files_query, projection)
        if args['merge']:
            experiment_files_query = experiment_files_query.distinct()
        if args['sort_by'] and args['order']:
            sort = "{} {}".format(args['sort_by'], args['order'])
        else:
            sort = "updated_at desc"
        experiment_files_query = experiment_files_query.order_by(text(sort))

        # create pagination
        page = args['page']
        per_page = args['per_page'] or current_app.config.get('ITEMS_PER_PAGE')
        pagination = experiment_files_query.paginate(page, per_page, False)
        # pagination headers
        link_header = create_pagination_header(self, pagination, page)

        # reponse body
        experiment_files = pagination.items
        result = experiment_file_schema.dump(experiment_files, many=True).data
        return result, 200, link_header


    @use_args({
        'temp_filename': fields.Str(load_from='X-Temp-File-Name', location='headers'),
        'filename': fields.Str(load_from='X-File-Name', location='headers'),
        'content-range': fields.Str(load_from='Content-Range', location='headers', missing=None),
        'content-length': fields.Int(load_from='Content-Length', location='headers', missing=0),
    })
    def post(self, args):
        user = g.user

        # Make the filename safe, remove unsupported chars
        filename = werkzeug.secure_filename(args['filename'])
        # get user folder
        user_folder = user.username

        input_file_path = os.path.join(current_app.config.get('DATA_STORAGE_PREUPLOADS'), args['temp_filename'])

        output_file_path = os.path.join(current_app.config.get('BRAINGINE_ROOT'), current_app.config.get('DATA_FOLDER'), user_folder, current_app.config.get('UPLOADS_FOLDER'), filename)

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
                experimentFile = store_file_upload(filename, user)
                result = experiment_file_schema.dump(experimentFile, many=False).data
                return result, 200
            # otherwise, return range as string
            else:
                return range_str, 201

        # handle small/non-chunked file upload
        else:
            # move file from preuploads to corresponding uploads folder
            shutil.move(input_file_path, output_file_path)
            experimentFile = store_file_upload(filename, user)
            result = experiment_file_schema.dump(experimentFile, many=False).data
            return result, 201


class FileController(Resource):
    decorators = [auth.login_required]

    def download_file(self, experiment_file, attachment=False, bytes_range=None):
        """Makes a Flask response with the corresponding content-type encoded body"""
        from flask import send_from_directory
        file_folder_path = os.path.dirname(os.path.abspath(experiment_file.path))
        # read only specific bytes-range
        if bytes_range:
            start, end = map(int, bytes_range.split('=')[1].split('-'))
            buffer_size = end - start
            with open(os.path.join(file_folder_path,experiment_file.name),"r") as file_object:
                file_object.seek(start) # set file pointer to start of range
                file_data = file_object.read(buffer_size)
            return file_data, 206
        return send_from_directory(file_folder_path, experiment_file.name, mimetype=experiment_file.mime_type, as_attachment=attachment)

    @use_args({
        'alt': fields.Str(location='querystring', missing=''), # return file contents with 'alt=media'
        'download': fields.Boolean(location='querystring', missing=False), # force download or not
        'range': fields.Str(load_from='Range', location='headers', missing=None)
    })
    def get(self, args, file_id):
        single_file = ExperimentFile.query.get(file_id)
        if not single_file:
            abort(404, "File {} doesn't exist".format(file_id))
        # return file contents if 'alt=media' in querystring
        if args['alt'] == 'media':
            return self.download_file(single_file, args['download'], args['range'])
        # return only file's metadata as json
        else:
            result = experiment_file_schema.dump(single_file).data
            return result, 200

    def delete(self, file_id):
        experiment_file = ExperimentFile.query.get(file_id)
        if not experiment_file:
            abort(404, "Experiment file {} doesn't exist".format(file_id))
        db.session.delete(experiment_file)
        db.session.commit()
        return {}, 204
