__version__ = '0.1.0'

from .composer import Composer, ComposerError, parse_action_name

_composer = Composer()


def composition(name, task):
    return _composer.composition(name, task)

def sequence(*arguments):
    return _composer.sequence(*arguments)

def literal(value):
    return _composer.literal(value)

def function(value):
    return _composer.function(value)

def openwhisk(options):
    return _composer.openwhisk(options)
