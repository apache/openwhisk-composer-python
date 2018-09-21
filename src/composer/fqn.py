
def parse_action_name(name):
    '''
      Parses a (possibly fully qualified) resource name and validates it. If it's not a fully qualified name,
      then attempts to qualify it.

      Examples string to namespace, [package/]action name
        foo => /_/foo
        pkg/foo => /_/pkg/foo
        /ns/foo => /ns/foo
        /ns/pkg/foo => /ns/pkg/foo
    '''
    if not isinstance(name, str):
        raise ComposerError('Name is not valid')
    name = name.strip()
    if len(name) == 0:
        raise ComposerError('Name is not specified')

    delimiter = '/'
    parts = name.split(delimiter)
    n = len(parts)
    leadingSlash = name[0] == delimiter if len(name) > 0 else False
    # no more than /ns/p/a
    if n < 1 or n > 4 or (leadingSlash and n == 2) or (not leadingSlash and n == 4):
        raise ComposerError('Name is not valid')

    # skip leading slash, all parts must be non empty (could tighten this check to match EntityName regex)
    for part in parts[1:]:
        if len(part.strip()) == 0:
            raise ComposerError('Name is not valid')

    newName = delimiter.join(parts)
    if leadingSlash:
        return newName
    elif n < 3:
        return delimiter+'_'+delimiter+newName
    else:
        return delimiter+newName

class ComposerError(Exception):
    def __init__(self, message, *arguments):
       self.message = message
       self.argument = arguments
 