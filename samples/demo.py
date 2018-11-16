import composer

def main():
    return composer.when(
        composer.action('authenticate',  { 'action': lambda env, args: { 'value': args['password'] == 'abc123' } }),
        composer.action('success', { 'action': lambda env, args: { 'message': 'success' } }),
        composer.action('failure', { 'action': lambda env, args: { 'message': 'failure' } }))
