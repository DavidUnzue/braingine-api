import werkzeug, os, shutil, magic
from flask import current_app
from ..models.experiment import Experiment, ExperimentFile
from ..utils import sha1_string
from .. import db


def file_upload(temp_filename, filename, experiment_id):
        # Make the filename safe, remove unsupported chars
        filename = werkzeug.secure_filename(filename)

        # get experiment
        experiment = Experiment.query.get(experiment_id)

        experiment_folder = sha1_string(experiment.name)

        # path to the file in the storage server
        file_path = os.path.join(current_app.config.get('EXPERIMENTS_FOLDER'), experiment_folder, current_app.config.get('UPLOADS_FOLDER'), filename)

        file_path_internal = os.path.join(current_app.config.get('DATA_ROOT_INTERNAL'), file_path)

        # destination where python should write the file to internally, using the symlink to the mounted storage server
        # write_file_to = os.path.join(current_app.config.get('DATA_ROOT_INTERNAL'), current_app.config.get('EXPERIMENTS_FOLDER'), experiment_folder, current_app.config.get('UPLOADS_FOLDER'), filename)
        # move file from preuploads to corresponding uploads folder
        shutil.move(os.path.join(current_app.config.get('SYMLINK_TO_DATA_STORAGE_PREUPLOADS'), temp_filename), file_path_internal)

        # initialize file handle for magic file type detection
        fh_magic = magic.Magic(magic_file=current_app.config.get('BIOINFO_MAGIC_FILE'), uncompress=True)
        # get bioinformatic file type using magic
        file_format_full = fh_magic.from_file(file_path_internal)
        # get mimetype of file using magic
        mimetype = magic.from_file(file_path_internal, mime=True)
        # get file size
        file_stats = os.stat(file_path_internal)
        file_size = file_stats.st_size

        experimentFile = ExperimentFile(experiment_id=experiment_id, size_in_bytes=file_size, name=filename, path=file_path, folder=experiment_folder, mime_type=mimetype, file_format_full=file_format_full, is_upload=True)
        db.session.add(experimentFile)
        db.session.commit()

        return experimentFile
