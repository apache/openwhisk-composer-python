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

#
# this is the main method for running the pycomposer as an OpenWhisk action
#
def compose(args):
    if args['source'] is None:
        raise Exception('Please provide a source parameter')

    composition = eval(args['source'])
    print(args['source'])

    if args['lower'] is not None:
        res = composer.lower(composition, args['lower'])
        print(str(res))
        return json.loads(str(res))
    else:
        return { "code": composer.encode(composer.composition('anonymous', composition), lower)['actions'][-1]['action']['exec']['code'] }
