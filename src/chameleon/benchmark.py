import unittest
import time
import os
import re

re_amp = re.compile(r'&(?!([A-Za-z]+|#[0-9]+);)')

BIGTABLE_ZPT = """\
<table xmlns="http://www.w3.org/1999/xhtml"
xmlns:tal="http://xml.zope.org/namespaces/tal">
<tr tal:repeat="row python: options['table']">
<td tal:repeat="c python: row.values()">
<span tal:define="d python: c + 1"
tal:attributes="class python: 'column-' + str(d)"
tal:content="python: d" />
</td>
</tr>
</table>"""

MANY_STRINGS_ZPT = """\
<table xmlns="http://www.w3.org/1999/xhtml"
xmlns:tal="http://xml.zope.org/namespaces/tal">
<tr tal:repeat="i python: xrange(1000)">
<td tal:content="string: number ${i}" />
</tr>
</table>
"""

HELLO_WORLD_ZPT = """\
<html xmlns="http://www.w3.org/1999/xhtml"
xmlns:tal="http://xml.zope.org/namespaces/tal">
<body>
<h1>Hello, world!</h1>
</body>
</html>
"""

I18N_ZPT = """\
<html xmlns="http://www.w3.org/1999/xhtml"
xmlns:tal="http://xml.zope.org/namespaces/tal"
xmlns:i18n="http://xml.zope.org/namespaces/i18n">
  <body>
    <div tal:repeat="i python: xrange(10)">
      <div i18n:translate="">
        Hello world!
      </div>
      <div i18n:translate="hello_world">
        Hello world!
      </div>
      <div i18n:translate="">
        <sup>Hello world!</sup>
      </div>
    </div>
  </body>
</html>
"""


def benchmark(title):
    def decorator(f):
        def wrapper(*args):
            print(
                "==========================\n " \
                "%s\n==========================" % \
                title)
            return f(*args)
        return wrapper
    return decorator


def timing(func, *args, **kwargs):
    t1 = t2 = time.time()
    i = 0
    while t2 - t1 < 3:
        func(**kwargs)
        func(**kwargs)
        func(**kwargs)
        func(**kwargs)
        i += 4
        t2 = time.time()
    return float(10 * (t2 - t1)) / i


START = 0
END = 1
TAG = 2


def yield_tokens(table=None):
    index = []
    tag = index.append
    _re_amp = re_amp
    tag(START)
    yield "<", "html", "", ">\n"
    for r in table:
        tag(START)
        yield "<", "tr", "", ">\n"

        for c in r.values():
            d = c + 1
            tag(START)
            yield "<", "td", "", ">\n"

            _tmp5 = d
            if not isinstance(_tmp5, unicode):
                _tmp5 = str(_tmp5)
            if ('&' in _tmp5):
                if (';' in _tmp5):
                    _tmp5 = _re_amp.sub('&amp;', _tmp5)
                else:
                    _tmp5 = _tmp5.replace('&', '&amp;')
            if ('<' in _tmp5):
                _tmp5 = _tmp5.replace('<', '&lt;')
            if ('>' in _tmp5):
                _tmp5 = _tmp5.replace('>', '&gt;')
            if ('"' in _tmp5):
                _tmp5 = _tmp5.replace('"', '&quot;')
            _tmp5 = "column-%s" % _tmp5

            _tmp = d
            if (_tmp.__class__ not in (str, unicode, int, float, )):
                raise
            if (_tmp is not None):
                if not isinstance(_tmp, unicode):
                    _tmp = str(_tmp)
                if ('&' in _tmp):
                    if (';' in _tmp):
                        _tmp = _re_amp.sub('&amp;', _tmp)
                    else:
                        _tmp = _tmp.replace('&', '&amp;')
                if ('<' in _tmp):
                    _tmp = _tmp.replace('<', '&lt;')
                if ('>' in _tmp):
                    _tmp = _tmp.replace('>', '&gt;')
            tag(START)

            t = ["classicism"]

            yield "<", "span", " ", t[0], '="', _tmp5, '"', ">\n"
            tag(END)
            yield "</", "span", ">\n"
            tag(END)
            yield "</", "td", ">\n"
        tag(END)
        yield "</", "tr", ">\n"
    tag(END)
    yield "</", "html", ">\n"


