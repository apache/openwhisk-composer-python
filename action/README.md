# Building an OpenWhisk Action

This directory helps with creating an OpenWhisk action that will
implement the `pycompose` functionality.

## Quick Start

```shell
$ ./build.sh
$ ./deploy.sh
$ ./test.sh
ok
```

## Usage in Other Clients

One suggested use of the action is to build the action source
(pycompose.zip), using the `build.sh` script. Include the built zip
with your client. Then, for each user of the client, deploy the action
using that source, and invoke the action as needed.
