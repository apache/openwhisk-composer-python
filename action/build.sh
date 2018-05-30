#!/usr/bin/env bash

PY_VERSION=3.6

# directory of script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOTDIR="$DIR/.."
cd "${ROOTDIR}/action"

# clean up
rm -rf virtualenv pycompose.zip

# create virtualenv
virtualenv --no-pip --no-wheel --no-setuptools virtualenv

# copy in the composer assets
cp -r "$ROOTDIR/src/composer" "virtualenv/lib/python${PY_VERSION}/site-packages"

# remove symlinks
find "virtualenv/lib/python${PY_VERSION}/" -type l -exec rm {} \;

# remove site.py
rm "virtualenv/lib/python${PY_VERSION}/site.py"

# remove the python exec stuff
rm "virtualenv/bin/python-config"
rm "virtualenv/bin/python${PY_VERSION}"

# remove pycaches
find "virtualenv/" -name __pycache__ -exec rm -rf {} \; 2>&1 | grep -v "No such file or directory"

# make the zip file
# the -y part says not to follow symlinks
echo "Zipping it up"
zip -qry pycompose.zip virtualenv __main__.py

# sanity check
unzip -ql pycompose.zip | grep composer.py > /dev/null && echo "ok" || (echo "fail" && exit 1)
