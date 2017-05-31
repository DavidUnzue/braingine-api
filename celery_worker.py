#!/usr/bin/env python
import os
from server import create_app
from server.tasks import celery

app = create_app(os.getenv('APP_SETTINGS') or 'default')
app.app_context().push()
