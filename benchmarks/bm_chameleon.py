#!/usr/bin/python2

"""
Benchmark for test the performance of Chameleon page template engine.
"""

__author__ = "mborch@gmail.com (Malthe Borch)"

# Python imports
import os
import sys
import optparse
import time

# Local imports
import util


def relative(*args):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), *args)

sys.path.insert(0, relative('..', 'src'))

# Chameleon imports
from chameleon import PageTemplate


LOREM_IPSUM = """Quisque lobortis hendrerit posuere. Curabitur
aliquet consequat sapien molestie pretium. Nunc adipiscing luc
tus mi, viverra porttitor lorem vulputate et. Ut at purus sem,
sed tincidunt ante. Vestibulum ante ipsum primis in faucibus
orci luctus et ultrices posuere cubilia Curae; Praesent pulvinar
sodales justo at congue. Praesent aliquet facilisis nisl a
molestie. Sed tempus nisl ut augue eleifend tincidunt. Sed a
lacinia nulla. Cras tortor est, mollis et consequat at,
vulputate et orci. Nulla sollicitudin"""

BASE_TEMPLATE = '''
<tal:macros condition="False">
    <table metal:define-macro="table">
       <tr tal:repeat="row table">
          <td tal:repeat="col row">${col}</td>
       </tr>
    </table>
    <img metal:define-macro="img" src="${src}" alt="${alt}" />
</tal:macros>
<html metal:define-macro="master">
    <head><title>${title.strip()}</title></head>
    <body metal:define-slot="body" />
</html>
'''

PAGE_TEMPLATE = '''
<html metal:define-macro="master" metal:extend-macro="base.macros['master']">
<body metal:fill-slot="body">
<table metal:use-macro="base.macros['table']" />
images:
<tal:images repeat="nr xrange(img_count)">
    <img tal:define="src '/foo/bar/baz.png';
                     alt 'no image :o'"
         metal:use-macro="base.macros['img']" />
</tal:images>
<metal:body define-slot="body" />
<p tal:repeat="nr paragraphs">${lorem}</p>
<table metal:use-macro="base.macros['table']" />
</body>
</html>
'''

CONTENT_TEMPLATE = '''
<html metal:use-macro="page.macros['master']">
<span metal:define-macro="fun1">fun1</span>
<span metal:define-macro="fun2">fun2</span>
<span metal:define-macro="fun3">fun3</span>
<span metal:define-macro="fun4">fun4</span>
<span metal:define-macro="fun5">fun5</span>
<span metal:define-macro="fun6">fun6</span>
<body metal:fill-slot="body">
<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit.
Nam laoreet justo in velit faucibus lobortis. Sed dictum sagittis
volutpat. Sed adipiscing vestibulum consequat. Nullam laoreet, ante
nec pretium varius, libero arcu porttitor orci, id cursus odio nibh
nec leo. Vestibulum dapibus pellentesque purus, sed bibendum tortor
laoreet id. Praesent quis sodales ipsum. Fusce ut ligula sed diam
pretium sagittis vel at ipsum. Nulla sagittis sem quam, et volutpat
velit. Fusce dapibus ligula quis lectus ultricies tempor. Pellente</p>
<span metal:use-macro="template.macros['fun1']" />
<span metal:use-macro="template.macros['fun2']" />
<span metal:use-macro="template.macros['fun3']" />
<span metal:use-macro="template.macros['fun4']" />
<span metal:use-macro="template.macros['fun5']" />
<span metal:use-macro="template.macros['fun6']" />
</body>
</html>
'''


def test_mako(count):
    template = PageTemplate(CONTENT_TEMPLATE)
    base = PageTemplate(BASE_TEMPLATE)
    page = PageTemplate(PAGE_TEMPLATE)

    table = [xrange(150) for i in xrange(150)]
    paragraphs = xrange(50)
    title = 'Hello world!'

    times = []
    for i in range(count):
        t0 = time.time()
        data = template.render(
            table=table, paragraphs=paragraphs,
            lorem=LOREM_IPSUM, title=title,
            img_count=50,
            base=base,
            page=page,
            )
        t1 = time.time()
        times.append(t1-t0)
    return times

if __name__ == "__main__":
    parser = optparse.OptionParser(
        usage="%prog [options]",
        description=("Test the performance of Chameleon templates."))
    util.add_standard_options_to(parser)
    (options, args) = parser.parse_args()

    util.run_benchmark(options, options.num_runs, test_mako)
