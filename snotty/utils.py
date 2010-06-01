from eventlet import Queue, event, spawn_n
from eventlet.green import subprocess
from nose.tools import ok_
from repoze.bfg.traversal import model_path_tuple
import json
import sys

from rpz.websocket import WebSocketView
from rpz.websocket.context import WebSocketAwareContext
from rpz.websocket.test_utils import Fixture




class WSTestGenerator(WebSocketView):

    def handle_websocket(self, ws):
        self._ws = ws
        return super(WSTestGenerator, self).handle_websocket(ws)

    def handler(self, ws):
        context = self.request.context
        # Spaces have been replaced with _ in the javascript
        ns = getattr(context, 'namespace', '').replace('_', ' ')
        q = context.queue
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

class JsTestFiles(object):

    def __init__(self, lib_files, test_files):
        self.lib_files = lib_files
        self.test_files = test_files

    def __call__(self, request):
        return dict(test_files=self.lib_files + self.test_files)

class NamespaceContext(WebSocketAwareContext):
    """A root object that will return instances of itself on traversal

    It provides a :attr:`namespace` attribute that keeps track of parents
    """

    def __init__(self, queue=None):
        self._queue = queue

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
        return namespace

    @property
    def namespace(self):
        return '.'.join(model_path_tuple(self)[1:])

    @property
    def queue(self):
        if self.__parent__:
            return self.__parent__.queue
        return self._queue

class ChromeNotFound(KeyError):
    """Raised by :class:`WSTestCase` if chrome can't be found"""

class WSTestCase(object):

    TST_FILES = []
    LIB_FILES = []
    # TODO: Make this less noddy
    CMD_LOOKUP = dict(
        darwin="/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome",
        linux="/usr/bin/google-chrome",
    )

    def setUp(self):
        print '#####################'
        print 'setup'
        queue = Queue()
        test_view = dict(view=JsTestFiles(self.LIB_FILES, self.TST_FILES),
                         view_renderer='snotty:templates/test.html')
        self.fixture = Fixture(zcml_file='snotty:tests.zcml',
                               root_factory=NamespaceContext.get_factory(queue),
                               routes=[['tests', '/run-tests', test_view]])
        self.fixture.start_server()
        self.queue = queue

    def tearDown(self):
        self.fixture.clear_up()

    def run(self):
        self.setUp()
        done = event.Event()
        spawn_n(self.start_chrome,
                'http://localhost:%s/run-tests' % self.fixture.port, done)
        while True:
            msg = self.queue.get()
            result = msg.pop('result', None)
            if result:
                msg.update(result)
                desc = "%(namespace)s.%(name)s: %(total)d tests run" % msg
                self.js_results_generator.description = desc
                yield self.js_results_generator, result
                self.js_results_generator.description = ''
            else:
                assert 'DONE' in msg
                done.send()
        self.tearDown()

    def js_results_generator(self, result):
        assert not result['failures']

    def start_chrome(self, url, done):
        chrome = self.CMD_LOOKUP.get(sys.platform)
        if not chrome:
            self.chrome = None
            raise ChromeNotFound('Executable for chrome not found')
        self.chrome = subprocess.Popen([chrome, url], shell=True)
        done.wait()
        self.chrome.kill()


        


class TestYieldingFromSetupTest(object):

    def test_yield(self):
        for i in range(1,4):
            yield self._test, i
        yield self._test, 0

    def _test(self, i):
        ok_(i > 0)
        

