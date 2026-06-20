import ast
import pathlib
import re
import sys
from typing import Any

import onlinejudge_template.generator.cplusplus as cplusplus
from onlinejudge_template.types import (
    Expr,
    ItemNode,
    LoopNode,
    NewlineNode,
    SequenceNode,
    VarDecl,
    VarName,
    VarType,
)
from utilities import (
    bounds_of_decl as _bounds_of_decl,
)
from utilities import (
    constraint_text as _constraint_text,
)
from utilities import (
    math_var_pattern as _math_var_pattern,
)
from utilities import (
    normalize_for_testcase_signal as _normalize_for_testcase_signal,
)
from utilities import (
    simple_expr as _simple_expr,
)

WORKSPACE_ROOT = pathlib.Path(r"__WORKSPACE_ROOT__")
BASE_TEMPLATE = WORKSPACE_ROOT / "templates" / "main.cpp"
CLANG_FORMAT = WORKSPACE_ROOT / ".clang-format"

TEMPLATES_DIR = WORKSPACE_ROOT / "templates"
if str(TEMPLATES_DIR) not in sys.path:
    sys.path.insert(0, str(TEMPLATES_DIR))

_CASE_COUNT_NAMES = {
    "t",
    "tc",
    "tt",
    "test",
    "tests",
    "testcase",
    "testcases",
    "test_case",
    "test_cases",
    "case_count",
    "cases_count",
    "num_cases",
    "num_testcases",
    "num_test_cases",
    "number_of_cases",
    "number_of_testcases",
    "number_of_test_cases",
    "n_cases",
    "n_tests",
}

_STRONG_CASE_COUNT_NAMES = {
    "testcase",
    "testcases",
    "test_case",
    "test_cases",
    "case_count",
    "cases_count",
    "num_cases",
    "num_testcases",
    "num_test_cases",
    "number_of_cases",
    "number_of_testcases",
    "number_of_test_cases",
    "n_cases",
    "n_tests",
}


def _scanner(exprs):
    expr_list = [str(expr) for expr, _ in exprs]
    if not expr_list:
        return []
    return [f"::in({', '.join(expr_list)});"]


def _normalize_identifier_name(name: object) -> str:
    s = str(name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    s = re.sub(r"[^A-Za-z0-9]+", "_", s)
    return s.strip("_").lower()


def _is_case_count_name(name: object) -> bool:
    return _normalize_identifier_name(name) in _CASE_COUNT_NAMES


def _is_strong_case_count_name(name: object) -> bool:
    return _normalize_identifier_name(name) in _STRONG_CASE_COUNT_NAMES


_BRACED_SUBSCRIPT_RE = re.compile(
    r"\b(?P<base>[A-Za-z_][A-Za-z0-9_]*)_\{(?P<subscript>[^{}]+)\}"
)


def _split_subscript_list(text: str) -> list[str]:
    result: list[str] = []
    depth = 0
    start = 0

    for i, ch in enumerate(text):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            result.append(text[start:i].strip())
            start = i + 1

    result.append(text[start:].strip())
    return [part for part in result if part]


def _subscript_suffix_name(text: str) -> str:
    text = _simple_expr(text)
    text = re.sub(r"\s+", "", text)

    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text):
        return text

    text = re.sub(r"[^A-Za-z0-9_]+", "_", text).strip("_")
    return text or "idx"


def _strip_braced_case_subscripts(text: str, *, counter: str) -> str:
    def replace(match: re.Match[str]) -> str:
        base = match.group("base")
        subscripts = _split_subscript_list(match.group("subscript"))

        if not subscripts:
            return match.group(0)

        if _is_testcase_index_expr(subscripts[0], counter=counter):
            rest = subscripts[1:]

            if not rest:
                return base

            return (
                base
                + "_"
                + "_".join(_subscript_suffix_name(subscript) for subscript in rest)
            )

        return match.group(0)

    return _BRACED_SUBSCRIPT_RE.sub(replace, text)


