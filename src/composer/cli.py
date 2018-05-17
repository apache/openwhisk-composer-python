
import openwhisk

def main():
    print(exec('import composer\ncomposer.task("a")', { '__builtins__': globals()['__builtins__']}))

main()