import ast
import html as html_lib
import pprint
import re
import unicodedata
from typing import Any

from onlinejudge_template.types import ItemNode, LoopNode, NewlineNode, SequenceNode


def outer_parentheses_wrap_whole_expr(text: str) -> bool:
    text = text.strip()

    if len(text) < 2:
        return False

    if text[0] != "(" or text[-1] != ")":
        return False

    depth = 0
    for i, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False
            if depth == 0:
                return i == len(text) - 1

    return False


def simple_expr(expr: object) -> str:
    text = str(expr).strip()
    while outer_parentheses_wrap_whole_expr(text):
        text = text[1:-1].strip()
    return text


def normalize_constraints(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)

    replacements = {
        "\\leqq": "<=",
        "\\leq": "<=",
        "\\le": "<=",
        "≤": "<=",
        "≦": "<=",
        "\\geqq": ">=",
        "\\geq": ">=",
        "\\ge": ">=",
        "≥": ">=",
        "≧": ">=",
        "\\lt": "<",
        "\\gt": ">",
        "\\times": "*",
        "\\cdot": "*",
        "×": "*",
        "⋅": "*",
        "·": "*",
        "−": "-",
    }

    for old, new in replacements.items():
        s = s.replace(old, new)

    # 1,000,000 -> 1000000
    s = re.sub(r"(?<=\d),(?=\d)", "", s)

    # 2e5 -> 2*10^5
    s = re.sub(r"([0-9]+)\s*[eE]\s*\+?\s*([0-9]+)", r"\1*10^\2", s)

    # 10^{18}, 10^(18) -> 10^18
    s = re.sub(r"([0-9]+)\s*\^\s*\{\s*([+-]?[0-9]+)\s*\}", r"\1^\2", s)
    s = re.sub(r"([0-9]+)\s*\^\s*\(\s*([+-]?[0-9]+)\s*\)", r"\1^\2", s)

    s = s.replace("$", " ")
    return s


