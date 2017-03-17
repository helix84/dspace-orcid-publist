# -*- coding: utf-8 -*-
#
# TODO: logging
# TODO: when postgres is restarted this servlet's connection is closed and any query will throw an error:
#       zxJDBC.Error: FATAL: terminating connection due to administrator command [SQLCode: 0], [SQLState: 57P01]
#       An I/O error occured while sending to the backend. [SQLCode: 0], [SQLState: 08006]
# TODO: before the first redirect, force logout from ORCID: https://members.orcid.org/api/resources/customize#logout
"""
jython 2.7.0 servlet

This servlet acts as ORCID client app which authenticates an ORCID ID and asks
the user to authorize this ORCID client app to access their ORCID profile.
It stores the authorization token into a postgres DB.


https://publikace.k.utb.cz/utb/orcid/auth.py
    Servlet redirects user to ORCID authentication. After the user logs in
    to ORCID and authorizes this client app, ORCID redirects back to:
https://publikace.k.utb.cz/utb/orcid/auth.py?code=XXXXX
    Servlet processess the auth code and asks ORCID for an auth token.
    Servlet then stores this token into Postgres.

requirements: requests, configparser
copy them into /dspace/webapps-utb/WEB-INF/lib/Lib/site-packages
"""

from javax.servlet.http import HttpServlet

from org.apache.log4j import Logger

from java.util import Properties
from com.ziclix.python.sql import zxJDBC

import re
import requests
import ConfigParser as configparser

# http://bugs.jython.org/issue2390
# http://stackoverflow.com/questions/29099404/ssl-insecureplatform-error-when-using-requests-package
import requests.packages.urllib3
requests.packages.urllib3.disable_warnings()


DSPACE_DIR = '/dspace'

# https://klokantech.github.io/styles/base.css

html_template = u"""<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta http-equiv='X-UA-Compatible' content='IE=edge' />
    <meta name='viewport' content='width=device-width, initial-scale=1.0, maximum-scale=1.0' />
    <link href="base.css" rel="stylesheet" />
  </head>
  <body>
    <div class="container main" style="padding-top:0">
      <div class="row">
        <!-- content -->
        <div class="col10 flip no-padding">
          <div class="row">
            <div class="col12">
%s
            </div>
          </div>
        </div>
        <div class="col2 flip text-right no-paddings" style="margin-top: 168px;">
          <img style="position:relative; top:2em;" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAAA8CAMAAADhV0xWAAAAA3NCSVQICAjb4U/gAAAACXBIWXMAAAPeAAAD3gHuRCeuAAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAaFQTFRFAAAAAP8AAIAAAKoAAL8AAMwAK6oAIL8AHMYAGrMAFb8AErYAEbsAHrQAHLgAG7wAGLYAF7kAFrwAFb8AE70AG7YAGrsAGb0AF7kAF7wAFboAFLwAGLgAF7kAFrwAFrgAGrgAGboAGLgAF7kAF7sAGLoAF7kAF7wAFroAGLkAF7kAF7oAF7sAFrkAFroAFrsAFrsAGLkAGLsAF7kAF7oAF7sAFrkAFroAFroAGLkAGLoAFroAFrsAGLkAGLkAGLoAGLoAFroAF7sAF7kAGLoAF7oAF7oAFrsAF7sAF7oAF7sAFroAFroAGLkAF7oAF7sAF7oAF7sAF7oAF7oAFroAGLoAF7kAF7oAF7oAF7sAF7oAF7oAFroAF7oAF7kAF7oAF7sAF7oAF7oAFroAGLoAF7oAF7kAF7oAF7oAF7oAF7oAF7oAF7kAF7oAF7oAFroAF7oAF7oAF7oAF7kAF7oAF7oAF7oAF7oAF7oAF7oAF7oAF7oAF7oAF7oAF7oAF7oAF7oAF7oAF7oAF7oAF7oAF7oAF7oAF7oAF7oAF7oAF7oAYulYuQAAAIp0Uk5TAAECAwQFBggJCgwODxESExUWFxgbHB4fISIlJissLi8yNDY3OD9CREZJTU5PUFFSU1RWWFlaW1xdX2BnaWp1dnd9g4eMkJGVmZydn6Cho6SmqKmqq62wsbKztLW2ubu8vr/AwcPFxsrQ09TW3N3h4+Tl5ufo6err7O3u7/Dx8/T19vf4+fr7/P3+kJojpwAAAgJJREFUGBmdwQtDS2EABuB3aUa2mdWikuuERroot9KEsZVrUipyj6IyNtFYtcx6f7WsnXO+nZ2zzvc9D5Tti31bn2mFMs97bllvhaoEi2ag6Bq3rUFNOMdtSSgJLrEkBhXuNyxZ9ELFbWrOQsVFahJQcSTLki8+KPB9ouYcFNRMUTMMFUPUJH1Q0F6g5jwUNGeoGYGCujlqkn7Icz2mrgMKBqm7BwVteWqSfshrTFPXAXmeWeruQ0Gcuq9+yOun4QLkhXPUPYC84CJ16QCk1b6moRPyYjQ8hLxeGtIHYHYoeifahCqOrtLQCbOBDZL5Gy7Y8X2m4RHMzmyyaGQ3rNVM05AKwOwVS176YGmIgi5UyFIz3wQLkU0aRlEpQ10qjAotGRrSAVQao2GtCyZ1cxR0w0JLjobCIMq4Ril4Aks9BQoSbgiiFHwPwtoARS+80LXlKeiGnZsUfTyIksY0BU9hyxWnKHkcRZ5ZCpaDsLdrjKJsBP/FKepBNXveUvQ3CqCfonFU5/3AMndrwzkKluuxg9ACy0wuUdSLHTWnaG8CDpz4TTvL9XDi9AZt9MGZvgItTcCp67Sy0gDHbtHCJTjnGmaFZ5DhnqZJJgQpe9+x3GVI2j9P0SSkhRZoyIQg7/AP6q5AxcksS6agJpJn0UoDFF0tcMufdig79fzXz/FjcOAfQ5MF9o+qylsAAAAASUVORK5CYII="/>
        </div>
      </div>
    </div>
  </body>
</html>"""