def _transform_expr(expr: object, *, counter: str) -> Expr:
    text = _simple_expr(expr)
    text = _strip_braced_case_subscripts(text, counter=counter)
    escaped_counter = re.escape(counter)
    text = re.sub(
        rf"\b([A-Za-z_]\w*)_\{{\s*{escaped_counter}\s*\}}(?=\b|_)",
        r"\1",
        text,
    )
    text = re.sub(
        rf"\b([A-Za-z_]\w*)_{escaped_counter}(?=\b|_)",
        r"\1",
        text,
    )
    return Expr(text)


def _transform_name(name: object, *, counter: str) -> str:
    return str(_transform_expr(name, counter=counter))


def _affine_counter_expr(expr: object, *, counter: str):
    """
    expr が counter + 定数 の形なら (1, 定数) を返す
    それ以外なら None を返す
    """
    text = _simple_expr(expr)

    try:
        node = ast.parse(text, mode="eval").body
    except SyntaxError:
        return None

    def visit(node):
        if isinstance(node, ast.Name):
            if node.id == counter:
                return 1, 0
            return None

        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return 0, node.value

        if isinstance(node, ast.UnaryOp):
            value = visit(node.operand)
            if value is None:
                return None
            a, b = value
            if isinstance(node.op, ast.UAdd):
                return a, b
            if isinstance(node.op, ast.USub):
                return -a, -b
            return None

        if isinstance(node, ast.BinOp):
            lhs = visit(node.left)
            rhs = visit(node.right)
            if lhs is None or rhs is None:
                return None
            la, lb = lhs
            ra, rb = rhs

            if isinstance(node.op, ast.Add):
                return la + ra, lb + rb
            if isinstance(node.op, ast.Sub):
                return la - ra, lb - rb

            return None

        return None

    return visit(node)


def _is_testcase_index_expr(expr: object, *, counter: str) -> bool:
    value = _affine_counter_expr(expr, counter=counter)
    if value is None:
        return False

    coefficient, _constant = value
    return coefficient == 1


def _clone_without_case_index(node, *, counter: str):
    if isinstance(node, ItemNode):
        name = _transform_name(node.name, counter=counter)
        indices = [_transform_expr(index, counter=counter) for index in node.indices]

        if indices and _is_testcase_index_expr(node.indices[0], counter=counter):
            indices = indices[1:]

        return ItemNode(name=name, indices=indices)

    if isinstance(node, NewlineNode):
        return NewlineNode()

    if isinstance(node, SequenceNode):
        return SequenceNode(
            items=[
                _clone_without_case_index(item, counter=counter) for item in node.items
            ],
        )

    if isinstance(node, LoopNode):
        return LoopNode(
            size=_transform_expr(node.size, counter=counter),
            name=str(node.name),
            body=_clone_without_case_index(node.body, counter=counter),
        )

    raise TypeError(f"unsupported input format node: {type(node).__name__}")


_IDENT_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")


def _decl_dependencies_from_expr(
    expr, *, known_names: set[str], counter: str
) -> set[VarName]:
    deps: set[VarName] = set()

    for token in _IDENT_RE.findall(_simple_expr(expr)):
        candidates = [
            token,
            _transform_name(token, counter=counter),
        ]

        for name in candidates:
            if name in known_names:
                deps.add(VarName(name))

    return deps


def _transform_decl(decl: VarDecl, *, count_name: str, counter: str) -> VarDecl:
    name = VarName(_transform_name(decl.name, counter=counter))

    dims: list[Expr] = [_transform_expr(dim, counter=counter) for dim in decl.dims]
    bases: list[Expr] = [_transform_expr(base, counter=counter) for base in decl.bases]

    if dims and _simple_expr(dims[0]) == count_name:
        dims = dims[1:]
        bases = bases[1:]

    return VarDecl(
        name=name,
        type=decl.type,
        dims=dims,
        bases=bases,
        depending=set(),  # recalculate from dims later
    )


