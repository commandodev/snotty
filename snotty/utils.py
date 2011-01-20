from pyramid.asset import abspath_from_asset_spec
import eventlet
import json
import logging
import pyramid_zcml
import sys

from eventlet import hubs, debug, event, wsgi
from eventlet.green import subprocess
from nose.tools import ok_
from paste.deploy import loadapp
from pyramid import testing
from pyramid.exceptions import NotFound
from pyramid.traversal import resource_path_tuple
from stargate import WebSocketView
from stargate.resource import WebSocketAwareResource
from StringIO import StringIO
from webob.exc import HTTPNotFound
from zope.interface import Interface


class Root(object):
    pass

def get_root(request):
    return Root()

def not_found(context, request):
    assert(isinstance(context, NotFound))
    return HTTPNotFound('404')

class ISnottyQueue(Interface):
    pass

class Fixture(object):
    """Use fixture to setup a server once for a module"""

    def __init__(self, config_url, **kwargs):
        """
        :param zcml_file: Path (or spec) of a zcml file
        :param views: List of dicts suitable as kwargs to
            :meth:`pyramid.configuration.Configurator.add_view`
        :param routes: List of tuples of (name, path, kwargs) to pass to
            :meth:`pyramid.configuration.Configurator.add_route`
        """
        self.app = loadapp(config_url, **kwargs)
        self.logfile = StringIO()
        self.killer = None

    def start_server(self, module=None):
        self._spawn_server()
        eventlet.sleep(0.3)

    def _spawn_server(self, **kwargs):
        """Spawns a new wsgi server with the given arguments.
        Sets self.port to the port of the server, and self.killer is the greenlet
        running it.

        Kills any previously-running server.
        """
        if self.killer:
            eventlet.greenthread.kill(self.killer)
            eventlet.sleep(0)

        new_kwargs = dict(max_size=128,
                          log=self.logfile)
        new_kwargs.update(kwargs)

        sock = eventlet.listen(('localhost', 0))

        self.port = sock.getsockname()[1]
        self.killer = eventlet.spawn_n(wsgi.server, sock, self.app, **new_kwargs)

    def clear_up(self, module=None):
        eventlet.greenthread.kill(self.killer)
        eventlet.sleep(0)
        try:
            hub = hubs.get_hub()
            num_readers = len(hub.get_readers())
            num_writers = len(hub.get_writers())
            assert num_readers == num_writers == 0
        except AssertionError:
            print "ERROR: Hub not empty"
            print debug.format_hub_timers()
            print debug.format_hub_listeners()

        eventlet.sleep(0)


class WSTestGenerator(WebSocketView):

    def handle_websocket(self, ws):
        self._ws = ws
        return super(WSTestGenerator, self).handle_websocket(ws)

    def handler(self, ws):
        context = self.request.context
        # Spaces have been replaced with _ in the javascript
        ns = getattr(context, 'namespace', '').replace('_', ' ')
        q = context.queue
        def close_down(evt):
            evt.wait()
#            context.shutdown()
            eventlet.sleep(0)
        LAST_MSG = event.Event()
        eventlet.spawn_n(close_down, LAST_MSG)
        while True:
            m = ws.wait()
            if m is None:
                break
            msg = json.loads(m)
            # 'name' in the message indicates a test result
            if 'name' in msg:
                q.put(dict(result=msg, namespace=ns))
            # Otherwise it's the DONE message
            else:
                q.put(msg)
                LAST_MSG.send()
                return

class JsTestFiles(object):

    def __init__(self):
        self.files = []

    def __call__(self, request):
        return dict(test_files=self.files)

js_test_view = JsTestFiles()

class NamespaceContext(WebSocketAwareResource):
    """A root object that will return instances of itself on traversal

    It provides a :attr:`namespace` attribute that keeps track of parents
    """

    def __init__(self, queue=None):
        self._queue = queue
        self.sub_namespaces = []

    __name__ = ''
    __parent__ = None

    @classmethod
    def get_factory(cls, queue):
        """``root_factory`` for :class:`repoze.bfg.configuration.Configuration`"""
        return lambda request: cls(queue)

    def __getitem__(self, key):
        namespace = NamespaceContext()
        namespace.__parent__ = self
        namespace.__name__ = key
        self.sub_namespaces.append(namespace)
        return namespace

    @property
    def namespace(self):
        return '.'.join(resource_path_tuple(self)[1:])

    @property
    def queue(self):
        if self.__parent__:
            return self.__parent__.queue
        return self._queue

    def shutdown(self):
        for ws in self.listeners:
            try:
                ws.close()
            except Exception, e:
                print e
        for child in self.sub_namespaces:
            child.shutdown()



def js_results_generator(result):
    assert not result['failures']

class ChromeNotFound(KeyError):
    """Raised by :class:`WSTestCase` if chrome can't be found"""

class WSTestCase(object):

    TST_FILES = []
    LIB_FILES = []
    # TODO: Make this less noddy
    CMD_LOOKUP = dict(
        darwin="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        linux="/usr/bin/google-chrome",
        linux2="/usr/bin/google-chrome",
    )

    def _setUp(self):
        self.fixture = Fixture("config:snotty/snotty.ini", relative_to='.')
        registry = self.fixture.app.registry
        self.queue = registry.getUtility(ISnottyQueue)
        self.fixture.start_server()

    def _tearDown(self):
        #from nose.tools import set_trace; set_trace()
        self.fixture.clear_up()

    def run(self):
        self._setUp()
        done = event.Event()
        js_test_view.files = self.LIB_FILES + self.TST_FILES
        eventlet.spawn_n(self.start_chrome,
                         'http://localhost:%s/run-tests' % self.fixture.port, done)
        try:
            while True:
                msg = self.queue.get()
                result = msg.pop('result', None)
                if result:
#                    msg.update(result)
                    desc = "%(namespace)s.%(name)s: %(total)d tests run" % result
                    js_results_generator.description = desc
                    yield js_results_generator, result
                    js_results_generator.description = ''
                else:
                    assert 'DONE' in msg
                    break
        finally:
            done.send()
            self._tearDown()

    def start_chrome(self, url, done):
        chrome = self.CMD_LOOKUP.get(sys.platform)
        if not chrome:
            self.chrome = None
            raise ChromeNotFound('Executable for chrome not found')
        self.chrome = subprocess.Popen([chrome, '--single-process', url],
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, shell=False)
        eventlet.spawn_n(self.kill_chrome, done)
        self.chrome.communicate()

    def kill_chrome(self, done):
        done.wait()
        print '##########\nGOT DONE'
        try:
            self.chrome.kill()
        except OSError: # Chrome was already running and it just opened another tab
            pass
        eventlet.sleep(0.2)


        


class TestYieldingFromSetupTest(object):

    def test_yield(self):
        for i in range(1,4):
            yield self._test, i
        yield self._test, 0

    def _test(self, i):
        ok_(i > 0)
        

