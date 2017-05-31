#!/usr/bin/env python
import os
from server import celery, create_app

app = create_app(os.getenv('APP_SETTINGS') or 'default')
app.app_context().push()
