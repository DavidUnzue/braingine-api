#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import current_app
from flask.ext.restful import Resource
import os, glob

class IlluminaFolderListController(Resource):
    def get(self):
        raw_data_folder = os.path.join(current_app.config.get('ILLUMINA_ROOT_INTERNAL'), current_app.config.get('ILLUMINA_DATA_FOLDER'))
        # get files from preuploads folder in storage server
        illumina_folders = [f for f in os.listdir(raw_data_folder) if os.path.isdir(os.path.join(raw_data_folder, f))]

        return illumina_folders, 200


class IlluminaFileListController(Resource):
    def get(self, folder_uid):
        files_folder = os.path.join(current_app.config.get('ILLUMINA_ROOT_INTERNAL'), current_app.config.get('ILLUMINA_DATA_FOLDER'), folder_uid, current_app.config.get('ILLUMINA_FASTQ_FOLDER'))
        # get files from preuploads folder in storage server
        illumina_files = glob.glob(os.path.join(files_folder, '*.fastq.gz'))

        return illumina_files, 200
