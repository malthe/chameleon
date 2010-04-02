try:
    from zope.i18n import interpolate
    from zope.i18n import translate
    from zope.i18nmessageid import Message
except ImportError:
    def fast_translate(msgid, *args, **kwargs):
        return kwargs.get('default', msgid)
else:
    def fast_translate(msgid, domain=None, mapping=None, context=None,
                       target_language=None, default=None):
        if msgid is None:
            return

        if target_language is not None:
            result = translate(
                msgid, domain=domain, mapping=mapping, context=context,
                target_language=target_language, default=default)
            if result!=msgid:
                return result

        if isinstance(msgid, Message):
            default = msgid.default
            mapping = msgid.mapping

        if default is None:
            default = unicode(msgid)

        if not isinstance(default, basestring):
            return default

        return interpolate(default, mapping)

class StringMarker(str):
    def __nonzero__(self):
        return False

marker = StringMarker()

