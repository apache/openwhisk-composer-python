#!/usr/bin/env python3

import argparse
import json
import composer
# from composer import __version__

def main():
    parser = argparse.ArgumentParser(description='process compositions', prog='pycompose', usage='%(prog)s composition.py command [flags]')
    parser.add_argument('file', metavar='composition', type=str, help='the composition')
    parser.add_argument('-v', '--version', action='store_true', help='output the composer version')
    parser.add_argument('--ast', action='store_true', help='output ast')


    args = parser.parse_args()

    if args.version:
        print(composer.__version__)
        return

    filename = args.file
    with open(filename, encoding='UTF-8') as f:
        source = f.read()

    main = '''exec(code + "\\n__out__['value'] = main()", {'__out__':__out__})'''
    
    try:
        out = {'value': None}
        exec(main, {'code': source, '__out__': out})        
    
        composition = out['value']
        composition = composition.compile()

        if args.ast:
            composition = str(composition['ast'])
        else:
            composition['ast'] = str(composition['ast'])
            composition['composition'] = str(composition['composition'])

        print(composition)
    except Exception as err:
        print(err)
        return 
    
if __name__ == '__main__':
    main()
