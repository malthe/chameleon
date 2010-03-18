from lxml import etree
import re
import sys

HTML_COMMENT = re.compile(r"<!--.*?-->")
EXPANSION = re.compile(r"\${.*?}")

NSMAP = { "xhtml" : "http://www.w3.org/1999/xhtml",
          "py"    : "http://genshi.edgewall.org/",
          "tal"   : "http://xml.zope.org/namespaces/tal",
          "i18n"  : "http://xml.zope.org/namespaces/i18n",
        }

def qn(ns, tag):
    return "{%s}%s" % (NSMAP[ns], tag)

ATTR_TRANSLATE = qn("i18n", "translate")
ATTR_NAME = qn("i18n", "name")
ATTR_ATTRIBUTES = qn("i18n", "attributes")
NO_I18N_TAGS = set([qn("xhtml", "script"),
                    qn("xhtml", "object")])
NO_I18N_ATTRS = set([qn("tal", "replace"),
                     qn("tal", "content"),
                     qn("py", "replace"),
                     qn("py", "content"),
                     ])
I18N_ATTRS = set(["title", "alt"])




class Counter(object):
    def __init__(self):
        self.count=1
    def __add__(self, other):
        self.count+=other
    def __int__(self):
        return self.count
    def __str__(self):
        return str(self.count)

def hasText(txt):
    if not txt:
        return False
    txt=HTML_COMMENT.sub(u"", txt)
    txt=EXPANSION.sub(u"", txt)
    return bool(txt.strip())
        

def mustTranslate(el):
    for attr in el.attrib.keys():
        if attr in NO_I18N_ATTRS:
            return False

    if hasText(el.text):
        return True

    for child in el:
        if hasText(child.tail):
            return True

    return False


def handleContent(el, counter):
    if el.tag in NO_I18N_TAGS or not mustTranslate(el):
        if ATTR_TRANSLATE in el.attrib:
            del el.attrib[ATTR_TRANSLATE]
        return

    if ATTR_TRANSLATE in el.attrib:
        return

    el.attrib[ATTR_TRANSLATE]="string%d" % counter
    counter+=1

    childcounter=1
    for child in el:
        if ATTR_NAME in child.attrib:
            continue
        child.attrib[ATTR_NAME]="sub%d" % childcounter
        childcounter+=1


def getTranslatedAttributes(el):
    spec=el.attrib.get(ATTR_ATTRIBUTES, "")
    if ";" not in spec:
        return dict([(a,a) for a in spec.split()])
    else:
        return dict([a.split() for a in filter(None, spec.split(";"))])


def setTranslatedAttributes(el, mapping):
    if not mapping:
        if ATTR_ATTRIBUTES in el.attrib:
            del el.attrib[ATTR_ATTRIBUTES]
        return
    el.attrib[ATTR_ATTRIBUTES]=";".join("%s %s" % a for a in mapping.items())



def handleAttributes(el, counter):
    spec=getTranslatedAttributes(el)
    for attr in spec.keys():
        if not el.attrib.get(attr, "").strip():
            del spec[attr]
    for attr in I18N_ATTRS:
        if attr not in spec and attr in el.attrib:
            spec[attr]="string%s" % counter
            counter+=1
    setTranslatedAttributes(el, spec)


if __name__=="__main__":
    tree=etree.parse(sys.argv[1])
    root=tree.getroot()
    if "i18n" not in root.nsmap:
        root.nsmap["i18n"]=NSMAP["i18n"]

    counter=Counter()
    for el in tree.iter():
        handleContent(el, counter)
        handleAttributes(el, counter)


    print etree.tostring(tree)

