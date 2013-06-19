import os
from unittest import TestCase
try:
    from unittest.mock import Mock, patch
except ImportError:
    from mock import Mock, patch

class Test_compile_one(TestCase):

    @patch('chameleon.precompile.CACHE_DIRECTORY')
    def test_it(self, cache_dir):
        template_factory = Mock()
        from chameleon.precompile import compile_one
        compile_one('path', template_factory=template_factory)
        template_factory.assert_called_once_with('path')
        template_factory().cook_check.assert_called_once_with()

class Test_walk_dir(TestCase):

    @patch('chameleon.precompile.compile_one')
    def test_it(self, compile_one):
        from chameleon.precompile import walk_dir
        inputs = os.path.join(os.path.dirname(__file__), "inputs")
        for result in walk_dir(inputs):
            self.assertTrue(result['success'])
        self.assertTrue(compile_one.call_count > 10)

class Test_compile(TestCase):

    @patch('sys.exit')
    @patch('chameleon.precompile.logging')
    @patch('chameleon.precompile.compile_one')
    @patch('chameleon.precompile.CACHE_DIRECTORY')
    def test_it(self, cache_dir, compile_one, logger, sys_exit):
        from chameleon.precompile import compile
        inputs = os.path.join(os.path.dirname(__file__), "inputs")
        compile(['script', '--dir', inputs])
        self.assertTrue(compile_one.call_count > 10)
        self.assertTrue(sys_exit.called_once_with(0))