def _transform_decls(
    decls: dict[VarName, VarDecl], *, count_name: str, counter: str
) -> dict[VarName, VarDecl]:
    transformed: dict[VarName, VarDecl] = {}

    for name, decl in decls.items():
        if str(name) == count_name:
            continue

        new_decl = _transform_decl(
            decl,
            count_name=count_name,
            counter=counter,
        )
        transformed[new_decl.name] = new_decl

    known_names = {str(name) for name in transformed.keys()}
    fixed: dict[VarName, VarDecl] = {}

    for name, decl in transformed.items():
        depending: set[VarName] = set()

        for dim in decl.dims:
            depending |= _decl_dependencies_from_expr(
                dim,
                known_names=known_names,
                counter=counter,
            )

        depending.discard(name)
        fixed[name] = decl._replace(depending=depending)

    return fixed


def _has_testcase_text_signal(
    data: dict[str, Any],
    *,
    count_name: str,
    allow_generic: bool = True,
    allow_bare_cases: bool = True,
) -> bool:
    text = _normalize_for_testcase_signal(_constraint_text(data))

    # シングルテストケースの問題を
    # マルチテストケースと誤検出しないように
    # 特に冠詞 a を変数 `a` と誤検出しないように
    test_cases = r"test\s*(?:cases\b|case\s*\(\s*s\s*\))"
    cases = r"(?:cases\b|case\s*\(\s*s\s*\))"

    testcase_count_names = [str(count_name).lower()]
    if "t" not in testcase_count_names:
        testcase_count_names.append("t")

    strong_patterns = []

    for candidate in testcase_count_names:
        candidate_name = _math_var_pattern(candidate)

        strong_patterns += [
            # T test cases
            rf"{candidate_name}\s+{test_cases}",
            # T denotes / represents / is the number of test cases
            rf"{candidate_name}[^.\n;。]*\b(?:denotes|represents|is)\b[^.\n;。]*\bnumber\s+of\s+{test_cases}",
            # number of test cases is T
            rf"\bnumber\s+of\s+{test_cases}[^.\n;。]*{candidate_name}",
            # first line contains T ... test cases
            rf"\bfirst\s+line\b[^.\n;。]*{candidate_name}[^.\n;。]*\b{test_cases}",
            # Japanese
            rf"{candidate_name}\s*個\s*の\s*テストケース",
        ]

    name = _math_var_pattern(count_name)

    bare_case_patterns = [
        # T cases
        rf"{name}\s+{cases}",
        # T denotes / represents / is the number of cases
        rf"{name}[^.\n;。]*\b(?:denotes|represents|is)\b[^.\n;。]*\bnumber\s+of\s+{cases}",
        # number of cases is T
        rf"\bnumber\s+of\s+{cases}[^.\n;。]*{name}",
        # first line contains T ... cases
        rf"\bfirst\s+line\b[^.\n;。]*{name}[^.\n;。]*\b{cases}",
    ]

    patterns = list(strong_patterns)
    if allow_bare_cases:
        patterns += bare_case_patterns

    if allow_generic:
        patterns += [
            # each test case / for each test case
            r"\bfor\s+each\s+test\s*case\b",
            r"\beach\s+test\s*case\b",
            # Japanese
            r"マルチテストケース",
        ]

    # online-judge-template-generator は
    # 先頭のテストケース数 `T` に対して
    #  `a` や `n` などの変数名を割り当てることがある。
    # 問題文からマルチテストケースであるとわかる場合のみ
    # fallback として `"t"` を入れておく。
    if any(re.search(pattern, text) for pattern in patterns):
        return True

    for endpoint in testcase_count_names:
        endpoint_name = _math_var_pattern(endpoint)
        case_index_pattern = (
            rf"\bcase\s*_?\s*1\b[\s\S]{{0,500}}"
            rf"\bcase\s*_?\s*{re.escape(endpoint)}(?![a-z0-9_])"
        )
        if not re.search(case_index_pattern, text):
            continue

        endpoint_testcase_patterns = [
            # T test cases
            rf"{endpoint_name}\s+{test_cases}",
            # T denotes / represents / is the number of test cases
            rf"{endpoint_name}[^.\n;。]*\b(?:denotes|represents|is)\b[^.\n;。]*\bnumber\s+of\s+{test_cases}",
            # number of test cases is T
            rf"\bnumber\s+of\s+{test_cases}[^.\n;。]*{endpoint_name}",
            # first line contains T ... test cases
            rf"\bfirst\s+line\b[^.\n;。]*{endpoint_name}[^.\n;。]*\b{test_cases}",
            # Japanese
            rf"{endpoint_name}\s*個\s*の\s*テストケース",
        ]

        if any(re.search(pattern, text) for pattern in endpoint_testcase_patterns):
            return True

    return False


