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
    ssh = connect_ssh(current_app.config.get('SSH_SERVER'), current_app.config.get('SSH_USER'), current_app.config.get('SSH_PASSWORD'))
    ssh.sendline(cmd)
    ssh.prompt()
    output = ssh.before
    return output
