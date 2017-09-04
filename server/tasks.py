# -*- coding: utf-8 -*-
"""
    server.tasks
    ~~~~~~~~~~~~~~
    module for long running tasks
"""
import os, magic
from flask import current_app
from . import celery
from .utils import connect_ssh, read_dir, write_file_in_chunks
# Import db instance
from . import db
from .models.analysis import Analysis, AssociationAnalysesOutputFiles
from .models.visualization import Visualization
from .models.file import ExperimentFile
from .models.plot import Plot
# celery logger
from celery.utils.log import get_task_logger
from celery import states as celery_states

logger = get_task_logger(__name__)

class PipelineError(Exception):
    """Exception raised when a remote running pipeline exits before finishing."""

    def __init__(self, message, exit_code, stdout, stderr):
        # call parent class with message
        super(PipelineError, self).__init__(message)
        # custom attributes
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr


class PlotError(Exception):
    """Exception raised when a remote running plot exits before finishing."""

    def __init__(self, message, exit_code, stdout, stderr):
        # call parent class with message
        super(PlotError, self).__init__(message)
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

        # retrieve folder to write output files to
        user = g.user
        user_folder = os.path.join(current_app.config.get('SYMLINK_TO_DATA_STORAGE'), user.username)
        analysis_folder = os.path.join(user_folder, current_app.config.get('ANALYSES_FOLDER'), str(experiment_analysis.id))

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

        # retrieve folder to write output files to
        user = g.user
        user_folder = os.path.join(current_app.config.get('EXPERIMENTS_FOLDER'), user.username)
        analysis_folder = os.path.join(user_folder, current_app.config.get('ANALYSES_FOLDER'), str(experiment_analysis.id))
        analysis_folder_internal = os.path.join(current_app.config.get('DATA_ROOT_INTERNAL'), analysis_folder)

        # create dict to associate analysis output files to corresponding fieldnames in pipeline definition
        # this will just invert the key/value pairs within the original analysis_outputs dictionary
        analysis_outputs = kwargs['analysis_outputs']
        analysis_output_file_fieldname_assoc = {}
        for fieldname, filename in analysis_outputs.items():
            analysis_output_file_fieldname_assoc[filename] = fieldname

        # create DB entries for each analysis output file
        for root, subdirs, files in os.walk(analysis_folder_internal):
            # read analysis files in directory
            for filename in files:
                # get name of folder where the file is located
                basename = os.path.basename(os.path.normpath(root))
                filename_no_ext = os.path.splitext(filename)[0]
                if filename in analysis_output_file_fieldname_assoc:
                    # in case fieldname in pipeline definition equals the output filename
                    pipeline_fieldname = analysis_output_file_fieldname_assoc[filename]
                elif filename_no_ext in analysis_output_file_fieldname_assoc:
                    # in case fieldname in pipeline definition equals the output filename without extension
                    pipeline_fieldname = analysis_output_file_fieldname_assoc[filename_no_ext]
                elif basename in analysis_output_file_fieldname_assoc:
                    # in case fieldname in pipeline definition equals the output file's folder
                    pipeline_fieldname = analysis_output_file_fieldname_assoc[basename]
                else:
                    continue

                # remove internal root part (DATA_ROOT_INTERNAL) of path
                clean_root = root[len(current_app.config.get('DATA_ROOT_INTERNAL')):]
                # remove prefix slash
                if (clean_root[0] == os.sep):
                    clean_root = clean_root[1:]

                # path to the file in the storage server
                file_path = os.path.join(clean_root, filename)
                file_path_internal = os.path.join(root, filename)

                # initialize file handle for magic file type detection
                fh_magic = magic.Magic(magic_file=current_app.config.get('BIOINFO_MAGIC_FILE'), uncompress=True)

                # get bioinformatic file type using magic
                file_format_full = fh_magic.from_file(file_path_internal)
                mime_type = magic.from_file(file_path_internal, mime=True)

                file_size = os.path.getsize(file_path_internal)

                # create file object and add to DB
                new_file = ExperimentFile(user_id=user.id, size_in_bytes=file_size, name=filename, path=file_path, mime_type=mime_type, file_format_full=file_format_full, folder=user.username)
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


