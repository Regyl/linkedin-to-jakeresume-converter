"""Common ArchUnit tests"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from archunitpython import assert_passes, project_files
from archunitpython.files.assertion.custom_file_logic import FileInfo

ROOT = str(Path(__file__).resolve().parents[1])
_SCHEMA_DDL = re.compile(r"\b(ALTER|CREATE)\s+")
_INSERT = re.compile(r"\bINSERT INTO\s+")


def _in_package(file: FileInfo, package: str) -> bool:
    return package in Path(file.path).parts


def _class_defs(file: FileInfo) -> list[ast.ClassDef]:
    return [node for node in ast.walk(ast.parse(file.content)) if isinstance(node, ast.ClassDef)]


def _decorator_name(decorator: ast.expr) -> str | None:
    if isinstance(decorator, ast.Name):
        return decorator.id
    if isinstance(decorator, ast.Attribute):
        return decorator.attr
    if isinstance(decorator, ast.Call):
        return _decorator_name(decorator.func)
    return None


def exceptions_reside_in_exception_package(file: FileInfo) -> bool:
    for node in _class_defs(file):
        if node.name.endswith("Error") and not _in_package(file, "exception"):
            return False
    return True


def dataclasses_reside_in_model_package(file: FileInfo) -> bool:
    for node in _class_defs(file):
        decorated = any(_decorator_name(item) == "dataclass" for item in node.decorator_list)
        if decorated and not _in_package(file, "model"):
            return False
    return True


def _calls_print(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "print"
    if isinstance(func, ast.Attribute) and func.attr == "print":
        return isinstance(func.value, ast.Name) and func.value.id == "builtins"
    return False


def python_files_contain_no_print(file: FileInfo) -> bool:
    tree = ast.parse(file.content)
    return not any(_calls_print(node) for node in ast.walk(tree))


def python_files_contain_no_ddl(file: FileInfo) -> bool:
    if _SCHEMA_DDL.search(file.content):
        return False
    if _INSERT.search(file.content) and not _in_package(file, "repository"):
        return False
    return True


def clients_reside_in_client_package(file: FileInfo) -> bool:
    for node in _class_defs(file):
        if node.name.endswith("Client") and not _in_package(file, "client"):
            return False
    return True


def _is_logging_get_logger(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "logging"
        and node.func.attr == "getLogger"
    )


def _is_module_logger_definition(node: ast.AST) -> bool:
    if not isinstance(node, ast.Assign) or len(node.targets) != 1:
        return False
    target = node.targets[0]
    if not isinstance(target, ast.Name) or target.id != "log":
        return False
    call = node.value
    if not _is_logging_get_logger(call) or call.keywords or len(call.args) != 1:
        return False
    argument = call.args[0]
    return isinstance(argument, ast.Name) and argument.id == "__name__"


def loggers_defined_with_module_name(file: FileInfo) -> bool:
    tree = ast.parse(file.content)
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            if _is_logging_get_logger(child) and not _is_module_logger_definition(node):
                return False
    return True


def test_exceptions_reside_in_exception_package() -> None:
    rule = (
        project_files(ROOT)
        .with_name("*.py")
        .should()
        .adhere_to(
            exceptions_reside_in_exception_package,
            "classes ending with Error reside in the exception package",
        )
    )
    assert_passes(rule)


def test_dataclasses_reside_in_model_package() -> None:
    rule = (
        project_files(ROOT)
        .with_name("*.py")
        .should()
        .adhere_to(
            dataclasses_reside_in_model_package,
            "classes marked with dataclass reside in the model package",
        )
    )
    assert_passes(rule)


def test_python_files_contain_no_print() -> None:
    rule = (
        project_files(ROOT)
        .with_name("*.py")
        .should()
        .adhere_to(
            python_files_contain_no_print,
            "output goes through logging, not print()",
        )
    )
    assert_passes(rule)


def test_python_files_contain_no_ddl() -> None:
    rule = (
        project_files(ROOT)
        .with_name("*.py")
        .should()
        .adhere_to(
            python_files_contain_no_ddl,
            "schema changes live in SQL, and insert statements live in the repository package",
        )
    )
    assert_passes(rule)


def test_clients_reside_in_client_package() -> None:
    rule = (
        project_files(ROOT)
        .with_name("*.py")
        .should()
        .adhere_to(
            clients_reside_in_client_package,
            "classes ending with Client reside in the client package",
        )
    )
    assert_passes(rule)


def test_loggers_defined_with_module_name() -> None:
    rule = (
        project_files(ROOT)
        .with_name("*.py")
        .should()
        .adhere_to(
            loggers_defined_with_module_name,
            "loggers are defined as log = logging.getLogger(__name__)",
        )
    )
    assert_passes(rule)


def _is_util_module(file: FileInfo) -> bool:
    return file.name in {"util", "utils"} or file.name.endswith("_util")


def util_modules_reside_in_util_package(file: FileInfo) -> bool:
    if _is_util_module(file) and not _in_package(file, "util"):
        return False
    return True


def test_util_modules_reside_in_util_package() -> None:
    rule = (
        project_files(ROOT)
        .with_name("*.py")
        .should()
        .adhere_to(
            util_modules_reside_in_util_package,
            "files named util.py, utils.py, or *_util.py reside in the util package",
        )
    )
    assert_passes(rule)
