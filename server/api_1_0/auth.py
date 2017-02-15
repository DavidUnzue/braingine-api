import ldap
from flask import jsonify, make_response, g, current_app
from flask.ext.httpauth import HTTPBasicAuth

auth = HTTPBasicAuth()

@auth.error_handler
def unauthorized():
    resp = make_response(jsonify({'error': 'Unauthorized access'}), 401)
    # avoid browser auth. popup for 401 status
    resp.headers['WWW-Authenticate'] = 'NoPopupBasic realm="Authentication Required"'
    return resp

@auth.verify_password
def verify_password(username, password):
    # connect to LDAP server and bind known user
    con = ldap.initialize(current_app.config.get('LDAP_SERVER'), bytes_mode=False)
    con.simple_bind_s(current_app.config.get('LDAP_USERNAME'), current_app.config.get('LDAP_PASSWORD'))
    # search for authenticating user
    results = con.search_s(current_app.config.get('LDAP_BASE_DN'), ldap.SCOPE_SUBTREE,                '(&(objectclass=Person)(|(mail={0})(sAMAccountName={0})))'.format(username))
    # if user not found
    if results is None or len(results) <= 0 or password == '':
        return False
    # if user found, authentication passed
    g.user = username
    return True
