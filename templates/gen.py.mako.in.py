import importlib
import pathlib
import re
import sys
import textwrap
import unicodedata
from typing import Any

from onlinejudge_template.types import ItemNode, LoopNode, NewlineNode, SequenceNode

WORKSPACE_ROOT = pathlib.Path(r"__WORKSPACE_ROOT__")

TEMPLATES_DIR = WORKSPACE_ROOT / "templates"
_TEMPLATES_DIR_STR = str(TEMPLATES_DIR)
if _TEMPLATES_DIR_STR not in sys.path:
    sys.path.insert(0, _TEMPLATES_DIR_STR)

_utilities: Any = importlib.import_module("utilities")
_bounds_of_name = _utilities.bounds_of_name
_collect_array_names_from_format = _utilities.collect_array_names_from_format
_collect_dimension_mentions = _utilities.collect_dimension_mentions
_collect_item_names = _utilities.collect_item_names
_const_prefix = _utilities.const_prefix
_constraint_text = _utilities.constraint_text
_default_bounds = _utilities.default_bounds
_format_node_to_data = _utilities.format_node_to_data
_format_python_literal = _utilities.format_python_literal
_simple_expr = _utilities.simple_expr
_value_kind = _utilities.value_kind


def _build_constants_and_tables(input_variables, input_format, *, data: dict[str, Any]):
    format_names = _collect_item_names(input_format)
    decls_by_name = {str(name): decl for name, decl in input_variables.items()}
    all_names = list(
        dict.fromkeys(
            [*decls_by_name.keys(), *sorted(format_names - set(decls_by_name))]
        )
    )

    size_like_names = _collect_dimension_mentions(input_variables)
    used_prefixes: set[str] = set()

    constant_lines = [
        "# まず、制約の下限・上限を編集してください。",
        "# なお、問題文から下限・上限を正常に検出できなかった変数については、TODO デフォルト値が使用されています。",
        "#",
        "# Bounds copied from the statement. Edit these constants first when stress-testing.",
        "# For variables whose bounds were not detected, conservative TODO defaults are used.",
    ]
    bounds_entries: list[str] = []
    kind_entries: list[str] = []
    alphabet_entries: list[str] = []

    for name in all_names:
        decl = decls_by_name.get(name)
        kind = _value_kind(decl)
        prefix = _const_prefix(name, used=used_prefixes)
        detected_lo, detected_hi = _bounds_of_name(name, data=data)
        default_lo, default_hi = _default_bounds(
            name, decl, size_like_names=size_like_names
        )

        if kind == "char":
            constant_lines.append(f'{prefix}_ALPHABET = "abcdefghijklmnopqrstuvwxyz"')
            alphabet_entries.append(f"    {name!r}: {prefix}_ALPHABET,")
            bounds_entries.append(f"    {name!r}: (1, 1),")
        elif kind == "string":
            lo = detected_lo if detected_lo is not None else default_lo
            hi = detected_hi if detected_hi is not None else default_hi
            comment_lo = (
                ""
                if detected_lo is not None
                else "  # TODO: length lower bound was not detected"
            )
            comment_hi = (
                ""
                if detected_hi is not None
                else "  # TODO: length upper bound was not detected"
            )
            constant_lines.append(f"{prefix}_LEN_MIN = {lo}{comment_lo}")
            constant_lines.append(f"{prefix}_LEN_MAX = {hi}{comment_hi}")
            constant_lines.append(f'{prefix}_ALPHABET = "abcdefghijklmnopqrstuvwxyz"')
            bounds_entries.append(
                f"    {name!r}: ({prefix}_LEN_MIN, {prefix}_LEN_MAX),"
            )
            alphabet_entries.append(f"    {name!r}: {prefix}_ALPHABET,")
        else:
            lo = detected_lo if detected_lo is not None else default_lo
            hi = detected_hi if detected_hi is not None else default_hi
            comment_lo = (
                ""
                if detected_lo is not None
                else "  # TODO: lower bound was not detected"
            )
            comment_hi = (
                ""
                if detected_hi is not None
                else "  # TODO: upper bound was not detected"
            )
            constant_lines.append(f"{prefix}_MIN = {lo}{comment_lo}")
            constant_lines.append(f"{prefix}_MAX = {hi}{comment_hi}")
            bounds_entries.append(f"    {name!r}: ({prefix}_MIN, {prefix}_MAX),")

        kind_entries.append(f"    {name!r}: {kind!r},")

    constant_lines.append("#")
    constant_lines.append("BOUNDS = {")
    constant_lines.extend(bounds_entries)
    constant_lines.append("}")
    constant_lines.append("#")
    constant_lines.append("VALUE_KINDS = {")
    constant_lines.extend(kind_entries)
    constant_lines.append("}")
    constant_lines.append("#")
    constant_lines.append("ALPHABETS = {")
    constant_lines.extend(alphabet_entries)
    constant_lines.append("}")

    array_names = set()
    array_names |= _collect_array_names_from_format(input_format)
    for name, decl in decls_by_name.items():
        if getattr(decl, "dims", []):
            array_names.add(name)

    return "\n".join(constant_lines), sorted(array_names)