def _split_top_level_testcases(analyzed, *, data: dict[str, Any]):
    config = data.get("config", {})

    force_multi = config.get("multi_testcases")

    if force_multi is False:
        return None

    input_format = analyzed.input_format
    input_variables = analyzed.input_variables

    if input_format is None or input_variables is None:
        return None

    if not isinstance(input_format, SequenceNode):
        return None

    # ignore NewlineNode
    items = [item for item in input_format.items if not isinstance(item, NewlineNode)]

    if len(items) != 2:
        return None

    count_node, loop = items

    if not isinstance(count_node, ItemNode):
        return None

    if not isinstance(loop, LoopNode):
        return None

    if count_node.indices:
        return None

    count_name = str(count_node.name)

    if (
        not _is_case_count_name(count_name)
        and force_multi is not True
        and not _has_testcase_text_signal(
            data,
            count_name=count_name,
            allow_generic=False,
            allow_bare_cases=False,
        )
    ):
        return None

    if _simple_expr(loop.size) != count_name:
        return None

    if force_multi is not True:
        if not (
            _is_strong_case_count_name(count_name)
            or _has_testcase_text_signal(data, count_name=count_name)
        ):
            return None

    return count_name, str(loop.name), loop.body


def _data_with_input(
    data: dict[str, Any],
    *,
    input_format,
    input_variables,
) -> dict[str, Any]:
    new_data = dict(data)

    config = dict(data.get("config", {}))
    config["rep_macro"] = "rep"
    config["long_long_int"] = "ll"
    config["scanner"] = lambda exprs: [f"::in({', '.join(expr for expr, _ in exprs)});"]

    new_data["config"] = config
    new_data["analyzed"] = data["analyzed"]._replace(
        input_format=input_format,
        input_variables=input_variables,
    )

    return new_data


INT_LIMIT = 10_000_000


def _fits_small_int_range(lower_bound: int, upper_bound: int) -> bool:
    return -INT_LIMIT < lower_bound and upper_bound < INT_LIMIT


def _select_integral_var_type(decl, *, data: dict[str, Any]):
    if decl.type not in (None, VarType.IndexInt, VarType.ValueInt):
        return decl.type

    lower_bound, upper_bound = _bounds_of_decl(decl, data=data)

    if lower_bound is None or upper_bound is None:
        return VarType.ValueInt

    if _fits_small_int_range(lower_bound, upper_bound):
        return VarType.IndexInt

    return VarType.ValueInt


def _adjust_input_variable_types(decls, *, data: dict[str, Any]):
    result = {}

    for name, decl in decls.items():
        result[name] = decl._replace(
            type=_select_integral_var_type(decl, data=data),
        )

    return result


_BRACED_INDEXED_VAR_RE = re.compile(
    r"\b(?P<base>[A-Za-z_][A-Za-z0-9_]*)_\{(?P<subscript>[^{}]+)\}"
)


def _collect_loop_counters(node) -> set[str]:
    if isinstance(node, LoopNode):
        return {str(node.name)} | _collect_loop_counters(node.body)

    if isinstance(node, SequenceNode):
        counters: set[str] = set()
        for item in node.items:
            counters |= _collect_loop_counters(item)
        return counters

    return set()


def _expr_mentions_counter(expr: object, *, counters: set[str]) -> bool:
    text = _simple_expr(expr)

    for counter in counters:
        if re.search(rf"\b{re.escape(counter)}\b", text):
            return True

    return False


