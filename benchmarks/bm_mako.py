#!/usr/bin/python

"""
Benchmark for test the performance of Mako templates engine.
Includes:
    -two template inherences
    -HTML escaping, XML escaping, URL escaping, whitespace trimming
    -function defitions and calls
    -forloops
"""

__author__ = "virhilo@gmail.com (Lukasz Fidosz)"

# Python imports
import os
import sys
import optparse
import time

# Local imports
import util

def relative(*args):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), *args)

sys.path.insert(0, relative('..', 'lib'))

# Mako imports
from mako.template import Template
from mako.lookup import TemplateLookup


LOREM_IPSUM = """Quisque lobortis hendrerit posuere. Curabitur
aliquet consequat sapien molestie pretium. Nunc adipiscing luc
tus mi, viverra porttitor lorem vulputate et. Ut at purus sem,
sed tincidunt ante. Vestibulum ante ipsum primis in faucibus 
orci luctus et ultrices posuere cubilia Curae; Praesent pulvinar
sodales justo at congue. Praesent aliquet facilisis nisl a
molestie. Sed tempus nisl ut augue eleifend tincidunt. Sed a
lacinia nulla. Cras tortor est, mollis et consequat at,
vulputate et orci. Nulla sollicitudin"""

BASE_TEMPLATE = """
<%def name="render_table(table)">
    <table>
    % for row in table:
        <tr>
        % for col in row:
            <td>${col|h}</td>
        % endfor
        </tr>
    % endfor
    </table>
</%def>
<%def name="img(src, alt)">
    <img src="${src|u}" alt="${alt}" />
</%def>
<html>
    <head><title>${title|h,trim}</title></head>
    <body>
        ${next.body()}
    </body>
<html>
"""

PAGE_TEMPLATE = """
<%inherit file="base.mako"/>
<table>
    % for row in table:
        <tr>
            % for col in row:
                <td>${col}</td>
            % endfor
        </tr>
    % endfor
</table>
% for nr in xrange(img_count):
    ${parent.img('/foo/bar/baz.png', 'no image :o')}
% endfor
${next.body()}
% for nr in paragraphs:
    <p>${lorem|x}</p>
% endfor
${parent.render_table(table)}
"""

CONTENT_TEMPLATE = """
<%inherit file="page.mako"/>
<%def name="fun1()">
    <span>fun1</span>
</%def>
<%def name="fun2()">
    <span>fun2</span>
</%def>
<%def name="fun3()">
    <span>foo3</span>
</%def>
<%def name="fun4()">
    <span>foo4</span>
</%def>
<%def name="fun5()">
    <span>foo5</span>
</%def>
<%def name="fun6()">
    <span>foo6</span>
</%def>
<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit.
Nam laoreet justo in velit faucibus lobortis. Sed dictum sagittis
volutpat. Sed adipiscing vestibulum consequat. Nullam laoreet, ante
nec pretium varius, libero arcu porttitor orci, id cursus odio nibh
nec leo. Vestibulum dapibus pellentesque purus, sed bibendum tortor
laoreet id. Praesent quis sodales ipsum. Fusce ut ligula sed diam
pretium sagittis vel at ipsum. Nulla sagittis sem quam, et volutpat
velit. Fusce dapibus ligula quis lectus ultricies tempor. Pellente</p>
${fun1()}
${fun2()}
${fun3()}
${fun4()}
${fun5()}
${fun6()}
"""


def test_mako(count):

    lookup = TemplateLookup()
    lookup.put_string('base.mako', BASE_TEMPLATE)
    lookup.put_string('page.mako', PAGE_TEMPLATE)

    template = Template(CONTENT_TEMPLATE, lookup=lookup)
    
    table = [xrange(150) for i in xrange(150)]
    paragraphs = xrange(50)
    title = 'Hello world!'

    times = []
    for i in range(count):
        t0 = time.time()
        data = template.render(table=table, paragraphs=paragraphs,
                               lorem=LOREM_IPSUM, title=title,
                               img_count=50)
        t1 = time.time()
        times.append(t1-t0)
    return times

if __name__ == "__main__":
    parser = optparse.OptionParser(
        usage="%prog [options]",
        description=("Test the performance of Mako templates."))
    util.add_standard_options_to(parser)
    (options, args) = parser.parse_args()

    util.run_benchmark(options, options.num_runs, test_mako)
