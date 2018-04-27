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
import copy
import inspect
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
    def __init__(self, **kwargs):
        if kwargs is not None:
            for k, v in kwargs.items():
                setattr(self, k, v)

    def __str__(self):
        return json.dumps(self.__dict__, indent=2, default=serialize)

    def visit(self, f):
        ''' apply f to all fields of type composition '''

        combinator = combinators[getattr(self, 'type')]
        if 'components' in combinator:
            self.components = tuple(map(f, self.components))

        if 'args' in combinator:
            for arg in combinator['args']:
                if 'type' not in arg:
                    setattr(self, arg['_'], f(getattr(self, arg['_']), arg['_']))

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
        '''detect task type and create corresponding composition object'''
        if task is None:
            return self.empty()

        if isinstance(task, Composition):
            return task

        # if (typeof task === 'function') return this.function(task)

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
            fun = { 'kind': 'nodejs:default', 'code': fun }

        if not isinstance(fun, dict) or fun is None:
            raise ComposerError('Invalid argument', fun)

        return Composition(type='function', function={ 'exec': fun })

    def _compose(self, type_, arguments):
        combinator = combinators[type_]
        skip = len(combinator['args']) if 'args' in combinator else 0
        if 'components' not in combinator and len(arguments) > skip:
            raise ComposerError('Too many arguments')

        composition = Composition(type=type_)

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

    def lower(self, composition, combinators = []):
        ''' recursively label and lower combinators to the desired set of combinators (including primitive combinators) '''

        if not isinstance(composition, Composition):
            raise ComposerError('Invalid argument', composition)

        # TODO

        return composition


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

class Compositions:
    ''' management class for compositions '''
    def __init__(self, wsk, composer):
        self.actions = wsk.actions
        self.composer = composer

    def deploy(self, composition, combinators=None):
        if not isinstance(composition, Composition):
            raise ComposerError('Invalid argument', composition)

        if composition.type != 'composition':
            raise ComposerError('Cannot deploy anonymous composition')

        obj = self.composer.encode(composition, combinators)

        if 'actions' in obj:
            for action in obj['actions']:
                action['serializer'] = serialize
                self.actions.delete(action)
                self.actions.update(action)

class Composer(Compiler):

    # return enhanced openwhisk client capable of deploying compositions
    def openwhisk(self, options):
        ''' try to extract apihost and key first from whisk property file file and then from os.environ '''

        wskpropsPath = os.environ['WSK_CONFIG_FILE'] if 'WSK_CONFIG_FILE' in os.environ else os.path.expanduser('~/.wskprops')
        with open(wskpropsPath) as f:
            lines = f.readlines()

        for line in lines:
            parts = line.strip().split('=')
            if len(parts) == 2:
                if parts[0] == 'APIHOST':
                    apihost = parts[1]
                elif parts[0] == 'AUTH':
                    api_key = parts[1]


        if '__OW_API_HOST' in os.environ:
            apihost = os.environ['__OW_API_HOST']

        if '__OW_API_KEY' in os.environ:
             api_key = os.environ['__OW_API_KEY']

        wsk = openwhisk.Client({ 'apihost': apihost, 'api_key': api_key })
        wsk.compositions = Compositions(wsk, self)
        return wsk


    def composition(self, name, composition):
        ''' enhanced composition combinator: mangle name '''

        if not isinstance(name, str):
            raise ComposerError('Invalid argument', name)

        name = parse_action_name(name)
        return Composition(type='composition', name=name, composition= self.task(composition))


    def encode(self, composition, combinators=[]):
        ''' recursively encode composition into { composition, actions }
            by encoding nested compositions into actions and extracting nested action definitions '''

        if not isinstance(composition, Composition):
            raise ComposerError('Invalid argument', composition)

        composition = self.lower(composition, combinators)

        actions = []

        def encode(composition, name):
            composition = copy.copy(composition)
            composition.visit(encode)
            if composition.type == 'composition':
                code = '// generated by composer v'+__version__+'\n\nconst composition = '+str(encode(composition.composition, ''))+'\n\n// do not edit below this point\n\n'+_conductorCode+'('+_compilerCode+'())' # invoke conductor on composition
                composition.action = { 'exec': { 'kind': 'nodejs:default', 'code':code }, 'annotations': [{ 'key': 'conductor', 'value': 'todo' }, { 'key': 'composer', 'value': __version__ }] }
                del composition.composition
                composition.type = 'action'

            if composition.type == 'action' and hasattr(composition, 'action'):
                actions.append({ 'name': composition.name, 'action': composition.action })
                del composition.action

            return composition


        composition = encode(composition, None)
        return { 'composition': composition, 'actions': actions }


