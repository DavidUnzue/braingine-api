import ldap
from ldap import filter as ldap_filter
from flask import jsonify, make_response, g, current_app
from flask.ext.httpauth import HTTPBasicAuth
from flask.ext.restful import Resource
from ..models.user import User, UserSchema, UserGroup
from .. import db

auth = HTTPBasicAuth()

@auth.error_handler
def unauthorized():
    resp = make_response(jsonify({'error': 'Unauthorized access'}), 401)
    # avoid browser auth. popup for 401 status
    resp.headers['WWW-Authenticate'] = 'NoPopupBasic realm="Authentication Required"'
    return resp

@auth.verify_password
def verify_password(login_name, password):
    # if current_app.config.get('DEBUG') == True:
    #     user = User.query.filter_by(username=login_name).first()
    #     g.user = user
    #     return True
    # connect to LDAP server and bind known user
    con = ldap.initialize(current_app.config.get('LDAP_SERVER'), bytes_mode=False)
    con.simple_bind_s(current_app.config.get('LDAP_USERNAME'), current_app.config.get('LDAP_PASSWORD'))
    # escape special chars before filtering to protect against LDAP injection
    login_name = ldap_filter.escape_filter_chars(login_name)

    # search for authenticating user using LDAP filtering
    user_search_filter = '(|(mail={0})(sAMAccountName={0}))'.format(login_name)
    user_search = con.search_s(current_app.config.get('LDAP_BASE_DN'), ldap.SCOPE_SUBTREE, user_search_filter, ['sAMAccountName','displayName','mail','primaryGroupID',])

    # failed authentication
    if user_search is None or len(user_search) <= 0 or password == '':
        return False
    # get inforamtion from found user
    username = user_search[0][1]['sAMAccountName'][0].decode("utf-8")
    fullname = user_search[0][1]['displayName'][0].decode("utf-8")
    user_email = user_search[0][1]['mail'][0].decode("utf-8")
    primary_group_id = user_search[0][1]['primaryGroupID'][0].decode("utf-8")
    # assign user to a group based on primaryGroupID
    # if (primary_group_id == get_group_token(con, 'SCHU')):
    # elif (primary_group_id == get_group_token(con, 'LAUR')):
    # elif (primary_group_id == get_group_token(con, 'SCIC')):

    # store user and group in DB if they do not exist already
    user = User.query.filter_by(username=username).first()
    user_group = UserGroup.query.filter_by(group_id=primary_group_id).first()
    if user_group is None:
        user_group = UserGroup(group_id=primary_group_id)
    if user is None:
        user = User(username=username, fullname=fullname, email=user_email)
        user.groups.append(user_group)
        db.session.add(user)
    elif user_group not in user.groups:
        # remove all user-group relations for this user and add new group(s)
        del user.groups[:]
        user.groups.append(user_group)
    db.session.commit()
    # store user in flask's g
    g.user = user
    # authentication passed
    return True


def get_group_token(ldap_connection, cn):
    """
    Get the primaryGroupToken (ID) of a group specified by it's CN value.
    """
    group_search_filter = '(&(objectClass=group)(cn={0}))'.format(cn)
    group_search = ldap_connection.search_s(current_app.config.get('LDAP_BASE_DN'), ldap.SCOPE_SUBTREE, group_search_filter, ['primaryGroupToken',])

    return group_search[0][1]['primaryGroupToken'][0].decode("utf-8")

# include only specific fields in reponse
user_schema = UserSchema(only=('id', 'username', 'email', 'fullname'))

class LoginController(Resource):
    decorators = [auth.login_required]

    def get(self):
        user = g.user
        return user_schema.dump(user).data, 200
