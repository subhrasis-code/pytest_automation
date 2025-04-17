# conftest.py
import pytest
import json

def pytest_addoption(parser):
    parser.addoption(
        "--global_json_file", action="store", default=None, help="Path to global.json config"
    )

@pytest.fixture
def global_config(request):
    path = request.config.getoption("--global_json_file")
    if not path:
        pytest.fail("Missing --global_json_file argument")
    with open(path, 'r') as f:
        return json.load(f)
