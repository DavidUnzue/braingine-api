#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import current_app
from flask.ext.restful import Resource
import json


class StorageFileListController(Resource):
    def get(self):
        from os import listdir
        from os.path import isfile, join
        # get files from preuploads folder in storage server (ignore those starting with ".")
        storage_files = [f for f in listdir(current_app.config.get('SYMLINK_TO_DATA_STORAGE_PREUPLOADS')) if isfile(join(current_app.config.get('SYMLINK_TO_DATA_STORAGE_PREUPLOADS'), f)) and not f.startswith(".")]

        return storage_files, 200
