import utils
import types
import config

function_template = """\
def bind():
%(imports)s
\tdef %(name)s(econtext, rcontext=None):
\t\t%(transient)s
%(source)s
%(return)s
\treturn %(name)s
"""

def indent_block(text, level=2):
    return "\n".join(("\t" * level + s for s in text.split('\n')))

def function_wrap(name, imports, source, transient="pass", return_expr=""):
    format_values = {
        'name': name,
        'imports': indent_block('\n'.join(imports), 1),
        'source': indent_block(source),
        'transient': transient,
        'return': indent_block("return %s" % return_expr)}

    return function_template % format_values

def initialize_tal():
    return ({}, utils.repeatdict())

def initialize_default():
    return utils.default()

def initialize_stream():
    out = BufferIO()
    return (out, out.write)

initialize_scope = utils.econtext

class BufferIO(list):
    def getvalue(self):
        return ''.join(self)

    write = list.append

class CodeIO(BufferIO):
    """Stream buffer suitable for writing Python-code. This class is
    used internally by the compiler to manage variable scopes, source
    annotations and temporary variables."""

    t_prefix = '_tmp'
    v_prefix = '_tmpv'

    annotation = None

    def __init__(self, symbols=None, encoding=None,
                 indentation=0, indentation_string="\t"):
        self.symbols = symbols or object
        self.symbol_mapping = {}
        self.encoding = encoding
        self.indentation = indentation
        self.indentation_string = indentation_string
        self.queue = []
        self.scope = [set()]
        self.annotations = {}
        self._variables = {}
        self.t_counter = 0
        self.v_counter = 0
        self.l_counter = 0

    def new_var(self):
        self.v_counter += 1
        return "%s%d" % (self.v_prefix, self.v_counter)
        
    def save(self):
        self.t_counter += 1
        return "%s%d" % (self.t_prefix, self.t_counter)

    def restore(self):
        var = "%s%d" % (self.t_prefix, self.t_counter)
        self.t_counter -= 1
        return var

    def indent(self, amount=1):
        if amount > 0:
            self.flush()
            self.indentation += amount

    def outdent(self, amount=1):
        if amount > 0:
            self.flush()
            self.indentation -= amount

    def annotate(self, annotation):
        if isinstance(annotation, types.expression):
            if annotation.label is not None:
                annotation = annotation.label

        # make sure the annotation is a base string type
        if isinstance(annotation, unicode):
            annotation = unicode(annotation)
        else:
            annotation = str(annotation)

        self.annotation = self.annotations[self.l_counter] = annotation

    def out(self, value):
        if isinstance(value, types.expression):
            assert isinstance(value, types.value)
        self.queue.append(value)
            
    def flush(self):
        if self.queue:
            # optimize queue to merge adjacent strings
            optimized = []

            current = None
            while self.queue:
                next = self.queue.pop(0)

                if type(current) in (str, unicode) and \
                   type(next) in (str, unicode):
                    current = current + next
                    continue
                elif current is not None:
                    optimized.append(current)

                current = next
            else:
                optimized.append(current)            

            assert len(self.queue) == 0
            
            self.write(
                "%s(%s)" %
                (self.symbols.write, " + ".join(
                isinstance(expression, types.value) and expression or \
                repr(expression) for expression in optimized)))

    def write(self, string):
        self.l_counter += len(string.split('\n'))-1
        self.flush()
        
        indent = self.indentation_string * self.indentation

        # if a source code annotation is set, write it as a
        # triple-quoted string prior to the source line
        if self.annotation:
            BufferIO.write(
                self, "%s%s\n" % (indent, repr(self.annotation)))
            self.annotation = None
            
        BufferIO.write(self, indent + string + '\n')

    def getvalue(self):
        self.flush()
        return BufferIO.getvalue(self)

    def escape(self, variable, escape_double_quote=False):
        self.symbol_mapping[config.SYMBOLS.re_amp] = utils.re_amp
        self.write("if '&' in %s:" % variable)
        self.indent()
        self.write("if ';' in %s: %s = %s.sub('&amp;', %s)" % (
            variable, variable, config.SYMBOLS.re_amp, variable))
        self.write("else: %s = %s.replace('&', '&amp;')" % (variable, variable))
        self.outdent()
        self.write("if '<' in %s:" % variable)
        self.indent()
        self.write("%s = %s.replace('<', '&lt;')" % (variable, variable))
        self.outdent()
        self.write("if '>' in %s:" % variable)
        self.indent()
        self.write("%s = %s.replace('>', '&gt;')" % (variable, variable))
        self.outdent()
        if escape_double_quote:
            self.write("if '\"' in %s:" % variable)
            self.indent()
            self.write("%s = %s.replace('\"', '&quot;')" % (variable, variable))
            self.outdent()

    def ensure_unicode(self, variable):
        """Converts variable to a unicode string, if it isn't
        already. If no encoding is required, non-unicode objects will
        be coerced to ``str`` (it's much faster).
        """

        self.write("if not isinstance(%s, unicode):" % variable)
        self.indent()
        if self.encoding:
            self.write("%s = unicode(str(%s), %s)"% (
                variable, variable, repr(self.encoding)))
        else:
            self.write("%s = str(%s)" % (variable, variable))
        self.outdent()

    def begin(self, clauses):
        if isinstance(clauses, (list, tuple)):
            for clause in clauses:
                self.begin(clause)
        else:
            clauses.begin(self)
                
    def end(self, clauses):
        if isinstance(clauses, (list, tuple)):
            for clause in reversed(clauses):
                self.end(clause)
        else:
            clauses.end(self)
