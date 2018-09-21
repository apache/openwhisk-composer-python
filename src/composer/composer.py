import json
import os
import sys
import inspect
import re
import base64
import marshal
import types
 
from .composer import __version__ 
from .fqn import parse_action_name, ComposerError

undefined = object() # special undefined value
composer = types.SimpleNamespace() # Simple object with attributes

composer.util = {
    'version': __version__
}

# Utility functions

def get_value(env, args):
    return env['value']

def set_params(env, args):
    env['params'] = args

def get_params(env, args):
    return env['params']

def retain_result(env, args):
    return { 'params': env['params'], 'result': args }

def retain_nested_result(env, args):
    return { 'params': args['params'], 'result': args['result']['result'] }

def dec_count(env, args):
    c = env['count']
    env['count'] -= 1
    return c > 0

def set_nested_params(env, args):
    return { 'params': args }

def get_nested_params(env, args):
    return args['params']

def set_nested_result(env, args):
    return { 'result': args }

def get_nested_result(env, args):
    return args['result']

def retry_cond(env, args):
    result = args['result']
    count = env['count']
    env['count'] -= 1
    return 'error' in result and count > 0

# lowerer 

lowerer = types.SimpleNamespace()
lowerer.literal = lambda value: composer.let({ 'value': value }, lambda env, args: env['value'])

def retain(*components):
    return composer.let(
        { 'params': None },
        composer.ensure(
            set_params,
            composer.seq(composer.mask(*components), retain_result)))

lowerer.retain = retain

def retain_catch(*components):
    return composer.seq(
        composer.retain(
            composer.ensure(
                composer.seq(*components),
                lambda env, args: { 'result' : args })),
        retain_nested_result)

lowerer.retain_catch = retain_catch

def when(test, consequent, alternate):
    return composer.let(
        { 'params': None },
        set_params,
        composer.ensure(
            lambda env, args: { 'params' : args },
            composer.when_nosave(
                composer.mask(test),
                composer.ensure(get_params, composer.mask(consequent)),
                composer.ensure(get_params, composer.mask(alternate)))))

lowerer.when = when

def loop(test, body):
    return composer.let(
        { 'params': None },
        composer.ensure(
            set_params,
            composer.seq(composer.loop_nosave(
                composer.mask(test),
                composer.ensure(get_params, composer.seq(composer.mask(body), set_params)),
            get_params))))

lowerer.loop = loop

def dowhile(body, test):
    return composer.let(
        { 'params': None },
        composer.ensure(
            set_params,
            composer.seq(composer.dowhile_nosave(
                composer.ensure(get_params, composer.seq(composer.mask(body), set_params)),
                composer.mask(test)),
            get_params)))

lowerer.dowhile = dowhile

def repeat(count, *components):
   return composer.let(
      { 'count': count },
      composer.loop(
        dec_count,
        composer.mask(*components)))

lowerer.repeat = repeat

def retry(count, *components):
    return composer.let(
        { 'count': count },
        set_nested_params,
        composer.dowhile(
            composer.ensure(get_nested_params, composer.mask(composer.retain_catch(*components))),
            retry_cond,
        get_nested_result))

lowerer.retry = retry

def prepare_payload(env, args):
    envs = env['req'].copy()
    del envs['action']
    return { 'action': env['req']['action'], 'args': envs, 'payload': args['payload'] , 'timeout': envs['timeout'] }

def invoke (req, timeout=None):
    return composer.let(
      { 'req': req, 'timeout': timeout },
      prepare_payload,
      composer.execute())

lowerer.invoke = invoke

def sleep(ms):
    return composer.invoke({ 'action': 'sleep', 'ms': ms })

lowerer.sleep = sleep

def merge (*components):
    return composer.seq(composer.retain(*components), lambda env, args: args['params'].update(args['result']))

lowerer.merge = merge

# == Done lowerer

def visit(composition, f):
    ''' apply f to all fields of type composition '''

    combinator = getattr(composition, '.combinator')
    if 'components' in combinator:
        composition.components = composition.components.map(f)

    if 'args' in combinator:
        for arg in combinator['args']:
            if 'type' not in arg and arg.name in composition:
                setattr(composition, arg.name, f(getattr(composition, arg.name), arg.name))
    return Composition(composition)

