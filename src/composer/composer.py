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

import json
import os
import sys
import openwhisk
import inspect
import re

from composer import conductor
from composer import __version__

# standard combinators

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
    'let': {'args': [{'_': 'declarations', 'type': 'dict'}], 'components': True, 'since': '0.4.0'},
    'mask': {'components': True, 'since': '0.4.0'},
    'action': {'args': [{'_': 'name', 'type': 'string'}, {'_': 'action', 'type': 'dict', 'optional': True}], 'since': '0.4.0'},
    'composition': {'args': [{'_': 'name', 'type': 'string'}, {'_': 'composition'}], 'since': '0.4.0'},
    'repeat': {'args': [{'_': 'count', 'type': 'int'}], 'components': True, 'since': '0.4.0'},
    'retry': {'args': [{'_': 'count', 'type': 'int'}], 'components': True, 'since': '0.4.0'},
    'value': {'args': [{'_': 'value', 'type': 'value'}], 'since': '0.4.0'},
    'literal': {'args': [{'_': 'value', 'type': 'value'}], 'since': '0.4.0'},
    'function': {'args': [{'_': 'function', 'type': 'dict'}], 'since': '0.4.0'}
}

class ComposerError(Exception):
    def __init__(self, message, *arguments):
       self.message = message
       self.argument = arguments

def serialize(obj):
    return obj.__dict__

class Composition:
    def __init__(self, obj):
        items = obj.items() if isinstance(obj, dict) else obj.__dict__.items() if isinstance(obj, Composition) else None
        if items is None:
            raise ComposerError('Invalid argument', obj)
        for k, v in items:
            setattr(self, k, v)

    def __str__(self):
        return json.dumps(self.__dict__, default=serialize, ensure_ascii=True)

    def visit(self, f):
        ''' apply f to all fields of type composition '''

        combinator = combinators[getattr(self, 'type')]
        if 'components' in combinator:
            self.components = tuple(map(lambda c: f(c, None), self.components))

        if 'args' in combinator:
            for arg in combinator['args']:
                if 'type' not in arg:
                    setattr(self, arg['_'], f(getattr(self, arg['_']), arg['_']))


def get_value(env, args):
   return env['value']

def set_params(env, args):
   env['params'] = args

def get_params(env, args):
   return env['params']

def retain_result(env, args):
   return { 'params': env['params'], 'result': args }

def dec_count(env, args):
    c = env['count']
    env['count'] -= 1
    return c > 0

# def nest_params(env, args):


