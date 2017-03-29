# -*- coding: utf-8 -*-
"""
    server.tasks
    ~~~~~~~~~~~~~~
    module for long running tasks
"""
import os, magic
from flask import current_app
from . import create_celery_app
from .utils import connect_ssh, read_dir, write_file_in_chunks
# Import db instance
from server import db
from server.models.experiment import Analysis, Experiment, ExperimentFile, AssociationAnalysesOutputFiles
# celery logger
from celery.utils.log import get_task_logger
from celery import states as celery_states

logger = get_task_logger(__name__)

celery = create_celery_app()

class PipelineError(Exception):
    """Exception raised when a remote running pipeline exits before finishing."""

    def __init__(self, message, exit_code, stdout, stderr):
        # call parent class with message
        super(PipelineError, self).__init__(message)
        # custom attributes
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr


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
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        # update analysis status
        experiment_analysis_id = kwargs['analysis_id']
        experiment_analysis = Analysis.query.get(experiment_analysis_id)
        experiment_analysis.state = celery_states.FAILURE
        db.session.add(experiment_analysis)
        db.session.commit()

        # retrieve experiment info and folder to write output files to
        experiment = Experiment.query.get(experiment_analysis.experiment_id)
        experiment_folder = os.path.join(current_app.config.get('SYMLINK_TO_DATA_STORAGE'), experiment.sha)
        analysis_folder = os.path.join(experiment_folder, current_app.config.get('ANALYSES_FOLDER'), str(experiment_analysis.id))

        # write stdout to file
        write_file_in_chunks(analysis_folder, "log.out", exc.stdout)

        # write stderr to file
        write_file_in_chunks(analysis_folder, "error.out", exc.stderr)

        # call method on parent class
        super(AnalysisTask, self).on_failure(exc, task_id, args, kwargs, einfo)

    def on_success(self, retval, task_id, args, kwargs):
        # update analysis status
        experiment_analysis_id = kwargs['analysis_id']
        experiment_analysis = Analysis.query.get(experiment_analysis_id)
        experiment_analysis.state = celery_states.SUCCESS
        db.session.add(experiment_analysis)

        # retrieve experiment info and folder to write output files to
        experiment = Experiment.query.get(experiment_analysis.experiment_id)
        experiment_folder = os.path.join(current_app.config.get('SYMLINK_TO_DATA_STORAGE'), experiment.sha)
        analysis_folder = os.path.join(experiment_folder, current_app.config.get('ANALYSES_FOLDER'), str(experiment_analysis.id))

        # create dict to associate analysis output files to corresponding fieldnames in pipeline definition
        analysis_outputs = kwargs['analysis_outputs']
        analysis_ouput_file_fieldname_assoc = {}
        for fieldname, filename in analysis_outputs.items():
            analysis_ouput_file_fieldname_assoc[filename] = fieldname

        # create DB entries for each analysis output file
        for root, subdirs, files in os.walk(analysis_folder):
            # read analysis files in directory
            for filename in files:
                basename = os.path.basename(os.path.normpath(os.path.dirname(filename)))
                if filename in analysis_ouput_file_fieldname_assoc:
                    pipeline_fieldname = filename
                elif basename in analysis_ouput_file_fieldname_assoc:
                    pipeline_fieldname = basename
                else:
                    continue

                file_path = os.path.join(root, filename)
                # initialize file handle for magic file type detection
                fh_magic = magic.Magic(magic_file=current_app.config.get('BIOINFO_MAGIC_FILE'))

                # get bioinformatic file type using magic
                file_type = fh_magic.from_file(file_path)
                mime_type = magic.from_file(file_path, mime=True)

                # create file object and add to DB
                new_file = ExperimentFile(experiment_id=experiment.id, size_in_bytes=os.path.getsize(file_path), name=filename, path=file_path, mime_type=mime_type, file_type=file_type, folder=experiment.sha)
                db.session.add(new_file)

                # link file to analysis output
                analysis_output_file_assoc = AssociationAnalysesOutputFiles(pipeline_fieldname=pipeline_fieldname)
                analysis_output_file_assoc.output_file = new_file
                experiment_analysis.output_files.append(analysis_output_file_assoc)

        db.session.commit()

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        # # update analysis status
        # experiment_analysis_id = kwargs['analysis_id']
        # experiment_analysis = Analysis.query.get(experiment_analysis_id)
        # experiment_analysis.state = status
        # db.session.add(experiment_analysis)
        # db.session.commit()
        pass


@celery.task(base=AnalysisTask)
def run_analysis(command, **kwargs):
    ssh = connect_ssh(current_app.config.get('COMPUTING_SERVER_IP'), current_app.config.get('COMPUTING_SERVER_USER'), current_app.config.get('COMPUTING_SERVER_PASSWORD'))
    stdin, stdout, stderr = ssh.exec_command(command)
    # exit code of pipeline script
    exit_code = stdout.channel.recv_exit_status()
    # if pipeline exits with error code (different than 0)
    if exit_code != 0:
        message = "The pipeline with id '{}' raised an error".format(kwargs['pipeline_id'])
        raise PipelineError(message, exit_code, stdout, stderr)
    return kwargs['analysis_id']
