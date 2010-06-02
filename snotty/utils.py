from eventlet import Queue, event, spawn_n, hubs, sleep
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
        def close_down(evt):
            evt.wait()
#            context.shutdown()
            sleep(0)
        LAST_MSG = event.Event()
        spawn_n(close_down, LAST_MSG)
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
        return '.'.join(model_path_tuple(self)[1:])

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
    )

    def _setUp(self):
        queue = Queue()
        test_view = dict(view=JsTestFiles(self.LIB_FILES, self.TST_FILES),
                         view_renderer='snotty:templates/test.html')
        self.fixture = Fixture(zcml_file='snotty:tests.zcml',
                               root_factory=NamespaceContext.get_factory(queue),
                               routes=[['tests', '/run-tests', test_view]])
        self.fixture.start_server()
        self.queue = queue

    def _tearDown(self):
        #from nose.tools import set_trace; set_trace()
        self.fixture.clear_up()

    def run(self):
        self._setUp()
        done = event.Event()
        spawn_n(self.start_chrome,
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
        spawn_n(self.kill_chrome, done)
        self.chrome.communicate()

    def kill_chrome(self, done):
        done.wait()
        print '##########\nGOT DONE'
        self.chrome.kill()
        sleep(0.5)


        


class TestYieldingFromSetupTest(object):

    def test_yield(self):
        for i in range(1,4):
            yield self._test, i
        yield self._test, 0

    def _test(self, i):
        ok_(i > 0)
        