class Compiler:

    def empty(self):
        return self._compose('empty', ())

    def literal(self, value):
        return self._compose('literal', (value,))

    def seq(self, *arguments):
        return self._compose('seq', arguments)

    def sequence(self, *arguments):
        return self._compose('sequence', arguments)

    def action(self, name, action=None):
        return self._compose('action', (name, action))

    def when(self, test, consequent, alternate=None):
        return self._compose('if', (test, consequent, alternate))

    def when_nosave(self, test, consequent, alternate=None):
        return self._compose('if_nosave', (test, consequent, alternate))

    def loop(self, test, body):
        return self._compose('while', (test, body))

    def loop_nosave(self, test, body):
        return self._compose('while_nosave', (test, body))

    def ensure(self, body, finalizer):
        return self._compose('finally', (body, finalizer))

    def mask(self, *arguments):
        return self._compose('mask', arguments)

    def let(self, declarations, *arguments):
        return self._compose('let', (declarations, *arguments))

    def task(self, task):
        '''detect task type and create corresponding composition object'''
        if task is None:
            return self.empty()

        if isinstance(task, Composition):
            return task

        if callable(task):
            return self.function(task)

        if isinstance(task, str): # python3 only
            return self.action(task)

        raise ComposerError('Invalid argument', task)

    def function(self, fun):
        ''' function combinator: stringify lambda code '''
        if callable(fun):
            try:
                fun = inspect.getsource(fun)
            except OSError:
                raise ComposerError('Invalid argument', fun)

        if isinstance(fun, str):
            # standardize function name
            fun = re.sub(r'def\s+([a-zA-Z_][a-zA-Z_0-9]*)\s*\(', 'def func(', fun)

            fun = { 'kind': 'python:3', 'code': fun }

        if not isinstance(fun, dict) or fun is None:
            raise ComposerError('Invalid argument', fun)

        return Composition({'type':'function', 'function':{ 'exec': fun }})

    # lowering

    def _empty(self, composition):
        return self.sequence()

    def _seq(self, composition):
        return self.sequence(*composition.components)

    def _value(self, composition):
        return self._literal(composition)

    def _literal(self, composition):
        return self.let({ 'value': composition.value }, get_value)

    def _retain(self, composition):
        return self.let(
            { 'params': None },
            set_params,
            self.mask(*composition.components),
            retain_result)

    def _retain_catch(self, composition):
        # return this.seq(
        #     this.retain(
        #         this.finally(
        #             this.seq(...composition.components),
        #             result => ({ result }))),
        #     ({ params, result }) => ({ params, result: result.result }))
        raise ComposerError('Not Implemented')

    def _if(self, composition):
        return self.let(
            { 'params': None },
            set_params,
            self.when_nosave(
                self.mask(composition.test),
                self.seq(get_params, self.mask(composition.consequent)),
                self.seq(get_params, self.mask(composition.alternate))))

    def _while(self, composition):
        return self.let(
            { 'params': None },
            set_params,
            self.loop_nosave(
                self.mask(composition.test),
                self.seq(get_params, self.mask(composition.body), set_params)),
            get_params)

    def _dowhile(self, composition):
        # return this.let(
        #     { params: null },
        #     args => { params = args },
        #     this.dowhile_nosave(
        #         this.seq(() => params, this.mask(composition.body), args => { params = args }),
        #         this.mask(composition.test)),
        #     () => params)
        raise ComposerError('Not Implemented')

    def _repeat(self, composition):
        return self.let(
            { 'count': composition.count },
            self.loop(
                dec_count,
                self.mask(self.seq(*composition.components))))

    def _retry(self, composition):
        # return self.let(
        #     { 'count': composition.count },
        #     params => ({ params }),
        #     this.dowhile(
        #         this.finally(({ params }) => params, this.mask(this.retain_catch(...composition.components))),
        #         ({ result }) => result.error !== undefined && count-- > 0),
        #     ({ result }) => result)
        raise ComposerError('Not Implemented')

    def _compose(self, type_, arguments):
        combinator = combinators[type_]
        skip = len(combinator['args']) if 'args' in combinator else 0
        composition = Composition({'type':type_})

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
                if type(argument).__name__ != arg['type']:
                    raise ComposerError('Invalid argument', argument)

                setattr(composition, arg['_'], argument)

        if 'components' in combinator:
            setattr(composition, 'components', tuple(map(lambda obj: self.task(obj), arguments[skip:])))

        return composition

    def deserialize(self, composition):
        ''' recursively deserialize composition '''

        composition = Composition(composition)
        composition.visit(lambda composition, name: self.deserialize(composition))
        return composition

    def label(self, composition):
        ''' label combinators with the json path '''

        if not isinstance(composition, Composition):
            raise ComposerError('Invalid argument', composition)

        def label(path):

            def labeler(composition, name, array=None) :
                nonlocal path
                composition = Composition(composition)
                segment = ''
                if name is not None:
                    if array is not None:
                        segment = '['+name+']'
                    else:
                        segment = '.'+name

                composition.path = path + segment

                # label nested combinators
                composition.visit(label(composition.path))
                return composition

            return labeler

        return label('')(composition, None, None)


    def lower(self, composition, combinators = []):
        ''' recursively label and lower combinators to the desired set of combinators (including primitive combinators) '''
        if not isinstance(composition, Composition):
            raise ComposerError('Invalid argument', composition)

        if combinators is False:
            return composition # no lowering

        if combinators is True or combinators == '':
            combinators = [] # maximal lowering

        # no semver in openwhisk python runtime
        # if isinstance(combinators, str): # lower to combinators of specific composer version
        #     combinators = Object.keys(this.combinators).filter(key => semver.gte(combinators, this.combinators[key].since))

        def lower(composition, name):
            composition =  Composition(composition) # copy
            # repeatedly lower root combinator

            while composition.type not in combinators and hasattr(self, '_'+composition.type):
                path = composition.path if hasattr(composition, 'path') else None
                composition = getattr(self, '_'+composition.type)(composition)
                if path is not None:
                    composition.path = path

            # lower nested combinators
            composition.visit(lower)
            return composition

        return lower(composition, None)

def parse_action_name(name):
    '''
      Parses a (possibly fully qualified) resource name and validates it. If it's not a fully qualified name,
      then attempts to qualify it.

      Examples string to namespace, [package/]action name
        foo => /_/foo
        pkg/foo => /_/pkg/foo
        /ns/foo => /ns/foo
        /ns/pkg/foo => /ns/pkg/foo
    '''
    if not isinstance(name, str):
        raise ComposerError('Name is not valid')
    name = name.strip()
    if len(name) == 0:
        raise ComposerError('Name is not specified')

    delimiter = '/'
    parts = name.split(delimiter)
    n = len(parts)
    leadingSlash = name[0] == delimiter if len(name) > 0 else False
    # no more than /ns/p/a
    if n < 1 or n > 4 or (leadingSlash and n == 2) or (not leadingSlash and n == 4):
        raise ComposerError('Name is not valid')

    # skip leading slash, all parts must be non empty (could tighten this check to match EntityName regex)
    for part in parts[1:]:
        if len(part.strip()) == 0:
            raise ComposerError('Name is not valid')

    newName = delimiter.join(parts)
    if leadingSlash:
        return newName
    elif n < 3:
        return delimiter+'_'+delimiter+newName
    else:
        return delimiter+newName

