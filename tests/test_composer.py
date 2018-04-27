import composer
import pytest
import os

name = 'TestAction'

wsk = composer.openwhisk({ 'ignore_certs': 'IGNORE_CERTS' in os.environ and os.environ['IGNORE_CERTS'] and os.environ['IGNORE_CERTS'] != '0' })

def define(action):
    ''' deploy action '''

    try:
        wsk.actions.delete(action['name'])
    except:
        pass
    wsk.actions.create(action)

def invoke(task, params = {}, blocking = True):
   ''' deploy and invoke composition '''
   wsk.compositions.deploy(composer.composition(name, task))
   return wsk.actions.invoke({ 'name': name, 'params': params, 'blocking': blocking })

@pytest.fixture(scope="session", autouse=True)
def deploy_actions():
    define({ 'name': 'echo', 'action': 'const main = x=>x', 'kind': 'nodejs:default' })
    define({ 'name': 'DivideByTwo', 'action': 'function main({n}) { return { n: n / 2 } }', 'kind': 'nodejs:default'})
    define({ 'name': 'TripleAndIncrement', 'action': 'function main({n}) { return { n: n * 3 + 1 } }', 'kind': 'nodejs:default' })
    define({ 'name': 'isNotOne', 'action': 'function main({n}) { return { value: n != 1 } }', 'kind': 'nodejs:default' })
    define({ 'name': 'isEven', 'action': 'function main({n}) { return { value: n % 2 == 0 } }', 'kind': 'nodejs:default'})

class TestAction:
    def test_parse_action_name(self):
        combos = [
            { "n": "", "s": False, "e": "Name is not specified" },
            { "n": " ", "s": False, "e": "Name is not specified" },
            { "n": "/", "s": False, "e": "Name is not valid" },
            { "n": "//", "s": False, "e": "Name is not valid" },
            { "n": "/a", "s": False, "e": "Name is not valid" },
            { "n": "/a/b/c/d", "s": False, "e": "Name is not valid" },
            { "n": "/a/b/c/d/", "s": False, "e": "Name is not valid" },
            { "n": "a/b/c/d", "s": False, "e": "Name is not valid" },
            { "n": "/a/ /b", "s": False, "e": "Name is not valid" },
            { "n": "a", "e": False, "s": "/_/a" },
            { "n": "a/b", "e": False, "s": "/_/a/b" },
            { "n": "a/b/c", "e": False, "s": "/a/b/c" },
            { "n": "/a/b", "e": False, "s": "/a/b" },
            { "n": "/a/b/c", "e": False, "s": "/a/b/c" }
        ]
        for combo in combos:
            if combo["s"] is not False:
                # good cases
                assert composer.parse_action_name(combo["n"]) == combo["s"]
            else:
                # error cases
                try:
                    composer.parse_action_name(combo["n"])
                    assert False
                except composer.ComposerError as error:
                    assert error.message == combo["e"]

@pytest.mark.literal
class TestLiteral:

    def test_boolean(self):
        activation = invoke(composer.literal(True))
        assert activation['response']['result'] == { 'value': True }

    def test_number(self):
        activation = invoke(composer.literal(42))
        assert activation['response']['result'] == { 'value': 42 }

    def test_invalid_arg(self):
        try:
            composer.literal(lambda x:x)
            assert False
        except composer.ComposerError as error:
            assert error.message == 'Invalid argument'

@pytest.mark.function
@pytest.mark.skip(reason='need python conductor')
class TestFunction:

    def test_function_true(self):
         activation = invoke(composer.function(lambda args: args['n'] % 2 == 0), { 'n': 4 })
         assert activation['response']['result'] == { 'value': True }

class TestTasks:

    def test_task_action(self):
        activation = invoke(composer.task('isNotOne'), { 'n': 0 })
        assert activation['response']['result'] == { 'value': True }

    @pytest.mark.skip(reason='need python conductor')
    def test_task_function(self):
        activation = invoke(composer.task(lambda args: args['n'] % 2 == 0), { 'n': 4 })
        assert activation['response']['result'] == { 'value': True }

    def test_task_none(self):
        activation = invoke(composer.task(None), { 'foo': 'foo' })
        assert activation['response']['result'] == { 'foo': 'foo' }

    def test_task_fail(self):
        '''none task must fail on error input'''
        try:
            invoke(composer.task(None), { 'error': 'foo' })
            assert False
        except Exception as error:
            print(error)

