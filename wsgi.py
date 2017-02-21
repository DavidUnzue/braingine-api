#!/usr/bin/python
import os

from server import create_app

app = create_app(os.getenv('APP_SETTINGS') or 'production')

if __name__ == "__main__":
    app.run()
