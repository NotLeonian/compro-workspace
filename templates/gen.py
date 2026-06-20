import functools
import math
import random
import re
import sys
from typing import TYPE_CHECKING, Any

# These globals are emitted before this runtime block by gen.py.mako.in.py.
if TYPE_CHECKING:
    FORMAT: Any = None
    ARRAY_NAMES: set[str] = set()
    BOUNDS: dict[str, tuple[Any, Any]] = {}
    VALUE_KINDS: dict[str, str] = {}
    ALPHABETS: dict[str, str] = {}
    SPECIALS: list[dict[str, Any]] = []

RNG = random.Random()
VALUES: dict[tuple[str, tuple[Any, ...]], Any] = {}
SPECIAL_CACHE: dict[tuple[int, str, tuple[Any, ...]], dict[str, Any]] = {}

_ALLOWED_NAMES = {
    "abs": abs,
    "min": min,
    "max": max,
    "sum": sum,
    "len": len,
    "int": int,
    "round": round,
    "pow": pow,
}

_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


def setv(name, indices, value):
    VALUES[(name, tuple(indices))] = value
    return value


def hasv(name, indices=()):
    return (name, tuple(indices)) in VALUES


def getv(name, indices=()):
    return VALUES[(name, tuple(indices))]


def ri(lo, hi):
    lo = int(lo)
    hi = int(hi)
    if lo > hi:
        raise ValueError(f"empty integer range: [{lo}, {hi}]")
    return RNG.randint(lo, hi)


def rand_string(length, alphabet):
    return "".join(RNG.choice(alphabet) for _ in range(int(length)))


def rand_permutation(n, base=1):
    xs = list(range(int(base), int(base) + int(n)))
    RNG.shuffle(xs)
    return xs


def rand_distinct_integers(n, lo, hi):
    n = int(n)
    lo = int(lo)
    hi = int(hi)
    if n < 0:
        raise ValueError("n must be non-negative")
    if hi - lo + 1 < n:
        raise ValueError(f"cannot choose {n} distinct integers from [{lo}, {hi}]")
    return RNG.sample(range(lo, hi + 1), n)


def rand_sum_sequence(n, total, lo, hi):
    n = int(n)
    total = int(total)
    lo = int(lo)
    hi = int(hi)
    if n < 0:
        raise ValueError("n must be non-negative")
    if lo > hi:
        raise ValueError(f"empty value range: [{lo}, {hi}]")
    if n == 0:
        if total != 0:
            raise ValueError("empty sequence can only have sum 0")
        return []
    if total < n * lo or total > n * hi:
        raise ValueError(f"sum {total} is infeasible for {n} values in [{lo}, {hi}]")

    xs = []
    remaining = total
    for i in range(n):
        rest = n - i - 1
        low = max(lo, remaining - rest * hi)
        high = min(hi, remaining - rest * lo)
        x = ri(low, high)
        xs.append(x)
        remaining -= x

    RNG.shuffle(xs)
    return xs


def _positive_power(base, exp):
    if exp < 0:
        raise ValueError("negative exponent is not supported")
    return int(base) ** int(exp)


