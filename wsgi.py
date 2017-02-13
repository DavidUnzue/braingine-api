#!/usr/bin/python
# import sys, os
# import logging
#
# activate_this = '/Users/davidunzue/.virtualenvs/flask-rest/bin/activate_this.py'
# execfile(activate_this, dict(__file__=activate_this))
#
# logging.basicConfig(stream=sys.stderr)
# sys.path.insert(0,"/var/www/braingine/")
# os.chdir("/var/www/braingine")

from server import create_app

app = create_app('production')

if __name__ == "__main__":
    app.run()