def _expr_has_indexed_known_variable(
    expr: object,
    *,
    known_names: set[str],
    counters: set[str],
) -> bool:
    text = _simple_expr(expr)

    # e.g. K_{i}, K_{i + 1}, A_{i,j}
    for m in _BRACED_INDEXED_VAR_RE.finditer(text):
        base = m.group("base")
        subscript = m.group("subscript")

        if base in known_names and _expr_mentions_counter(
            subscript,
            counters=counters,
        ):
            return True

    # e.g. K_i, A_i_j
    for name in sorted(known_names, key=len, reverse=True):
        escaped_name = re.escape(name)

        for counter in counters:
            escaped_counter = re.escape(counter)

            if re.search(
                rf"\b{escaped_name}_{escaped_counter}(?=\b|_)",
                text,
            ):
                return True

    return False


def _format_has_unsafe_indexed_loop_size(
    node,
    *,
    known_names: set[str],
    active_counters: tuple[str, ...] = (),
) -> bool:
    if isinstance(node, LoopNode):
        counters = set(active_counters)

        if _expr_has_indexed_known_variable(
            node.size,
            known_names=known_names,
            counters=counters,
        ):
            return True

        return _format_has_unsafe_indexed_loop_size(
            node.body,
            known_names=known_names,
            active_counters=active_counters + (str(node.name),),
        )

    if isinstance(node, SequenceNode):
        return any(
            _format_has_unsafe_indexed_loop_size(
                item,
                known_names=known_names,
                active_counters=active_counters,
            )
            for item in node.items
        )

    return False


def _decls_have_unsafe_indexed_dimensions(
    decls,
    *,
    counters: set[str],
) -> bool:
    known_names = {str(name) for name in decls.keys()}

    for decl in decls.values():
        for dim in decl.dims:
            if _expr_has_indexed_known_variable(
                dim,
                known_names=known_names,
                counters=counters,
            ):
                return True

    return False


def _can_use_stock_read_input(input_format, input_variables) -> bool:
    known_names = {str(name) for name in input_variables.keys()}
    counters = _collect_loop_counters(input_format)

    if _format_has_unsafe_indexed_loop_size(
        input_format,
        known_names=known_names,
    ):
        return False

    if _decls_have_unsafe_indexed_dimensions(
        input_variables,
        counters=counters,
    ):
        return False

    return True


def _read_input_fallback(message: str = "failed to analyze input format") -> str:
    return "\n".join(
        [
            f"    // {message}",
            "    // TODO: write input receiving code here",
        ]
    )


_CPP_KEYWORDS = {
    "alignas",
    "alignof",
    "and",
    "and_eq",
    "asm",
    "auto",
    "bitand",
    "bitor",
    "bool",
    "break",
    "case",
    "catch",
    "char",
    "class",
    "compl",
    "concept",
    "const",
    "consteval",
    "constexpr",
    "constinit",
    "continue",
    "co_await",
    "co_return",
    "co_yield",
    "decltype",
    "default",
    "delete",
    "do",
    "double",
    "dynamic_cast",
    "else",
    "enum",
    "explicit",
    "export",
    "extern",
    "false",
    "float",
    "for",
    "friend",
    "goto",
    "if",
    "inline",
    "int",
    "long",
    "mutable",
    "namespace",
    "new",
    "noexcept",
    "not",
    "not_eq",
    "nullptr",
    "operator",
    "or",
    "or_eq",
    "private",
    "protected",
    "public",
    "register",
    "reinterpret_cast",
    "requires",
    "return",
    "short",
    "signed",
    "sizeof",
    "static",
    "static_assert",
    "static_cast",
    "struct",
    "switch",
    "template",
    "this",
    "thread_local",
    "throw",
    "true",
    "try",
    "typedef",
    "typeid",
    "typename",
    "union",
    "unsigned",
    "using",
    "virtual",
    "void",
    "volatile",
    "while",
    "xor",
    "xor_eq",
}

