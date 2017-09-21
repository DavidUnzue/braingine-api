#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import current_app, g
from flask.ext.restful import Resource
import os, glob
from .auth import auth
from .api_utils import store_illumina_file
from ..models.collection import Collection
from webargs import fields
from webargs.flaskparser import use_args

class IlluminaFolderListController(Resource):
    decorators = [auth.login_required]

    def get(self):
        raw_data_folder = current_app.config.get('ILLUMINA_ROOT_INTERNAL')
        # get list of illumina run folders
        illumina_folders = [f for f in os.listdir(raw_data_folder) if os.path.isdir(os.path.join(raw_data_folder, f))]

        return illumina_folders, 200


class IlluminaFolderFileListController(Resource):
    decorators = [auth.login_required]

    def get(self, folder_uid):
        files_folder = os.path.join(current_app.config.get('ILLUMINA_ROOT_INTERNAL'), folder_uid, current_app.config.get('ILLUMINA_FASTQ_FOLDER'))
        # get fastq files from specific illumina run folder
        illumina_files = glob.glob(os.path.join(files_folder, '*.fastq.gz'))

        return illumina_files, 200

    def post(self, folder_uid):
        user = g.user
        files_folder = os.path.join(current_app.config.get('ILLUMINA_ROOT_INTERNAL'), folder_uid, current_app.config.get('ILLUMINA_FASTQ_FOLDER'))
        # get fastq files from specific illumina run folder
        illumina_files = [f for f in os.listdir(files_folder) if os.path.isfile(os.path.join(files_folder, f)) and not f.startswith(".") and f.endswith('.fastq.gz')]

        for fastq_file in illumina_files:
            new_file = store_illumina_file(fastq_file, folder_uid, user)

        return {}, 200
