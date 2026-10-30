import unittest


class ScopeTestCase(unittest.TestCase):
    def setUp(self):
        from chameleon.utils import Scope
        scope = Scope()
        scope['a'] = 1
        scope.set_global("b", 2)

        self.parent = scope
        self.child = scope.copy()

    def test_items(self):
        assert list(self.child.items()) == [('a', 1), ('b', 2)]

    def test_keys(self):
        assert list(self.child.keys()) == ['a', 'b']

    def test_values(self):
        assert list(self.child.values()) == [1, 2]


class ResolveDottedTestCase(unittest.TestCase):
    import os.path as _path

    def test_relative_name(self):
        from chameleon.utils import _resolve_dotted
        assert _resolve_dotted('.path', 'os') is self._path

    def test_relative_name_up_one_level(self):
        from chameleon.utils import _resolve_dotted
        assert _resolve_dotted('..path', 'os.sep') is self._path