def _has_permutation_signal(text: str, name: str) -> bool:
    normalized = unicodedata.normalize("NFKC", text).lower()
    lowered = name.lower()

    if "permutation" not in normalized and "順列" not in normalized:
        return False

    if lowered in {"p", "perm", "permutation"}:
        return True

    name_pat = re.escape(lowered)
    return (
        re.search(rf"{name_pat}.{{0,80}}permutation", normalized, re.DOTALL) is not None
        or re.search(rf"permutation.{{0,80}}{name_pat}", normalized, re.DOTALL)
        is not None
        or re.search(rf"{name_pat}.{{0,80}}順列", normalized, re.DOTALL) is not None
        or re.search(rf"順列.{{0,80}}{name_pat}", normalized, re.DOTALL) is not None
    )


def _collect_permutation_specials(
    input_variables, *, data: dict[str, Any]
) -> list[dict[str, object]]:
    text = _constraint_text(data)
    specials: list[dict[str, object]] = []

    for name, decl in input_variables.items():
        var_name = str(name)
        dims = list(getattr(decl, "dims", []))
        if len(dims) != 1:
            continue
        if _value_kind(decl) != "int":
            continue
        if not _has_permutation_signal(text, var_name):
            continue

        lower, _upper = _bounds_of_name(var_name, data=data)
        base = lower if lower in (0, 1) else 1
        specials.append(
            {
                "kind": "permutation",
                "name": var_name,
                "size": _simple_expr(dims[0]),
                "base": base,
            }
        )

    return specials


def _strip_minus_one(expr: object) -> str | None:
    text = _simple_expr(expr)
    m = re.fullmatch(r"(.+?)\s*-\s*1", text)
    if m:
        return _simple_expr(m.group(1))
    m = re.fullmatch(r"(.+?)\s*\+\s*-1", text)
    if m:
        return _simple_expr(m.group(1))
    return None


def _flat_items_ignoring_newlines(node) -> list[ItemNode] | None:
    if isinstance(node, ItemNode):
        return [node]
    if isinstance(node, NewlineNode):
        return []
    if isinstance(node, SequenceNode):
        result: list[ItemNode] = []
        for item in node.items:
            xs = _flat_items_ignoring_newlines(item)
            if xs is None:
                return None
            result.extend(xs)
        return result
    return None


def _has_tree_signal(text: str) -> bool:
    normalized = unicodedata.normalize("NFKC", text).lower()
    return "tree" in normalized or "木" in normalized


def _collect_tree_edge_specials(
    node, *, data: dict[str, Any]
) -> list[dict[str, object]]:
    if not _has_tree_signal(_constraint_text(data)):
        return []

    specials: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()

    def visit(cur):
        if isinstance(cur, LoopNode):
            vertices_expr = _strip_minus_one(cur.size)
            items = _flat_items_ignoring_newlines(cur.body)

            if vertices_expr is not None and items is not None and len(items) == 2:
                u = str(items[0].name)
                v = str(items[1].name)
                if u != v:
                    lo_u, _ = _bounds_of_name(u, data=data)
                    lo_v, _ = _bounds_of_name(v, data=data)
                    base = 0 if lo_u == 0 or lo_v == 0 else 1
                    key = (u, v, vertices_expr)
                    if key not in seen:
                        seen.add(key)
                        specials.append(
                            {
                                "kind": "tree_edges",
                                "names": (u, v),
                                "size": vertices_expr,
                                "base": base,
                            }
                        )

            visit(cur.body)

        elif isinstance(cur, SequenceNode):
            for item in cur.items:
                visit(item)

    visit(node)
    return specials


