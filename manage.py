import os

# unit tests coverage
COV = None
if os.environ.get('FLASK_COVERAGE'):
    import coverage
    COV = coverage.coverage(branch=True, include='server/*')
    COV.start()

from flask.ext.script import Manager, Server
from flask.ext.migrate import Migrate, MigrateCommand

from server import create_app, db
from celery.bin.celery import main as celery_main

# create app instance with settings defined by enviroment variable
app = create_app(os.getenv('APP_SETTINGS') or 'default')

migrate = Migrate(app, db)
manager = Manager(app)

manager.add_command('db', MigrateCommand)
# make the development server capable of handling concurrent requests with threaded=True
manager.add_command('runserver', Server(threaded=True))

@manager.command
def test(coverage=False):
    """Run the unit tests."""
    if coverage and not os.environ.get('FLASK_COVERAGE'):
        import sys
        os.environ['FLASK_COVERAGE'] = '1'
        os.execvp(sys.executable, [sys.executable] + sys.argv)
    import unittest
    tests = unittest.TestLoader().discover('tests')
    unittest.TextTestRunner(verbosity=2).run(tests)
    if COV:
        COV.stop()
        COV.save()
        print('Coverage Summary:')
        COV.report()
        basedir = os.path.abspath(os.path.dirname(__file__))
        covdir = os.path.join(basedir, 'tmp/coverage')
        COV.html_report(directory=covdir)
        print('HTML version: file://%s/index.html' % covdir)
        COV.erase()

@manager.option('-n', '--hostname', dest='hostname', default='worker1', help='Unique name for a worker instance')
def celeryworker(hostname):
    """Run a celery worker process."""
    celery_args = ['celery', '-A', 'server.tasks', 'worker', '-n', hostname, '--loglevel=info']
    with app.app_context():
        return celery_main(celery_args)

@manager.command
def deploy():
    """Run deployment tasks."""
    from flask.ext.migrate import upgrade

    # migrate database to latest revision
    upgrade()

if __name__ == '__main__':
    manager.run()