def rand_product_sequence_range(n, min_product, max_product, lo, hi):
    n = int(n)
    min_product = int(min_product)
    max_product = int(max_product)
    lo = int(lo)
    hi = int(hi)

    if n < 0:
        raise ValueError("n must be non-negative")
    if lo <= 0:
        raise ValueError("product generator currently supports positive integers only")
    if lo > hi:
        raise ValueError(f"empty value range: [{lo}, {hi}]")
    if n == 0:
        if min_product <= 1 <= max_product:
            return []
        raise ValueError("empty sequence has product 1")

    feasible_min = _positive_power(lo, n)
    feasible_max = _positive_power(hi, n)
    min_product = max(min_product, feasible_min)
    max_product = min(max_product, feasible_max)
    if min_product > max_product:
        raise ValueError("product range is infeasible")

    for _ in range(500):
        xs = []
        product = 1
        ok = True
        for i in range(n):
            rest = n - i - 1
            high = min(hi, max_product // (product * _positive_power(lo, rest)))
            if high < lo:
                ok = False
                break
            x = ri(lo, high)
            xs.append(x)
            product *= x
        if ok and min_product <= product <= max_product:
            RNG.shuffle(xs)
            return xs

    # Note for template and runtime maintainers:
    # Deterministic fallback: start from all lo and greedily increase values.
    xs = [lo] * n
    product = feasible_min
    for i in range(n):
        while xs[i] < hi and product < min_product:
            nxt = xs[i] + 1
            new_product = product // xs[i] * nxt
            if new_product > max_product:
                break
            xs[i] = nxt
            product = new_product

    if min_product <= product <= max_product:
        RNG.shuffle(xs)
        return xs

    raise ValueError("failed to generate product-constrained sequence")


def _divisors_in_range(x, lo, hi):
    result = []
    d = 1
    while d * d <= x:
        if x % d == 0:
            q = x // d
            if lo <= d <= hi:
                result.append(d)
            if q != d and lo <= q <= hi:
                result.append(q)
        d += 1
    RNG.shuffle(result)
    return result


def rand_product_sequence_exact(n, total, lo, hi):
    n = int(n)
    total = int(total)
    lo = int(lo)
    hi = int(hi)

    if n < 0:
        raise ValueError("n must be non-negative")
    if lo <= 0 or total <= 0:
        raise ValueError(
            "exact product generator currently supports positive integers only"
        )
    if lo > hi:
        raise ValueError(f"empty value range: [{lo}, {hi}]")
    if n == 0:
        if total == 1:
            return []
        raise ValueError("empty sequence has product 1")

    @functools.lru_cache(maxsize=None)
    def feasible(k, remaining):
        if k == 0:
            return remaining == 1
        if remaining < _positive_power(lo, k) or remaining > _positive_power(hi, k):
            return False
        return any(
            feasible(k - 1, remaining // d)
            for d in _divisors_in_range(remaining, lo, hi)
        )

    if not feasible(n, total):
        raise ValueError(
            f"product {total} is infeasible for {n} values in [{lo}, {hi}]"
        )

    xs = []
    remaining = total
    for k in range(n, 0, -1):
        candidates = [
            d
            for d in _divisors_in_range(remaining, lo, hi)
            if feasible(k - 1, remaining // d)
        ]
        x = RNG.choice(candidates)
        xs.append(x)
        remaining //= x

    RNG.shuffle(xs)
    return xs


def rand_tree_edges(n, base=1, *, shuffle_endpoints=True):
    n = int(n)
    base = int(base)
    if n <= 0:
        return []
    edges = []
    for v in range(1, n):
        p = RNG.randrange(v)
        a = base + p
        b = base + v
        if shuffle_endpoints and RNG.randrange(2):
            a, b = b, a
        edges.append((a, b))
    RNG.shuffle(edges)
    return edges


def _orient_undirected_edges(edges, *, shuffle_endpoints=True):
    result = []
    for a, b in edges:
        if shuffle_endpoints and RNG.randrange(2):
            a, b = b, a
        result.append((a, b))
    RNG.shuffle(result)
    return result


def _sample_undirected_canonical_edges(n, m, base=1, forbidden=()):
    n = int(n)
    m = int(m)
    base = int(base)
    forbidden = set(forbidden)
    max_edges = n * (n - 1) // 2
    available = max_edges - len(forbidden)
    if m < 0 or m > available:
        raise ValueError("requested edge count is impossible")

    if max_edges <= 300_000 or m > available // 3:
        candidates = [
            (base + i, base + j)
            for i in range(n)
            for j in range(i + 1, n)
            if (base + i, base + j) not in forbidden
        ]
        RNG.shuffle(candidates)
        return candidates[:m]

    result = set()
    while len(result) < m:
        i = RNG.randrange(n)
        j = RNG.randrange(n - 1)
        if j >= i:
            j += 1
        a = base + min(i, j)
        b = base + max(i, j)
        e = (a, b)
        if e not in forbidden:
            result.add(e)
    return list(result)


def rand_simple_graph_edges(n, m, base=1, connected=False, *, shuffle_endpoints=True):
    n = int(n)
    m = int(m)
    base = int(base)
    if n < 0 or m < 0:
        raise ValueError("n and m must be non-negative")

    max_edges = n * (n - 1) // 2
    min_edges = n - 1 if connected and n > 0 else 0
    if m < min_edges or m > max_edges:
        raise ValueError("requested edge count is impossible")

    edges = set()
    if connected and n > 0:
        for v in range(1, n):
            p = RNG.randrange(v)
            a = base + min(p, v)
            b = base + max(p, v)
            edges.add((a, b))

    need = m - len(edges)
    if need:
        edges.update(
            _sample_undirected_canonical_edges(
                n,
                need,
                base,
                forbidden=edges,
            )
        )

    return _orient_undirected_edges(edges, shuffle_endpoints=shuffle_endpoints)


def _sample_dag_position_pairs(n, m):
    n = int(n)
    m = int(m)
    max_edges = n * (n - 1) // 2
    if m < 0 or m > max_edges:
        raise ValueError("requested DAG edge count is impossible")

    if max_edges <= 300_000 or m > max_edges // 3:
        pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
        RNG.shuffle(pairs)
        return pairs[:m]

    result = set()
    while len(result) < m:
        i = RNG.randrange(n)
        j = RNG.randrange(n - 1)
        if j >= i:
            j += 1
        if i > j:
            i, j = j, i
        result.add((i, j))
    return list(result)


def rand_dag_edges(n, m, base=1):
    n = int(n)
    m = int(m)
    base = int(base)
    order = rand_permutation(n, base)
    edges = [(order[i], order[j]) for i, j in _sample_dag_position_pairs(n, m)]
    RNG.shuffle(edges)
    return edges


_BRACED_INDEX_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9]*)_\{([^{}]+)\}")


def _split_indices(text):
    parts = []
    depth = 0
    start = 0
    for i, ch in enumerate(text):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            parts.append(text[start:i].strip())
            start = i + 1
    parts.append(text[start:].strip())
    return [part for part in parts if part]


def _prepare_expr(expr, local):
    expr = str(expr).strip()
    expr = expr.replace("^", "**")
    expr = expr.replace("\\times", "*").replace("\\cdot", "*").replace("×", "*")
    expr = expr.replace("−", "-")

    def replace_braced(match):
        name = match.group(1)
        indices = ", ".join(_split_indices(match.group(2)))
        return f"getv({name!r}, [{indices}])"

    expr = _BRACED_INDEX_RE.sub(replace_braced, expr)

    # Note for template and runtime maintainers:
    # We only rewrite bases that are known arrays and counters currently in scope,
    # which keeps ordinary scalar names intact.
    for base in sorted(ARRAY_NAMES, key=len, reverse=True):
        escaped_base = re.escape(base)
        counters = sorted(local.keys(), key=len, reverse=True)
        if not counters:
            continue
        counter_pattern = "|".join(re.escape(counter) for counter in counters)
        pattern = rf"\b{escaped_base}_({counter_pattern})(?:_({counter_pattern}))*\b"

        def replace_plain_index(match, base=base):
            suffix = match.group(0)[len(base) + 1 :]
            indices = suffix.split("_")
            return f"getv({base!r}, [{', '.join(indices)}])"

        expr = re.sub(pattern, replace_plain_index, expr)

    return expr


def eval_expr(expr, local):
    if isinstance(expr, (int, float)):
        return expr
    prepared = _prepare_expr(expr, local)
    scope = dict(_ALLOWED_NAMES)
    scope["getv"] = getv

    for (name, indices), value in VALUES.items():
        if not indices and _IDENTIFIER_RE.fullmatch(name):
            scope[name] = value

    scope.update(local)
    return eval(prepared, {"__builtins__": {}}, scope)


def _eval_int(value, local):
    return int(eval_expr(value, local)) if isinstance(value, str) else int(value)


def _field(spec, *keys, default=None):
    for key in keys:
        if key in spec:
            return spec[key]
    return default


def _spec_size(spec, local):
    return _eval_int(_field(spec, "size", "n"), local)


def _spec_base(spec, local):
    return _eval_int(_field(spec, "base", default=1), local)


def _spec_value_bounds(spec, name, local):
    lo, hi = BOUNDS.get(name, (0, 10))
    lo = _field(spec, "lo", "min_value", default=lo)
    hi = _field(spec, "hi", "max_value", default=hi)
    return _eval_int(lo, local), _eval_int(hi, local)


def _prefix_of(indices):
    return tuple(indices[:-1]) if indices else ()


def _last_index_of(indices):
    if not indices:
        raise ValueError("special generator requires an indexed variable")
    return indices[-1]


def _position_for_access(cache, indices):
    last = _last_index_of(indices)
    pos_by_index = cache["pos_by_index"]
    if last not in pos_by_index:
        pos_by_index[last] = len(pos_by_index)
    return pos_by_index[last]


def _special_permutation(spec_id, spec, name, indices, local):
    if name != spec["name"] or not indices:
        return None

    prefix = _prefix_of(indices)
    key = (spec_id, "permutation", prefix)
    cache = SPECIAL_CACHE.get(key)
    if cache is None:
        n = _spec_size(spec, local)
        cache = {
            "values": rand_permutation(n, spec.get("base", 1)),
            "pos_by_index": {},
        }
        SPECIAL_CACHE[key] = cache

    pos = _position_for_access(cache, indices)
    xs = cache["values"]
    if pos >= len(xs):
        raise ValueError(f"too many accesses to permutation variable {name!r}")
    return setv(name, indices, xs[pos])


def _special_distinct(spec_id, spec, name, indices, local):
    if name != spec["name"] or not indices:
        return None

    prefix = _prefix_of(indices)
    key = (spec_id, "distinct", prefix)
    cache = SPECIAL_CACHE.get(key)
    if cache is None:
        n = _spec_size(spec, local)
        lo, hi = _spec_value_bounds(spec, name, local)
        cache = {
            "values": rand_distinct_integers(n, lo, hi),
            "pos_by_index": {},
        }
        SPECIAL_CACHE[key] = cache

    pos = _position_for_access(cache, indices)
    xs = cache["values"]
    if pos >= len(xs):
        raise ValueError(f"too many accesses to distinct variable {name!r}")
    return setv(name, indices, xs[pos])


def _special_tree_edges(spec_id, spec, name, indices, local):
    names = tuple(spec["names"])
    if name not in names or not indices:
        return None

    prefix = _prefix_of(indices)
    key = (spec_id, "tree_edges", prefix)
    cache = SPECIAL_CACHE.get(key)
    if cache is None:
        n = _spec_size(spec, local)
        cache = {
            "edges": rand_tree_edges(
                n,
                spec.get("base", 1),
                shuffle_endpoints=spec.get("shuffle_endpoints", True),
            ),
            "pos_by_index": {},
        }
        SPECIAL_CACHE[key] = cache

    pos = _position_for_access(cache, indices)
    edges = cache["edges"]
    if pos >= len(edges):
        raise ValueError(f"too many accesses to tree edge variables {names!r}")

    edge = edges[pos]
    value = edge[0] if name == names[0] else edge[1]
    return setv(name, indices, value)


def _sum_target_name(spec):
    return _field(spec, "target_name", "sum_name", "total_name")


def _sum_exact_expr(spec):
    return _field(spec, "target", "sum", "total")


def _choose_sum_total(spec, prefix, local):
    name = spec["name"]
    n = _spec_size(spec, local)
    lo, hi = _spec_value_bounds(spec, name, local)
    target_name = _sum_target_name(spec)
    exact_expr = _sum_exact_expr(spec)

    if target_name and hasv(target_name, prefix):
        return getv(target_name, prefix)

    # Note for template and runtime maintainers:
    # `target: "S", target_name: "S"` means S itself should be generated
    # consistently with the array, so do not evaluate S before it exists.
    if exact_expr is not None and not (
        target_name
        and isinstance(exact_expr, str)
        and exact_expr == target_name
        and not hasv(target_name, prefix)
    ):
        return _eval_int(exact_expr, local)

    low = n * lo
    high = n * hi
    low = max(low, _eval_int(_field(spec, "min_sum", "min_total", default=low), local))
    high = min(
        high, _eval_int(_field(spec, "max_sum", "max_total", default=high), local)
    )

    if target_name:
        target_lo, target_hi = BOUNDS.get(target_name, (low, high))
        low = max(low, int(target_lo))
        high = min(high, int(target_hi))

    return ri(low, high)


def _ensure_sum_cache(spec_id, spec, prefix, local):
    key = (spec_id, "sum", prefix)
    cache = SPECIAL_CACHE.get(key)
    if cache is None:
        name = spec["name"]
        n = _spec_size(spec, local)
        lo, hi = _spec_value_bounds(spec, name, local)
        total = _choose_sum_total(spec, prefix, local)
        cache = {
            "values": rand_sum_sequence(n, total, lo, hi),
            "target": total,
            "pos_by_index": {},
        }
        SPECIAL_CACHE[key] = cache

        target_name = _sum_target_name(spec)
        if target_name:
            setv(target_name, prefix, total)

    return cache


def _special_sum(spec_id, spec, name, indices, local):
    target_name = _sum_target_name(spec)
    if target_name and name == target_name:
        prefix = tuple(indices)
        cache = _ensure_sum_cache(spec_id, spec, prefix, local)
        return setv(name, indices, cache["target"])

    if name != spec["name"] or not indices:
        return None

    prefix = _prefix_of(indices)
    cache = _ensure_sum_cache(spec_id, spec, prefix, local)
    pos = _position_for_access(cache, indices)
    xs = cache["values"]
    if pos >= len(xs):
        raise ValueError(f"too many accesses to sum-constrained variable {name!r}")
    return setv(name, indices, xs[pos])


def _product_target_name(spec):
    return _field(spec, "target_name", "product_name", "total_name")


def _product_exact_expr(spec):
    return _field(spec, "target", "product", "total")


def _choose_product_values_and_target(spec, prefix, local):
    name = spec["name"]
    n = _spec_size(spec, local)
    lo, hi = _spec_value_bounds(spec, name, local)
    target_name = _product_target_name(spec)
    exact_expr = _product_exact_expr(spec)

    if target_name and hasv(target_name, prefix):
        target = int(getv(target_name, prefix))
        return rand_product_sequence_exact(n, target, lo, hi), target

    if exact_expr is not None and not (
        target_name
        and isinstance(exact_expr, str)
        and exact_expr == target_name
        and not hasv(target_name, prefix)
    ):
        target = _eval_int(exact_expr, local)
        return rand_product_sequence_exact(n, target, lo, hi), target

    min_product = _eval_int(
        _field(spec, "min_product", "min_total", default=_positive_power(lo, n)),
        local,
    )
    max_product = _eval_int(
        _field(spec, "max_product", "max_total", default=_positive_power(hi, n)),
        local,
    )

    if target_name:
        target_lo, target_hi = BOUNDS.get(target_name, (min_product, max_product))
        min_product = max(min_product, int(target_lo))
        max_product = min(max_product, int(target_hi))

    values = rand_product_sequence_range(n, min_product, max_product, lo, hi)
    return values, math.prod(values)


def _ensure_product_cache(spec_id, spec, prefix, local):
    key = (spec_id, "product", prefix)
    cache = SPECIAL_CACHE.get(key)
    if cache is None:
        values, target = _choose_product_values_and_target(spec, prefix, local)
        cache = {
            "values": values,
            "target": target,
            "pos_by_index": {},
        }
        SPECIAL_CACHE[key] = cache

        target_name = _product_target_name(spec)
        if target_name:
            setv(target_name, prefix, target)

    return cache


def _special_product(spec_id, spec, name, indices, local):
    target_name = _product_target_name(spec)
    if target_name and name == target_name:
        prefix = tuple(indices)
        cache = _ensure_product_cache(spec_id, spec, prefix, local)
        return setv(name, indices, cache["target"])

    if name != spec["name"] or not indices:
        return None

    prefix = _prefix_of(indices)
    cache = _ensure_product_cache(spec_id, spec, prefix, local)
    pos = _position_for_access(cache, indices)
    xs = cache["values"]
    if pos >= len(xs):
        raise ValueError(f"too many accesses to product-constrained variable {name!r}")
    return setv(name, indices, xs[pos])


def _edge_count_expr(spec):
    return _field(spec, "edges", "m", "edge_count")


def _edge_count_name(spec):
    expr = _edge_count_expr(spec)
    if isinstance(expr, str) and _IDENTIFIER_RE.fullmatch(expr):
        return expr
    return None


def _edge_count_limits(spec, n, connected, local):
    max_edges = n * (n - 1) // 2
    min_edges = n - 1 if connected and n > 0 else 0
    min_edges = max(
        min_edges,
        _eval_int(_field(spec, "min_edges", "min_m", default=min_edges), local),
    )
    max_edges = min(
        max_edges,
        _eval_int(_field(spec, "max_edges", "max_m", default=max_edges), local),
    )
    return min_edges, max_edges


def _choose_edge_count(spec, prefix, n, connected, local):
    edge_name = _edge_count_name(spec)
    edge_expr = _edge_count_expr(spec)
    min_edges, max_edges = _edge_count_limits(spec, n, connected, local)

    if edge_name and hasv(edge_name, prefix):
        return int(getv(edge_name, prefix))

    if edge_expr is not None and not (
        edge_name
        and isinstance(edge_expr, str)
        and edge_expr == edge_name
        and not hasv(edge_name, prefix)
    ):
        return _eval_int(edge_expr, local)

    if edge_name:
        lo, hi = BOUNDS.get(edge_name, (min_edges, max_edges))
        min_edges = max(min_edges, int(lo))
        max_edges = min(max_edges, int(hi))

    return ri(min_edges, max_edges)


def _ensure_edge_cache(spec_id, spec, prefix, local):
    kind = spec["kind"]
    key = (spec_id, kind, prefix)
    cache = SPECIAL_CACHE.get(key)
    if cache is not None:
        return cache

    n = _spec_size(spec, local)
    base = _spec_base(spec, local)
    connected = kind in {
        "simple_connected_graph_edges",
        "connected_graph_edges",
    } or bool(spec.get("connected", False))
    m = _choose_edge_count(spec, prefix, n, connected, local)

    if kind == "dag_edges":
        edges = rand_dag_edges(n, m, base)
    else:
        edges = rand_simple_graph_edges(
            n,
            m,
            base,
            connected=connected,
            shuffle_endpoints=spec.get("shuffle_endpoints", True),
        )

    cache = {
        "edges": edges,
        "edge_count": m,
        "pos_by_index": {},
    }
    SPECIAL_CACHE[key] = cache

    edge_name = _edge_count_name(spec)
    if edge_name:
        setv(edge_name, prefix, m)

    return cache


def _special_graph_edges(spec_id, spec, name, indices, local):
    edge_name = _edge_count_name(spec)
    if edge_name and name == edge_name:
        prefix = tuple(indices)
        cache = _ensure_edge_cache(spec_id, spec, prefix, local)
        return setv(name, indices, cache["edge_count"])

    names = tuple(spec["names"])
    if name not in names or not indices:
        return None

    prefix = _prefix_of(indices)
    cache = _ensure_edge_cache(spec_id, spec, prefix, local)
    pos = _position_for_access(cache, indices)
    edges = cache["edges"]
    if pos >= len(edges):
        raise ValueError(f"too many accesses to edge variables {names!r}")

    edge = edges[pos]
    value = edge[0] if name == names[0] else edge[1]
    return setv(name, indices, value)


def special_value(name, indices, local):
    for spec_id, spec in enumerate(SPECIALS):
        kind = spec.get("kind")
        if kind == "permutation":
            value = _special_permutation(spec_id, spec, name, indices, local)
        elif kind == "distinct":
            value = _special_distinct(spec_id, spec, name, indices, local)
        elif kind == "tree_edges":
            value = _special_tree_edges(spec_id, spec, name, indices, local)
        elif kind == "sum":
            value = _special_sum(spec_id, spec, name, indices, local)
        elif kind == "product":
            value = _special_product(spec_id, spec, name, indices, local)
        elif kind in {
            "simple_graph_edges",
            "simple_connected_graph_edges",
            "connected_graph_edges",
            "dag_edges",
        }:
            value = _special_graph_edges(spec_id, spec, name, indices, local)
        else:
            value = None

        if value is not None:
            return value

    return None


def random_value(name, indices, local):
    indices = tuple(indices)
    if hasv(name, indices):
        return getv(name, indices)

    value = special_value(name, indices, local)
    if value is not None:
        return value

    kind = VALUE_KINDS.get(name, "int")
    lo, hi = BOUNDS.get(name, (0, 10))

    if kind == "string":
        alphabet = ALPHABETS.get(name, "abcdefghijklmnopqrstuvwxyz")
        value = rand_string(ri(lo, hi), alphabet)
    elif kind == "char":
        alphabet = ALPHABETS.get(name, "abcdefghijklmnopqrstuvwxyz")
        value = RNG.choice(alphabet)
    elif kind == "float":
        value = RNG.uniform(float(lo), float(hi))
    else:
        value = ri(lo, hi)

    return setv(name, indices, value)


def flush(line):
    print(" ".join(map(str, line)))
    line.clear()


def emit(node, local, line):
    kind = node[0]

    if kind == "seq":
        for child in node[1]:
            emit(child, local, line)
        return

    if kind == "newline":
        flush(line)
        return

    if kind == "item":
        _, name, index_exprs = node
        indices = tuple(eval_expr(expr, local) for expr in index_exprs)
        line.append(random_value(name, indices, local))
        return

    if kind == "loop":
        _, counter, size_expr, body = node
        size = int(eval_expr(size_expr, local))
        if size < 0:
            raise ValueError(f"negative loop size for {counter}: {size}")

        sentinel = object()
        old = local.get(counter, sentinel)
        for i in range(size):
            local[counter] = i
            emit(body, local, line)

        if old is sentinel:
            local.pop(counter, None)
        else:
            local[counter] = old
        return

    raise ValueError(f"unknown format node kind: {kind!r}")


def generate():
    VALUES.clear()
    SPECIAL_CACHE.clear()

    line = []
    emit(FORMAT, {}, line)
    if line:
        flush(line)


def _seed_from_argv():
    if len(sys.argv) < 2:
        return None
    seed = sys.argv[1]
    try:
        return int(seed)
    except ValueError:
        return seed


if __name__ == "__main__":
    RNG.seed(_seed_from_argv())
    generate()
