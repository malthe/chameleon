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
