# -*- coding: utf-8 -*-
"""
    server.tasks
    ~~~~~~~~~~~~~~
    module for long running tasks
"""
from flask import current_app
from . import create_celery_app
from utils import connect_ssh

celery = create_celery_app()


@celery.task()
def execute_command(cmd):
    ssh = connect_ssh(current_app.config.get('COMPUTING_SERVER_IP'), current_app.config.get('COMPUTING_SERVER_USER'), current_app.config.get('COMPUTING_SERVER_PASSWORD'))
    stdin, stdout, stderr = ssh.exec_command(cmd)
    output = ''
    for line in stdout:
        output += line.strip('\n')
    return output
