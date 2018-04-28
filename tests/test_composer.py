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
    def test_action_true(self):
        ''' action must return true '''
        activation = invoke(composer.action('isNotOne'), { 'n': 0 })
        assert activation['response']['result'] == { 'value': True }

    def test_action_false(self):
        ''' action must return false '''
        activation = invoke(composer.action('isNotOne'), { 'n': 1 })
        assert activation['response']['result'] == { 'value': False }

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

    def test_invalid(self):
        '''invalid argument'''
        try:
            invoke(composer.action(42))
            assert False
        except composer.ComposerError as error:
            assert error.message == 'Name is not valid'

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

class TestSequence:

    def test_flat(self):
        activation = invoke(composer.sequence('TripleAndIncrement', 'DivideByTwo', 'DivideByTwo'), { 'n': 5 })
        assert activation['response']['result'] == { 'n': 4 }

    def test_nested_right(self):
        activation = invoke(composer.sequence('TripleAndIncrement', composer.sequence('DivideByTwo', 'DivideByTwo')), { 'n': 5 })
        assert activation['response']['result'] == { 'n': 4 }

    def test_nested_left(self):
        activation = invoke(composer.sequence(composer.sequence('TripleAndIncrement', 'DivideByTwo'), 'DivideByTwo'), { 'n': 5 })
        assert activation['response']['result'] == { 'n': 4 }

    def test_seq(self):
        activation = invoke(composer.seq('TripleAndIncrement', 'DivideByTwo', 'DivideByTwo'), { 'n': 5 })
        assert activation['response']['result'] == { 'n': 4 }

class TestIf:
    def test_condition_true(self):
        activation = invoke(composer.when('isEven', 'DivideByTwo', 'TripleAndIncrement'), { 'n': 4 })
        assert activation['response']['result'] == { 'n': 2 }

    def test_condition_false(self):
        activation =  invoke(composer.when('isEven', 'DivideByTwo', 'TripleAndIncrement'), { 'n': 3 })
        assert activation['response']['result'] == { 'n': 10 }

    def test_condition_true_then_branch_only(self):
        activation =  invoke(composer.when('isEven', 'DivideByTwo'), { 'n': 4 })
        assert activation['response']['result'] == { 'n': 2 }

    def test_condition_false_then_branch_only(self):
        activation =  invoke(composer.when('isEven', 'DivideByTwo'), { 'n': 3 })
        assert activation['response']['result'] == { 'n': 3 }

    # def test_condition_true_nosave_option(self):
    #     activation =  invoke(composer.if_nosave('isEven', params => { params.then = true }, params => { params.else = true }), { n: 2 })
    #     assert activation['response']['result'] == { value: true, then: true }))

    # def test_condition_false_nosave_option(self):
    #     activation = invoke(composer.if_nosave('isEven', params => { params.then = true }, params => { params.else = true }), { n: 3 })
    #     assert activation['response']['result'] == { value: false, else: true }))

class TestLoop:

    @pytest.mark.skip(reason='need python conductor')
    def test_a_few_iterations(self) :
        activation = invoke(composer.loop('isNotOne', '({ n }) => ({ "n": n - 1 }))', { 'n': 4 }))
        assert activation['response']['result'] == { 'n': 1 }

    @pytest.mark.skip(reason='need python conductor')
    def test_no_iteration(self):
        activation = invoke(composer.loop('() => false', '({ n }) => ({ "n": n - 1 }))', { 'n': 1 }))
        assert activation['response']['result'] == { 'n': 1 }

    @pytest.mark.skip(reason='need python conductor')
    def test_nosave_option(self) :
        activation = invoke(composer.loop_nosave('({ n }) => ({ n, value: n !== 1 })', '({ n }) => ({ n: n - 1 }))', { 'n': 4 }))
        assert activation['response']['result'] == { 'value': False, 'n': 1 }

@pytest.mark.skip(reason='need python conductor')
class TestDoLoop:

    def test_a_few_iterations(self) :
        activation = invoke(composer.doloop('({ n }) => ({ n: n - 1 })', 'isNotOne'), { 'n': 4 })
        assert activation['response']['result'] == { 'n': 1 }

    def test_one_iteration(self) :
        activation = invoke(composer.doloop('({ n }) => ({ n: n - 1 })', '() => false'), { 'n': 1 })
        assert activation['response']['result'] == { 'n': 0 }

    def test_nosave_option(self) :
        activation = invoke(composer.doloop_nosave(('{ n }) => ({ n: n - 1 })', '({ n }) => ({ n, value: n !== 1 }))', { 'n': 4 })))
        assert activation['response']['result'] == { 'value': False, 'n': 1 }

@pytest.mark.skip(reason='need python conductor')
class TestDo: # Try
    def test_no_error(self):
        activation = invoke(composer.do('() => true', 'error => ({ message: error.error })'))
        assert activation['response']['result'] == { 'value': True }

    def test_error(self) :
        activation = invoke(composer.do('() => ({ error: "foo" })', 'error => ({ message: error.error })'))
        assert activation['response']['result'] == { 'message': 'foo' }

    def test_try_must_throw(self) :
        activation = invoke(composer.do(composer.task(None), 'error => ({ message: error.error }))', { 'error': 'foo' }))
        assert activation['response']['result'] == { 'message': 'foo' }

    def test_while_must_throw(self) :
        activation = invoke(composer.do(composer.loop(composer.literal(False), None), 'error => ({ message: error.error })'), { 'error': 'foo' })
        assert activation['response']['result'] == { 'message': 'foo' }

    def test_if_must_throw(self) :
        activation = invoke(composer.do(composer.when(composer.literal(False), None), 'error => ({ message: error.error })'), { 'error': 'foo' })
        assert activation['response']['result'] == { 'message': 'foo' }

    def test_retain(self) :
        activation = invoke(composer.retain(composer.do('() => ({ p: 4 })', None)), { 'n': 3 })
        assert activation['response']['result'] == { 'params': { 'n': 3 }, 'result': { 'p': 4 } }

