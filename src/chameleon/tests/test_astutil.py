import ast
import sys
import unittest


class ASTCodeGeneratorTestCase(unittest.TestCase):
    def _eval(self, tree, env):
        from chameleon.astutil import ASTCodeGenerator
        source = ASTCodeGenerator(tree).code
        code = compile(source, '<string>', 'exec')
        exec(code, env)

    @unittest.skipIf(sys.version_info < (3, 7),
                     'Only applicable on Python 3.7+')
    def test_slice(self):
        tree = ast.Module(
            body=[
                ast.Assign(
                    targets=[
                        ast.Name(id='x', ctx=ast.Store())],
                    value=ast.Call(
                        func=ast.Name(id='f', ctx=ast.Load()),
                        args=[
                            ast.Slice(
                                upper=ast.Constant(value=0))],
                        keywords=[]))],
            type_ignores=[]
        )
        def f(x): return x
        d = {"f": f}
        self._eval(tree, d)
        assert d['x'] == slice(None, 0, None)