text_complete = {}
text_complete['en'] = u"""
              <img alt="ORCID member logo" height="117" src="https://www.utb.cz/uploads/knihovna/VedaAVyzkum/orcid_utb_logo.png" width="690">
              <h1>Process complete</h1>
              <p>Thank you for granting TBU Library the authorization to add works (publications) to your ORCID account.<br/>We'll be updating your publication list periodically every few weeks.</p>
              %s
              <p>You have completed the procedure we asked you to do. It is now safe to close this window.<p>
              <p>As a next step, we suggest you look around your ORCID account and complete any missing information.<p>
              <a style="position:relative; top:2em;" class="btn-stroke-light" href="https://orcid.org/my-orcid">Go to my ORCID account</a>
"""
text_complete['cs'] = u"""
              <img alt="ORCID member logo" height="117" src="https://www.utb.cz/uploads/knihovna/VedaAVyzkum/orcid_utb_logo.png" width="690">
              <h1>Hotovo!</h1>
              <p>Děkujeme vám, že jste Knihovně UTB udělili oprávnění přidávat publikace do vašeho účtu ORCID.<br/>Váš profil budeme pravidelně aktualizovat v intervalu několika týdnů.</p>
              %s
              <p>Úspěšně jste dokončili proces, o který jsme vás žádali. Toto okno můžete bezpečně zavřít.<p>
              <p>Pokud si přejete, můžete se podívat do svého účtu ORCID a doplnit případné chybějící informace.<p>
              <a style="position:relative; top:2em;" class="btn-stroke-light" href="https://orcid.org/my-orcid">Přejít do mého účtu ORCID</a>
"""
text_complete['en_US'] = text_complete['en']
text_complete['cs_CZ'] = text_complete['cs']

text_orcid = {}
text_orcid['en'] = u"<p>Your ORCID ID is: <img src='orcid_16x16.gif' width='16' height='16' alt='orcid logo small' style='position:relative; top:3px' /> <a href='https://orcid.org/%s'>%s</a></p>"
text_orcid['cs'] = u"<p>Váš identifikátor ORCID je: <img src='orcid_16x16.gif' width='16' height='16' alt='orcid logo small' style='position:relative; top:3px' /> <a href='https://orcid.org/%s'>%s</a></p>"
text_orcid['en_US'] = text_orcid['en']
text_orcid['cs_CZ'] = text_orcid['cs']

class auth(HttpServlet):
    def doGet(self, request, response):
        self.doPost(request, response)

    def doPost(self, request, response):
        response.setContentType("text/html; charset=UTF-8")
        toClient = response.getWriter()

        best_locale = self.choose_best_locale(request, available_locales=['en', 'cs'])
        if best_locale is None:
            best_locale = 'en'

        complete = request.getParameter("complete")
        if complete is not None:
            orcid = request.getParameter("orcid")

            text_orcid_best = ""
            if orcid is not None and self.orcid_pattern.match(orcid):
                text_orcid_best = text_orcid[best_locale] % (orcid, orcid)
            text_complete_best = text_complete[best_locale] % text_orcid_best
            html = html_template % text_complete_best
            toClient.println(html)
	    return