def _has_distinct_signal(text: str, name: str, *, single_candidate: bool) -> bool:
    normalized = unicodedata.normalize("NFKC", text).lower()
    lowered = name.lower()
    signals = [
        "distinct",
        "pairwise different",
        "all different",
        "different integers",
        "互いに異なる",
        "相異なる",
        "すべて異なる",
        "全て異なる",
        "重複しない",
    ]

    if not any(signal in normalized for signal in signals):
        return False

    # 候補となる 1 次元配列が 1 つしかなければ、
    # “all elements are distinct”などの記述は
    # 通常、その配列についての制約である。
    if single_candidate:
        return True

    name_pat = re.escape(lowered)
    for signal in signals:
        signal_pat = re.escape(signal)
        if re.search(rf"{name_pat}.{{0,100}}{signal_pat}", normalized, re.DOTALL):
            return True
        if re.search(rf"{signal_pat}.{{0,100}}{name_pat}", normalized, re.DOTALL):
            return True

    return False


def _collect_distinct_specials(
    input_variables, *, data: dict[str, Any]
) -> list[dict[str, object]]:
    text = _constraint_text(data)
    candidates: list[tuple[str, object]] = []

    for name, decl in input_variables.items():
        var_name = str(name)
        dims = list(getattr(decl, "dims", []))
        if len(dims) != 1:
            continue
        if _value_kind(decl) != "int":
            continue
        candidates.append((var_name, decl))

    specials: list[dict[str, object]] = []
    single_candidate = len(candidates) == 1

    for var_name, decl in candidates:
        if not _has_distinct_signal(text, var_name, single_candidate=single_candidate):
            continue
        specials.append(
            {
                "kind": "distinct",
                "name": var_name,
                "size": _simple_expr(next(iter(getattr(decl, "dims", [])))),
            }
        )

    return specials


def _has_connected_graph_signal(text: str) -> bool:
    normalized = unicodedata.normalize("NFKC", text).lower()
    return any(
        signal in normalized
        for signal in [
            "simple connected graph",
            "connected simple graph",
            "connected undirected graph",
            "connected graph",
            "単純連結グラフ",
            "連結単純グラフ",
            "連結な単純グラフ",
            "連結な単純無向グラフ",
            "単純連結無向グラフ",
            "連結グラフ",
        ]
    )


def _has_dag_signal(text: str) -> bool:
    normalized = unicodedata.normalize("NFKC", text).lower()
    return any(
        signal in normalized
        for signal in [
            "dag",
            "directed acyclic graph",
            "acyclic directed graph",
            "有向非巡回グラフ",
            "非巡回有向グラフ",
            "有向非巡回",
            "非巡回有向",
        ]
    )


def _guess_vertex_count_expr(input_variables) -> str | None:
    scalar_int_names: list[str] = []
    for name, decl in input_variables.items():
        if getattr(decl, "dims", []):
            continue
        if _value_kind(decl) != "int":
            continue
        scalar_int_names.append(str(name))

    normalized = {name.lower(): name for name in scalar_int_names}
    for candidate in [
        "n",
        "v",
        "vertex_count",
        "vertices_count",
        "num_vertices",
        "number_of_vertices",
    ]:
        if candidate in normalized:
            return normalized[candidate]

    for name in scalar_int_names:
        if name.lower().startswith("n"):
            return name

    return scalar_int_names[0] if scalar_int_names else None


def _edge_endpoint_base(names: tuple[str, str], *, data: dict[str, Any]) -> int:
    lower0, _ = _bounds_of_name(names[0], data=data)
    lower1, _ = _bounds_of_name(names[1], data=data)
    return 0 if lower0 == 0 or lower1 == 0 else 1


def _collect_graph_edge_specials(
    input_variables, input_format, *, data: dict[str, Any]
) -> list[dict[str, object]]:
    text = _constraint_text(data)
    is_dag = _has_dag_signal(text)
    is_connected_graph = _has_connected_graph_signal(text)

    if not is_dag and not is_connected_graph:
        return []

    vertex_count_expr = _guess_vertex_count_expr(input_variables)
    if vertex_count_expr is None:
        return []

    specials: list[dict[str, object]] = []
    seen: set[tuple[str, str, str, str]] = set()

    def visit(cur) -> None:
        if isinstance(cur, LoopNode):
            items = _flat_items_ignoring_newlines(cur.body)
            if items is not None and len(items) == 2:
                u = str(items[0].name)
                v = str(items[1].name)
                if u != v:
                    names = (u, v)
                    kind = "dag_edges" if is_dag else "simple_connected_graph_edges"
                    edge_count_expr = _simple_expr(cur.size)
                    key = (kind, u, v, edge_count_expr)
                    if key not in seen:
                        seen.add(key)
                        specials.append(
                            {
                                "kind": kind,
                                "names": names,
                                "size": vertex_count_expr,
                                "edges": edge_count_expr,
                                "base": _edge_endpoint_base(names, data=data),
                            }
                        )

            visit(cur.body)

        elif isinstance(cur, SequenceNode):
            for item in cur.items:
                visit(item)

    visit(input_format)
    return specials


