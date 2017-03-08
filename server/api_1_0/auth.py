import ldap
from ldap import filter as ldap_filter
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
    # escape special chars before filtering to protect against LDAP injection
    username = ldap_filter.escape_filter_chars(username)

    # search for authenticating user using LDAP filtering
    user_search_filter = '(|(mail={0})(sAMAccountName={0}))'.format(username)
    user_search = con.search_s(current_app.config.get('LDAP_BASE_DN'), ldap.SCOPE_SUBTREE, user_search_filter, ['primaryGroupID',])

    # if user not found
    if user_search is None or len(user_search) <= 0 or password == '':
        return False
    # get primaryGroupID value from found user
    primary_group_id = user_search[0][1]['primaryGroupID'][0].decode("utf-8")
    # assign user to a group based on primaryGroupID
    # if (primary_group_id == get_group_token(con, 'SCHU')):
    # elif (primary_group_id == get_group_token(con, 'LAUR')):
    # elif (primary_group_id == get_group_token(con, 'SCIC')):

    # if user found, authentication passed
    g.user = username
    return True


def get_group_token(ldap_connection, cn):
    """
    Get the primaryGroupToken of a group specified by it's CN value.
    """
    group_search_filter = '(&(objectClass=group)(cn={0}))'.format(cn)
    group_search = ldap_connection.search_s(current_app.config.get('LDAP_BASE_DN'), ldap.SCOPE_SUBTREE, group_search_filter, ['primaryGroupToken',])

    return group_search[0][1]['primaryGroupToken'][0].decode("utf-8")