def normalize_for_testcase_signal(s: str) -> str:
    s = normalize_constraints(s)
    s = unicodedata.normalize("NFKC", s)

    s = s.replace("\\(", " ")
    s = s.replace("\\)", " ")
    s = s.replace("\\[", " ")
    s = s.replace("\\]", " ")
    s = s.replace("$", " ")

    s = re.sub(
        r"\\(?:mathrm|mathit|mathbf|mathsf|mathtt|text)\s*\{\s*([^{}]+?)\s*\}",
        r"\1",
        s,
    )

    s = s.replace("{", " ")
    s = s.replace("}", " ")
    s = re.sub(r"\\[,;:! ]", " ", s)
    s = re.sub(r"\\[A-Za-z]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.lower()


def math_var_pattern(name: str) -> str:
    name = re.escape(name.lower())
    return rf"(?<![a-z0-9_]){name}(?![a-z0-9_])"


def inline_text_from_html(s: str) -> str:
    # Don't remove inequality signs
    s = re.sub(r"(?is)</?[A-Za-z][A-Za-z0-9:-]*(?:\s[^<>]*)?>", "", s)
    return html_lib.unescape(s).strip()


def html_to_text(s: str) -> str:
    s = re.sub(r"(?is)<script\b.*?</script>", " ", s)
    s = re.sub(r"(?is)<style\b.*?</style>", " ", s)

    # A<sub>i</sub> -> A_{i}
    s = re.sub(
        r"(?is)<sub\b[^>]*>(.*?)</sub>",
        lambda m: "_{" + inline_text_from_html(m.group(1)) + "}",
        s,
    )

    # 10<sup>9</sup> -> 10^{9}
    s = re.sub(
        r"(?is)<sup\b[^>]*>(.*?)</sup>",
        lambda m: "^{" + inline_text_from_html(m.group(1)) + "}",
        s,
    )

    s = re.sub(
        r"(?is)</?(?:li|p|div|tr|br|h[1-6]|section|ul|ol|table|tbody|thead|td|th)[^>]*>",
        "\n",
        s,
    )

    s = re.sub(r"(?is)</?[A-Za-z][A-Za-z0-9:-]*(?:\s[^<>]*)?>", " ", s)
    return html_lib.unescape(s)


def decode_maybe_bytes(x: object) -> str:
    if x is None:
        return ""

    if isinstance(x, bytes):
        for enc in ("utf-8", "utf-8-sig", "cp932"):
            try:
                return x.decode(enc)
            except UnicodeDecodeError:
                pass
        return x.decode("utf-8", errors="ignore")

    return str(x)


def constraint_text(data: dict[str, Any]) -> str:
    analyzed = data.get("analyzed")
    resources = getattr(analyzed, "resources", None)

    chunks: list[str] = []
    if resources is not None:
        html = decode_maybe_bytes(getattr(resources, "html", None))
        if html:
            chunks.append(html_to_text(html))

        for attr in ("input_format_string", "output_format_string"):
            text = decode_maybe_bytes(getattr(resources, attr, None))
            if text:
                chunks.append(text)

    return "\n".join(chunks)


def eval_int_expr(expr: str) -> int | None:
    expr = normalize_constraints(expr)
    expr = expr.replace("^", "**")
    expr = expr.strip()

    if not expr:
        return None

    if not re.fullmatch(r"[0-9+\-*/().\s*]+", expr):
        return None

    try:
        root = ast.parse(expr, mode="eval")
    except SyntaxError:
        return None

    def visit(node: ast.AST) -> int | None:
        if isinstance(node, ast.Expression):
            return visit(node.body)

        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return int(node.value)

        if isinstance(node, ast.UnaryOp):
            value = visit(node.operand)
            if value is None:
                return None
            if isinstance(node.op, ast.UAdd):
                return value
            if isinstance(node.op, ast.USub):
                return -value
            return None

        if isinstance(node, ast.BinOp):
            lhs = visit(node.left)
            rhs = visit(node.right)
            if lhs is None or rhs is None:
                return None

            if isinstance(node.op, ast.Add):
                return lhs + rhs
            if isinstance(node.op, ast.Sub):
                return lhs - rhs
            if isinstance(node.op, ast.Mult):
                return lhs * rhs
            if isinstance(node.op, ast.Pow):
                if rhs < 0 or rhs > 100:
                    return None
                return lhs**rhs
            if isinstance(node.op, ast.FloorDiv):
                if rhs == 0:
                    return None
                return lhs // rhs
            if isinstance(node.op, ast.Div):
                if rhs == 0 or lhs % rhs != 0:
                    return None
                return lhs // rhs

        return None

    value = visit(root)
    if value is None:
        return None

    # Insurance against too long expressions
    if abs(value) > 10**100:
        return None

    return value


def inclusive_lower_bound(expr: str, *, strict: bool) -> int | None:
    value = eval_int_expr(expr)
    if value is None:
        return None
    return value + 1 if strict else value


def inclusive_upper_bound(expr: str, *, strict: bool) -> int | None:
    value = eval_int_expr(expr)
    if value is None:
        return None
    return value - 1 if strict else value


_NUM_EXPR = r"[-+]?\s*\d[\d\s+\-*/^().]*"
_VAR_TOKEN = (
    r"[A-Za-z][A-Za-z0-9]*"
    r"(?:\s*_\s*(?:\{[^{}]+\}|[A-Za-z0-9]+(?:\s*,\s*[A-Za-z0-9]+)*))?"
)
_VAR_LIST = rf"{_VAR_TOKEN}(?:\s*,\s*{_VAR_TOKEN})*"

_RANGE_RE = re.compile(
    rf"(?P<lower>{_NUM_EXPR})\s*(?P<lower_op><=|<)\s*"
    rf"(?P<vars>{_VAR_LIST})\s*(?P<upper_op><=|<)\s*"
    rf"(?P<upper>{_NUM_EXPR})"
)
_RIGHT_UPPER_RE = re.compile(
    rf"(?P<vars>{_VAR_LIST})\s*(?P<op><=|<)\s*(?P<upper>{_NUM_EXPR})"
)
_RIGHT_LOWER_RE = re.compile(
    rf"(?P<vars>{_VAR_LIST})\s*(?P<op>>=|>)\s*(?P<lower>{_NUM_EXPR})"
)
_LEFT_UPPER_RE = re.compile(
    rf"(?P<upper>{_NUM_EXPR})\s*(?P<op>>=|>)\s*(?P<vars>{_VAR_LIST})"
)
_LEFT_LOWER_RE = re.compile(
    rf"(?P<lower>{_NUM_EXPR})\s*(?P<op><=|<)\s*(?P<vars>{_VAR_LIST})"
)
_ABS_BAR_RE = re.compile(
    rf"\|\s*(?P<vars>{_VAR_LIST})\s*\|\s*(?P<op><=|<)\s*(?P<upper>{_NUM_EXPR})"
)
_ABS_FUNC_RE = re.compile(
    rf"abs\s*\(\s*(?P<vars>{_VAR_LIST})\s*\)\s*(?P<op><=|<)\s*(?P<upper>{_NUM_EXPR})",
    re.IGNORECASE,
)


def _previous_non_space(text: str, pos: int) -> str | None:
    i = pos - 1
    while i >= 0 and text[i].isspace():
        i -= 1
    return text[i] if i >= 0 else None


def _next_non_space(text: str, pos: int) -> str | None:
    i = pos
    while i < len(text) and text[i].isspace():
        i += 1
    return text[i] if i < len(text) else None


def _is_ascii_identifier_char(ch: str) -> bool:
    return ch == "_" or "0" <= ch <= "9" or "A" <= ch <= "Z" or "a" <= ch <= "z"


_NUMERIC_BOUND_FORBIDDEN_LEFT_CHARS = ")]}+-*/^"
_NUMERIC_BOUND_FORBIDDEN_RIGHT_CHARS = "([{"


def _numeric_bound_group_is_standalone(
    line: str,
    match: re.Match[str],
    group_name: str,
) -> bool:
    """
    Return False when a numeric regex group is
    only a suffix/prefix of a larger symbolic expression.
    """

    start, end = match.span(group_name)
    if start < 0 or end < 0:
        return False

    previous = _previous_non_space(line, start)
    if previous is not None and (
        _is_ascii_identifier_char(previous)
        or previous in _NUMERIC_BOUND_FORBIDDEN_LEFT_CHARS
    ):
        return False

    following = _next_non_space(line, end)
    return not (
        following is not None
        and (
            _is_ascii_identifier_char(following)
            or following in _NUMERIC_BOUND_FORBIDDEN_RIGHT_CHARS
        )
    )


def _numeric_bound_groups_are_standalone(
    line: str,
    match: re.Match[str],
    *group_names: str,
) -> bool:
    return all(
        _numeric_bound_group_is_standalone(line, match, group_name)
        for group_name in group_names
    )


def split_var_list(s: str) -> list[str]:
    result: list[str] = []
    depth = 0
    start = 0

    for i, ch in enumerate(s):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            result.append(s[start:i].strip())
            start = i + 1

    result.append(s[start:].strip())
    return [x for x in result if x]


def constraint_keys_from_token(token: str) -> set[str]:
    token = unicodedata.normalize("NFKC", token)
    token = re.sub(r"\s+", "", token)
    token = token.replace("{", "").replace("}", "")

    keys = {token}

    # For arrays: A_i, A_{i}, A_{i,j} -> also A
    m = re.fullmatch(r"([A-Za-z][A-Za-z0-9]*)(?:_.*)?", token)
    if m:
        keys.add(m.group(1))

    return keys


BoundsMap = dict[str, dict[str, int | None]]


def ensure_bound_record(bounds: BoundsMap, key: str) -> dict[str, int | None]:
    if key not in bounds:
        bounds[key] = {"lower": None, "upper": None}
    return bounds[key]


def add_lower_bound(bounds: BoundsMap, vars_text: str, lower: int | None) -> None:
    if lower is None:
        return

    for token in split_var_list(vars_text):
        for key in constraint_keys_from_token(token):
            record = ensure_bound_record(bounds, key)
            old = record["lower"]
            if old is None or lower > old:
                record["lower"] = lower


def add_upper_bound(bounds: BoundsMap, vars_text: str, upper: int | None) -> None:
    if upper is None:
        return

    for token in split_var_list(vars_text):
        for key in constraint_keys_from_token(token):
            record = ensure_bound_record(bounds, key)
            old = record["upper"]
            if old is None or upper < old:
                record["upper"] = upper


def collect_bounds(data: dict[str, Any]) -> BoundsMap:
    cache = data.setdefault("__compro_template_utilities_cache__", {})
    if "bounds" in cache:
        return cache["bounds"]

    text = normalize_constraints(constraint_text(data))
    bounds: BoundsMap = {}

    for line in re.split(r"[\n;。]+", text):
        line = line.strip()
        if not line:
            continue

        # |X_i| <= 10^9
        # abs(X_i) <= 10^9
        for pattern in (_ABS_BAR_RE, _ABS_FUNC_RE):
            for m in pattern.finditer(line):
                if not _numeric_bound_groups_are_standalone(line, m, "upper"):
                    continue

                upper = inclusive_upper_bound(
                    m.group("upper"),
                    strict=(m.group("op") == "<"),
                )
                if upper is None:
                    continue
                add_upper_bound(bounds, m.group("vars"), upper)
                add_lower_bound(bounds, m.group("vars"), -upper)

        # 1 <= N <= 2 * 10^5
        # -10^18 <= X <= 10
        for m in _RANGE_RE.finditer(line):
            if not _numeric_bound_groups_are_standalone(line, m, "lower", "upper"):
                continue

            lower = inclusive_lower_bound(
                m.group("lower"),
                strict=(m.group("lower_op") == "<"),
            )
            upper = inclusive_upper_bound(
                m.group("upper"),
                strict=(m.group("upper_op") == "<"),
            )
            add_lower_bound(bounds, m.group("vars"), lower)
            add_upper_bound(bounds, m.group("vars"), upper)

        # X <= 10^9
        # A_i < 10^7
        for m in _RIGHT_UPPER_RE.finditer(line):
            if not _numeric_bound_groups_are_standalone(line, m, "upper"):
                continue

            upper = inclusive_upper_bound(
                m.group("upper"),
                strict=(m.group("op") == "<"),
            )
            add_upper_bound(bounds, m.group("vars"), upper)

        # X >= -10^9
        # X > -10^9
        for m in _RIGHT_LOWER_RE.finditer(line):
            if not _numeric_bound_groups_are_standalone(line, m, "lower"):
                continue

            lower = inclusive_lower_bound(
                m.group("lower"),
                strict=(m.group("op") == ">"),
            )
            add_lower_bound(bounds, m.group("vars"), lower)

        # 10^9 >= X
        # 10^7 > A_i
        for m in _LEFT_UPPER_RE.finditer(line):
            if not _numeric_bound_groups_are_standalone(line, m, "upper"):
                continue

            upper = inclusive_upper_bound(
                m.group("upper"),
                strict=(m.group("op") == ">"),
            )
            add_upper_bound(bounds, m.group("vars"), upper)

        # -10^9 <= X
        # -10^9 < X
        for m in _LEFT_LOWER_RE.finditer(line):
            if not _numeric_bound_groups_are_standalone(line, m, "lower"):
                continue

            lower = inclusive_lower_bound(
                m.group("lower"),
                strict=(m.group("op") == "<"),
            )
            add_lower_bound(bounds, m.group("vars"), lower)

    cache["bounds"] = bounds
    return bounds


def bounds_of_name(name: str, *, data: dict[str, Any]) -> tuple[int | None, int | None]:
    bounds = collect_bounds(data)
    lower: int | None = None
    upper: int | None = None

    for key in constraint_keys_from_token(name):
        record = bounds.get(key)
        if record is None:
            continue

        candidate_lower = record.get("lower")
        candidate_upper = record.get("upper")
        if candidate_lower is not None and (lower is None or candidate_lower > lower):
            lower = candidate_lower
        if candidate_upper is not None and (upper is None or candidate_upper < upper):
            upper = candidate_upper

    return lower, upper


def bounds_of_decl(decl, *, data: dict[str, Any]) -> tuple[int | None, int | None]:
    return bounds_of_name(str(decl.name), data=data)


def value_kind(decl: object | None) -> str:
    if decl is None:
        return "int"

    type_text = str(getattr(decl, "type", "")).lower()
    if "string" in type_text:
        return "string"
    if "char" in type_text:
        return "char"
    if "float" in type_text:
        return "float"
    return "int"


def collect_item_names(node) -> set[str]:
    if isinstance(node, ItemNode):
        return {str(node.name)}
    if isinstance(node, LoopNode):
        return collect_item_names(node.body)
    if isinstance(node, SequenceNode):
        result: set[str] = set()
        for item in node.items:
            result |= collect_item_names(item)
        return result
    return set()


def collect_array_names_from_format(node) -> set[str]:
    if isinstance(node, ItemNode):
        return {str(node.name)} if node.indices else set()
    if isinstance(node, LoopNode):
        return collect_array_names_from_format(node.body)
    if isinstance(node, SequenceNode):
        result: set[str] = set()
        for item in node.items:
            result |= collect_array_names_from_format(item)
        return result
    return set()


def collect_dimension_mentions(input_variables) -> set[str]:
    names = {str(name) for name in input_variables}
    mentioned: set[str] = set()

    for decl in input_variables.values():
        for dim in getattr(decl, "dims", []):
            text = simple_expr(dim)
            for name in names:
                if re.search(
                    rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])",
                    text,
                ):
                    mentioned.add(name)

    return mentioned


