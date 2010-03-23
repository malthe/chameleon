import optparse
import os
import re
import sys

try:
    from lxml import etree
except ImportError:
    etree = None

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
        if attr not in spec and el.attrib.get(attr, "").strip():
            spec[attr]="string%s" % counter
            counter+=1
    setTranslatedAttributes(el, spec)


def main():
    parser=optparse.OptionParser(
            usage="i18nify [options] [<template>..]",
            description="This script adds i18n attributes to Genshi and ZPT "
                        "templates so they can be translated by Chameleon.")
    parser.add_option("-o", "--output", metavar="FILE",
            help="Store the result in FILE instead.",
            dest="output", action="store")
    parser.add_option("-i", "--inplace",
            help="Modify template files in-place.",
            dest="inplace", action="store_true", default=False)

    if etree is None:
        print >>sys.stderr, "Must have ``lxml`` package installed."
        sys.exit(1)

    (options, args) = parser.parse_args()
    if not args:
        args=[sys.stdin]
    if options.output and len(args)>1:
        print >>sys.stderr, "Can not use -o/--output with multipe input files."
        sys.exit(1)
    if options.output and options.inplace:
        print >>sys.stderr, "Using both -i/--inplace and -o/--output is not possible."
        sys.exit(1)

    for filename in args:
        try:
            tree=etree.parse(filename)
        except (IOError, etree.XMLSyntaxError), e:
            msg=str(e)
            if len(args)>1:
                print >> sys.stderr, "%s: %s" % (filename, msg)
            else:
                print >> sys.stderr, msg
            sys.exit(2)
        root=tree.getroot()
        if "i18n" not in root.nsmap:
            newroot=etree.Element(root.tag,
                    nsmap=dict(i18n=NSMAP["i18n"], **root.nsmap))
            newroot[:]=root[:]
            root=newroot

        counter=Counter()
        for el in tree.iter():
            handleContent(el, counter)
            handleAttributes(el, counter)

        if options.inplace:
            tmpname="%s~" % filename
            tree.write(tmpname, encoding="utf-8")
            os.rename(tmpname, filename)
        else:
            if options.output:
                output=open(options.output, "w")
            else:
                output=sys.stdout

            if tree.docinfo.doctype:
                output.write(tree.docinfo.doctype)
                output.write("\n")
            output.write(etree.tostring(root))
            output.write("\n")


if __name__=="__main__":
    main()
