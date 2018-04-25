__version__ = '0.1.0'

from .composer import Compiler, ComposerError, parse_action_name

_composer = Compiler()

def sequence(*arguments):
    return _composer.sequence(*arguments)

def literal(value):
    return _composer.literal(value)