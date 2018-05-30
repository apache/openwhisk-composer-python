#!/usr/bin/env bash

bx wsk action invoke pycompose -p source "composer.sequence('echo', 'echo')" -p lower 0.4.0 -br | jq --raw-output .type | grep -q '^sequence$'

if [ $? == 0 ]; then
    echo "ok"
    exit 0
else
    echo "fail"
    exit 1
fi
   
