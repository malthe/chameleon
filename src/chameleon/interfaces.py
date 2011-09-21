from zope.interface import Interface
from zope.interface import Attribute


class ITALExpressionErrorInfo(Interface):

    type = Attribute("type",
                     "The exception class.")

    value = Attribute("value",
                      "The exception instance.")

    lineno = Attribute("lineno",
                       "The line number the error occurred on in the source.")

    offset = Attribute("offset",
                       "The character offset at which the error occurred.")


class ITALIterator(Interface):  # pragma: no cover
    """A TAL iterator

    Not to be confused with a Python iterator.
    """

    def next():
        """Advance to the next value in the iteration, if possible

        Return a true value if it was possible to advance and return
        a false value otherwise.
        """


class ITALESIterator(ITALIterator):  # pragma: no cover
    """TAL Iterator provided by TALES

    Values of this iterator are assigned to items in the repeat namespace.

    For example, with a TAL statement like: tal:repeat="item items",
    an iterator will be assigned to "repeat/item".  The iterator
    provides a number of handy methods useful in writing TAL loops.

    The results are undefined of calling any of the methods except
    'length' before the first iteration.
    """

    def index():
        """Return the position (starting with "0") within the iteration
        """

    def number():
        """Return the position (starting with "1") within the iteration
        """

    def even():
        """Return whether the current position is even
        """

    def odd():
        """Return whether the current position is odd
        """

    def parity():
        """Return 'odd' or 'even' depending on the position's parity

        Useful for assigning CSS class names to table rows.
        """

    def start():
        """Return whether the current position is the first position
        """

    def end():
        """Return whether the current position is the last position
        """

    def letter():
        """Return the position (starting with "a") within the iteration
        """

    def Letter():
        """Return the position (starting with "A") within the iteration
        """

    def roman():
        """Return the position (starting with "i") within the iteration
        """

    def Roman():
        """Return the position (starting with "I") within the iteration
        """

    def item():
        """Return the item at the current position
        """

    def length():
        """Return the length of the sequence

        Note that this may fail if the TAL iterator was created on a Python
        iterator.
        """
