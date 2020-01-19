'''
Exceptions for chiptune-sak library
'''

class ChiptuneSAKException(Exception):
    """
    Generic base class for Chiptune-SAK exceptions
    """
    pass

class ChiptuneSAKValueError(ChiptuneSAKException, ValueError):
    """
    Value error
    """
    pass
