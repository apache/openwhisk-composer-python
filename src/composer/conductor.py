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
import functools
import json
import marshal
import base64 
import types

# dummy composition and compiler
composition = {} # will be overridden
class Compiler:
    def lower(self, composition, combinators = []):
        pass
    def deserialize(self, composition):
        pass
    def label(self, composition):
        pass

def conductor():
    global composition
    compiler = Compiler()

    def chain(front, back):
        front[-1]['next'] = 1
        front.extend(back)
        return front

    def sequence(components):
        if len(components) == 0:
            return [{ 'type': 'empty' }]
        return functools.reduce(chain, map(compile, components))

    def compile(json):
        path = json.path if hasattr(json, 'path') else None
        type_ = json.type
        if type_ == 'sequence':
            return chain([{ 'type': 'pass', 'path':path }], sequence(json.components))
        elif type_ == 'action':
            return [{ 'type': 'action', 'name': json.name, 'path': path }]
        elif type_ == 'function':
            return [{ 'type': 'function', 'exec': json.function['exec'], 'path':path }]
        elif type_ == 'finally':
            body = compile(json.body)
            finalizer = compile(json.finalizer)
            fsm = functools.reduce(chain, [[{'type': 'try', 'path': path}], body, [{ 'type': 'exit' }], finalizer])
            fsm[0]['catch'] = len(fsm) - len(finalizer)
            return fsm
        elif type_ == 'let':
            body = sequence(json.components)
            return functools.reduce(chain, [[{ 'type': 'let', 'let': json.declarations, 'path':path }], body, [{ 'type': 'exit' }]])
        elif type_ == 'mask':
            body = sequence(json.components)
            return functools.reduce(chain, [[{ 'type': 'let', 'let': None, 'path': path }], body, [{ 'type': 'exit' }]])
        elif type_ == 'try':
            body = compile(json.body)
            handler = chain(compile(json.handler), [{ 'type': 'pass' }])
            fsm = functools.reduce(chain, [[{ 'type': 'try', 'path':path }], body, [{ 'type': 'exit' }]])
            fsm[0]['catch'] = len(fsm)
            fsm[-1]['next'] = len(handler)
            fsm.extend(handler)
            return fsm
        elif type_ == 'if_nosave':
            consequent = compile(json.consequent)
            alternate = chain(compile(json.alternate), [{ 'type': 'pass' }])
            fsm = functools.reduce(chain, [[{ 'type': 'pass', 'path':path }], compile(json.test), [{ 'type': 'choice', 'then': 1, 'else': len(consequent) + 1 }]])
            consequent[-1]['next'] = len(alternate)
            fsm.extend(consequent)
            fsm.extend(alternate)
            return fsm
        elif type_ == 'while_nosave':
            consequent = compile(json.body)
            alternate = [{ 'type': 'pass' }]
            fsm = functools.reduce(chain, [[{ 'type': 'pass', 'path':path }], compile(json.test), [{ 'type': 'choice', 'then': 1, 'else': len(consequent) + 1 }]])
            consequent[-1]['next'] = 1 - len(fsm) - len(consequent)
            fsm.extend(consequent)
            fsm.extend(alternate)
            return fsm
        elif type_ == 'dowhile_nosave':
            test = compile(json.test)
            fsm = functools.reduce(chain, [[{ 'type': 'pass', 'path':path }], compile(json.body), test, [{ 'type': 'choice', 'then': 1, 'else': 2 }]])
            fsm[-1]['then'] = 1 - len(fsm)
            fsm[-1]['else'] = 1
            alternate = [{ 'type': 'pass' }]
            fsm.extend(alternate)
            return fsm

    fsm = compile(compiler.lower(compiler.label(compiler.deserialize(composition))))

    isObject = lambda x: isinstance(x, dict)

    def encodeError(error):
        return {
            'code': error['code'] if isinstance(error['code'], int) else 500,
            'error': error['error'] if isinstance(error['error'], str) else (error['message'] if 'message' in error else (error if isinstance(error, str) else 'An internal error occurred'))
        }

    # error status codes
    badRequest = lambda error: { 'code': 400, 'error': error }
    internalError = lambda error: encodeError(error)

    def guarded_invoke(params):
        try:
            return invoke(params)
        except Exception as err:
            return internalError(err)

    def invoke(params):
        ''' do invocation '''
        # initial state and stack
        state = 0
        stack = []

        # wrap params if not a dictionary, branch to error handler if error
        def inspect_errors():
            nonlocal params
            nonlocal state
            nonlocal stack
            params = params if isObject(params) else { 'value': params }
            if 'error' in params:
                params = { 'error': params['error'] } # discard all fields but the error field
                state = None # abort unless there is a handler in the stack
                while len(stack) > 0:
                    first = stack[0]
                    stack = stack[1:]
                    if 'catch' in first:
                        state = first['catch']
                        if isinstance(state, int):
                            break


        # restore state and stack when resuming
        if '$resume' in params:
            if not isObject(params['$resume']):
                return badRequest('The type of optional $resume parameter must be object')
            if not 'state' in params['$resume'] and not isinstance(params['$resume']['state'], int):
                return badRequest('The type of optional $resume["state"] parameter must be number')
            state = params['$resume']['state']
            stack = params['$resume']['stack']
            if not isinstance(stack, list):
                return badRequest('The type of $resume["stack"] must be an array')
            del params['$resume']
            inspect_errors() # handle error objects when resuming

        # run function f on current stack
        def run(f, kind):
            # handle let/mask pairs
            view = []
            n = 0
            for frame in stack:
                if 'let' in frame and frame['let'] is None:
                    n += 1
                elif 'let' in frame:
                    if n == 0:
                        view.append(frame)
                    else:
                        n -= 1


            # update value of topmost matching symbol on stack if any
            def set(symbol, value):
                lets = [element for element in view if 'let' in element and symbol in element['let']]
                if len(lets) > 0:
                    element = lets[0]
                    element['let'][symbol] = value # TODO: JSON.parse(JSON.stringify(value))


            def reduceRight(func, init, seq):
                if not seq:
                    return init
                else:
                    return func(reduceRight(func, init, seq[1:]), seq[0])

            def update(dict, dict2):
                dict.update(dict2)
                return dict

            # collapse stack for invocation
            env = reduceRight(lambda acc, cur: update(acc, cur['let']) if 'let' in cur and isinstance(cur['let'], dict) else acc, {}, view)
            if kind == 'python:3':
                main = '''exec(code + "\\n__out__['value'] = func(env, args)", {'env': env, 'args': args, '__out__':__out__})'''
                code = f
            else: # lambda
                main = '''__out__['value'] = code(env, args)'''
                code = types.FunctionType(marshal.loads(base64.b64decode(bytearray(f, 'ASCII'))), {})

            try:
                out = {'value': None}
                exec(main, {'env': env, 'args': params, 'code': code, '__out__': out})
                return out['value']
            finally:
                for name in env:
                    set(name, env[name])

        while True:
            # final state, return composition result
            if state is None:
                print('Entering final state')
                print(json.dumps(params))
                if 'error' in params:
                    return params
                else:
                    return { 'params': params }

            # process one state
            jsonv = fsm[state] # jsonv definition for current state
            if hasattr(jsonv, 'path'):
                print('Entering composition'+jsonv.path)
            current = state
            state = current + jsonv['next'] if 'next' in jsonv else None # default next state
            if jsonv['type'] == 'choice':
                state = current + (jsonv['then'] if params['value'] else jsonv['else'])
            elif jsonv['type'] == 'try':
                stack.insert(0, { 'catch': current + jsonv['catch'] })
            elif jsonv['type'] == 'let':
                stack.insert(0, { 'let': jsonv['let'] }) # JSON.parse(JSON.stringify(jsonv.let))
            elif jsonv['type'] == 'exit':
                if len(stack) == 0:
                    return internalError('State '+str(current)+' attempted to pop from an empty stack')
                stack = stack[1:]
            elif jsonv['type'] == 'action':
                return { 'action': jsonv['name'], 'params': params, 'state': { '$resume': { 'state': state, 'stack': stack } } } # invoke continuation
            elif jsonv['type'] == 'function':
                result = None
                try:
                    result = run(jsonv['exec']['code'], jsonv['exec']['kind'])
                except Exception as error:
                    print(error)
                    result = { 'error': 'An exception was caught at state '+str(current)+' (see log for details)' }

                if callable(result):
                    result = { 'error': 'State '+str(current)+' evaluated to a function' }

                # if a function has only side effects and no return value (or return None), return params
                params = params if result is None else result
                inspect_errors()
            elif jsonv['type'] == 'empty':
                inspect_errors()
            elif jsonv['type'] == 'pass':
                pass
            else:
                return internalError('State '+str(current)+ 'has an unknown type')

    return guarded_invoke