def format_node_to_data(node):
    if isinstance(node, ItemNode):
        return (
            "item",
            str(node.name),
            [simple_expr(index) for index in node.indices],
        )
    if isinstance(node, NewlineNode):
        return ("newline",)
    if isinstance(node, SequenceNode):
        return ("seq", [format_node_to_data(item) for item in node.items])
    if isinstance(node, LoopNode):
        return (
            "loop",
            str(node.name),
            simple_expr(node.size),
            format_node_to_data(node.body),
        )
    raise TypeError(f"unsupported input format node: {type(node).__name__}")


def default_bounds(
    name: str,
    decl: object | None,
    *,
    size_like_names: set[str],
) -> tuple[int, int]:
    kind = value_kind(decl)
    if kind in {"string", "char"}:
        return 1, 10
    if name in size_like_names:
        return 1, 10
    return 0, 10


def const_prefix(name: str, *, used: set[str]) -> str:
    base = re.sub(r"[^A-Za-z0-9_]", "_", name).upper().strip("_") or "X"
    if re.match(r"[0-9]", base):
        base = "_" + base

    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}_{suffix}"
        suffix += 1

    used.add(candidate)
    return candidate


def format_python_literal(obj) -> str:
    return pprint.pformat(obj, width=88, sort_dicts=False)