class Compositions:
    ''' management class for compositions '''
    def __init__(self, wsk, composer):
        self.actions = wsk.actions
        self.composer = composer

    def deploy(self, composition, combinators=[]):
        if not isinstance(composition, Composition):
            raise ComposerError('Invalid argument', composition)

        if composition.type != 'composition':
            raise ComposerError('Cannot deploy anonymous composition')

        obj = self.composer.encode(composition, combinators)

        if 'actions' in obj:
            for action in obj['actions']:
                try:
                    self.actions.delete(action)
                except Exception:
                    pass
                self.actions.update(action)

class Composer(Compiler):
    def action(self, name, options = {}):
        ''' enhanced action combinator: mangle name, capture code '''
        name = parse_action_name(name) # raise ComposerError if name is not valid
        exec = None
        if hasattr(options, 'sequence'): # native sequence
            exec = { 'kind': 'sequence', 'components': tuple(map(parse_action_name, options['sequence'])) }

        if hasattr(options, 'filename') and isinstance(options['filename'], str): # read action code from file
            raise ComposerError('read from file not implemented')
            # exec = fs.readFileSync(options.filename, { encoding: 'utf8' })

        # if (typeof options.action === 'function') { // capture function
        #     exec = `const main = ${options.action}`
        #     if (exec.indexOf('[native code]') !== -1) throw new ComposerError('Cannot capture native function', options.action)
        # }

        if hasattr(options, 'action') and (isinstance(options['action'], str) or isinstance(options['action'],  dict)):
            exec = options['action']

        if isinstance(exec, str):
            exec = { 'kind': 'python:3', 'code': exec }

        return Composition({'type':'action', 'exec':exec, 'name':name})

    def openwhisk(self, options):
        ''' return enhanced openwhisk client capable of deploying compositions '''
        # try to extract apihost and key first from whisk property file file and then from os.environ

        wskpropsPath = os.environ['WSK_CONFIG_FILE'] if 'WSK_CONFIG_FILE' in os.environ else os.path.expanduser('~/.wskprops')
        with open(wskpropsPath) as f:
            lines = f.readlines()

        options = dict(options)

        for line in lines:
            parts = line.strip().split('=')
            if len(parts) == 2:
                if parts[0] == 'APIHOST':
                    options['apihost'] = parts[1]
                elif parts[0] == 'AUTH':
                    options['api_key'] = parts[1]


        if '__OW_API_HOST' in os.environ:
            options['apihost'] = os.environ['__OW_API_HOST']

        if '__OW_API_KEY' in os.environ:
             options['api_key'] = os.environ['__OW_API_KEY']

        wsk = openwhisk.Client(options)
        wsk.compositions = Compositions(wsk, self)
        return wsk


    def composition(self, name, composition):
        ''' enhanced composition combinator: mangle name '''

        if not isinstance(name, str):
            raise ComposerError('Invalid argument', name)

        name = parse_action_name(name)
        return Composition({'type':'composition', 'name':name, 'composition': self.task(composition)})


    def encode(self, composition, localcombinators=[]):
        ''' recursively encode composition into { composition, actions }
            by encoding nested compositions into actions and extracting nested action definitions '''

        if not isinstance(composition, Composition):
            raise ComposerError('Invalid argument', composition)

        composition = self.lower(composition, localcombinators)

        actions = []

        def escape(str):
            return re.sub(r'(\n|\t|\r|\f|\v|\\|\')', lambda m:{'\n':'\\n','\t':'\\t','\r':'\\r','^\f':'\\f','\v':'\\v','\\':'\\\\','\'':'\\\''}[m.group()], str)

        def encode(composition, name):
            composition = Composition(composition)
            composition.visit(encode)
            if composition.type == 'composition':
                code = '# generated by composer v'+__version__+'\n\nimport functools\nimport json\nimport inspect\nimport re'
                code += '\n\n' + inspect.getsource(ComposerError)
                code += '\ncomposition=json.loads(\''+escape(str(encode(composition.composition, '')))+'\')'

                src = inspect.getsource(conductor)
                code += '\n'+ src[src.index('def conductor'):]
                code += '\ncombinators ='+ str(combinators)
                code += '\n' + inspect.getsource(serialize)
                code += '\n' + inspect.getsource(Composition)
                code += '\n' + inspect.getsource(get_value)
                code += '\n' + inspect.getsource(get_params)
                code += '\n' + inspect.getsource(set_params)
                code += '\n' + inspect.getsource(retain_result)
                code += '\n' + inspect.getsource(Compiler)
                code += 'def main(args):'
                code += '\n    return conductor()(args)'

                composition.action = { 'exec': { 'kind': 'python:3', 'code':code }, 'annotations': [{ 'key': 'conductor', 'value': str(composition.composition) }, { 'key': 'composer', 'value': __version__ }] }

                del composition.composition
                composition.type = 'action'

            if composition.type == 'action' and hasattr(composition, 'action'):
                actions.append({ 'name': composition.name, 'action': composition.action, 'serializer': serialize })
                del composition.action

            return composition


        composition = encode(composition, None)
        return { 'composition': composition, 'actions': actions }
