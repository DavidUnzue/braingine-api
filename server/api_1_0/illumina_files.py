#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import current_app
from flask.ext.restful import Resource
import os, glob
from api_utils import store_illumina_file

class IlluminaFolderListController(Resource):
    def get(self):
        raw_data_folder = current_app.config.get('ILLUMINA_ROOT_INTERNAL')
        # get list of illumina run folders
        illumina_folders = [f for f in os.listdir(raw_data_folder) if os.path.isdir(os.path.join(raw_data_folder, f))]

        return illumina_folders, 200


class IlluminaFolderFileListController(Resource):
    def get(self, folder_uid):
        files_folder = os.path.join(current_app.config.get('ILLUMINA_ROOT_INTERNAL'), folder_uid, current_app.config.get('ILLUMINA_FASTQ_FOLDER'))
        # get fastq files from specific illumina run folder
        illumina_files = glob.glob(os.path.join(files_folder, '*.fastq.gz'))

        return illumina_files, 200

    @use_args({
        'experiment_id': fields.Boolean(location='header', missing=None)
    })
    def post(self, args, folder_uid):
        files_folder = os.path.join(current_app.config.get('ILLUMINA_ROOT_INTERNAL'), folder_uid, current_app.config.get('ILLUMINA_FASTQ_FOLDER'))
        # get fastq files from specific illumina run folder
        illumina_files = [f for f in listdir(current_app.config.get('ILLUMINA_ROOT_INTERNAL')) if isfile(join(current_app.config.get('ILLUMINA_ROOT_INTERNAL'), f)) and not f.startswith(".") and f.endswith('.fastq.gz')]

        for fastq_file in illumina_files:
            store_illumina_file()
