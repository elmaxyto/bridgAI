from __future__ import annotations

from pathlib import Path

from local_ai_bridge.core.models import ChangePlan
from local_ai_bridge.services.text_file_lexer import tokenize_text_file_operations
from local_ai_bridge.services.text_file_models import (
    RawBlock,
    TextFileOperation,
    TextFileOperationsDocument,
    TextFileOperationsParseError,
)
from local_ai_bridge.services.text_file_parser import parse_operations_from_tokens
from local_ai_bridge.services.text_file_planner import plan_from_operations

__all__ = [
    "RawBlock",
    "TextFileOperation",
    "TextFileOperationsDocument",
    "TextFileOperationsParseError",
    "inspect_text_file_operations",
    "parse_text_file_operations",
]


def parse_text_file_operations(text: str) -> TextFileOperationsDocument:
    """Parse complete text-file operations while tolerating harmless Markdown wrappers."""
    tokens, ignored_lines = tokenize_text_file_operations(text)
    document = parse_operations_from_tokens(tokens)
    return TextFileOperationsDocument(
        document.operations,
        ignored_lines,
        document.normalizations,
    )


def inspect_text_file_operations(workspace: Path, text: str) -> ChangePlan:
    """Build one reviewable plan from complete text-file operations."""
    return plan_from_operations(workspace, parse_text_file_operations(text))
