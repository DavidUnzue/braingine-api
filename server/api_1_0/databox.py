#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os, json, werkzeug, shutil
from flask import abort, current_app, g
from flask.ext.restful import Resource

from .. import db
from sqlalchemy import text
from ..models.file import ExperimentFile, ExperimentFileSchema
from ..models.user import User
from ..models.databox import DataBox, DataBoxSchema
from .auth import auth
from . import api
from webargs import fields
from webargs.flaskparser import use_args
from ..utils import sha1_string
from .api_utils import create_pagination_header, create_projection, store_file_upload

experiment_file_schema = ExperimentFileSchema()
databox_schema = DataBoxSchema()

class DataboxController(Resource):
    decorators = [auth.login_required]

    def get(self):
        user = g.user
        databox = DataBox.query.filter_by(user_id=user.id)

        result = databox_schema.dump(databox).data
        return result, 200


class DataBoxFileListController(Resource):
    decorators = [auth.login_required]

    @use_args({
        'fileIds[]': fields.List(fields.Int(), missing=[]),
    })
    def post(self, args):
        if len(args['fileIds[]']) > 0:
            user = g.user
            databox = DataBox.query.filter_by(user_id=user.id).first()
            files = ExperimentFile.query.filter(ExperimentFile.id in args['fileIds[]']).all()
            print(files)
            # for fileId in args['fileIds']:
            #     currentFile = ExperimentFile.query.get(fileId)
            #     databox.files.append(currentFile)
            # for currentFile in files:
            #     databox.files.append(currentFile)
            # # databox.files.extend(files)
            # db.session.commit()
            return 201, databox.files


    @use_args({
        # access querystring arguments to filter files by is_upload
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
        if args['where']:
            filters.update(json.loads(args['where']))

        databox = DataBox.query.filter_by(user_id=user.id).first()
        databox_files_query = databox.files.filter_by(**filters)

        if args['projection']:
            projection = json.loads(args['projection'])
            databox_files_query = create_projection(databox_files_query, projection)
        if args['merge']:
            databox_files_query = databox_files_query.distinct()
        if args['sort_by'] and args['order']:
            sort = "{} {}".format(args['sort_by'], args['order'])
        else:
            sort = "updated_at desc"
        databox_files_query = databox_files_query.order_by(text(sort))

        # create pagination
        page = args['page']
        per_page = args['per_page'] or current_app.config.get('ITEMS_PER_PAGE')
        pagination = databox_files_query.paginate(page, per_page, False)
        # pagination headers
        link_header = create_pagination_header(self, pagination, page)

        # reponse body
        databox_files = pagination.items
        result = experiment_file_schema.dump(databox_files, many=True).data
        return result, 200, link_header
