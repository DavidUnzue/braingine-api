# braiNgine API

braiNgine is a platform for managing, analyzing and visualizing bioinformatics data in a user-friendly, accessible way.

## Development

1. Change to API directory and create virtual environment: `python -m venv venv`
2. Activate created virtual environment: `source ./venv/bin/activate`
3. Install dependencies: `pip install -r requirements`
4. Start PostgreSQL
5. Copy `nignx.conf` to NGINX sites-available directory (`/usr/local/etc/nginx/sites-available`), create symlink to it in sites-enabled directory and start NGINX web server: `nginx`
6. Start UWSGI server: `uwsgi --ini uwsgi.ini`
7. Start Celery workers: `python manage.py celeryworker`


## API documentation

See the API documentation [here](https://github.molgen.mpg.de/braiNgine/braingine-api/wiki/Documentation).

## Deployment

Follow deployment instructions [here](https://github.molgen.mpg.de/braiNgine/braingine-api/wiki/Deployment).
