import re
import types

re_interpolation = re.compile(
    r'(?P<prefix>[^\\]\$|^\$)({((?P<expression>.*)})?|'
    '(?P<variable>[A-Za-z][A-Za-z0-9_]*))')

def interpolate(string, translator):
    """Splits up an interpolation string expression on the form
    ${<expression>} into a ``join`` expression.
    
    >>> def translator(string):
    ...     return types.value(string)

    >>> interpolate("${abc}", translator)
    (value('abc'),)

    >>> interpolate(" ${abc}", translator)
    (' ', value('abc'))

    >>> interpolate("abc${def}", translator)
    ('abc', value('def'))

    >>> interpolate("${def}abc", translator)
    (value('def'), 'abc')

    >>> interpolate("abc${def}ghi", translator)
    ('abc', value('def'), 'ghi')

    >>> interpolate("abc${def}ghi${jkl}", translator)
    ('abc', value('def'), 'ghi', value('jkl'))

    >>> interpolate("abc${def}", translator)
    ('abc', value('def'))

    >>> print interpolate(u"abc${ghi}", translator)
    (u'abc', value('ghi'))

    >>> print interpolate(u"}${abc}", translator)
    (u'}', value('abc'))
    
    """

    m = match_interpolate(string, translator)
    if m is None:
        return (string,)

    prefix = m.group('prefix')
    parts = []

    start = m.start() + len(prefix) - 1
    if start > 0:
        text = string[:start]
        parts.append(text)

    expression = m.group('expression')
    variable = m.group('variable')

    if expression:
        parts.append(translator(expression))
    elif variable:
        parts.append(translator(variable))

    rest = string[m.end():]
    if len(rest):
        parts.extend(interpolate(rest, translator))

    return tuple(parts)

def match_interpolate(string, translator):
    """Search for an interpolation and return a match.

    >>> def translator(string):
    ...     return types.value(string)

    >>> match_interpolate('${abc}', translator).group('expression')
    'abc'

    >>> match_interpolate(' ${abc}', translator).group('expression')
    'abc'

    >>> match_interpolate('abc${def}', translator).group('expression')
    'def'

    >>> match_interpolate('abc${def}ghi${jkl}', translator).group('expression')
    'def'

    >>> match_interpolate('$abc', translator).group('variable')
    'abc'

    >>> match_interpolate('${abc', translator)
    Traceback (most recent call last):
      ...
    SyntaxError: Interpolation expressions must be of the form ${<expression>} (${abc)

    """

    m = re_interpolation.search(string)
    if m is None:
        return None

    expression = m.group('expression')
    variable = m.group('variable')

    if expression:
        left = m.start()+len(m.group('prefix'))+1
        right = string.find('}')

        while right != -1:
            if right > left:
                match = string[left:right]
                try:
                    exp = translator(match)
                    break
                except SyntaxError:
                    pass
            right = string.find('}', right+1)
        else:
            raise

        string = string[:right+1]
        return re_interpolation.search(string)

    if m is None or (expression is None and variable is None):
        raise SyntaxError(
            "Interpolation expressions must be of the "
            "form ${<expression>} (%s)" % string)

    if expression and not m.group('expression'):
        raise SyntaxError(expression)

    return m
