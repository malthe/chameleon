import collections
import re
import tokenize
from chameleon.zpt.language import Parser

def safe_eval(s):
    return eval(s, {"__builtins__":{}}, {})


class PythonExtractor(object):
    def __call__(self, fileobj, keywords, comment_tags, options):
        self.state = self.stateWaiting
        self.msg = None
        self.keywords = keywords
        self.state = self.stateWaiting
        self.msg = None
        self.messages=[]
        tokens = tokenize.generate_tokens(fileobj.readline)
        for ( ttype, tstring, stup, etup, line) in tokens:
            self.state(ttype, tstring, stup[0])
        return self.messages

    def stateWaiting(self, ttype, tstring, lineno):
        if ttype == tokenize.NAME and tstring in self.keywords:
            self.state = self.stateKeywordSeen
            self.msg = dict(lineno=lineno)

    def stateKeywordSeen(self, ttype, tstring, lineno):
        # We have seen _, now check if this is a _( .. ) call
        if ttype==tokenize.OP and tstring=="(":
            self.state=self.stateWaitForLabel
        else:
            self.state=self.stateWaiting

    def stateWaitForLabel(self, ttype, tstring, lineno):
        # We saw _(, wait for the message label
        if ttype==tokenize.STRING:
            self.msg.setdefault("label", []).append(safe_eval(tstring))
        elif ttype==tokenize.OP and tstring==",":
            self.state=self.stateWaitForDefault
        elif ttype==tokenize.OP and tstring==")":
            self.addMessage(self.msg)
            self.state = self.stateWaiting
        elif ttype==tokenize.NAME:
            self._parameter = tstring
            self.state = self.stateInFactoryParameter
        else:
            # Effectively a syntax error, but ignore and reset state
            self.msg = None
            self.state = self.stateWaiting

    def stateWaitForDefault(self, ttype, tstring, lineno):
        # We saw _("label", now wait for a default translation
        if ttype==tokenize.STRING:
            self.msg.setdefault("default", []).append(safe_eval(tstring))
        elif ttype==tokenize.NAME:
            self._parameter = tstring
            self.state = self.stateInFactoryParameter
        elif ttype==tokenize.OP and tstring==",":
            self.state=self.stateInFactoryWaitForParameter
        elif ttype==tokenize.OP and tstring==")":
            self.addMessage(self.msg)
            self.state = self.stateWaiting
        else:
            # Effectively a syntax error, but ignore and reset state
            self.msg = None
            self.state = self.stateWaiting

    def stateInFactoryWaitForParameter(self, ttype, tstring, lineno):
        if ttype==tokenize.OP and tstring==")":
            self.addMessage(self.msg)
            self.msg = None
            self.state = self.stateWaiting
        elif ttype==tokenize.NAME:
            self._parameter = tstring
            self.state = self.stateInFactoryParameter

    def stateInFactoryParameter(self, ttype, tstring, lineno):
        if ttype==tokenize.STRING:
            self.msg.setdefault(self._parameter, []).append(safe_eval(tstring))
        elif ttype==tokenize.OP and tstring==",":
            self.state = self.stateInFactoryWaitForParameter
        elif ttype==tokenize.OP and tstring==")":
            self.addMessage(self.msg)
            self.state = self.stateWaiting

    def addMessage(self, msg):
        if not msg.get("label"):
            return
        default = msg.get("default", None)
        if default:
            comments = [u"Default: %s" % u"".join(default)]
        else:
            comments = []
        self.messages.append((msg["lineno"], None, u"".join(msg["label"]), comments))


extract_python = PythonExtractor()


def extract_xml(fileobj, keywords, comment_tags, options):
    parser = Parser()
    doc = parser.parse(fileobj.read())
    root = doc.getroot()

    todo = collections.deque([(root, None)])
    while todo:
        (node, domain) = todo.pop()
        domain = getattr(node, "i18n_domain", domain)

        attrs = getattr(node, "i18n_attributes", None)
        if attrs:
            for (attr, label) in attrs:
                value = node.attrib.get(attr, None)
                if not value:
                    continue
                if value==label:
                    yield (1, None, label, [])
                else:
                    yield (1, None, label, [u"Default: %s" % value])

        label = getattr(node, "i18n_translate", None)
        if label is not None:
            msg = []
            if node.text:
                msg.append(node.text.lstrip())
            for child in node.getchildren():
                name = getattr(child, "i18n_name")
                if name:
                    msg.append(u"${%s}" % name)
                if child.tail:
                    msg.append(child.tail)
            msg = u"".join(msg)
            msg = re.sub(u"\s{2,}", u" ", msg)
            if label:
                yield (node.position[0], None, label, [u"Default: %s" % msg])
            else:
                yield (node.position[0], None, msg, [])

        for child in node.getchildren():
            todo.append((child, domain))