class VisualizationTask(BaseTask):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        # update status
        visualization_id = kwargs['visualization_id']
        visualization = Analysis.query.get(visualization_id)
        visualization.state = celery_states.FAILURE
        db.session.add(visualization)
        db.session.commit()

        # retrieve experiment info and folder to write output files to
        user = g.user
        user_folder = os.path.join(current_app.config.get('SYMLINK_TO_DATA_STORAGE'), user.username)
        visualization_folder = os.path.join(user_folder, current_app.config.get('VISUALIZATIONS_FOLDER'), str(visualization.id))

        # write stdout to file
        write_file_in_chunks(visualization_folder, "log.out", exc.stdout)

        # write stderr to file
        write_file_in_chunks(visualization_folder, "error.out", exc.stderr)

        # call method on parent class
        super(VisualizationTask, self).on_failure(exc, task_id, args, kwargs, einfo)

    def on_success(self, retval, task_id, args, kwargs):
        # update visualization status
        visualization_id = kwargs['visualization_id']
        visualization = Visualization.query.get(visualization_id)
        visualization.state = celery_states.SUCCESS
        db.session.add(visualization)

        # retrieve experiment info and folder to write output files to
        user = g.user
        user_folder = os.path.join(current_app.config.get('SYMLINK_TO_DATA_STORAGE'), user.username)
        visualization_folder = os.path.join(user_folder, current_app.config.get('VISUALIZATIONS_FOLDER'), str(visualization.id))

        plot = Plot.query.get(kwargs['plot_id'])
        visualization_file = os.path.join(visualization_folder, plot.output_filename, '.html')

        # create DB entries for each analysis output file
        for root, subdirs, files in os.walk(visualization_folder):
            # read analysis files in directory
            for filename in files:
                # remove internal root part (DATA_ROOT_INTERNAL) of path
                clean_root = root[len(current_app.config.get('DATA_ROOT_INTERNAL')):]
                # remove prefix slash
                if (clean_root[0] == os.sep):
                    clean_root = clean_root[1:]

                file_path = os.path.join(clean_root, filename)
                file_path_internal = os.path.join(root, filename)
                file_size = os.path.getsize(file_path_internal)
                # initialize file handle for magic file type detection
                fh_magic = magic.Magic(magic_file=current_app.config.get('BIOINFO_MAGIC_FILE'))

                # get bioinformatic file type using magic
                file_format_full = fh_magic.from_file(file_path_internal)
                mime_type = magic.from_file(file_path_internal, mime=True)

                # create file object and add to DB
                new_file = ExperimentFile(user_id=user.id, size_in_bytes=file_size, name=filename, path=file_path, mime_type=mime_type, file_format_full=file_format_full, folder=user.username)
                db.session.add(new_file)
                db.session.flush()

                # link file to visualization output
                visualization.output_file_id = new_file.id

        db.session.commit()