#        client_id = 'APP-U5LLQCW33OX4QL72' # sandbox public
#        client_id = 'APP-LT1GI96T0HCIQY8N' # sandbox member
        client_id = 'APP-WTHDFZPAUVXQW8GG' # production member

        code = request.getParameter("code")
        locale = request.getParameter("locale")
        if code is None:
            self.redirect(response, client_id, scope='/activities/update /read-limited', locale=locale)
            return

        result = self.get_and_store_token(response, client_id, code)

        self.complete(response)  # redirect

    def choose_best_locale(self, request, available_locales=[]):
        """
        request is ServletRequest, available_locales is the list of available locales
        Choose the first of the requested locales, which is available.
        """
        requested_locales = request.getLocales()
        for locale in requested_locales:
            if str(locale) in available_locales:
                return str(locale)
        return None

    def redirect(self, response, client_id, scope='/authenticate', locale=None):
        """Redirect user to ORCID to log in and to authorize this client app."""
        if self.client[client_id]['env'] == 'production':
            base_url = 'https://orcid.org'
        else:
            base_url = 'https://sandbox.orcid.org'

        if locale is None:
            locale = 'en'

        location = base_url + '/oauth/authorize?client_id=' + client_id + \
            '&response_type=code&scope=' + scope + \
            '&redirect_uri=' + self.client[client_id]['redirect_uri'] + \
            '&lang=' + locale

        response.sendRedirect(location)  # redirect to ORCID /oauth/authorize
        return

    def complete(self, response):
        location = "https://publikace.k.utb.cz/utb/orcid/auth.py?complete"
        response.sendRedirect(location)
        return

    def get_and_store_token(self, response, client_id, code=None):
        """
        Get token from ORCID based on either:
        a) code returned after user granted authorization to our client app.
        b) requested scope
        Then store the token into DB.
        """
        if code is not None:
            resp = self.get_token(client_id, code)
        else:
            raise Exception("get_and_store_token(): must provide 'code' parameter.")
        # example:
        # {u'scope': u'/activities/update', u'refresh_token': u'1fa39904-db2d-483b-a932-ac649d6e2005', u'orcid': u'0000-0012-3456-789X', u'expires_in': 631138518, u'access_token': u'0ab341e9-89a8-4c66-9385-d01f1ac36850', u'token_type': u'bearer', u'name': u'Name Surname'}

        toClient = response.getWriter()
        if 'error' in resp:
            toClient.println(resp)
            response.flushBuffer()
            return

