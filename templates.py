import jinja2


pytest_template = '''
import pytest

{% for test in tests %}
{{ test.import_str }}
{% endfor %}

{% for test in tests %}
def test_{{test.func_name}}_normal():

{% for case in test.ok %}
    {{ case }}
{% endfor %}

{% if test.errors %}
def test_{{test.func_name}}_errors():

{% for case in test.errors %}
    with pytest.raises({{case.error_name}}):
        {{ case.body }}
{% endfor %}
{% endif %}

{% endfor %}
'''

env = jinja2.Environment(
    trim_blocks=True
)

templates = {
    "pytest": env.from_string(pytest_template),
}

def format_tests(tests, framework="pytest"):
    return templates[framework].render(tests=tests)

