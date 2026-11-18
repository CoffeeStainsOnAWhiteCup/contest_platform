import uuid

import docker
import pytest

from app.models.models import Language
from app.modules.judge.sandbox.languages import get_language_config
from app.modules.judge.sandbox.runner import SandboxOutputLimitExceeded, SandboxSession

pytestmark = pytest.mark.docker


@pytest.fixture(scope="module", autouse=True)
def require_docker():
    try:
        client = docker.from_env()
        client.ping()
        client.close()
    except Exception as exc:
        pytest.skip(f"Docker is unavailable: {exc}")


def run_code(language: Language, code: str, input_data: str, *, time_limit_ms=1000, memory_limit_mb=128):
    config = get_language_config(language)
    with SandboxSession(uuid.uuid4(), config, time_limit_ms, memory_limit_mb) as session:
        compiled, stdout, stderr = session.compile(code)
        return compiled, stdout, stderr, session.run_test(input_data)


def test_python_accepted():
    compiled, _, _, execution = run_code(
        Language.PYTHON,
        "a, b = map(int, input().split())\nprint(a + b)\n",
        "1 2\n",
    )
    assert compiled
    assert execution.exit_code == 0
    assert execution.stdout.strip() == "3"
    assert execution.memory_kb is not None


def test_cpp_accepted():
    code = (
        "#include <iostream>\n"
        "int main(){int a,b;std::cin>>a>>b;std::cout<<a+b<<std::endl;}\n"
    )
    compiled, _, _, execution = run_code(Language.CPP, code, "1 2\n")
    assert compiled
    assert execution.exit_code == 0
    assert execution.stdout.strip() == "3"


def test_java_accepted():
    code = (
        "import java.util.Scanner;\n"
        "public class Main {\n"
        "  public static void main(String[] args) {\n"
        "    Scanner sc = new Scanner(System.in);\n"
        "    System.out.println(sc.nextInt() + sc.nextInt());\n"
        "  }\n"
        "}\n"
    )
    compiled, _, _, execution = run_code(Language.JAVA, code, "1 2\n")
    assert compiled
    assert execution.exit_code == 0
    assert execution.stdout.strip() == "3"


def test_cpp_compile_error():
    compiled, _, stderr, _ = run_code(Language.CPP, "int main( {\n", "")
    assert not compiled
    assert stderr


def test_python_time_limit():
    _, _, _, execution = run_code(
        Language.PYTHON,
        "while True:\n    pass\n",
        "",
        time_limit_ms=300,
    )
    assert execution.timed_out


def test_python_runtime_error():
    _, _, _, execution = run_code(
        Language.PYTHON,
        "raise RuntimeError('boom')\n",
        "",
    )
    assert execution.exit_code != 0
    assert "boom" in execution.stderr


def test_python_output_limit_is_enforced():
    code = (
        "import sys\n"
        "while True:\n"
        "    sys.stdout.write('x' * 4096)\n"
        "    sys.stdout.flush()\n"
    )
    with pytest.raises(SandboxOutputLimitExceeded):
        run_code(Language.PYTHON, code, "", time_limit_ms=5000)


def test_network_is_disabled():
    _, _, _, execution = run_code(
        Language.PYTHON,
        "import socket\nsocket.create_connection(('1.1.1.1', 80), timeout=1)\nprint('ok')\n",
        "",
    )
    assert execution.exit_code != 0
    assert execution.stdout.strip() != "ok"


def test_python_memory_limit():
    _, _, _, execution = run_code(
        Language.PYTHON,
        "x = bytearray(300 * 1024 * 1024)\nprint(len(x))\n",
        "",
        time_limit_ms=3000,
        memory_limit_mb=64,
    )
    assert execution.exit_code != 0 or execution.timed_out
