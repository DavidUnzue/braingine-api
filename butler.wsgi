#!/usr/bin/python
import sys, os
import logging

activate_this = '/opt/butler/bin/activate_this.py'
execfile(activate_this, dict(__file__=activate_this))

logging.basicConfig(stream=sys.stderr)
sys.path.insert(0,"/var/www/butler/")
os.chdir("/var/www/butler")

from server import app as application