# Use Node js server-side code

_conductorCode = '''
const main=(function conductor({ Compiler }) {
    const compiler = new Compiler()

    this.require = require

    function chain(front, back) {
        front.slice(-1)[0].next = 1
        front.push(...back)
        return front
    }

    function sequence(components) {
        if (components.length === 0) return [{ type: 'empty' }]
        return components.map(compile).reduce(chain)
    }

    function compile(json) {
        const path = json.path
        switch (json.type) {
            case 'sequence':
                return chain([{ type: 'pass', path }], sequence(json.components))
            case 'action':
                return [{ type: 'action', name: json.name, path }]
            case 'function':
                return [{ type: 'function', exec: json.function.exec, path }]
            case 'finally':
                var body = compile(json.body)
                const finalizer = compile(json.finalizer)
                var fsm = [[{ type: 'try', path }], body, [{ type: 'exit' }], finalizer].reduce(chain)
                fsm[0].catch = fsm.length - finalizer.length
                return fsm
            case 'let':
                var body = sequence(json.components)
                return [[{ type: 'let', let: json.declarations, path }], body, [{ type: 'exit' }]].reduce(chain)
            case 'mask':
                var body = sequence(json.components)
                return [[{ type: 'let', let: null, path }], body, [{ type: 'exit' }]].reduce(chain)
            case 'try':
                var body = compile(json.body)
                const handler = chain(compile(json.handler), [{ type: 'pass' }])
                var fsm = [[{ type: 'try', path }], body, [{ type: 'exit' }]].reduce(chain)
                fsm[0].catch = fsm.length
                fsm.slice(-1)[0].next = handler.length
                fsm.push(...handler)
                return fsm
            case 'if_nosave':
                var consequent = compile(json.consequent)
                var alternate = chain(compile(json.alternate), [{ type: 'pass' }])
                var fsm = [[{ type: 'pass', path }], compile(json.test), [{ type: 'choice', then: 1, else: consequent.length + 1 }]].reduce(chain)
                consequent.slice(-1)[0].next = alternate.length
                fsm.push(...consequent)
                fsm.push(...alternate)
                return fsm
            case 'while_nosave':
                var consequent = compile(json.body)
                var alternate = [{ type: 'pass' }]
                var fsm = [[{ type: 'pass', path }], compile(json.test), [{ type: 'choice', then: 1, else: consequent.length + 1 }]].reduce(chain)
                consequent.slice(-1)[0].next = 1 - fsm.length - consequent.length
                fsm.push(...consequent)
                fsm.push(...alternate)
                return fsm
            case 'dowhile_nosave':
                var test = compile(json.test)
                var fsm = [[{ type: 'pass', path }], compile(json.body), test, [{ type: 'choice', then: 1, else: 2 }]].reduce(chain)
                fsm.slice(-1)[0].then = 1 - fsm.length
                fsm.slice(-1)[0].else = 1
                var alternate = [{ type: 'pass' }]
                fsm.push(...alternate)
                return fsm
        }
    }

    const fsm = compile(compiler.lower(compiler.label(compiler.deserialize(composition))))

    const isObject = obj => typeof obj === 'object' && obj !== null && !Array.isArray(obj)

    // encode error object
    const encodeError = error => ({
        code: typeof error.code === 'number' && error.code || 500,
        error: (typeof error.error === 'string' && error.error) || error.message || (typeof error === 'string' && error) || 'An internal error occurred'
    })

    // error status codes
    const badRequest = error => Promise.reject({ code: 400, error })
    const internalError = error => Promise.reject(encodeError(error))

    return params => Promise.resolve().then(() => invoke(params)).catch(internalError)

    // do invocation
    function invoke(params) {
        // initial state and stack
        let state = 0
        let stack = []

        // restore state and stack when resuming
        if (params.$resume !== undefined) {
            if (!isObject(params.$resume)) return badRequest('The type of optional $resume parameter must be object')
            state = params.$resume.state
            stack = params.$resume.stack
            if (state !== undefined && typeof state !== 'number') return badRequest('The type of optional $resume.state parameter must be number')
            if (!Array.isArray(stack)) return badRequest('The type of $resume.stack must be an array')
            delete params.$resume
            inspect() // handle error objects when resuming
        }

        // wrap params if not a dictionary, branch to error handler if error
        function inspect() {
            if (!isObject(params)) params = { value: params }
            if (params.error !== undefined) {
                params = { error: params.error } // discard all fields but the error field
                state = undefined // abort unless there is a handler in the stack
                while (stack.length > 0) {
                    if (typeof (state = stack.shift().catch) === 'number') break
                }
            }
        }

        // run function f on current stack
        function run(f) {
            // handle let/mask pairs
            const view = []
            let n = 0
            for (let frame of stack) {
                if (frame.let === null) {
                    n++
                } else if (frame.let !== undefined) {
                    if (n === 0) {
                        view.push(frame)
                    } else {
                        n--
                    }
                }
            }

            // update value of topmost matching symbol on stack if any
            function set(symbol, value) {
                const element = view.find(element => element.let !== undefined && element.let[symbol] !== undefined)
                if (element !== undefined) element.let[symbol] = JSON.parse(JSON.stringify(value))
            }

            // collapse stack for invocation
            const env = view.reduceRight((acc, cur) => typeof cur.let === 'object' ? Object.assign(acc, cur.let) : acc, {})
            let main = '(function(){try{'
            for (const name in env) main += `var ${name}=arguments[1]['${name}'];`
            main += `return eval((${f}))(arguments[0])}finally{`
            for (const name in env) main += `arguments[1]['${name}']=${name};`
            main += '}})'
            try {
                return (1, eval)(main)(params, env)
            } finally {
                for (const name in env) set(name, env[name])
            }
        }

        while (true) {
            // final state, return composition result
            if (state === undefined) {
                console.log(`Entering final state`)
                console.log(JSON.stringify(params))
                if (params.error) return params; else return { params }
            }

            // process one state
            const json = fsm[state] // json definition for current state
            if (json.path !== undefined) console.log(`Entering composition${json.path}`)
            const current = state
            state = json.next === undefined ? undefined : current + json.next // default next state
            switch (json.type) {
                case 'choice':
                    state = current + (params.value ? json.then : json.else)
                    break
                case 'try':
                    stack.unshift({ catch: current + json.catch })
                    break
                case 'let':
                    stack.unshift({ let: JSON.parse(JSON.stringify(json.let)) })
                    break
                case 'exit':
                    if (stack.length === 0) return internalError(`State ${current} attempted to pop from an empty stack`)
                    stack.shift()
                    break
                case 'action':
                    return { action: json.name, params, state: { $resume: { state, stack } } } // invoke continuation
                    break
                case 'function':
                    let result
                    try {
                        result = run(json.exec.code)
                    } catch (error) {
                        console.error(error)
                        result = { error: `An exception was caught at state ${current} (see log for details)` }
                    }
                    if (typeof result === 'function') result = { error: `State ${current} evaluated to a function` }
                    // if a function has only side effects and no return value, return params
                    params = JSON.parse(JSON.stringify(result === undefined ? params : result))
                    inspect()
                    break
                case 'empty':
                    inspect()
                    break
                case 'pass':
                    break
                default:
                    return internalError(`State ${current} has an unknown type`)
            }
        }
    }
})
'''

