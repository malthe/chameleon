from unittest import TestCase

from chameleon import exc
from chameleon import tokenize


class TestTemplateError(TestCase):

    def test_keep_token_location_info(self):
        # tokens should not lose information when passed to a TemplateError
        token = tokenize.Token('stuff', 5, 'more\nstuff', 'mystuff.txt')
        error = exc.TemplateError('message', token)
        s = str(error)
        self.assertTrue(
            '- Location:   (line 2: col 0)' in s,
            'No location data found\n%s' % s)

    def test_umlaut_exc_to_string(self):
        # test if an exception is convertible to a string
        body = '<p>uumlaut:\xfc</p>'
        string = body[3:-4]
        token = tokenize.Token(string, 3, body)
        e = exc.LanguageError('Invalid define syntax', token)
        # its fine if we get no exception from the following line
        str(e)
