"""
Simple per thread proxy functionality for stdout based on werkzeug LocalProxy
"""
import sys
import io
from typing import Dict
import threading

import werkzeug

# directory of non-default stdouts
thread_proxies: Dict[int, io.TextIOBase] = {}

# save the default stdout; needed by the proxy as default for threads w/o redirection
_default_stdout = sys.stdout


def redirect(f:io.TextIOBase)->io.TextIOBase:
    """
    Set stdout redirection for current thread
    :param f: file like object stdout should be redirected to
    :return: same as input parameter
    """
    ident = threading.currentThread().ident
    thread_proxies[ident] = f
    return thread_proxies[ident]


def end_redirect()->None:
    """
    End stdout redirection for current thread
    :return: None
    """
    ident = threading.currentThread().ident
    thread_proxies.pop(ident, None)


def proxy():
    ident = threading.currentThread().ident
    return thread_proxies.get(ident, _default_stdout)


sys.stdout = werkzeug.local.LocalProxy(proxy)
