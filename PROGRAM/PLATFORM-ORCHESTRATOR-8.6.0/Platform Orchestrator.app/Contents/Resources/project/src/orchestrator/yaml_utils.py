"""Fail-closed YAML loading helpers.

PyYAML's default SafeLoader silently accepts duplicate mapping keys and keeps the
last value. Configuration/manifests are security- and behavior-sensitive, so a
duplicate key is treated as a configuration error instead.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class DuplicateYAMLKeyError(ValueError):
    """Raised when a YAML mapping contains the same key more than once."""


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_mapping(loader: _UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
    if not isinstance(node, yaml.MappingNode):
        raise yaml.constructor.ConstructorError(None, None, "expected a mapping", node.start_mark)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise DuplicateYAMLKeyError(f"unhashable YAML mapping key at {key_node.start_mark}") from exc
        if duplicate:
            line = key_node.start_mark.line + 1
            col = key_node.start_mark.column + 1
            raise DuplicateYAMLKeyError(
                f"duplicate YAML key {key!r} at line {line}, column {col}"
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


def load_unique_yaml_text(text: str, *, source: str = "<string>") -> Any:
    """Load YAML and reject duplicate mapping keys."""
    try:
        return yaml.load(text, Loader=_UniqueKeyLoader)
    except DuplicateYAMLKeyError as exc:
        raise DuplicateYAMLKeyError(f"{source}: {exc}") from exc


def load_unique_yaml(path: str | Path) -> Any:
    """Read a YAML file and reject duplicate mapping keys."""
    p = Path(path)
    return load_unique_yaml_text(p.read_text(encoding="utf-8"), source=str(p))
