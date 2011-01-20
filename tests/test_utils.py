from eventlet import Queue, spawn_n, sleep, tpool, with_timeout
from nose.tools import eq_, ok_, assert_raises
from unittest import TestCase
from snotty.utils import NamespaceContext, WSTestCase, ChromeNotFound, Fixture


def listener(q, acc):

    while not q.empty():
#        print 'qsize: ', q.qsize()
#        print 'qputting: ', q.putting()
        acc.append(q.get())
        q.task_done()
        sleep()

def pub(q, to_pub):
    for pub in to_pub:
        q.put(pub)
        #sleep()

#def test_ipc():
#    q = Queue(4)
#    spawn_n(pub, q, [1,2,3])
#    spawn_n(pub, q, [4,5,6])
#
#    acc = []
#    spawn_n(listener, q, acc)
#    q.join()
#
#    eq_(acc, range(1,7))

def test_namespacecontext_get_factory():
    QUEUE = object()
    factory = NamespaceContext.get_factory(QUEUE)
    ns = factory(None) # factory take a 'request' arg which isn't used
    subns = ns['one']['two']
    ok_(subns.queue is QUEUE)

def test_namespace_context_traversal():
    ns = NamespaceContext()
    subns = ns['one']['two']
    eq_(subns.namespace, 'one.two')

def test_namespace_contexts_share_queue():
    ns = NamespaceContext()
    subns = ns['one']['two']
    ok_(subns.queue is ns.queue)

def test_chromenotfound_raised():
    class _WSTestCase(WSTestCase):
        CMD_LOOKUP = {}
    ws_testcase = _WSTestCase()
    assert_raises(ChromeNotFound, ws_testcase.start_chrome, 'some-url', None)
    assert_raises(KeyError, ws_testcase.start_chrome, 'some-url', None)

class TestFixture(TestCase):

    def test_fixture_init(self):
        fixture = Fixture('config:snotty/snotty.ini', relative_to='.')


class TestQuint(WSTestCase):

    TST_FILES = ['/static/tests/same.js', '/static/tests/test.js']

    def test_qunit(self):
        for i in self.run():
            yield i