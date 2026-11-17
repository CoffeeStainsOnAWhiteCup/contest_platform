import pytest

from app.models.models import Language
from app.modules.judge.sandbox.languages import get_language_config


@pytest.mark.parametrize(
    ("language", "filename", "image"),
    [
        (Language.PYTHON, "main.py", "python:3.11-slim"),
        (Language.CPP, "main.cpp", "gcc:13"),
        (Language.JAVA, "Main.java", "eclipse-temurin:17-jdk"),
    ],
)
def test_language_configs(language, filename, image):
    config = get_language_config(language)
    assert config.source_filename == filename
    assert config.image == image
    assert config.compile_command
    assert config.run_command


def test_java_run_command_uses_heap_limit():
    config = get_language_config(Language.JAVA)
    assert "-Xmx" in config.build_run_command(256)


def test_java_container_memory_has_overhead():
    config = get_language_config(Language.JAVA)
    assert config.container_memory_mb(256) > 256
