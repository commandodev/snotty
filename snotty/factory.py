"""This module provides a paste [server_factory]_ to run repoze.bfg inside an
eventlet wsgi server

See `Paste Deploy <http://pythonpaste.org/deploy/#paste-server-factory>`_
for more details.
"""
import pyramid_zcml

from eventlet import spawn_n
from eventlet import Queue

from pyramid import testing

from snotty.utils import NamespaceContext, JsTestFiles, ISnottyQueue



import os.path

def read_q(q):
    while True:
        print q.get()



def test_app_factory(global_config, **settings):
    """ This function returns a WSGI application.

    It is usually called by the PasteDeploy framework during
    ``paster serve``.
    """
    queue = Queue()
    zcml_file = settings.get('configure_zcml', 'tests.zcml')
    config = testing.setUp()
    config.setup_registry(root_factory=NamespaceContext.get_factory(queue),
                          settings=settings)
    config.include(pyramid_zcml)
    config.load_zcml(zcml_file)
    lib_files_dir = os.path.join(os.path.abspath(__file__), '..', 'static')
    jqtest_dir = os.path.join(os.path.dirname(__file__), '..', 'static/jquery-tests')
    lib_files = []#['/static/jquery.min.js', '/static/testinit.js', '/static/testrunner.js']

    config.registry.registerUtility(queue, ISnottyQueue)
    
    if settings.get('debug', None):
        try:
            from werkzeug.debug import DebuggedApplication
            return DebuggedApplication(config.make_wsgi_app(), True)
        except ImportError:
            pass
    spawn_n(read_q, queue)
    return config.make_wsgi_app()