from unittest import TestCase

class TestTemplateError(TestCase):

    def test_keep_token_location_info(self):
        # tokens should not lose information when passed to a TemplateError
        from chameleon import exc, tokenize, utils
        token = tokenize.Token('stuff', 5, 'more\nstuff', 'mystuff.txt')
        error = exc.TemplateError('message', token)
        s = str(error)
        self.assertTrue(
                '- Location:   (line 2: col 0)' in s,
                'No location data found\n%s' % s)
