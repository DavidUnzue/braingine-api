# -*- coding: utf-8 -*-
"""
    server.tasks
    ~~~~~~~~~~~~~~
    module for long running tasks
"""
import os, magic
from flask import current_app
from . import create_celery_app
from utils import connect_ssh, read_dir
# Import db instance
from server import db
from server.models.experiment import Analysis, Experiment, ExperimentFile
# celery logger
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

celery = create_celery_app()

class BaseTask(celery.Task):
    """Abstract base class for all tasks."""

    abstract = True

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Log the exceptions to celery logger at retry."""
        logger.info(exc)
        super(BaseTask, self).on_retry(exc, task_id, args, kwargs, einfo)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Log the exceptions to celery logger."""
        logger.info(exc)
        super(BaseTask, self).on_failure(exc, task_id, args, kwargs, einfo)


class AnalysisTask(BaseTask):

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        experiment_analysis_id = retval
        experiment_analysis = Analysis.query.get(experiment_analysis_id)
        experiment_analysis.state = status
        db.session.add(experiment_analysis)

        experiment = Experiment.query.get(experiment_analysis.experiment_id)
        experiment_folder = os.path.join(current_app.config.get('SYMLINK_TO_DATA_STORAGE'), experiment.sha)
        analysis_folder = os.path.join(experiment_folder, current_app.config.get('ANALYSES_FOLDER'), str(experiment_analysis.id))

        # read analysis files in directory
        for filename in read_dir(analysis_folder):
            file_path = os.path.join(analysis_folder, filename)
            # initialize file handle for magic file type detection
            fh_magic = magic.Magic(magic_file=current_app.config.get('BIOINFO_MAGIC_FILE'))
            # get bioinformatic file type using magic on the first chunk of the file
            file_type = fh_magic.from_file(file_path)
            mime_type = magic.from_file(file_path, mime=True)

            new_file = ExperimentFile(experiment_id=experiment.id, size_in_bytes=os.path.getsize(file_path), name=filename, path=file_path, mime_type=mime_type, file_type=file_type, folder=experiment.sha)
            experiment_analysis.output_files.append(new_file)
            db.session.add(new_file)

        db.session.commit()


@celery.task(base=AnalysisTask)
def run_analysis(command, analysis_id):
    ssh = connect_ssh(current_app.config.get('COMPUTING_SERVER_IP'), current_app.config.get('COMPUTING_SERVER_USER'), current_app.config.get('COMPUTING_SERVER_PASSWORD'))
    stdin, stdout, stderr = ssh.exec_command(command, get_pty=True)
    output = ''
    for line in stdout:
        print line.strip('\n')
        output += line.strip('\n')
    return analysis_id
