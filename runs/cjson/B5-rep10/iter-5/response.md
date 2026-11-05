```python
from hypothesis import strategies as st
import json

# ---------- leaf pieces ----------

_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f'
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\\",
)

_simple_escapes = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)

_unicode_escape = st.builds(lambda h: "\\u" + h, _hex4)

# surrogate escapes: lone (rejected) and paired (accepted)
_surrogate_high = st.integers(min_value=0xD800, max_value=0xDBFF)
_surrogate_low = st.integers(min_value=0xDC00, max_value=0xDFFF)


def _u(i):
    return "\\u" + format(i, "04x")


_paired_surrogate = st.builds(
    lambda hi, lo: _u(hi) + _u(lo), _surrogate_high, _surrogate_low
)
_lone_surrogate = st.one_of(
    st.builds(_u, st.integers(min_value=0xD800, max_value=0xDFFF)),
)

_escape = st.one_of(_simple_escapes, _unicode_escape, _paired_surrogate, _lone_surrogate)

# raw control / NUL bytes inside strings (accepted by target)
_raw_control = st.sampled_from(
    ["\x00", "\x01", "\x07", "\x08", "\t", "\n", "\x0b", "\x0c", "\r", "\x1f", "\x7f"]
)

_string_char = st.one_of(_safe_chars, _escape, _raw_control)

_string_body = st.lists(_string_char, max_size=12).map("".join)

# strings: mostly well-formed, sometimes unterminated / bad escapes
_quoted_string = _string_body.map(lambda s: '"' + s + '"')
_unterminated_string = _string_body.map(lambda s: '"' + s)
_bad_escape = _string_body.map(lambda s: '"' + s + "\\q")
_invalid_escape_string = st.builds(lambda b: '"' + b + '\\x41"', _string_body)


def _string_strategy():
    return st.one_of(
        st.just('""'),
        _quoted_string,
        _unterminated_string,
        _bad_escape,
        _invalid_escape_string,
    )


# ---------- numbers ----------

_int_part = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.integers(min_value=0, max_value=10**6).map(lambda n: "0" + str(n)),  # leading zeros
    st.integers(min_value=0, max_value=2**64).map(lambda n: "0x" + format(n, "x")),  # hex
)

_frac_part = st.one_of(
    st.integers(min_value=0, max_value=10**9).map(lambda n: "." + str(n)),
    st.just("."),  # trailing dot accepted
    st.integers(min_value=0, max_value=10**6).map(lambda n: ".0" + str(n)),
)

_exp_part = st.one_of(
    st.integers(min_value=-400, max_value=400).map(lambda n: "e" + str(n)),
    st.integers(min_value=0, max_value=400).map(lambda n: "E+" + str(n)),
    st.integers(min_value=0, max_value=400).map(lambda n: "e-" + str(n)),
    st.just("e309"),
    st.just("e308"),
    st.just("e-309"),
    st.just("e999999"),
    st.just("e01"),
)

_sign = st.sampled_from(["", "-"])


def _number_strategy():
    base = st.tuples(_sign, _int_part).map(lambda t: t[0] + t[1])
    with_frac = st.tuples(base, _frac_part).map(lambda t: t[0] + t[1])
    with_exp = st.tuples(base, _exp_part).map(lambda t: t[0] + t[1])
    full = st.tuples(with_frac, _exp_part).map(lambda t: t[0] + t[1])
    malformed = st.one_of(
        st.just("-"),
        st.just("+1"),
        st.just(".5"),
        st.just("-.5"),
        st.just("1."),
        st.just("01"),
        st.just("00"),
        st.just("NaN"),
        st.just("Infinity"),
        st.just("-Infinity"),
        st.just("1e"),
        st.just("1e+"),
        st.just("--1"),
    )
    return st.one_of(base, with_frac, with_exp, full, malformed)


# ---------- recursive values ----------

_ws = st.sampled_from(["", " ", "\n", "\t", "\r", "  ", " \n "])

_literal = st.sampled_from(["true", "false", "null"])


def _build_value(children):
    return st.one_of(
        _string_strategy(),
        _number_strategy(),
        _literal,
        children,
    )


def _build_obj(value):
    key = _string_strategy()
    pair = st.tuples(key, _ws, st.just(":"), _ws, value).map(lambda t: "".join(t))
    pairs = st.lists(pair, max_size=4).map(lambda ps: ",".join(ps))
    obj = st.tuples(st.just("{"), _ws, pairs, _ws, st.just("}")).map(lambda t: "".join(t))
    empty = st.just("{}")
    malformed = st.one_of(
        st.tuples(st.just("{"), pairs, st.just("}")).map(lambda t: t[0] + t[1] + t[2]),
        # double comma
        st.tuples(pair, pair).map(lambda t: "{" + t[0] + ",," + t[1] + "}"),
        # missing colon
        st.tuples(key, value).map(lambda t: "{" + t[0] + " " + t[1] + "}"),
        # trailing comma
        st.tuples(pair).map(lambda t: "{" + t[0] + ",}"),
        # unterminated
        st.tuples(pair).map(lambda t: "{" + t[0]),
        st.just("{"),
    )
    return st.one_of(empty, obj, malformed)


def _build_arr(value):
    elems = st.lists(value, max_size=4).map(lambda vs: ",".join(vs))
    arr = st.tuples(st.just("["), _ws, elems, _ws, st.just("]")).map(lambda t: "".join(t))
    empty = st.just("[]")
    malformed = st.one_of(
        st.tuples(value, value).map(lambda t: "[" + t[0] + ",," + t[1] + "]"),
        st.tuples(elems).map(lambda t: "[" + t[0] + ",]"),
        st.tuples(elems).map(lambda t: "[" + t[0]),
        st.just("["),
    )
    return st.one_of(empty, arr, malformed)


_value = st.recursive(
    _build_value(st.nothing()),
    _build_value,
    max_leaves=20,
)


def _obj_or_arr(value):
    return st.one_of(_build_obj(value), _build_arr(value))


_recursive_value = st.recursive(
    _build_value(st.nothing()),
    lambda children: st.one_of(_build_value(children), _obj_or_arr(children)),
    max_leaves=20,
)


# ---------- deep nesting near the 1000 limit ----------

def _deep(depth, open_ch, close_ch):
    return open_ch * depth + close_ch * depth


_deep_nesting = st.one_of(
    st.integers(min_value=0, max_value=1005).map(lambda d: _deep(d, "[", "]")),
    st.integers(min_value=0, max_value=1005).map(lambda d: _deep(d, '{"a":', "}")),
    st.integers(min_value=990, max_value=1010).map(lambda d: _deep(d, "[", "]")),
    st.integers(min_value=990, max_value=1010).map(lambda d: _deep(d, '{"k":', "}")),
    st.integers(min_value=0, max_value=1000).map(lambda d: "[" * d + "1" + "]" * d),
    st.integers(min_value=0, max_value=1000).map(
        lambda d: '{"x":' * d + "0" + "}" * d
    ),
)


# ---------- top-level wrappers ----------

_bom = st.just("\ufeff")
_ws_prefix = st.sampled_from(["", " ", "\n", "\t", " \n\t\r "])
_trailing = st.sampled_from(["", " ", "abc", " 1 2", "\x00", "  \n"])


def _with_affixes(v):
    return st.tuples(_ws_prefix, st.just(v), _trailing).map(lambda t: t[0] + t[1] + t[2])


# Small set of targeted single-feature JSON fragments for mutation-style fuzzing.
_fragments = st.one_of(
    _string_strategy(),
    _number_strategy(),
    _literal,
    st.just("{}"),
    st.just("[]"),
)


def _mutated(v):
    """Splice a fragment into a valid value to produce structural near-misses."""
    return st.tuples(st.just(v), _fragments).map(
        lambda t: t[0] + "," + t[1]
    )


_top = st.one_of(
    _recursive_value,
    _deep_nesting,
    st.just(""),
    st.just("   "),
    st.just("\x00"),
    st.just("1abc"),
    st.just("1 2"),
    st.just("\ufeff1"),
    st.just("\ufeff{}"),
    st.just('{"a":1,"a":2}'),
    st.just('"\\ud800"'),
    st.just('"\\udc00"'),
    st.just('"\\ud83d\\ude00"'),
    st.just('"\\u0000"'),
    st.just('"a\x00b"'),
    st.just("1e309"),
    st.just("-1e309"),
    st.just("0x10"),
    st.just("01"),
    st.just("1."),
    st.just("[]"),
    st.just("{}"),
)

# ---------- structural mutation of valid documents ----------

# Bytes that are useful for splicing into valid JSON to create near-misses.
_splice_bytes = st.sampled_from(
    list('{}[],:"\\ \n\t0123456789.eE+-tfn') + ["\x00", "\x7f", "\ufeff"]
)


def _splice(v):
    """Insert/delete/replace a small chunk inside a valid document."""
    n = len(v)

    def _do(op, idx, chunk):
        i = min(idx, n)
        if op == 0:  # insert
            return v[:i] + chunk + v[i:]
        if op == 1 and n > 0:  # delete a byte
            j = min(i + 1, n)
            return v[:i] + v[j:]
        if n > 0:  # replace
            j = min(i + 1, n)
            return v[:i] + chunk + v[j:]
        return v + chunk

    return st.tuples(
        st.integers(min_value=0, max_value=2),
        st.integers(min_value=0, max_value=max(n, 1)),
        _splice_bytes,
    ).map(lambda t: _do(t[0], t[1], t[2]))


def _truncate(v):
    n = len(v)
    return st.integers(min_value=0, max_value=n).map(lambda k: v[:k])


def _mutations(v):
    return st.one_of(_splice(v), _truncate(v))


# ---------- multi-splice mutation (improved fuzzing) ----------

def _multi_splice(v):
    """Apply several insert/delete/replace operations in sequence for
    deeper structural corruption of a valid document."""
    n = len(v)

    def _do_ops(ops):
        s = v
        for op, idx, chunk in ops:
            m = len(s)
            i = min(idx, m)
            if op == 0:  # insert
                s = s[:i] + chunk + s[i:]
            elif op == 1 and m > 0:  # delete
                j = min(i + 1, m)
                s = s[:i] + s[j:]
            elif m > 0:  # replace
                j = min(i + 1, m)
                s = s[:i] + chunk + s[j:]
            else:
                s = s + chunk
        return s

    op = st.tuples(
        st.integers(min_value=0, max_value=2),
        st.integers(min_value=0, max_value=max(n, 1)),
        _splice_bytes,
    )
    return st.lists(op, min_size=1, max_size=4).map(_do_ops)


strategy = st.one_of(
    _top,
    _top.flatmap(_with_affixes),
    _recursive_value.flatmap(_with_affixes),
    _recursive_value.flatmap(_mutated),
    _recursive_value.flatmap(_mutations),
    _recursive_value.flatmap(_multi_splice),
    _deep_nesting.flatmap(_mutations),
)
```