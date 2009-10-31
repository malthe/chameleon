def dt(name, pubid, system):
    return '<!DOCTYPE %s PUBLIC "%s" "%s">' % (name, pubid, system)

html_strict  = dt('HTML', '-//W3C//DTD HTML 4.01//EN',
                  'http://www.w3.org/TR/html4/strict.dtd')
html         = dt('HTML', '-//W3C//DTD HTML 4.01 Transitional//EN',
                  'http://www.w3.org/TR/html4/loose.dtd')
xhtml_strict = dt('html', '-//W3C//DTD XHTML 1.0 Strict//EN',
                  'http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd')
xhtml        = dt('html', '-//W3C//DTD XHTML 1.0 Transitional//EN',
                  'http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd')
html5        = '<!DOCTYPE html>'

no_doctype = ()

