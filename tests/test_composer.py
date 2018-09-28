import composer
import pytest

def check(combinator, n, name=None):
    assert getattr(composer, combinator)(*['foo' for _ in range(n)]).type == name if name is not None else combinator


class TestAction:
    def test_combinator_type(self): 
       assert getattr(composer.action('foo'), 'type') == 'action'
    
    def test_valid_and_invalid_names(self):
        combos = [
            { "n": 42, "s": False, "e": "Name must be a string" },
            { "n": "", "s": False, "e": "Name is not valid" },
            { "n": " ", "s": False, "e": "Name is not valid" },
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
                assert composer.action(combo["n"]).name == combo["s"]
            else:
                # error cases
                try:
                    composer.action(combo["n"])
                    assert False
                except composer.ComposerError as error:
                    assert error.message.startswith(combo["e"])

    def test_valid_and_invalid_options(self):
        composer.action('foo', {})
        try:
            composer.action('foo', 42)
            assert False
        except composer.ComposerError as error:
            assert error.message.startswith('Invalid argument')

class TestComposition:
    def test_combinator_type(self): 
       assert getattr(composer.composition('foo'), 'type') == 'composition'

    def test_valid_and_invalid_names(self):
        combos = [
            { "n": 42, "s": False, "e": "Name must be a string" },
            { "n": "", "s": False, "e": "Name is not valid" },
            { "n": " ", "s": False, "e": "Name is not valid" },
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
                assert composer.composition(combo["n"]).name == combo["s"]
            else:
                # error cases
                try:
                    composer.composition(combo["n"])
                    assert False
                except composer.ComposerError as error:
                    assert error.message.startswith(combo["e"])


class TestFunction:
    def test_check(self):
        check('function', 1)
    
    def test_function(self):
        composer.function(lambda : {})

    def test_string(self):
        composer.function('lambda : {}')

    def test_number_invalid(self):
        try:
            composer.function(42)
        except composer.ComposerError as error:
            assert error.message.startswith('Invalid argument')

class TestLiteral:
    def test_check(self):
        check('literal', 1)
    
    def test_boolean(self):
        composer.literal(True)

    def test_number(self):
        composer.literal(42)
        
    def test_string(self):
        composer.literal('foo')

    def test_dict(self):
        composer.literal({ 'foo':42 })
    
    def test_function_invalid(self):
        try:
            composer.literal(lambda : {})
        except composer.ComposerError as error:
            assert error.message.startswith('Invalid argument')

class TestValue:
    def test_check(self):
        check('value', 1)
    
    def test_boolean(self):
        composer.value(True)

    def test_number(self):
        composer.value(42)
        
    def test_string(self):
        composer.value('foo')

    def test_dict(self):
        composer.value({ 'foo':42 })
    
    def test_function_invalid(self):
        try:
            composer.value(lambda : {})
        except composer.ComposerError as error:
            assert error.message.startswith('Invalid argument')


class TestParse:
    
    def test_combinator_type(self):
        composer.parse({
            'type': 'sequence',
            'components': [{
                'type': 'action',
                'name': 'echo'
            }, {
                'type': 'action',
                'name': 'echo'
            }]
        }).type == 'sequence'
        