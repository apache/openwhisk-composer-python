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

#
# this is the main method for running the pycomposer as an OpenWhisk action
#
def compose(args):
    if 'source' not in args and 'composition' not in args:
        raise Exception('Please provide a source or composition parameter')

    if 'composition' in args:
        print('accepting composition as input')
        print(args['composition'])
        composition = deserialize(args['composition'])
    else:
        print(args['source'])
        composition = eval(args['source'])

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
        print(comp)
        print(str(comp))

        return comp
#        return { "code": composer.encode(composer.composition(name, composition), args['encode'])['actions'][-1]['action']['exec']['code'] }
 
