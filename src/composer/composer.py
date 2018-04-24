# Copyright 2018 IBM Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# standard combinators
import json

combinators = {
    'empty': {'since': '0.4.0'},
    'seq': {'components': True, 'since': '0.4.0'},
    'sequence': {'components': True, 'since': '0.4.0'},
    'if': {'args': [{'_': 'test'}, {'_': 'consequent'}, {'_': 'alternate', 'optional': True}], 'since': '0.4.0'},
    'if_nosave': {'args': [{'_': 'test'}, {'_': 'consequent'}, {'_': 'alternate', 'optional': True}], 'since': '0.4.0'},
    'while': {'args': [{'_': 'test'}, {'_': 'body'}], 'since': '0.4.0'},
    'while_nosave': {'args': [{'_': 'test'}, {'_': 'body'}], 'since': '0.4.0'},
    'dowhile': {'args': [{'_': 'body'}, {'_': 'test'}], 'since': '0.4.0'},
    'dowhile_nosave': {'args': [{'_': 'body'}, {'_': 'test'}], 'since': '0.4.0'},
    'try': {'args': [{'_': 'body'}, {'_': 'handler'}], 'since': '0.4.0'},
    'finally': {'args': [{'_': 'body'}, {'_': 'finalizer'}], 'since': '0.4.0'},
    'retain': {'components': True, 'since': '0.4.0'},
    'retain_catch': {'components': True, 'since': '0.4.0'},
    'let': {'args': [{'_': 'declarations', 'type': 'object'}], 'components': True, 'since': '0.4.0'},
    'mask': {'components': True, 'since': '0.4.0'},
    'action': {'args': [{'_': 'name', 'type': 'string'}, {'_': 'action', 'type': 'object', 'optional': True}], 'since': '0.4.0'},
    'composition': {'args': [{'_': 'name', 'type': 'string'}, {'_': 'composition'}], 'since': '0.4.0'},
    'repeat': {'args': [{'_': 'count', 'type': 'number'}], 'components': True, 'since': '0.4.0'},
    'retry': {'args': [{'_': 'count', 'type': 'number'}], 'components': True, 'since': '0.4.0'},
    'value': {'args': [{'_': 'value', 'type': 'value'}], 'since': '0.4.0'},
    'literal': {'args': [{'_': 'value', 'type': 'value'}], 'since': '0.4.0'},
    'function': {'args': [{'_': 'function', 'type': 'object'}], 'since': '0.4.0'}
}

class ComposerError(Exception):
    def __init__(self, message, *arguments):
       self.message = message
       self.argument = arguments


def serialize(obj):
    return obj.__dict__

class Composition:
    def __init__(self, type):
        self.type = type

    def __str__(self):
        return json.dumps(self.__dict__, indent=2, default=serialize)

def empty():
    return _compose('empty', ())

def seq(*arguments):
    return _compose('seq', arguments)

def sequence(*arguments):
    return _compose('sequence', arguments)

def action(*arguments):
    return _compose('action', arguments)

def task(task):
    """detect task type and create corresponding composition object"""
    if task is None:
        return empty()

    if isinstance(task, Composition):
        return task

    # if (typeof task === 'function') return this.function(task)

    if isinstance(task, str): # python3 only
        return action(task)

    raise ComposerError('Invalid argument', task)

def _compose(type_, arguments):
    combinator = combinators[type_]
    skip = len(combinator['args']) if 'args' in combinator else 0
    if 'components' not in combinator and len(arguments) > skip:
        raise ComposerError('Too many arguments')

    composition = Composition(type_)

    # process named arguments
    for i in range(skip):
        arg = combinator['args'][i]
        argument = arguments[i] if len(arguments) > i else None

        if 'type' not in arg:
            setattr(composition, arg['_'], task(argument))
        elif arg['type'] == 'value':
            # if (typeof argument === 'function') throw new ComposerError('Invalid argument', argument)
            setattr(composition, arg['_'], argument)
        else:
            setattr(composition, arg['_'], argument)

    if 'components' in combinator:
        setattr(composition, 'components', tuple(map(lambda obj: task(obj), arguments)))


    return composition