class IlluminaImportTask(BaseTask):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        # update status
        visualization_id = kwargs['visualization_id']
        visualization = Analysis.query.get(visualization_id)
        visualization.state = celery_states.FAILURE
        db.session.add(visualization)
        db.session.commit()

        # retrieve folder to write output files to
        user = g.user
        user_folder = os.path.join(current_app.config.get('SYMLINK_TO_DATA_STORAGE'), user.username)
        visualization_folder = os.path.join(user_folder, current_app.config.get('VISUALIZATIONS_FOLDER'), str(visualization.id))

        # write stdout to file
        write_file_in_chunks(visualization_folder, "log.out", exc.stdout)

        # write stderr to file
        write_file_in_chunks(visualization_folder, "error.out", exc.stderr)

        # call method on parent class
        super(VisualizationTask, self).on_failure(exc, task_id, args, kwargs, einfo)

    def on_success(self, retval, task_id, args, kwargs):
        # update visualization status
        visualization_id = kwargs['visualization_id']
        visualization = Visualization.query.get(visualization_id)
        visualization.state = celery_states.SUCCESS
        db.session.add(visualization)

        # retrieve folder to write output files to
        user = g.user
        user_folder = os.path.join(current_app.config.get('SYMLINK_TO_DATA_STORAGE'), user.username)
        visualization_folder = os.path.join(user_folder, current_app.config.get('VISUALIZATIONS_FOLDER'), str(visualization.id))

        plot = Plot.query.get(kwargs['plot_id'])
        visualization_file = os.path.join(visualization_folder, plot.output_filename, '.html')

        # create DB entries for each analysis output file
        for root, subdirs, files in os.walk(visualization_folder):
            # read analysis files in directory
            for filename in files:
                # remove internal root part (DATA_ROOT_INTERNAL) of path
                clean_root = root[len(current_app.config.get('DATA_ROOT_INTERNAL')):]
                # remove prefix slash
                if (clean_root[0] == os.sep):
                    clean_root = clean_root[1:]

                file_path = os.path.join(clean_root, filename)
                file_path_internal = os.path.join(root, filename)
                file_size = os.path.getsize(file_path_internal)
                # initialize file handle for magic file type detection
                fh_magic = magic.Magic(magic_file=current_app.config.get('BIOINFO_MAGIC_FILE'))

                # get bioinformatic file type using magic
                file_format_full = fh_magic.from_file(file_path_internal)
                mime_type = magic.from_file(file_path_internal, mime=True)

                # create file object and add to DB
                new_file = ExperimentFile(user_id=user.id, size_in_bytes=file_size, name=filename, path=file_path, mime_type=mime_type, file_format_full=file_format_full, folder=user.username)
                db.session.add(new_file)
                db.session.flush()

                # link file to visualization output
                visualization.output_file_id = new_file.id

        db.session.commit()


@celery.task(base=AnalysisTask)
def run_analysis(command, **kwargs):
    ssh = connect_ssh(current_app.config.get('COMPUTING_SERVER_IP'), current_app.config.get('COMPUTING_SERVER_USER'), current_app.config.get('COMPUTING_SERVER_PASSWORD'))
    stdin, stdout, stderr = ssh.exec_command(command)
    print(command)
    # print stdout
    for line in stdout:
        print(line.strip("\n"))
    # exit code of pipeline script
    exit_code = stdout.channel.recv_exit_status()
    # if pipeline exits with error code (different than 0)
    if exit_code != 0:
        message = "The pipeline with id '{}' raised an error".format(kwargs['pipeline_id'])
        raise PipelineError(message, exit_code, stdout, stderr)
    return kwargs['analysis_id']


@celery.task(base=VisualizationTask)
def create_visualization(command, **kwargs):
    ssh = connect_ssh(current_app.config.get('COMPUTING_SERVER_IP'), current_app.config.get('COMPUTING_SERVER_USER'), current_app.config.get('COMPUTING_SERVER_PASSWORD'))
    stdin, stdout, stderr = ssh.exec_command(command)
    print(command)
    # print stdout
    for line in stdout:
        print(line.strip("\n"))
    # exit code of pipeline script
    exit_code = stdout.channel.recv_exit_status()
    # if pipeline exits with error code (different than 0)
    if exit_code != 0:
        message = "The plot with id '{}' raised an error".format(kwargs['plot_id'])
        raise PlotError(message, exit_code, stdout, stderr)
    return kwargs['visualization_id']

# TODO: finish this
@celery.task(base=IlluminaImportTask)
def import_illumina(command, **kwargs):
    ssh = connect_ssh(current_app.config.get('COMPUTING_SERVER_IP'), current_app.config.get('COMPUTING_SERVER_USER'), current_app.config.get('COMPUTING_SERVER_PASSWORD'))
    stdin, stdout, stderr = ssh.exec_command(command)
    print(command)
    # print stdout
    for line in stdout:
        print(line.strip("\n"))
    # exit code of pipeline script
    exit_code = stdout.channel.recv_exit_status()
    # if pipeline exits with error code (different than 0)
    if exit_code != 0:
        message = "The plot with id '{}' raised an error".format(kwargs['plot_id'])
        raise PlotError(message, exit_code, stdout, stderr)
    return kwargs['visualization_id']
