from dataclasses import dataclass

from app.core.config import settings
from app.models.models import Language


@dataclass(frozen=True)
class LanguageConfig:
    language: Language
    source_filename: str
    image: str
    compile_command: str | None
    run_command: str
    memory_overhead_mb: int = settings.SANDBOX_MEMORY_OVERHEAD_MB

    def build_run_command(self, memory_limit_mb: int) -> str:
        if self.language == Language.JAVA:
            heap_mb = max(64, memory_limit_mb - 64)
            return self.run_command.format(heap_mb=heap_mb)
        return self.run_command

    def container_memory_mb(self, memory_limit_mb: int) -> int:
        return memory_limit_mb + self.memory_overhead_mb


LANGUAGE_CONFIGS: dict[Language, LanguageConfig] = {
    Language.PYTHON: LanguageConfig(
        language=Language.PYTHON,
        source_filename="main.py",
        image="python:3.11-slim",
        compile_command="python -m py_compile main.py",
        run_command="python main.py",
    ),
    Language.CPP: LanguageConfig(
        language=Language.CPP,
        source_filename="main.cpp",
        image="gcc:13",
        compile_command="g++ -O2 -std=c++17 main.cpp -o main",
        run_command="./main",
    ),
    Language.JAVA: LanguageConfig(
        language=Language.JAVA,
        source_filename="Main.java",
        image="eclipse-temurin:17-jdk",
        compile_command="javac Main.java",
        run_command="java -Xmx{heap_mb}m Main",
        memory_overhead_mb=settings.SANDBOX_JAVA_MEMORY_OVERHEAD_MB,
    ),
}


def get_language_config(language: Language) -> LanguageConfig:
    try:
        return LANGUAGE_CONFIGS[language]
    except KeyError as exc:
        raise ValueError(f"Unsupported language: {language}") from exc
