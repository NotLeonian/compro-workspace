from collections.abc import Sequence
from enum import Enum
from typing import NamedTuple, NewType

VarName = NewType("VarName", str)
Expr = NewType("Expr", str)

class FormatNode: ...

class ItemNode(FormatNode):
    name: VarName
    indices: list[Expr]
    def __init__(self, *, name: str, indices: Sequence[str] = ...) -> None: ...

class NewlineNode(FormatNode): ...

class SequenceNode(FormatNode):
    items: list[FormatNode]
    def __init__(self, *, items: Sequence[FormatNode]) -> None: ...

class LoopNode(FormatNode):
    size: Expr
    name: VarName
    body: FormatNode
    def __init__(self, *, size: str, name: str, body: FormatNode) -> None: ...

class VarType(Enum):
    IndexInt = "IndexInt"
    ValueInt = "ValueInt"
    Float = "Float"
    String = "String"
    Char = "Char"

class VarDecl(NamedTuple):
    name: VarName
    type: VarType | None
    dims: list[Expr]
    bases: list[Expr]
    depending: set[VarName]
