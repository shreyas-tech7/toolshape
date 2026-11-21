"""The tool shapes. Each one exposes the same TaskDesk capabilities with a different tool design."""

from .base import Shape, ToolResult
from .shape_a import ShapeA
from .shape_b import ShapeB
from .shape_c import ShapeC

SHAPES = {"A": ShapeA, "B": ShapeB, "C": ShapeC}


def make_shape(key: str, api_url: str) -> Shape:
    return SHAPES[key](api_url)


__all__ = ["SHAPES", "Shape", "ShapeA", "ShapeB", "ShapeC", "ToolResult", "make_shape"]