_compilerCode = '''
function compiler() {
    const util = require('util')
    const semver = require('semver')

    // standard combinators
    const combinators = {
        empty: { since: '0.4.0' },
        seq: { components: true, since: '0.4.0' },
        sequence: { components: true, since: '0.4.0' },
        if: { args: [{ _: 'test' }, { _: 'consequent' }, { _: 'alternate', optional: true }], since: '0.4.0' },
        if_nosave: { args: [{ _: 'test' }, { _: 'consequent' }, { _: 'alternate', optional: true }], since: '0.4.0' },
        while: { args: [{ _: 'test' }, { _: 'body' }], since: '0.4.0' },
        while_nosave: { args: [{ _: 'test' }, { _: 'body' }], since: '0.4.0' },
        dowhile: { args: [{ _: 'body' }, { _: 'test' }], since: '0.4.0' },
        dowhile_nosave: { args: [{ _: 'body' }, { _: 'test' }], since: '0.4.0' },
        try: { args: [{ _: 'body' }, { _: 'handler' }], since: '0.4.0' },
        finally: { args: [{ _: 'body' }, { _: 'finalizer' }], since: '0.4.0' },
        retain: { components: true, since: '0.4.0' },
        retain_catch: { components: true, since: '0.4.0' },
        let: { args: [{ _: 'declarations', type: 'object' }], components: true, since: '0.4.0' },
        mask: { components: true, since: '0.4.0' },
        action: { args: [{ _: 'name', type: 'string' }, { _: 'action', type: 'object', optional: true }], since: '0.4.0' },
        composition: { args: [{ _: 'name', type: 'string' }, { _: 'composition' }], since: '0.4.0' },
        repeat: { args: [{ _: 'count', type: 'number' }], components: true, since: '0.4.0' },
        retry: { args: [{ _: 'count', type: 'number' }], components: true, since: '0.4.0' },
        value: { args: [{ _: 'value', type: 'value' }], since: '0.4.0' },
        literal: { args: [{ _: 'value', type: 'value' }], since: '0.4.0' },
        function: { args: [{ _: 'function', type: 'object' }], since: '0.4.0' }
    }

    // composer error class
    class ComposerError extends Error {
        constructor(message, argument) {
            super(message + (argument !== undefined ? '\\nArgument: ' + util.inspect(argument) : ''))
        }
    }

    // composition class
    class Composition {
        // weaker instanceof to tolerate multiple instances of this class
        static [Symbol.hasInstance](instance) {
            return instance.constructor && instance.constructor.name === Composition.name
        }

        // construct a composition object with the specified fields
        constructor(composition) {
            return Object.assign(this, composition)
        }

        // apply f to all fields of type composition
        visit(f) {
            const combinator = combinators[this.type]
            if (combinator.components) {
                this.components = this.components.map(f)
            }
            for (let arg of combinator.args || []) {
                if (arg.type === undefined) {
                    this[arg._] = f(this[arg._], arg._)
                }
            }
        }
    }

    // compiler class
    class Compiler {
        // detect task type and create corresponding composition object
        task(task) {
            if (arguments.length > 1) throw new ComposerError('Too many arguments')
            if (task === null) return this.empty()
            if (task instanceof Composition) return task
            if (typeof task === 'function') return this.function(task)
            if (typeof task === 'string') return this.action(task)
            throw new ComposerError('Invalid argument', task)
        }

        // function combinator: stringify function code
        function(fun) {
            if (arguments.length > 1) throw new ComposerError('Too many arguments')
            if (typeof fun === 'function') {
                fun = `${fun}`
                if (fun.indexOf('[native code]') !== -1) throw new ComposerError('Cannot capture native function', fun)
            }
            if (typeof fun === 'string') {
                fun = { kind: 'nodejs:default', code: fun }
            }
            if (typeof fun !== 'object' || fun === null) throw new ComposerError('Invalid argument', fun)
            return new Composition({ type: 'function', function: { exec: fun } })
        }

        // lowering

        _empty() {
            return this.sequence()
        }

        _seq(composition) {
            return this.sequence(...composition.components)
        }

        _value(composition) {
            return this._literal(composition)
        }

        _literal(composition) {
            return this.let({ value: composition.value }, () => value)
        }

        _retain(composition) {
            return this.let(
                { params: null },
                args => { params = args },
                this.mask(...composition.components),
                result => ({ params, result }))
        }

        _retain_catch(composition) {
            return this.seq(
                this.retain(
                    this.finally(
                        this.seq(...composition.components),
                        result => ({ result }))),
                ({ params, result }) => ({ params, result: result.result }))
        }

        _if(composition) {
            return this.let(
                { params: null },
                args => { params = args },
                this.if_nosave(
                    this.mask(composition.test),
                    this.seq(() => params, this.mask(composition.consequent)),
                    this.seq(() => params, this.mask(composition.alternate))))
        }

        _while(composition) {
            return this.let(
                { params: null },
                args => { params = args },
                this.while_nosave(
                    this.mask(composition.test),
                    this.seq(() => params, this.mask(composition.body), args => { params = args })),
                () => params)
        }

        _dowhile(composition) {
            return this.let(
                { params: null },
                args => { params = args },
                this.dowhile_nosave(
                    this.seq(() => params, this.mask(composition.body), args => { params = args }),
                    this.mask(composition.test)),
                () => params)
        }

        _repeat(composition) {
            return this.let(
                { count: composition.count },
                this.while(
                    () => count-- > 0,
                    this.mask(this.seq(...composition.components))))
        }

        _retry(composition) {
            return this.let(
                { count: composition.count },
                params => ({ params }),
                this.dowhile(
                    this.finally(({ params }) => params, this.mask(this.retain_catch(...composition.components))),
                    ({ result }) => result.error !== undefined && count-- > 0),
                ({ result }) => result)
        }

        // define combinator methods for the standard combinators
        static init() {
            for (let type in combinators) {
                const combinator = combinators[type]
                // do not overwrite hand-written combinators
                Compiler.prototype[type] = Compiler.prototype[type] || function () {
                    const composition = new Composition({ type })
                    const skip = combinator.args && combinator.args.length || 0
                    if (!combinator.components && (arguments.length > skip)) {
                        throw new ComposerError('Too many arguments')
                    }
                    for (let i = 0; i < skip; ++i) {
                        const arg = combinator.args[i]
                        const argument = arg.optional ? arguments[i] || null : arguments[i]
                        switch (arg.type) {
                            case undefined:
                                composition[arg._] = this.task(argument)
                                continue
                            case 'value':
                                if (typeof argument === 'function') throw new ComposerError('Invalid argument', argument)
                                composition[arg._] = argument === undefined ? {} : argument
                                continue
                            case 'object':
                                if (argument === null || Array.isArray(argument)) throw new ComposerError('Invalid argument', argument)
                            default:
                                if (typeof argument !== arg.type) throw new ComposerError('Invalid argument', argument)
                                composition[arg._] = argument
                        }
                    }
                    if (combinator.components) {
                        composition.components = Array.prototype.slice.call(arguments, skip).map(obj => this.task(obj))
                    }
                    return composition
                }
            }
        }

        // return combinator list
        get combinators() {
            return combinators
        }

        // recursively deserialize composition
        deserialize(composition) {
            if (arguments.length > 1) throw new ComposerError('Too many arguments')
            composition = new Composition(composition) // copy
            composition.visit(composition => this.deserialize(composition))
            return composition
        }

        // label combinators with the json path
        label(composition) {
            if (arguments.length > 1) throw new ComposerError('Too many arguments')
            if (!(composition instanceof Composition)) throw new ComposerError('Invalid argument', composition)

            const label = path => (composition, name, array) => {
                composition = new Composition(composition) // copy
                composition.path = path + (name !== undefined ? (array === undefined ? `.${name}` : `[${name}]`) : '')
                // label nested combinators
                composition.visit(label(composition.path))
                return composition
            }

            return label('')(composition)
        }

        // recursively label and lower combinators to the desired set of combinators (including primitive combinators)
        lower(composition, combinators = []) {
            if (arguments.length > 2) throw new ComposerError('Too many arguments')
            if (!(composition instanceof Composition)) throw new ComposerError('Invalid argument', composition)
            if (!Array.isArray(combinators) && typeof combinators !== 'boolean' && typeof combinators !== 'string') throw new ComposerError('Invalid argument', combinators)

            if (combinators === false) return composition // no lowering
            if (combinators === true || combinators === '') combinators = [] // maximal lowering
            if (typeof combinators === 'string') { // lower to combinators of specific composer version
                combinators = Object.keys(this.combinators).filter(key => semver.gte(combinators, this.combinators[key].since))
            }

            const lower = composition => {
                composition = new Composition(composition) // copy
                // repeatedly lower root combinator
                while (combinators.indexOf(composition.type) < 0 && this[`_${composition.type}`]) {
                    const path = composition.path
                    composition = this[`_${composition.type}`](composition)
                    if (path !== undefined) composition.path = path
                }
                // lower nested combinators
                composition.visit(lower)
                return composition
            }

            return lower(composition)
        }
    }

    Compiler.init()

    return { ComposerError, Composition, Compiler }
}
'''