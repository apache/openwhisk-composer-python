import argparse
import json
import composer
from composer import __version__
import traceback

def main():
    parser = argparse.ArgumentParser(description='process compositions', prog='pycompose', usage='%(prog)s composition.[py|json] command [flags]')
    parser.add_argument('file', metavar='composition', type=str, help='the composition')
    parser.add_argument('--deploy', metavar='NAME', type=str, help='deploy the composition with name NAME')
    parser.add_argument('--encode', action='store_true', help='output the conductor action code for the composition')
    parser.add_argument('--lower',  metavar='VERSION', default=False, type=str, nargs='?', help='lower to primitive combinators or specific composer version')
    parser.add_argument('--apihost', nargs=1, metavar='HOST', help='API HOST')
    parser.add_argument('-u', '--auth', nargs=1, metavar='KEY', help='authorization KEY')
    parser.add_argument('-i', '--insecure', action='store_true', help='bypass certificate checking')
    parser.add_argument('-v', '--version', action='store_true', help='output the composer version')

    args = parser.parse_args()

    if args.version:
        print(__version__)
        return

    filename = args.file
    with open(filename, encoding='UTF-8') as f:
        source = f.read()

    composition =  eval(source) if filename.endswith('.py') else composer.deserialize(json.loads(source))
    lower = args.lower
    if args.deploy is not None:
        options = { 'ignore_certs': args.insecure }
        if args.apihost is not None:
            options['apihost'] = args.apihost
        if args.auth is not None:
            options['api_key'] = args.auth

        try:
            obj = composer.openwhisk(options).compositions.deploy(composer.composition(args.deploy, composition), lower)
            names = ', '.join(map(lambda action: action['name'], obj['actions']))
            print('ok: created action'+'s' if len(names) > 1 else ''+names)
        except Exception as err:
            traceback.print_exc()
            print(err)
    elif args.encode is True:
        print(composer.encode(composer.composition('anonymous', composition), lower)['actions'][-1]['action']['exec']['code'])
    else:
        print(str(composer.lower(composition, lower)))

if __name__ == '__main__':
    main()