#        toClient.println(resp)  # DEBUG

        for single_scope in resp['scope'].split(' '):
            toClient.println(single_scope)

            result = self.store(
                response,
                client_id = client_id,
                orcid = resp['orcid'],
                scope = single_scope,
                token = resp['access_token'],
                expires_in = resp['expires_in'],
                refresh_token = resp['refresh_token'],
            )

        return result

    def get_token(self, client_id, code):
        """Get token from ORCID based on code returned after user granted authorization to our client app."""
        headers = {
            'Accept': 'application/json',
        }

        data = {
            'client_id': self.client[client_id]['client_id'],
            'client_secret': self.client[client_id]['client_secret'],
            'grant_type': 'authorization_code',
            'redirect_uri': self.client[client_id]['redirect_uri'],
            'code': code,
        }        

        if self.client[client_id]['env'] == 'production':
            url = 'https://orcid.org/oauth/token'
        else:
            url = 'https://sandbox.orcid.org/oauth/token'

        r = requests.post(url=url, headers=headers, data=data, verify=True)
        
        return r.json()

    def init(self, config):
        """servlet startup"""
        self.props = self.read_dspace_config(DSPACE_DIR + '/config/dspace.cfg')
        self.conn = zxJDBC.connect(
            self.props.getProperty('db.url'),
            self.props.getProperty('db.username'),
            self.props.getProperty('db.password'),
            self.props.getProperty('db.driver'),
        )
        self.conn.autocommit = True
        self.cursor = self.conn.cursor()

        self.client = self.read_orcid_config_db()

        self.orcid_pattern = re.compile(r"^\d{4}-\d{4}-\d{4}-(\d{3}X|\d{4})$")
        self.token_pattern = re.compile(r"^[0-f]{8}-[0-f]{4}-[0-f]{4}-[0-f]{4}-[0-f]{12}$")
        self.available_scopes = [
            '/authenticate',
            '/activities/update',
            '/person/update',
            '/read-limited',
            '/read-public',
            '/webhook',
        ]
        self.available_envs = [
            'sandbox',
            'production',
        ]
        self.logger = Logger.getLogger("orcid/auth.py")
        self.logger.info("initialized")

    def destroy(self):
        """servlet shutdown: clean up DB connections"""
        self.cursor.close()
        self.conn.close()

    def read_orcid_config_db(self):
        """
        Read ORCID client app(s) configuration from database

        config example (format returned by this method):
        client = {
            'APP-U5LLQCW33OX4QL72': {
                'env': 'sandbox',
                'api': 'public',
                'client_id': 'APP-U5LLQCW33OX4QL72',
                'client_secret': '11111111-2222-3333-4444-aaaaaabbbbbb'
            },
            ...
        }
        """
        self.cursor.execute("SELECT * FROM utb_orcid_client_apps;")

        client = {}
        for row in self.cursor.fetchall():
            client_id = row[2]
            client[client_id] = {}
            client[client_id]['env'] = row[0]
            client[client_id]['api'] = row[1]
            client[client_id]['client_id'] = row[2]
            client[client_id]['client_secret'] = row[3]
            client[client_id]['redirect_uri'] = row[4]

        return client

    def read_dspace_config(self, filename):
        """read dspace.cfg"""
        f = open(filename, 'r')
        props = Properties()
        props.load(f)
        f.close()
        return props

    def doQuery(self, response, query):
        """execute DB query with error handling"""
        try:
            self.cursor.execute(query)
        except zxJDBC.DatabaseError, msg:
            toClient = response.getWriter()
            toClient.println(msg)

    def validate(self, client_id, orcid, scope, token):
        """validate arguments against regexes"""
        if orcid is None:
            self.logger.info("parameter not specified: orcid")
            return False

        if scope is None:
            self.logger.info("parameter not specified: scope")
            return False

        if token is None:
            self.logger.info("parameter not specified: token")
            return False

        if client_id is None:
            self.logger.info("parameter not specified: client_id")
            return False

        if self.orcid_pattern.match(orcid):
            self.logger.info("match: %s" % orcid)
        else:
            self.logger.info("parameter is not a valid ORCID ID: %s" % orcid)
            return False

        if self.token_pattern.match(token):
            self.logger.info("match: %s" % token)
        else:
            self.logger.info("parameter is not a valid token: %s" % token)
            return False

        if scope in self.available_scopes:
            self.logger.info("match: %s" % scope)
        else:
            self.logger.info("parameter is not a valid scope: %s" % scope)
            return False

        if client_id in self.client.keys():
            self.logger.info("match: %s" % client_id)
        else:
            self.logger.info("parameter is not a valid client_id: %s" % client_id)
            return False
        return True
        # TODO: change to raise Exception; concat all messages

    def already_stored(self, response, client_id, orcid, scope, token):
        """store new token into database"""
        if not self.validate(client_id, orcid, scope, token):
            raise Exception('Arguments failed to validate.')
            return

        self.doQuery(response, "SELECT * FROM utb_orcid_tokens WHERE client_id = '%s' AND orcid = '%s' AND scope = '%s';" % (client_id, orcid, scope))
        return (self.cursor.rowcount > 0)

    def store(self, response, client_id, orcid, scope, token, expires_in=0, refresh_token=None):
        """store new token into database (UPSERT)"""
        if not self.validate(client_id, orcid, scope, token):
            raise Exception('Arguments failed to validate.')
            return

        # the arguments were validated against a regex or set
        try:
            env = self.client[client_id]['env']
            self.cursor.execute("INSERT INTO utb_orcid_tokens (env, client_id, orcid, scope, token, expiry, refresh_token) VALUES ('%s', '%s', '%s', '%s', '%s', CURRENT_TIMESTAMP - INTERVAL '1 day' + '%s seconds', '%s');" % (env, client_id, orcid, scope, token, expires_in, refresh_token))
        except zxJDBC.IntegrityError, e:
            # IntegrityError('ERROR: duplicate key value violates unique constraint "utb_orcid_tokens_pk"\n  Detail: Key (client_id, orcid, scope)=(APP-U5LLQCW33OX4QL72, 0000-0012-3456-789X, /activities/update) already exists. [SQLCode: 0], [SQLState: 23505]',)
            try:
                # row already exists, let's delete it and store again with new token, expiry
                i = self.delete_stored(response, client_id, orcid, scope, token)
                self.cursor.execute("INSERT INTO utb_orcid_tokens (env, client_id, orcid, scope, token, expiry, refresh_token) VALUES ('%s', '%s', '%s', '%s', '%s', CURRENT_TIMESTAMP - INTERVAL '1 day' + '%s seconds', '%s');" % (env, client_id, orcid, scope, token, expires_in, refresh_token))
            except zxJDBC.DatabaseError, msg:
#                toClient = response.getWriter()
#                toClient.println(msg)
                pass
        except zxJDBC.DatabaseError, msg:
#            toClient = response.getWriter()
#            toClient.println(msg)
            pass
            
        return orcid

    def delete_stored(self, response, client_id, orcid, scope, token):
        """delete token from database"""
        if not self.validate(client_id, orcid, scope, token):
            raise Exception('Arguments failed to validate.')
            return

        self.doQuery(response, "DELETE FROM utb_orcid_tokens WHERE client_id = '%s' AND orcid = '%s' AND scope = '%s';" % (client_id, orcid, scope))
        return (self.cursor.rowcount > 0)
