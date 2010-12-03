import os
import unittest

from chameleon.core import config, filecache

class TestTemporaryFilecache(unittest.TestCase):

    def setUp(self):
        self.old_disk_cache = config.DISK_CACHE
        config.DISK_CACHE = False

    def test_debug_temporary_registry(self):
        # In debug mode and with disk caching turned off templates
        # are stored in a temporary directory
        path = os.path.join(os.path.dirname(__file__), "templates")
        from chameleon.zpt.template import PageTextTemplateFile
        t = PageTextTemplateFile(os.path.join(path, 'helloworld.txt'), debug=True)
        registry = t.registry
        self.assertEquals(type(registry), filecache.TemporaryTemplateCache)
        # the filename used to be wrong
        self.assertEquals(os.path.dirname(registry.module_filename), registry.path)

    def tearDown(self):
        config.DISK_CACHE = self.old_disk_cache

def test_suite():
    import sys
    return unittest.findTestCases(sys.modules[__name__])

