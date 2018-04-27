__version__ = '0.1.0'

from .composer import Composer, ComposerError, parse_action_name

_composer = Composer()

def composition(name, task):
    return _composer.composition(name, task)

def seq(*arguments):
    return _composer.sequence(*arguments)

def sequence(*arguments):
    return _composer.sequence(*arguments)

def literal(value):
    return _composer.literal(value)

def action(name, action=None):
    return _composer.action(name, action)

def task(task):
    return _composer.task(task)

def function(value):
    return _composer.function(value)

def openwhisk(options):
    return _composer.openwhisk(options)
