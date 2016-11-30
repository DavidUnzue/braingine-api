#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import current_app
from flask.ext.restful import Resource
# get celery app instance (this is not the celery module/extension)
from server.tasks import celery

from . import api

class TaskStatusController(Resource):

    def get(self, task_id):
        task  = celery.AsyncResult(task_id)
        return {'task_id': task_id, 'state': task.state}, 200