def yield_tokens_dict_version(**kwargs):
    index = []
    tag = index.append
    _re_amp = re_amp
    tag(START)
    yield "<", "html", "", ">\n"

    for r in kwargs['table']:
        kwargs['r'] = r
        tag(START)
        yield "<", "tr", "", ">\n"

        for c in kwargs['r'].values():
            kwargs['d'] = c + 1
            tag(START)
            yield "<", "td", "", ">\n"

            _tmp5 = kwargs['d']
            if not isinstance(_tmp5, unicode):
                _tmp5 = str(_tmp5)
            if ('&' in _tmp5):
                if (';' in _tmp5):
                    _tmp5 = _re_amp.sub('&amp;', _tmp5)
                else:
                    _tmp5 = _tmp5.replace('&', '&amp;')
            if ('<' in _tmp5):
                _tmp5 = _tmp5.replace('<', '&lt;')
            if ('>' in _tmp5):
                _tmp5 = _tmp5.replace('>', '&gt;')
            if ('"' in _tmp5):
                _tmp5 = _tmp5.replace('"', '&quot;')
            _tmp5 = "column-%s" % _tmp5

            _tmp = kwargs['d']
            if (_tmp.__class__ not in (str, unicode, int, float, )):
                raise
            if (_tmp is not None):
                if not isinstance(_tmp, unicode):
                    _tmp = str(_tmp)
                if ('&' in _tmp):
                    if (';' in _tmp):
                        _tmp = _re_amp.sub('&amp;', _tmp)
                    else:
                        _tmp = _tmp.replace('&', '&amp;')
                if ('<' in _tmp):
                    _tmp = _tmp.replace('<', '&lt;')
                if ('>' in _tmp):
                    _tmp = _tmp.replace('>', '&gt;')
            tag(START)

            t = ["classicism"]

            yield "<", "span", " ", t[0], '="', _tmp5, '"', ">\n"
            tag(END)
            yield "</", "span", ">\n"
            tag(END)
            yield "</", "td", ">\n"
        tag(END)
        yield "</", "tr", ">\n"
    tag(END)
    yield "</", "html", ">\n"


def yield_stream(table=None):
    _re_amp = re_amp
    yield START, ("html", "", "\n"), None
    for r in table:
        yield START, ("tr", "", "\n"), None

        for c in r.values():
            d = c + 1
            yield START, ("td", "", "\n"), None

            _tmp5 = d
            if not isinstance(_tmp5, unicode):
                _tmp5 = str(_tmp5)
            if ('&' in _tmp5):
                if (';' in _tmp5):
                    _tmp5 = _re_amp.sub('&amp;', _tmp5)
                else:
                    _tmp5 = _tmp5.replace('&', '&amp;')
            if ('<' in _tmp5):
                _tmp5 = _tmp5.replace('<', '&lt;')
            if ('>' in _tmp5):
                _tmp5 = _tmp5.replace('>', '&gt;')
            if ('"' in _tmp5):
                _tmp5 = _tmp5.replace('"', '&quot;')
            _tmp5 = "column-%s" % _tmp5

            _tmp = d
            if (_tmp.__class__ not in (str, unicode, int, float, )):
                raise
            if (_tmp is not None):
                if not isinstance(_tmp, unicode):
                    _tmp = str(_tmp)
                if ('&' in _tmp):
                    if (';' in _tmp):
                        _tmp = _re_amp.sub('&amp;', _tmp)
                    else:
                        _tmp = _tmp.replace('&', '&amp;')
                if ('<' in _tmp):
                    _tmp = _tmp.replace('<', '&lt;')
                if ('>' in _tmp):
                    _tmp = _tmp.replace('>', '&gt;')
            yield START, ("span", "", _tmp, " ", "class", _tmp5), None

            yield END, ("span", "", "\n"), None
            yield END, ("td", "", "\n"), None
        yield END, ("tr", "", "\n"), None
    yield END, ("html", "", "\n"), None

