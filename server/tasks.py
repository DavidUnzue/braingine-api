# -*- coding: utf-8 -*-
"""
    server.tasks
    ~~~~~~~~~~~~~~
    module for long running tasks
"""
from flask import current_app
from . import create_celery_app
from utils import connect_ssh
# Import db instance
from server import db
from server.models.experiment import ExperimentAnalysis
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
        experiment_analysis = ExperimentAnalysis.query.get(experiment_analysis_id)
        experiment_analysis.state = status
        db.session.add(experiment_analysis)
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
