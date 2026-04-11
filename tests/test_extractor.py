"""Tests for the function extractor (T-014)."""

import textwrap

from qallm.verification.extractor import extract_functions_from_source


def test_extracts_simple_function():
    source = textwrap.dedent("""\
        def add(a, b):
            return a + b
    """)
    funcs = extract_functions_from_source(source)
    assert len(funcs) == 1
    assert funcs[0].name == "add"
    assert "return a + b" in funcs[0].source


def test_extracts_function_with_docstring():
    source = textwrap.dedent('''\
        def greet(name):
            """Say hello."""
            return f"Hello, {name}"
    ''')
    funcs = extract_functions_from_source(source)
    assert len(funcs) == 1
    assert funcs[0].docstring == "Say hello."


def test_extracts_function_with_type_annotations():
    source = textwrap.dedent("""\
        def divide(a: float, b: float) -> float:
            return a / b
    """)
    funcs = extract_functions_from_source(source)
    assert len(funcs) == 1
    assert ("a", "float") in funcs[0].args
    assert ("b", "float") in funcs[0].args


def test_extracts_multiple_functions():
    source = textwrap.dedent("""\
        def first():
            return 1

        def second():
            return 2

        def third():
            return 3
    """)
    funcs = extract_functions_from_source(source)
    names = [f.name for f in funcs]
    assert names == ["first", "second", "third"]


def test_skips_private_functions():
    source = textwrap.dedent("""\
        def public():
            return 1

        def _private():
            return 2

        def __dunder():
            return 3
    """)
    funcs = extract_functions_from_source(source)
    assert len(funcs) == 1
    assert funcs[0].name == "public"


def test_skips_pass_only_functions():
    source = textwrap.dedent("""\
        def placeholder():
            pass

        def real():
            return 42
    """)
    funcs = extract_functions_from_source(source)
    assert len(funcs) == 1
    assert funcs[0].name == "real"


def test_skips_ellipsis_only_functions():
    source = textwrap.dedent("""\
        def abstract():
            ...

        def concrete():
            return 1
    """)
    funcs = extract_functions_from_source(source)
    assert len(funcs) == 1
    assert funcs[0].name == "concrete"


def test_extracts_class_methods():
    source = textwrap.dedent("""\
        class Calculator:
            def add(self, a, b):
                return a + b

            def subtract(self, a, b):
                return a - b
    """)
    funcs = extract_functions_from_source(source)
    names = [f.name for f in funcs]
    assert "add" in names
    assert "subtract" in names
    # 'self' should be excluded from args
    add_func = next(f for f in funcs if f.name == "add")
    arg_names = [a[0] for a in add_func.args]
    assert "self" not in arg_names


def test_records_lineno():
    source = textwrap.dedent("""\
        # comment

        def on_line_three():
            return True
    """)
    funcs = extract_functions_from_source(source)
    assert funcs[0].lineno == 3


def test_records_filepath():
    source = "def f(): return 1\n"
    funcs = extract_functions_from_source(source, filepath="my_module.py")
    assert funcs[0].filepath == "my_module.py"


def test_handles_syntax_error_gracefully():
    source = "def broken(:\n    return\n"
    funcs = extract_functions_from_source(source)
    assert funcs == []


def test_handles_empty_source():
    funcs = extract_functions_from_source("")
    assert funcs == []


def test_handles_no_functions():
    source = "x = 1\ny = 2\nprint(x + y)\n"
    funcs = extract_functions_from_source(source)
    assert funcs == []


def test_function_with_no_annotation():
    source = textwrap.dedent("""\
        def compute(data):
            return sum(data)
    """)
    funcs = extract_functions_from_source(source)
    assert funcs[0].args == [("data", None)]
