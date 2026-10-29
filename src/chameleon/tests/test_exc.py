import os
import tempfile
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

    def test_render_error_of_non_utf8_file_to_string(self):
        # the source lines are read back from the file for the error
        # message; a file that is not valid in the locale's encoding
        # must not make the conversion to a string fail
        from chameleon import PageTemplateFile
        body = '<?xml version="1.0" encoding="latin-1"?>\n<p>caf\xe9 ${missing}</p>'
        with tempfile.TemporaryDirectory() as path:
            filename = os.path.join(path, 'latin.pt')
            with open(filename, 'wb') as f:
                f.write(body.encode('latin-1'))
            template = PageTemplateFile(filename)
            with self.assertRaises(NameError) as context:
                template()
            self.assertIn('missing', str(context.exception))
