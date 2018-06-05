#
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
#

import composer
import json

from composer import deserialize

class My:
    composition = None

#
# this is the main method for running the pycomposer as an OpenWhisk action
#
def compose(args):
    if 'source' not in args and 'composition' not in args:
        raise Exception('Please provide a source or composition parameter')

    if 'composition' in args:
        print('accepting composition as input')
#        print(args['composition'])
        composition = deserialize(args['composition'])
    else:
        print('accepting source as input')
#        print(args['source'])
#        composition = eval(args['source'])
        code = args['source']

        try:
            print('trying eval')
            composition = eval(code)
            print('eval worked!')

        except SyntaxError as error:
            # if the code isn't an expression, eval will fail with a syntax error;
            # admittedly the eval might've failed for a more "true" syntax error, but
            # the best we can do is hope for the best, and resort to an exec
            print('eval did not work; falling back to exec')

            name = args['name'] if 'name' in args else 'action'
            path = f'/tmp/{name}'
            file = open(path, 'w')
            file.write(code)
            file.close()

            file = open(path, 'r')

            try:
                x = compile(file.read(), path, 'exec')
                my = My()
                exec(x, {'my': my, 'composer': composer})  # we use `my` as an outval
                composition = my.composition

            finally:
                file.close()

            if composition is None:
                raise Exception('Source did not produce a composition')

    if 'lower' in args:
        res = composer.lower(composition, args['lower'])
        print(str(res))
        return json.loads(str(res))
    else:
        if 'name' in args:
            name = 'anonymous'
        else:
            name = args['name']

        compat = args['encode']

        comp = composer.encode(composer.composition(name, composition), compat)
        comp['composition'] = json.loads(str(composer.lower(comp['composition'], compat)))

        print('success in encode')

        return comp
#        return { "code": composer.encode(composer.composition(name, composition), args['encode'])['actions'][-1]['action']['exec']['code'] }
 