_TEMPLATE_HELPER_NAMES = {
    # input helpers
    "in",
    "in_z",
    "input",
    "input_z",
    # output/debug helpers
    "out",
    "out_and_flush",
    "out2",
    "out2_and_flush",
    "err",
    "err2",
    "change_out_sep",
    "change_err_sep",
    "change_seps",
    "sep",
    "current_sep",
    # common utilities
    "yes",
    "no",
    "yn",
    "chmin",
    "chmax",
    "increment",
    "decrement",
    "sum_of",
    "min_of",
    "max_of",
    "gcd_of",
    "lcm_of",
    "floor_div",
    "floor_mod",
    "floor_div_mod",
    "ceil_div",
    "make_vector",
    "make_array",
    # aliases / constants / macros that users are likely to use
    "ll",
    "uint",
    "ull",
    "mint",
    "inf32",
    "inf64",
    "ten_powers",
    "two_powers",
    "min_heap",
    "rep",
    "rep_r",
    "rep_t",
    "rep_t_r",
    "all",
    "all_r",
    "iter",
    "dir",
    "dir_2",
    "dir_8",
    # namespaces in the template
    "atcoder",
    "suisen",
}

_RESERVED_GENERATED_NAMES = _CPP_KEYWORDS | _TEMPLATE_HELPER_NAMES


def _collect_loop_counter_names(node) -> set[str]:
    if isinstance(node, LoopNode):
        return {str(node.name)} | _collect_loop_counter_names(node.body)

    if isinstance(node, SequenceNode):
        result: set[str] = set()

        for item in node.items:
            result |= _collect_loop_counter_names(item)

        return result

    return set()


def _is_valid_cpp_identifier(name: str) -> bool:
    return re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is not None


def _sanitize_identifier(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_]", "_", name)

    if not name:
        name = "x"

    if re.match(r"[0-9]", name):
        name = "_" + name

    return name


def _allocate_safe_identifier(
    preferred: str,
    *,
    current: str,
    used: set[str],
    original_names: set[str],
    reserved_names: set[str],
) -> str:
    base = _sanitize_identifier(preferred)

    candidate = base
    suffix = 0

    while (
        not _is_valid_cpp_identifier(candidate)
        or candidate in reserved_names
        or candidate in used
        or (candidate in original_names and candidate != current)
    ):
        suffix += 1
        candidate = f"{base}_{suffix}" if suffix > 1 else f"{base}_"

    return candidate


def _constant_names(data: dict[str, Any]) -> set[str]:
    analyzed = data.get("analyzed")
    constants = getattr(analyzed, "constants", {}) if analyzed is not None else {}
    return {str(name) for name in constants.keys()}


def _make_lowercase_rename_map(
    input_format,
    input_variables,
    *,
    data: dict[str, Any],
) -> dict[str, str]:
    names = [str(name) for name in input_variables.keys()]
    original_names = set(names)
    loop_counters = _collect_loop_counter_names(input_format)

    reserved_names = _RESERVED_GENERATED_NAMES | _constant_names(data) | loop_counters

    grouped: dict[str, list[str]] = {}

    for name in names:
        grouped.setdefault(name.lower(), []).append(name)

    rename_map: dict[str, str] = {}
    used: set[str] = set()

    for name in names:
        lowered = name.lower()

        # e.g. `A` and `a`
        if len(grouped[lowered]) == 1:
            preferred = lowered
        else:
            preferred = name

        target = _allocate_safe_identifier(
            preferred,
            current=name,
            used=used,
            original_names=original_names,
            reserved_names=reserved_names,
        )

        used.add(target)
        if target != name:
            rename_map[name] = target

    return rename_map


def _rename_expr(expr, *, rename_map: dict[str, str]):
    text = _simple_expr(expr)
    for old, new in sorted(
        rename_map.items(), key=lambda item: len(item[0]), reverse=True
    ):
        escaped = re.escape(old)
        text = re.sub(
            rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])",
            new,
            text,
        )
    return Expr(text)


