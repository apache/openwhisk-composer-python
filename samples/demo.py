import composer

def main():
    return composer.when(
        composer.action('authenticate',  { 'action': lambda args: { 'value': args['password'] == 'abc123' } }),
        composer.action('success', { 'action': lambda args: { 'message': 'success' } }),
        composer.action('failure', { 'action': lambda args: { 'message': 'failure' } }))