def _collect_specials(
    input_variables, input_format, *, data: dict[str, Any]
) -> list[dict[str, object]]:
    return [
        *_collect_permutation_specials(input_variables, data=data),
        *_collect_distinct_specials(input_variables, data=data),
        *_collect_tree_edge_specials(input_format, data=data),
        *_collect_graph_edge_specials(input_variables, input_format, data=data),
    ]


_GENERATED_RUNTIME = (TEMPLATES_DIR / "gen.py").read_text(encoding="utf-8")


def _fallback_source(message: str) -> str:
    return textwrap.dedent(
        f"""\
        #!/usr/bin/env python3
        # {message}
        # The input format was not analyzed.  Edit this file manually.
        #
        import random

        rng = random.Random()

        def main():
            # TODO: write random input generation here.
            pass

        if __name__ == "__main__":
            main()
        """
    )


def _build_gen_py(data: dict[str, Any], *, logger) -> str:
    try:
        analyzed = data.get("analyzed")
        input_format = getattr(analyzed, "input_format", None)
        input_variables = getattr(analyzed, "input_variables", None)

        if input_format is None or input_variables is None:
            return _fallback_source("failed to analyze input format")

        format_data = _format_node_to_data(input_format)
        constants, array_names = _build_constants_and_tables(
            input_variables,
            input_format,
            data=data,
        )
        specials = _collect_specials(input_variables, input_format, data=data)

        source = "\n".join(
            [
                "#!/usr/bin/env python3",
                "#",
                "# 最初に制約と `SPECIALS` を編集し、必要に応じて`random_value()` も編集してください。",
                "# Edit constants and `SPECIALS` first, then tune `random_value()` if needed.",
                "#",
                f"FORMAT = {_format_python_literal(format_data)}",
                f"ARRAY_NAMES = set({_format_python_literal(array_names)})",
                "#",
                constants,
                "#",
                "# 以下の特殊な入力生成器も、自由に編集できます。",
                "# Auto-detected coordinated generators. Edit this list freely.",
                "#",
                "# 以下の特殊な制約をサポートしています。",
                "# Supported kinds / examples:",
                "#   {\"kind\": \"permutation\", \"name\": \"P\", \"size\": \"N\", \"base\": 1}",
                "#   {\"kind\": \"distinct\", \"name\": \"A\", \"size\": \"N\", \"lo\": 0, \"hi\": 100}",
                "#   {\"kind\": \"sum\", \"name\": \"A\", \"size\": \"N\", \"target_name\": \"S\", \"target\": \"S\", \"lo\": 0, \"hi\": 10}",
                "#   {\"kind\": \"sum\", \"name\": \"A\", \"size\": \"N\", \"max_sum\": \"X\", \"lo\": 0, \"hi\": 10}",
                "#   {\"kind\": \"product\", \"name\": \"A\", \"size\": \"N\", \"max_product\": \"X\", \"lo\": 1, \"hi\": 10}",
                "#   {\"kind\": \"tree_edges\", \"names\": (\"U\", \"V\"), \"size\": \"N\", \"base\": 1}",
                "#   {\"kind\": \"simple_connected_graph_edges\", \"names\": (\"U\", \"V\"), \"size\": \"N\", \"edges\": \"M\", \"base\": 1}",
                "#   {\"kind\": \"dag_edges\", \"names\": (\"U\", \"V\"), \"size\": \"N\", \"edges\": \"M\", \"base\": 1}",
                "#",
                "# 現在、\"product\" では各要素が正の整数であることを前提としています。",
                "# Product constraints currently assume positive integer elements.",
                "#",
                f"SPECIALS = {_format_python_literal(specials)}",
                "#",
                _GENERATED_RUNTIME.strip(),
                "#",
            ]
        )

        return source
    except Exception:
        logger.exception("failed to generate gen.py")
        return _fallback_source("failed to generate gen.py")
