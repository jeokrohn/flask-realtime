import sys
import werkzeug
import threading

thread_proxies = {}

sys_stdout_saved = sys.stdout

def redirect(f):
    ident = threading.currentThread().ident
    thread_proxies[ident] = f
    return thread_proxies[ident]

def end_redirect():
    ident = threading.currentThread().ident
    thread_proxies.pop(ident, None)

def proxy():
    ident = threading.currentThread().ident
    return thread_proxies.get(ident, sys_stdout_saved)

sys.stdout = werkzeug.local.LocalProxy(proxy)