def _rename_input_format(node, *, rename_map: dict[str, str]):
    if isinstance(node, ItemNode):
        return ItemNode(
            name=rename_map.get(str(node.name), str(node.name)),
            indices=[
                _rename_expr(index, rename_map=rename_map) for index in node.indices
            ],
        )

    if isinstance(node, NewlineNode):
        return NewlineNode()

    if isinstance(node, SequenceNode):
        return SequenceNode(
            items=[
                _rename_input_format(item, rename_map=rename_map) for item in node.items
            ],
        )

    if isinstance(node, LoopNode):
        return LoopNode(
            size=_rename_expr(node.size, rename_map=rename_map),
            name=str(node.name),
            body=_rename_input_format(node.body, rename_map=rename_map),
        )

    raise TypeError(f"unsupported input format node: {type(node).__name__}")


def _rename_input_variables(input_variables, *, rename_map: dict[str, str]):
    result = {}

    for _name, decl in input_variables.items():
        new_name = VarName(rename_map.get(str(decl.name), str(decl.name)))

        new_decl = decl._replace(
            name=new_name,
            dims=[_rename_expr(dim, rename_map=rename_map) for dim in decl.dims],
            bases=[_rename_expr(base, rename_map=rename_map) for base in decl.bases],
            depending={
                VarName(rename_map.get(str(dep), str(dep))) for dep in decl.depending
            },
        )

        result[new_name] = new_decl

    return result


def _normalize_input_variable_names(
    input_format, input_variables, *, data: dict[str, Any]
):
    rename_map = _make_lowercase_rename_map(
        input_format,
        input_variables,
        data=data,
    )

    if not rename_map:
        return input_format, input_variables

    return (
        _rename_input_format(input_format, rename_map=rename_map),
        _rename_input_variables(input_variables, rename_map=rename_map),
    )


def _build_generated_parts(data: dict[str, Any], *, logger):
    try:
        base_data = dict(data)
        base_config = dict(data.get("config", {}))
        base_config["rep_macro"] = "rep"
        base_config["long_long_int"] = "ll"
        base_config["scanner"] = lambda exprs: [
            f"::in({', '.join(expr for expr, _ in exprs)});"
        ]
        base_data["config"] = base_config

        analyzed = base_data["analyzed"]
        constants = cplusplus.declare_constants(base_data).rstrip()

        if analyzed.input_format is None or analyzed.input_variables is None:
            return constants, _read_input_fallback(), "    // ::in(t);"

        typed_variables = _adjust_input_variable_types(
            analyzed.input_variables,
            data=base_data,
        )

        split = _split_top_level_testcases(analyzed, data=base_data)

        if split is None:
            input_format = analyzed.input_format
            input_variables = typed_variables

            if not _can_use_stock_read_input(
                input_format,
                input_variables,
            ):
                return (
                    constants,
                    _read_input_fallback(
                        "detected unsupported input format; edit here"
                    ),
                    "    // ::in(t);",
                )

            input_format, input_variables = _normalize_input_variable_names(
                input_format,
                input_variables,
                data=base_data,
            )

            input_data = _data_with_input(
                base_data,
                input_format=input_format,
                input_variables=input_variables,
            )

            return (
                constants,
                cplusplus.read_input(input_data, nest=1).rstrip(),
                "    // ::in(t);",
            )

        count_name, counter, body = split

        case_format = _clone_without_case_index(
            body,
            counter=counter,
        )

        case_variables = _transform_decls(
            typed_variables,
            count_name=count_name,
            counter=counter,
        )

        if not _can_use_stock_read_input(
            case_format,
            case_variables,
        ):
            return (
                constants,
                _read_input_fallback(
                    "detected unsupported per-case input format; edit here"
                ),
                "    ::in(t);",
            )

        case_format, case_variables = _normalize_input_variable_names(
            case_format,
            case_variables,
            data=base_data,
        )

        case_data = _data_with_input(
            base_data,
            input_format=case_format,
            input_variables=case_variables,
        )

        return (
            constants,
            cplusplus.read_input(case_data, nest=1).rstrip(),
            "    ::in(t);",
        )

    except Exception as exc:
        logger.warning("failed to generate input receiving code: %s", exc)
        return (
            "",
            "    // failed to generate input receiving code; edit here",
            "    // ::in(t);",
        )
