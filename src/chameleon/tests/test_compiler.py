import functools
import unittest


class ExpressionEvaluatorTestCase(unittest.TestCase):
    def test_no_builtins(self):
        from chameleon.compiler import ExpressionEngine
        from chameleon.compiler import ExpressionEvaluator
        from chameleon.tales import ExpressionParser
        from chameleon.tales import PythonExpr
        from chameleon.utils import Scope

        parser = ExpressionParser({'python': PythonExpr}, 'python')
        engine = functools.partial(ExpressionEngine, parser)
        evaluator = ExpressionEvaluator(engine, {})
        result = evaluator(Scope({'boo': 'baz'}), {}, 'python', 'boo * 2')
        assert result == 'bazbaz'
