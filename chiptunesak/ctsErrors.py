'''
Exceptions for chiptune-sak library
'''


class ChiptuneSAKException(Exception):
    """
    Generic base class for Chiptune-SAK exceptions
    """
    pass


class ChiptuneSAKTypeError(Exception):
    """
    Type error
    """
    pass


class ChiptuneSAKIOError(Exception):
    """
    IO error
    """
    pass


class ChiptuneSAKValueError(ChiptuneSAKException, ValueError):
    """
    Value error
    """
    pass


class ChiptuneSAKQuantizationError(ChiptuneSAKException):
    """
    Quantization error
    """
    pass


class ChiptuneSAKPolyphonyError(ChiptuneSAKException):
    """
    Polyphony error
    """
    pass


class ChiptuneSAKContentError(ChiptuneSAKException):
    """
    Content error (such as no measures or no tracks)
    """
    pass


class ChiptuneSAKNotImplemented(ChiptuneSAKException):
    """
    Not implemented error
    """
    pass
