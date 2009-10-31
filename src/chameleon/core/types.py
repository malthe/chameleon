from utils import emptydict

class expression:
    label = None
    symbol_mapping = emptydict

    def __init__(self, *args):
        self.symbol_mapping = {}

class parts(tuple, expression):
    exceptions = (Exception,)
    
    def __new__(cls, value=()):
        if not isinstance(value, (tuple, list)):
            value = (value,)
        inst = tuple.__new__(cls, value)
        inst.symbol_mapping = {}
        for part in value:
            if isinstance(part, expression):
                inst.symbol_mapping.update(part.symbol_mapping)
        return inst
    
    def __repr__(self):
        return 'parts'+tuple.__repr__(self)

class value(unicode, expression):
    def __init__(self, *args):
        super(value, self).__init__()
        self.symbol_mapping = {}
        
    def __repr__(self):
        try:
            r = repr(self.encode())
        except UnicodeEncodeError:
            r = unicode.__repr__(self)
            
        return "value(%s)" % r        

class template(value):
    def __repr__(self):
        return 'template(%s)' % value.__repr__(self)

class join(tuple, expression):
    def __repr__(self):
        return 'join'+tuple.__repr__(self)

class declaration(tuple):
    global_scope = False
    
    def __repr__(self):
        items = map(repr, self)
        if self.global_scope:
            items.append('global_scope=%s' % repr(self.global_scope))
        return 'declaration(%s)' % ', '.join(items)

class mapping(tuple):
    def __repr__(self):
        return 'mapping'+tuple.__repr__(self)

class definitions(tuple):
    def __repr__(self):
        return 'definitions'+tuple.__repr__(self)

class escape(parts):
    def __repr__(self):
        return 'escape'+tuple.__repr__(self)

class method(expression):
    def __init__(self, name, args, decorators=()):
        self.name = name
        self.args = args
        self.decorators = decorators
        self.symbol_mapping = {}
        
    def __repr__(self):
        return "%s%s(%s)" % (
            "".join("%s\n" % d for d in self.decorators),
            self.name, ", ".join(arg for arg in self.args))
        