def label(composition):
    ''' recursively label combinators with the json path '''
    def label(path):
        def labeler(composition, name=None, array=False):
            nonlocal path
            segment = ''
            if name is not None:
                if array:
                    segment = '['+name+']'
                else:
                    segment = '.'+name

            p = path + segment
            composition = visit(composition, label(p))
            composition.path = p
            return composition

        return labeler

    return label('')(composition)


def declare(combinators, prefix=None):
    ''' 
        derive combinator methods from combinator table 
        check argument count and map argument positions to argument names
        delegate to Composition constructor for the rest of the validation
    '''
    if not isinstance(combinators, dict):
        raise ComposerError('Invalid argument "combinators" in "declare"', combinators)
    
    if prefix is not None and not isinstance(prefix, str):
        raise ComposerError('Invalid argument "prefix" in "declare"', prefix)

    composer = types.SimpleNamespace()
    for key in combinators:
        type_ = prefix + '.' + key if prefix is not None else key
        combinator = combinators[key]

        if not isinstance(combinator, dict) or ('args' in combinator and not isinstance(combinator['args'], list)):
            raise ComposerError('Invalid "'+type_+'" combinator specification in "declare"', combinator)

        if 'args' in combinator:
            for arg in combinator.args:
                if not isinstance(arg['name'], str):
                    raise ComposerError('Invalid "'+type_+'" combinator specification in "declare"', combinator)
       
        def combine(*arguments):
            composition = { 'type': type_, '.combinator': lambda : combinator }
            skip = len(combinator['args']) if 'args' in combinator else 0 

            if 'components' not in combinator and len(arguments) > skip:
                raise ComposerError('Too many arguments in "'+type_+'" combinator')
            
            for i in range(skip):
                composition[combinator['args'][i]['name']] = arguments[i]
                
            if 'components' in combinator:
                composition['components'] = arguments[skip:]
                
            return Composition(composition)

        setattr(composer, key, combine)
 
    return composer

def serialize(obj):
    return obj.__dict__

class Composition:

    def __init__(self, composition):
        '''  construct a composition object with the specified fields '''
        combinator = getattr(composition, '.combinator')()
        
        # shallow copy of obj attributes
        items = composition.items() if isinstance(composition, dict) else composition.__dict__.items() if isinstance(composition, Composition) else None
        if items is None:
            raise ComposerError('Invalid argument', composition)
        for k, v in items:
            setattr(self, k, v)
        
        if 'args' in combinator:
            for arg in combinator.args:
                if arg.name not in composition and optional and 'type' in arg:
                    continue
                optional = getattr(arg, 'optional', False)
                if 'type' not in arg:
                    try:
                        value = getattr(composition, arg.name, None if optional else undefined)
                        setattr(self, arg.name, composer.task(value))
                    except Exception:
                        raise ComposerError('Invalid argument "'+arg.name+'" in "'+composition.type+' combinator"', value)
                elif arg.type == 'name':
                    try:
                        setattr(self, arg.name, parse_action_name(getattr(composition, arg.name)))
                    except ComposerError as ce:
                        raise ComposerError(ce.message + 'in "'+composition.type+' combinator"', getattr(composition, arg.name))
                elif arg.type == 'value':
                    if arg.name not in composition or callable(getattr(composition, arg.name)):
                        raise ComposerError('Invalid argument "' + arg.name+'" in "'+ composition.type+'combinator"', getattr(composition, arg.name))
                elif arg.type == 'object':
                    if arg.name not in composition or not isinstance(getattr(composition, arg.name), Composition):
                        raise ComposerError('Invalid argument "' + arg.name+'" in "'+ composition.type+'combinator"', getattr(composition, arg.name))
                else:
                    if type(getattr(composition, arg.name)) != arg.type: 
                        raise ComposerError('Invalid argument "' + arg.name+'" in "'+ composition.type+'combinator"', getattr(composition, arg.name))
        
        if 'components' in combinator:
            self.components = map(composer.task, getattr(composition, 'components', []))


    def __str__(self):
        return json.dumps(self.__dict__, default=serialize, ensure_ascii=True)

    def compile(self):
        '''  compile composition. Returns a dictionary '''
        actions = []

        def flatten(composition, _=None):
            composition = visit(composition, flatten)
            if composition.type == 'action' and hasattr(composition, 'action'): # pylint: disable=E1101
                actions.append({ 'name': composition.name, 'action': composition.action })
            del composition.action # pylint: disable=E1101
            return composition
        
        obj = { 'composition': label(flatten(self)).lower(), 'ast': self, 'version': __version__ }
        if len(actions) > 0:
            obj['actions'] = actions
        return obj
     
    def lower(self, combinators = []):
        ''' recursively lower combinators to the desired set of combinators (including primitive combinators) '''
        if not isinstance(combinators, list) and not isinstance(combinators, str):
            raise ComposerError('Invalid argument "combinators" in "lower"', combinators)

        def lower(composition, _):
            # repeatedly lower root combinator

            while getattr(getattr(composition, '.combinator')(), 'def', False):
                path = composition.path if hasattr(composition, 'path') else None
                combinator = getattr(composition, '.combinator')()
                if isinstance(combinator, list) and combinator.indexOf(composition.type) >= 0:
                    break
                
                # no semver in openwhisk python runtime
                # if isinstance(combinator, str) and getattr(combinator, 'since', False):
                #     break;    

                # map argument names to positions
                args = []
                skip = len(getattr(combinator, 'args', []))
                for i in range(skip): 
                    args.append(getattr(composition, combinator.args[i].name))

                if 'components' in combinator:
                    args.extend(composition.components)

                composition = combinator['def'](args)

                # preserve path
                if path is not None:
                    composition.path = path
            
            return visit(composition, lower)
                
        return lower(self, None)
 

