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

class Compiler:
    def literal(self, value):
        return self._compose('literal', (value,))

    def empty(self):
        return self._compose('empty', ())

    def seq(self, *arguments):
        return self._compose('seq', arguments)

    def sequence(self, *arguments):
        return self._compose('sequence', arguments)

    def action(self, *arguments):
        return self._compose('action', arguments)

    def task(self, task):
        """detect task type and create corresponding composition object"""
        if task is None:
            return self.empty()

        if isinstance(task, Composition):
            return task

        # if (typeof task === 'function') return this.function(task)

        if isinstance(task, str): # python3 only
            return self.action(task)

        raise ComposerError('Invalid argument', task)

    def _compose(self, type_, arguments):
        combinator = combinators[type_]
        skip = len(combinator['args']) if 'args' in combinator else 0
        if 'components' not in combinator and len(arguments) > skip:
            raise ComposerError('Too many arguments')

        composition = Composition(type_)

        # process declared arguments
        for i in range(skip):
            arg = combinator['args'][i]
            argument = arguments[i] if len(arguments) > i else None

            if 'type' not in arg:
                setattr(composition, arg['_'], self.task(argument))
            elif arg['type'] == 'value':
                if type(argument).__name__ == 'function':
                    raise ComposerError('Invalid argument', argument)
                setattr(composition, arg['_'], argument)
            else:
                setattr(composition, arg['_'], argument)

        if 'components' in combinator:
            setattr(composition, 'components', tuple(map(lambda obj: self.task(obj), arguments)))

        return composition

def parse_action_name(name):
    """
      Parses a (possibly fully qualified) resource name and validates it. If it's not a fully qualified name,
      then attempts to qualify it.

      Examples string to namespace, [package/]action name
        foo => /_/foo
        pkg/foo => /_/pkg/foo
        /ns/foo => /ns/foo
        /ns/pkg/foo => /ns/pkg/foo
    """
    name = name.strip()
    if len(name) == 0:
        raise ComposerError("Name is not specified")

    delimiter = '/'
    parts = name.split(delimiter)
    n = len(parts)
    leadingSlash = name[0] == delimiter if len(name) > 0 else False
    # no more than /ns/p/a
    if n < 1 or n > 4 or (leadingSlash and n == 2) or (not leadingSlash and n == 4):
        raise ComposerError("Name is not valid")

    # skip leading slash, all parts must be non empty (could tighten this check to match EntityName regex)
    for part in parts[1:]:
        if len(part.strip()) == 0:
            raise ComposerError("Name is not valid")

    newName = delimiter.join(parts)
    if leadingSlash:
        return newName
    elif n < 3:
        return delimiter+"_"+delimiter+newName
    else:
        return delimiter+newName

# class Composer(Compiler):
#   def action(self, name, options):
#     """ enhanced action combinator: mangle name, capture code """

#             name = parseActionName(name)
# let exec

# const composition = { type: 'action', name }
# if (exec) composition.action = { exec }
# return new Composition(composition)