@pytest.mark.skip(reason='need python conductor')
class TestEnsure: # Finally

    def test_no_error(self) :
        activation = invoke(composer.ensure('() => true', 'params => ({ params })'))
        assert activation['response']['result'] == { 'params': { 'value': True } }

    def test_error(self) :
        activation = invoke(composer.ensure('() => ({ error: "foo" })', 'params => ({ params })'))
        assert activation['response']['result'] == { 'params': { 'error': 'foo' } }

@pytest.mark.skip(reason='need python conductor')
class TestLet:

    def test_one_variable(self) :
        activation = invoke(composer.let({ 'x': 42 }, '() => x'))
        assert activation['response']['result'] == { 'value': 42 }

    def test_masking(self) :
        activation = invoke(composer.let({ 'x': 42 }, composer.let({ 'x': 69 }, '() => x')))
        assert activation['response']['result'] == { value: 69 }

    def test_two_variables(self) :
        activation = invoke(composer.let({ 'x': 42 }, composer.let({ 'y': 69 }, '() => x + y')))
        assert activation['response']['result'] == { 'value': 111 }

    def test_two_variables_combined(self) :
        activation = invoke(composer.let({ 'x': 42, 'y': 69 }, '() => x + y'))
        assert activation['response']['result'] == { 'value': 111 }

    def test_scoping(self) :
        activation = invoke(composer.let({ 'x': 42 }, composer.let({ 'x': 69 }, '() => x'), '({ value }) => value + x'))
        assert activation['response']['result'] == { 'value': 111 }

    def test_invalid_argument(self):
        try:
            invoke(composer.let(invoke))
            assert False
        except Exception as error:
            assert error.message.startswith('Invalid argument')

@pytest.mark.skip(reason='need python conductor')
class TestMask:

    def test_let_let_mask(self) :
        activation = invoke(composer.let({ 'x': 42 }, composer.let({ 'x': 69 }, composer.mask('() => x'))))
        assert activation['response']['result'] == { 'value': 42 }

    def test_let_mask_let(self) :
        activation = invoke(composer.let({ 'x': 42 }, composer.mask(composer.let({ 'x': 69 }, '() => x'))))
        assert activation['response']['result'] == { 'value': 69 }

    def test_let_let_try_mask(self) :
        activation = invoke(composer.let({ 'x': 42 }, composer.let({ 'x': 69 },
            composer.do(composer.mask('() => x'), '() => { }'))))
        assert activation['response']['result'] == { 'value': 42 }

    def test_let_let_let_mask(self) :
        activation = invoke(composer.let({ 'x': 42 }, composer.let({ 'x': 69 },
            composer.let({ 'x': -1 }, composer.mask('() => x')))))
        assert activation['response']['result'] == { 'value': 69 }

    def test_let_let_let_mask_mask(self) :
        activation = invoke(composer.let({ 'x': 42 }, composer.let({ 'x': 69 },
            composer.let({ 'x': -1 }, composer.mask(composer.mask('() => x'))))))
        assert activation['response']['result'] == { 'value': 42 }

    def test_let_let_mask_let_mask(self) :
        activation = invoke(composer.let({ 'x': 42 }, composer.let({ 'x': 69 },
            composer.mask(composer.let({ 'x': -1 }, composer.mask('() => x'))))))
        assert activation['response']['result'] == { 'value': 42 }

class TestRetain:

    def test_base_case(self) :
        activation = invoke(composer.retain('TripleAndIncrement'), { 'n': 3 })
        assert activation['response']['result'] == { 'params': { 'n': 3 }, 'result': { 'n': 10 } }

    @pytest.mark.skip(reason='need python conductor')
    def test_throw_error(self) :
        try:
            activation = invoke(composer.retain('() => ({ error: "foo" })'), { 'n': 3 })
            assert False
        except composer.ComposerError as error:
            assert error.error.response.result == { 'error': 'foo' }

    @pytest.mark.skip(reason='need python conductor')
    def test_catch_error(self) :
        try:
            activation = invoke(composer.retain_catch('() => ({ error: "foo" })'), { 'n': 3 })
        except Exception as activation:
            assert activation['response']['result'] == { 'params': { 'n': 3 }, 'result': { 'error': 'foo' } }

class TestRepeat:

    def test_a_few_iterations(self) :
        activation = invoke(composer.repeat(3, 'DivideByTwo'), { 'n': 8 })
        assert activation['response']['result'] == { 'n': 1 }

    def test_invalid_argument(self) :
        try:
            invoke(composer.repeat('foo'))
            assert False
        except composer.ComposerError as error:
            assert error.message.startswith('Invalid argument')

class TestRetry:

    @pytest.mark.skip(reason='need python conductor')
    def test_success(self) :
        activation = invoke(composer.let({ 'x': 2 }, composer.retry(2, '() => x-- > 0 ? { error: "foo" } : 42')))
        assert activation['response']['result'] == { 'value': 42 }

    @pytest.mark.skip(reason='need python conductor')
    def test_failure(self) :
        try:
            activation = invoke(composer.let({ 'x': 2 }, composer.retry(1, '() => x-- > 0 ? { error: "foo" } : 42')))
            assert False
        except Exception as activation:
            assert activation.error.response.result.error, 'foo'

    def test_invalid_argument(self) :
        try:
            invoke(composer.retry('foo'))
            assert False
        except Exception as error:
            assert error.message.startswith('Invalid argument')