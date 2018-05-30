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

#!/usr/bin/env bash

bx wsk action invoke pycompose -p source "composer.sequence('echo', 'echo')" -p lower 0.4.0 -br \
    | jq --raw-output .type \
    | grep -q '^sequence$'

if [ $? == 0 ]; then
    echo "ok"
    exit 0
else
    echo "fail"
    exit 1
fi
   
