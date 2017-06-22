#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import current_app
from flask.ext.restful import Resource
import os

class IlluminaFileListController(Resource):
    def get(self):
        raw_data_folder = os.path.join(current_app.config.get('ILLUMINA_ROOT_INTERNAL'), 'raw_data')
        # get files from preuploads folder in storage server
        illumina_folders = [f for f in os.listdir(raw_data_folder) if os.path.isdir(os.path.join(raw_data_folder, f))]

        return illumina_folders, 200