# primitive combinators
combinators = {
  'sequence': { 'components': True, 'since': '0.4.0' },
  'if_nosave': { 'args': [{ 'name': 'test' }, { 'name': 'consequent' }, { 'name': 'alternate', 'optional': True }], 'since': '0.4.0' },
  'while_nosave': { 'args': [{ 'name': 'test' }, { 'name': 'body' }], 'since': '0.4.0' },
  'dowhile_nosave': { 'args': [{ 'name': 'body' }, { 'name': 'test' }], 'since': '0.4.0' },
  'try': { 'args': [{ 'name': 'body' }, { 'name': 'handler' }], 'since': '0.4.0' },
  'finally': { 'args': [{ 'name': 'body' }, { 'name': 'finalizer' }], 'since': '0.4.0' },
  'let': { 'args': [{ 'name': 'declarations', 'type': 'object' }], 'components': True, 'since': '0.4.0' },
  'mask': { 'components': True, 'since': '0.4.0' },
  'action': { 'args': [{ 'name': 'name', 'type': 'name' }, { 'name': 'action', 'type': 'object', 'optional': True }], 'since': '0.4.0' },
  'function': { 'args': [{ 'name': 'function', 'type': 'object' }], 'since': '0.4.0' },
  'async': { 'components': True, 'since': '0.6.0' },
  'execute': { 'since': '0.5.2' },
  'parallel': { 'components': True, 'since': '0.6.0' },
  'map': { 'components': True, 'since': '0.6.0' },
  'composition': { 'args': [{ 'name': 'name', 'type': 'name' }], 'since': '0.6.0' }
}

composer.__dict__.update(declare(combinators).__dict__)

