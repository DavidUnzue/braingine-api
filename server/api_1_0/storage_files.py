#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json, os
from flask import current_app, g
from flask.ext.restful import Resource
from webargs import fields
from webargs.flaskparser import use_args
from .auth import auth
from .api_utils import store_storage_file


class StorageFileListController(Resource):
    decorators = [auth.login_required]

    def get(self):
        # get files from preuploads folder in storage server (ignore those starting with ".")
        storage_files = [f for f in os.listdir(current_app.config.get('DATA_STORAGE_PREUPLOADS')) if os.path.isfile(os.path.join(current_app.config.get('DATA_STORAGE_PREUPLOADS'), f)) and not f.startswith(".")]

        return storage_files, 200

    @use_args({
        'file_path': fields.Str(location='headers', missing=None),
    })
    def post(self, args):
        if args['file_path'] is None:
            abort(404, "File path is missing")
        user = g.user
        path = os.path.abspath(args['file_path'])
        if os.path.exists(path):
            if os.path.isdir(path):
                storage_files = [os.path.join(path, f) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)) and not f.startswith(".")]
                for filepath in storage_files:
                    new_file = store_storage_file(filepath, user)
            elif os.path.isfile(path):
                store_storage_file(path, user)
        else:
            abort(404, "Path does not exist")

        return {}, 200