from itertools import chain


def bigtable_python_tokens(table=None, renderer=None):
    iterable = renderer(table=table)
    stream = chain(*iterable)
    return "".join(stream)


def bigtable_python_stream(table=None, renderer=None):
    stream = renderer(table=table)
    return "".join(stream_output(stream))


def bigtable_python_stream_with_filter(table=None, renderer=None):
    stream = renderer(table=table)
    return "".join(stream_output(uppercase_filter(stream)))


def uppercase_filter(stream):
    for kind, data, pos in stream:
        if kind is START:
            data = (data[0], data[1], data[2].upper(),) + data[3:]
        elif kind is END:
            data = (data[0], data[1], data[2].upper())
        elif kind is TAG:
            raise NotImplemented
        yield kind, data, pos


def stream_output(stream):
    for kind, data, pos in stream:
        if kind is START:
            tag = data[0]
            yield "<%s" % tag
            l = len(data)

            # optimize for common cases
            if l == 3:
                pass
            elif l == 6:
                yield '%s%s="%s"' % (data[3], data[4], data[5])
            else:
                i = 3
                while i < l:
                    yield '%s%s="%s"' % (data[i], data[i + 1], data[i + 2])
                    i += 3
            yield "%s>%s" % (data[1], data[2])
        elif kind is END:
            yield "</%s%s>%s" % data
        elif kind is TAG:
            raise NotImplemented