# derived combinators
extra = {
  'empty': { 'since': '0.4.0', 'def': composer.sequence },
  'seq': { 'components': True, 'since': '0.4.0', 'def': composer.sequence },
  'if': { 'args': [{ 'name': 'test' }, { 'name': 'consequent' }, { 'name': 'alternate', 'optional': True }], 'since': '0.4.0', 'def': lowerer.when },
  'while': { 'args': [{ 'name': 'test' }, { 'name': 'body' }], 'since': '0.4.0', 'def': lowerer.loop },
  'dowhile': { 'args': [{ 'name': 'body' }, { 'name': 'test' }], 'since': '0.4.0', 'def': lowerer.doloop },
  'repeat': { 'args': [{ 'name': 'count', 'type': 'number' }], 'components': True, 'since': '0.4.0', 'def': lowerer.repeat },
  'retry': { 'args': [{ 'name': 'count', 'type': 'number' }], 'components': True, 'since': '0.4.0', 'def': lowerer.retry },
  'retain': { 'components': True, 'since': '0.4.0', 'def': lowerer.retain },
  'retain_catch': { 'components': True, 'since': '0.4.0', 'def': lowerer.retain_catch },
  'value': { 'args': [{ 'name': 'value', 'type': 'value' }], 'since': '0.4.0', 'def': lowerer.literal },
  'literal': { 'args': [{ 'name': 'value', 'type': 'value' }], 'since': '0.4.0', 'def': lowerer.literal },
  'sleep': { 'args': [{ 'name': 'ms', 'type': 'number' }], 'since': '0.5.0', 'def': lowerer.sleep },
  'invoke': { 'args': [{ 'name': 'req', 'type': 'object' }, { 'name': 'timeout', 'type': 'number', 'optional': True }], 'since': '0.5.0', 'def': lowerer.invoke },
  'par': { 'components': True, 'since': '0.8.2', 'def': composer.parallel },
  'merge': { 'components': True, 'since': '0.13.0', 'def': lowerer.merge }
}

composer.__dict__.update(declare(extra).__dict__)

# add or override definitions of some combinators

def task(task):
    ''' detect task type and create corresponding composition object '''
    if task is undefined:
        raise ComposerError('Invalid argument in "task" combinator', task)

    if task is None:
        return composer.empty() 

    if isinstance(task, Composition):
        return task

    if callable(task):
        return composer.function(task)

    if isinstance(task, str): # python3 only
        return composer.action(task)

    raise ComposerError('Invalid argument "task" in "task" combinator', task)

composer.task = task


def function(fun):
    ''' function combinator: stringify def/lambda code '''

    if fun.__name__ == '<lambda>':
        exc = str(base64.b64encode(marshal.dumps(fun.__code__)), 'ASCII')
    elif callable(fun):
        try:
            exc = inspect.getsource(fun)
        except OSError:
            raise ComposerError('Invalid argument', fun)
    else:
        exc = fun

    if isinstance(exc, str):
        if exc.startswith('def'):
            # standardize function name
            pattern = re.compile(r'def\s+([a-zA-Z_][a-zA-Z_0-9]*)\s*\(')
            match = pattern.match(exc)
            functionName = match.group(1)

            exc = { 'kind': 'python:3', 'code': exc, 'functionName': functionName }
        else: # lambda 
            exc = { 'kind': 'python:3+lambda', 'code': exc }

    if not isinstance(exc, dict) or exc is None:
        raise ComposerError('Invalid argument "function" in "function" combinator', fun)

    return Composition({'type':'function', 'function':{ 'exec': exc }, '.combinator': lambda: combinators['function'] })

composer.function = function

def action(name, options = {}):
    ''' action combinator '''
    if not isinstance(options, dict):
        raise ComposerError('Invalid argument "options" in "action" combinator', options)
    exc = None
    if 'sequence' in options and isinstance(options['sequence'], list): # native sequence
        exc = { 'kind': 'sequence', 'components': tuple(map(parse_action_name, options['sequence'])) }
    elif 'filename' in options and isinstance(options['filename'], str): # read action code from file
        raise ComposerError('read from file not implemented')
        # exc = fs.readFileSync(options.filename, { encoding: 'utf8' })
    
    elif 'action' in options and callable(options['action']):
        if options['action'].__name__ == '<lambda>':
            exc = str(base64.b64encode(marshal.dumps(options['action'].__code__)), 'ASCII')
        else:    
            try:
                exc = inspect.getsource(options['action'])
            except OSError:
                raise ComposerError('Invalid argument "options" in "action" combinator', options['action'])
    elif 'action' in options and (isinstance(options['action'], str) or isinstance(options['action'],  dict)):
        exc = options['action']
    
    if isinstance(exc, str):
        exc = { 'kind': 'python:3', 'code': exc }
    
    composition = { 'type': 'action', 'name': name, '.combinator': lambda: combinators['action']}
    if exc is not None:
        composition.action = exc

    return Composition(composition)
