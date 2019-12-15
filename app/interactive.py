from flask import Blueprint, render_template, session, current_app, request, redirect
from urllib.parse import urlencode, parse_qs
from uuid import uuid4
from requests import post, get
from functools import wraps
from typing import Dict, Optional
from datetime import datetime, timedelta
import os
import logging

log = logging.getLogger(__name__)

bp = Blueprint('interactive', __name__, url_prefix=None)


class Token:
    # Token registry mapping from user ID to token for that user
    _registry: Dict[str, "Token"] = {}

    # minimal remaining token lifetime; minimum time before token will be refreshed
    MIN_TOKEN_LIFETIME = 300

    def __init__(self, access_token, expires_in, refresh_token, refresh_token_expires_in):
        self.access_token: str = access_token
        self.exprires_in: int = expires_in
        self.refresh_token: str = refresh_token
        self.refresh_token_expires_in: int = refresh_token_expires_in
        self.access_token_exprires_at: datetime = None
        self.refresh_token_exprires_at: datetime = None
        self.update_expiry()

    def update_expiry(self)->None:
        """
        Determine the absolute token expiration based on exprires_in and current time
        :return: NOne
        """
        self.access_token_exprires_at = datetime.utcnow() + timedelta(0, self.exprires_in)
        self.refresh_token_exprires_at = datetime.utcnow() + timedelta(0, self.refresh_token_expires_in)

    @staticmethod
    def get_token(user_id: str) -> Optional["Token"]:
        """
        Obtain token for given user id
        :param user_id: user id to obtain token for
        :return: token registered for that user .. or None
        """
        return Token._registry.get(user_id)

    @staticmethod
    def from_dict(user_id: str, d: Dict) -> "Token":
        """
        Create token from data returned by identity service
        :param user_id: user id to register the resulting token for
        :param d: token data
        :return: created token
        """
        assert Token._registry.get(user_id) is None
        token = Token(**d)
        Token._registry[user_id] = token
        return token

    @property
    def needs_refresh(self) -> bool:
        """
        Determine if a given access token needs refresh
        :return: True/False - does the access token need refresh?
        """
        seconds_remaining = (self.access_token_exprires_at - datetime.utcnow()).total_seconds()
        return seconds_remaining < Token.MIN_TOKEN_LIFETIME

    def refresh(self)->None:
        """
        Refresh the access token
        :return: None
        """
        tokens = WxHelper.access_token(self.refresh_token)
        for k, v in tokens.items():
            self.__dict__[k] = v
        self.update_expiry()

    @staticmethod
    def assert_token(user_id: str, refresh_token: str) -> "Token":
        """
        Make sure an access toekn is registered for a given user id. If no access token is registered then
        a new access token is obtained based on the refresh token passed
        :param user_id: user ID
        :param refresh_token: refresh token
        :return: access token registered for the given user
        """
        token = Token.get_token(user_id)
        if token is None:
            token = WxHelper.access_token(refresh_token)
            token = Token.from_dict(user_id, token)
        return token

    @property
    def bearer(self) -> str:
        """
        Bearer string to be used in Authorization header
        :return:
        """
        if self.needs_refresh:
            self.refresh()
        return f'Bearer {self.access_token}'


class WxHelper:
    CLIENT_ID = os.getenv("CLIENT_ID")
    CLIENT_SECRET = os.getenv("CLIENT_SECRET")
    REDIRECT_URI = os.getenv("REDIRECT_URI")
    SCOPE = os.getenv("SCOPE")

    BASE_URL = 'https://api.ciscospark.com'

    @staticmethod
    def auth_url(state: Optional[str] = None) -> str:
        '''
        build something like: https://api.ciscospark.com/v1/authorize?client_id
        =C9f35a8ab07f81667e4b4b981ea0fa606899b42fa9dbbafae961495f9170860e3&response_type=code&redirect_uri=http%3A%2F
        %2Flocalhost%3A5000%2Fredirect&scope=spark%3Aall%20spark%3Akms&state=set_state_here
        :return: URL
        '''
        state = state or f'{uuid4()}'
        qs = urlencode(dict(
            client_id=WxHelper.CLIENT_ID,
            response_type='code',
            redirect_uri=WxHelper.REDIRECT_URI,
            scope=WxHelper.SCOPE,
            state=state
        ))
        return f'{WxHelper.BASE_URL}/v1/authorize?{qs}'

    @staticmethod
    def get_tokens(code: str) -> dict:
        data = dict(
            grant_type='authorization_code',
            client_id=WxHelper.CLIENT_ID,
            client_secret=WxHelper.CLIENT_SECRET,
            code=code,
            redirect_uri=WxHelper.REDIRECT_URI
        )
        r = post(f'{WxHelper.BASE_URL}/v1/access_token', data=data)
        r.raise_for_status()
        tokens = r.json()
        return tokens

    @staticmethod
    def me(access_token: str) -> dict:
        headers = {'Authorization': f'Bearer {access_token}'}
        r = get(f'{WxHelper.BASE_URL}/v1/people/me', headers=headers)
        r.raise_for_status()
        return r.json()

    @staticmethod
    def access_token(refresh_token: str):
        data = dict(
            grant_type='refresh_token',
            client_id=WxHelper.CLIENT_ID,
            client_secret=WxHelper.CLIENT_SECRET,
            refresh_token=refresh_token
        )
        r = post(f'{WxHelper.BASE_URL}/v1/access_token', data=data)
        r.raise_for_status()
        tokens = r.json()
        return tokens


def auth_required(f):
    """
    Decorator to enforce OAauth authentication for a given URL
    :param f: function to be decorated
    :return: decorated function
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        session['sid'] = session.sid
        if session.get('user') is None:
            # not authenticated: need to initiate OAuth auth flow
            session['url'] = request.url
            state = uuid4()
            session['state'] = str(state)
            url = WxHelper.auth_url(state=state)
            log.debug(f'sid {session.sid}: {request.url} requires authentication. Redirecting to {url}')
            return redirect(url)
        # make sure that the tokens for the user are registered
        Token.assert_token(session['user_id'], session['refresh_token'])
        return f(*args, *kwargs)

    return decorated


@bp.route('/')
@bp.route('/index')
@auth_required
def index():
    return render_template('index.html', user=session['user'])


@bp.route('/redirect')
def redirect_url():
    """
    Redurect URL at the end of the OAuth authentication flow
    :return:
    """
    log.debug(f'redirect_url: sid={session.sid}, query={request.query_string}')

    # extract code, state
    query = parse_qs(request.query_string.decode())
    code = query.get('code', [''])[0]
    state = query.get('state', [''])[0]

    # verify state
    assert state == session['state']
    session.pop('state')

    # use code to obtain tokens
    tokens = WxHelper.get_tokens(code)
    log.debug(f'redirect: sid={session.sid}, exchanged code for tokens: {tokens}')

    session['access_token'] = tokens['access_token']
    session['refresh_token'] = tokens['refresh_token']

    # use token to get user info
    user = WxHelper.me(tokens['access_token'])
    session['user'] = f'{user["displayName"]} ({user["emails"][0]})'
    session['user_id'] = user['id']

    log.debug(f'redirect: sid={session.sid}, got user info: {session["user"]}, {session["user_id"]}')
    url = session.pop('url')
    log.debug(f'redirect: sid={session.sid}, redirecting to: {url}')

    # redirect back to the url from which we initiated the OAuth auth flow
    return redirect(url)


@bp.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


@bp.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500