class Benchmarks(unittest.TestCase):
    table = [dict(a=1, b=2, c=3, d=4, e=5, f=6, g=7, h=8, i=9, j=10) \
             for x in range(1000)]

    def setUp(self):
        # set up i18n component
        from zope.i18n import translate
        from zope.i18n.interfaces import INegotiator
        from zope.i18n.interfaces import ITranslationDomain
        from zope.i18n.negotiator import Negotiator
        from zope.i18n.simpletranslationdomain import SimpleTranslationDomain
        from zope.i18n.tests.test_negotiator import Env
        from zope.tales.tales import Context

        self.env = Env(('klingon', 'da', 'en', 'fr', 'no'))

        class ZopeI18NContext(Context):

            def translate(self, msgid, domain=None, context=None,
                          mapping=None, default=None):
                context = self.vars['options']['env']
                return translate(msgid, domain, mapping,
                                 context=context, default=default)

        def _getContext(self, contexts=None, **kwcontexts):
            if contexts is not None:
                if kwcontexts:
                    kwcontexts.update(contexts)
                else:
                    kwcontexts = contexts
            return ZopeI18NContext(self, kwcontexts)

        def _pt_getEngineContext(namespace):
            self = namespace['template']
            engine = self.pt_getEngine()
            return _getContext(engine, namespace)

        import zope.component
        zope.component.provideUtility(Negotiator(), INegotiator)
        catalog = SimpleTranslationDomain('domain')
        zope.component.provideUtility(catalog, ITranslationDomain, 'domain')
        self.files = os.path.abspath(os.path.join(__file__, '..', 'input'))

    @staticmethod
    def _chameleon(body, **kwargs):
        from .zpt.template import PageTemplate
        return PageTemplate(body, **kwargs)

    @staticmethod
    def _zope(body):
        from zope.pagetemplate.pagetemplatefile import PageTemplate
        template = PageTemplate()
        template.pt_edit(body, 'text/xhtml')
        return template

    @benchmark(u"BIGTABLE [python]")
    def test_bigtable(self):
        options = {'table': self.table}

        t_chameleon = timing(self._chameleon(BIGTABLE_ZPT), options=options)
        print("chameleon:         %7.2f" % t_chameleon)

        t_chameleon_utf8 = timing(
            self._chameleon(BIGTABLE_ZPT, encoding='utf-8'), options=options)
        print("chameleon (utf-8): %7.2f" % t_chameleon_utf8)

        t_tokens = timing(
            bigtable_python_tokens, table=self.table, renderer=yield_tokens)
        print("token:             %7.2f" % t_tokens)

        t_tokens_dict_version = timing(
            bigtable_python_tokens, table=self.table,
            renderer=yield_tokens_dict_version)
        print("token (dict):      %7.2f" % t_tokens_dict_version)

        t_stream = timing(
            bigtable_python_stream, table=self.table, renderer=yield_stream)
        print("stream:            %7.2f" % t_stream)

        t_zope = timing(self._zope(BIGTABLE_ZPT), table=self.table)
        print("zope.pagetemplate: %7.2f" % t_zope)
        print("                  %7.1fX" % (t_zope / t_chameleon))

        print("--------------------------")
        print("check: %d vs %d" % (
            len(self._chameleon(BIGTABLE_ZPT)(options=options)),
            len(self._zope(BIGTABLE_ZPT)(table=self.table))))
        print("--------------------------")

    @benchmark(u"MANY STRINGS [python]")
    def test_many_strings(self):
        t_chameleon = timing(self._chameleon(MANY_STRINGS_ZPT))
        print("chameleon:         %7.2f" % t_chameleon)
        t_zope = timing(self._zope(MANY_STRINGS_ZPT))
        print("zope.pagetemplate: %7.2f" % t_zope)
        print("                  %7.1fX" % (t_zope / t_chameleon))

        print("--------------------------")
        print("check: %d vs %d" % (
            len(self._chameleon(MANY_STRINGS_ZPT)()),
            len(self._zope(MANY_STRINGS_ZPT)())))
        print("--------------------------")

    @benchmark(u"HELLO WORLD")
    def test_hello_world(self):
        t_chameleon = timing(self._chameleon(HELLO_WORLD_ZPT)) * 1000
        print("chameleon:         %7.2f" % t_chameleon)
        t_zope = timing(self._zope(HELLO_WORLD_ZPT)) * 1000
        print("zope.pagetemplate: %7.2f" % t_zope)
        print("                  %7.1fX" % (t_zope / t_chameleon))

        print("--------------------------")
        print("check: %d vs %d" % (
            len(self._chameleon(HELLO_WORLD_ZPT)()),
            len(self._zope(HELLO_WORLD_ZPT)())))
        print("--------------------------")

    @benchmark(u"I18N")
    def test_i18n(self):
        from zope.i18n import translate
        t_chameleon = timing(
            self._chameleon(I18N_ZPT),
            translate=translate,
            language="klingon") * 1000
        print("chameleon:         %7.2f" % t_chameleon)
        t_zope = timing(self._zope(I18N_ZPT), env=self.env) * 1000
        print("zope.pagetemplate: %7.2f" % t_zope)
        print("                  %7.1fX" % (t_zope / t_chameleon))

    @benchmark(u"COMPILATION")
    def test_compilation(self):
        template = self._chameleon(HELLO_WORLD_ZPT)

        def chameleon_cook_and_render(template=template):
            template.cook(HELLO_WORLD_ZPT)
            template()

        t_chameleon = timing(chameleon_cook_and_render) * 1000
        print("chameleon:         %7.2f" % t_chameleon)

        template = self._zope(HELLO_WORLD_ZPT)

        def zope_cook_and_render(templte=template):
            template._cook()
            template()

        t_zope = timing(zope_cook_and_render) * 1000
        print("zope.pagetemplate: %7.2f" % t_zope)
        print("                    %0.3fX" % (t_zope / t_chameleon))


def start():
    result = unittest.TestResult()
    test = unittest.makeSuite(Benchmarks)
    test.run(result)

    for error in result.errors:
        print("Error in %s...\n" % error[0])
        print(error[1])

    for failure in result.failures:
        print("Failure in %s...\n" % failure[0])
        print(failure[1])
