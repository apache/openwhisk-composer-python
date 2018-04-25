import composer
import pytest

def test_parse_action_name():
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

def test_main():
    composition = composer.sequence("first", "second")
    print(composition)

@pytest.mark.literal
class TestLiteral:

    def test_boolean(self):
        composition = composer.literal(True)
        print(composition)

    def test_number(self):
        composition = composer.literal(42)
        print(composition)

    def test_invalid_arg(self):
        try:
            composer.literal(lambda x:x)
            assert False
        except composer.ComposerError as error:
            assert error.message == 'Invalid argument'

