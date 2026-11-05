```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Basic character / text fragments
# ---------------------------------------------------------------------------

# Printable ASCII plus tabs, but no newline, no quote/backslash unless escaped.
_SAFE_CHARS = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    " _-.,:;!?@#$%^&*()+=<>/|~`'"
)

# Control bytes (no NUL, no newline / CR which would break single-line strings)
_CTRL = "".join(chr(c) for c in range(1, 32) if c not in (10, 13)) + "\x7f"

_ESC_SEQS = [
    "\\\"", "\\\\", "\\b", "\\f", "\\n", "\\r", "\\t",
    "\\u0000", "\\u00e9", "\\uFFFF", "\\u0041",
    "\\U0001F600", "\\U0010FFFF",
    # invalid / edge escapes to exercise error paths
    "\\q", "\\x", "\\ ", "\\u12", "\\U0001",
]

_NON_ASCII = "éßüñΩλ中文字😀🎉\u00e9\u0301"


def _basic_string_body():
    """Body of a single-line basic string: safe chars, escapes, ctrl, non-ascii."""
    piece = st.one_of(
        st.sampled_from(list(_SAFE_CHARS)) if _SAFE_CHARS else st.just("a"),
        st.sampled_from(_ESC_SEQS),
        st.sampled_from(list(_CTRL)),
        st.sampled_from(list(_NON_ASCII)),
    )
    return st.lists(piece, max_size=12).map("".join)


def _literal_string_body():
    piece = st.one_of(
        st.sampled_from(list(_SAFE_CHARS)) if _SAFE_CHARS else st.just("a"),
        st.sampled_from(list(_CTRL)),
        st.sampled_from(list(_NON_ASCII)),
        st.just('"'),
    )
    return st.lists(piece, max_size=12).map("".join)


def _ml_basic_body():
    piece = st.one_of(
        st.sampled_from(list(_SAFE_CHARS + " \t\n")),
        st.sampled_from(_ESC_SEQS),
        st.sampled_from(list(_CTRL)),
        st.sampled_from(list(_NON_ASCII)),
        st.just("\\\n"),
        st.just("\\\r\n"),
        st.just('"'),
        st.just('""'),
    )
    return st.lists(piece, max_size=16).map("".join)


def _ml_literal_body():
    piece = st.one_of(
        st.sampled_from(list(_SAFE_CHARS + " \t\n")),
        st.sampled_from(list(_CTRL)),
        st.sampled_from(list(_NON_ASCII)),
        st.just('"'),
        st.just("'"),
        st.just("''"),
    )
    return st.lists(piece, max_size=16).map("".join)


# ---------------------------------------------------------------------------
# Strings (all four quoting forms)
# ---------------------------------------------------------------------------

def _basic_string():
    return _basic_string_body().map(lambda b: '"' + b + '"')


def _literal_string():
    return _literal_string_body().map(lambda b: "'" + b + "'")


def _ml_basic_string():
    return _ml_basic_body().map(lambda b: '"""' + b + '"""')


def _ml_literal_string():
    return _ml_literal_body().map(lambda b: "'''" + b + "'''")


_string_strategy = st.one_of(
    _basic_string(),
    _literal_string(),
    _ml_basic_string(),
    _ml_literal_string(),
    st.just('""'),
    st.just("''"),
    st.just('""""""'),
    st.just("''''''"),
)


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

def _dec_int():
    sign = st.sampled_from(["", "+", "-"])
    digits = st.one_of(
        st.just("0"),
        st.just("007"),
        st.just("000"),
        st.integers(min_value=0, max_value=9).map(str),
        st.integers(min_value=0, max_value=10**30).map(str),
        st.integers(min_value=0, max_value=10**6).map(
            lambda n: "_".join(str(n))
        ),
        st.just("9223372036854775808"),
        st.just("18446744073709551616"),
        st.just("1" + "_0" * 40 + "0"),
        # malformed
        st.just("_1"),
        st.just("1_"),
        st.just("1__2"),
        st.just("+-1"),
        st.just("-"),
    )
    return st.tuples(sign, digits).map(lambda t: t[0] + t[1])


def _hex_int():
    body = st.one_of(
        st.just("0"),
        st.just("F"),
        st.just("deadBEEF"),
        st.just("7f_ff"),
        st.integers(min_value=0, max_value=16**20).map(lambda n: format(n, "x")),
        st.just(""),
        st.just("_"),
    )
    return body.map(lambda b: "0x" + b)


def _oct_int():
    body = st.one_of(
        st.just("0"),
        st.just("7"),
        st.just("1_2_3"),
        st.integers(min_value=0, max_value=8**20).map(lambda n: format(n, "o")),
        st.just(""),
        st.just("8"),
    )
    return body.map(lambda b: "0o" + b)


def _bin_int():
    body = st.one_of(
        st.just("0"),
        st.just("1"),
        st.just("1_0_1"),
        st.integers(min_value=0, max_value=2**40).map(lambda n: format(n, "b")),
        st.just(""),
        st.just("2"),
    )
    return body.map(lambda b: "0b" + b)


def _float():
    sign = st.sampled_from(["", "+", "-"])
    cases = st.one_of(
        st.just("1.0"),
        st.just("1."),
        st.just(".5"),
        st.just("0.0"),
        st.just("3.14159"),
        st.just("1e10"),
        st.just("1E+10"),
        st.just("1e-10"),
        st.just("6.02e23"),
        st.just("1_000.000_1"),
        st.just("1e309"),
        st.just("-1e309"),
        st.just("1e-400"),
        st.just("0.0000001"),
        st.just("123456789012345678901234567890.123456789"),
        st.integers(min_value=0, max_value=10**9).map(lambda n: "%d.%d" % (n, n)),
        st.integers(min_value=1, max_value=10**6).map(lambda n: "%de%d" % (n, n)),
        # malformed floats
        st.just("."),
        st.just("1e"),
        st.just("1e+"),
        st.just("1.2.3"),
        st.just("_1.0"),
    )
    return st.tuples(sign, cases).map(lambda t: t[0] + t[1])


def _inf_nan():
    return st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])


_integer_strategy = st.one_of(_dec_int(), _hex_int(), _oct_int(), _bin_int())
_float_strategy = st.one_of(_float(), _inf_nan())


# ---------------------------------------------------------------------------
# Booleans & date-times
# ---------------------------------------------------------------------------

_bool_strategy = st.sampled_from(["true", "false", "TRUE", "False", "tru"])


def _two(minv, maxv):
    return st.integers(min_value=minv, max_value=maxv).map(lambda n: "%02d" % n)


def _four():
    return st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n)


def _full_date():
    return st.tuples(_four(), _two(0, 99), _two(0, 99)).map(
        lambda t: t[0] + "-" + t[1] + "-" + t[2]
    )


def _partial_time():
    return st.tuples(_two(0, 99), _two(0, 99), _two(0, 99)).map(
        lambda t: t[0] + ":" + t[1] + ":" + t[2]
    )


def _secfrac():
    return st.integers(min_value=1, max_value=10**9).map(lambda n: "." + str(n))


def _offset():
    return st.one_of(
        st.just("Z"),
        st.just("z"),
        st.tuples(st.sampled_from(["+", "-"]), _two(0, 99), _two(0, 99)).map(
            lambda t: t[0] + t[1] + ":" + t[2]
        ),
        st.tuples(st.sampled_from(["+", "-"]), _two(0, 99)).map(
            lambda t: t[0] + t[1]
        ),
    )


def _delim():
    return st.sampled_from(["T", "t", " "])


def _offset_date_time():
    return st.tuples(
        _full_date(), _delim(), _partial_time(),
        st.one_of(st.just(""), _secfrac()), _offset(),
    ).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4])


def _local_date_time():
    return st.tuples(
        _full_date(), _delim(), _partial_time(),
        st.one_of(st.just(""), _secfrac()),
    ).map(lambda t: t[0] + t[1] + t[2] + t[3])


def _local_date():
    return _full_date()


def _local_time():
    return st.tuples(_partial_time(), st.one_of(st.just(""), _secfrac())).map(
        lambda t: t[0] + t[1]
    )


_date_time_strategy = st.one_of(
    _offset_date_time(),
    _local_date_time(),
    _local_date(),
    _local_time(),
    st.just("1979-02-30"),
    st.just("1979-05-27 07:32:00Z"),
    st.just("1979-05-27T07:32:00.999999-07:00"),
    # malformed date-times
    st.just("1979-13-01"),
    st.just("1979-05-27T25:00:00Z"),
    st.just("1979-05-27T07:32"),
    st.just("1979-5-27"),
)


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

def _unquoted_key():
    return st.one_of(
        st.just("a"),
        st.just("key"),
        st.just("A-B_c"),
        st.just("123"),
        st.just("x" * 10000),
        st.text(
            alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-",
            min_size=1, max_size=8,
        ),
    )


def _quoted_key():
    return st.one_of(_basic_string(), _literal_string(), st.just('""'), st.just("''"))


def _simple_key():
    return st.one_of(_quoted_key(), _unquoted_key())


def _dotted_key():
    return st.lists(_simple_key(), min_size=2, max_size=4).map(
        lambda ks: ".".join(ks)
    )


_key_strategy = st.one_of(_simple_key(), _dotted_key())


# ---------------------------------------------------------------------------
# Values: recursive (arrays & inline tables)
# ---------------------------------------------------------------------------

def _value_leaf():
    return st.one_of(
        _string_strategy,
        _integer_strategy,
        _float_strategy,
        _bool_strategy,
        _date_time_strategy,
    )


def _ws():
    return st.sampled_from(["", " ", "  ", "\t", " \t "])


def _comment():
    return st.one_of(
        st.just(""),
        st.just("#"),
        st.just("# comment"),
        st.just("#\x01\x02"),
        st.just("# " + "x" * 40),
    )


def _array_of(value):
    def build_elems(vals):
        if not vals:
            return st.just("[]")
        # elements separated by commas, optional trailing comma
        parts = []
        for v in vals:
            parts.append(v)
        joined = st.just(", ".join(parts))
        return st.tuples(joined, st.sampled_from(["", ","])).map(
            lambda t: "[" + t[0] + t[1] + "]"
        )

    # Build from a recursive value strategy
    inner = st.lists(value, max_size=4).flatmap(build_elems)
    return st.one_of(inner, st.just("[]"))


def _inline_table_of(value):
    def build_pairs(pairs):
        if not pairs:
            return st.just("{}")
        text = ", ".join(k + " = " + v for (k, v) in pairs)
        return st.tuples(
            st.just(text),
            st.sampled_from(["", ","]),
        ).map(lambda t: "{" + t[0] + t[1] + "}")

    kv = st.tuples(_simple_key(), value)
    return st.lists(kv, max_size=3).flatmap(build_pairs)


def _value_recursive():
    return st.recursive(
        _value_leaf(),
        lambda children: st.one_of(
            _array_of(children),
            _inline_table_of(children),
        ),
        max_leaves=20,
    )


_value_strategy = _value_recursive()


def _simple_value():
    """A non-recursive value (for shallow contexts)."""
    return _value_leaf()


# ---------------------------------------------------------------------------
# Deep nesting (arrays / inline tables) in the 1500-2048 band
# ---------------------------------------------------------------------------

def _deep_array(depth):
    def build(d):
        if d == 0:
            return st.just("[]")
        return build(d - 1).map(lambda inner: "[" + inner + "]")
    return build(depth)


def _deep_inline(depth):
    def build(d):
        if d == 0:
            return st.just("{}")
        return build(d - 1).map(lambda inner: "{a = " + inner + "}")
    return build(depth)


_deep_strategy = st.integers(min_value=1500, max_value=2048).flatmap(
    lambda d: st.one_of(_deep_array(d), _deep_inline(d))
)


# ---------------------------------------------------------------------------
# Key/value lines, tables, documents
# ---------------------------------------------------------------------------

def _key_value():
    return st.tuples(_key_strategy, _ws(), _value_strategy, _comment()).map(
        lambda t: t[0] + " = " + t[2] + t[3]
    )


def _key_value_deep():
    return st.tuples(_simple_key(), _deep_strategy).map(
        lambda t: t[0] + " = " + t[1]
    )


def _standard_table():
    return st.tuples(_key_strategy, _comment()).map(
        lambda t: "[" + t[0] + "]" + t[1]
    )


def _array_table():
    return st.tuples(_key_strategy, _comment()).map(
        lambda t: "[[" + t[0] + "]]" + t[1]
    )


def _blank_or_comment():
    return st.one_of(
        st.just(""),
        st.just("#"),
        st.just("# comment"),
        st.just("#\x01"),
        st.just("   "),
        st.just("\t"),
    )


def _expression():
    return st.one_of(
        _key_value(),
        _key_value_deep(),
        _standard_table(),
        _array_table(),
        _blank_or_comment(),
    )


def _nl():
    return st.sampled_from(["\n", "\r\n", "\n\n", "\r\n\r\n"])


def _document():
    return st.lists(_expression(), min_size=0, max_size=8).flatmap(
        lambda exprs: _join_document(exprs)
    )


def _join_document(exprs):
    if not exprs:
        return st.just("")
    seps = st.lists(_nl(), min_size=len(exprs) - 1, max_size=len(exprs) - 1)
    trailing = st.sampled_from(["", "\n", "\r\n"])

    def assemble(sep_list):
        parts = [exprs[0]]
        for s, e in zip(sep_list, exprs[1:]):
            parts.append(s)
            parts.append(e)
        return "".join(parts)

    return st.tuples(seps, trailing).map(
        lambda t: assemble(t[0]) + t[1]
    )


# ---------------------------------------------------------------------------
# Malformed / near-valid inputs
# ---------------------------------------------------------------------------

def _malformed():
    return st.one_of(
        # missing / doubled delimiters
        st.just("a = [1, 2"),
        st.just("a = [1, 2]]"),
        st.just("a = {b = 1"),
        st.just("a = {b = 1}}"),
        st.just("[t"),
        st.just("[t]]"),
        st.just("[[t]"),
        st.just("[[t]]]"),
        st.just("a = "),
        st.just("a"),
        st.just("= 1"),
        st.just("a == 1"),
        # unterminated strings
        st.just('a = "abc'),
        st.just("a = 'abc"),
        st.just('a = """abc'),
        st.just("a = '''abc"),
        # stray tokens
        st.just("a = 1 2"),
        st.just("a = @"),
        st.just("a = 1 @ 2"),
        st.just("a b = 1"),
        st.just("a = 1 = 2"),
        st.just("a = [1 2]"),
        st.just("a = {b 1}"),
        st.just("a = {b = }"),
        st.just("a = {= 1}"),
        # newline inside inline table
        st.just("a = {b = 1,\nc = 2}"),
        # invalid escape
        st.just('a = "\\q"'),
        # value on next line
        st.just("a =\n1"),
        # non-ascii bare key
        st.just("é = 1"),
        st.just("ключ = 1"),
        # duplicate keys / tables
        st.just("a = 1\na = 2"),
        st.just("[t]\n[t]"),
        st.just("[[a]]\n[[a]]"),
        st.just("[t]\na = 1\n[t.sub]\n[t]"),
        # bare key with bad char
        st.just("a.b.c = 1\na.b = 2"),
        # empty-ish
        st.just("\x00"),
    )


# ---------------------------------------------------------------------------
# Top-level strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _document(),
    _malformed(),
    st.just(""),
    st.just("\n"),
    st.just("# only a comment"),
    st.just("#\x01\x02\x03"),
    st.just('"" = 1'),
    st.just("a = 007"),
    st.just("a = 1."),
    st.just("a = .5"),
    st.just('a = "x\x01y"'),
    st.just("a = {b = 1,}"),
    st.just("a = 1979-02-30"),
    st.just("a = []"),
    st.just("a = {}"),
    st.just("[t]"),
    st.just("[[a]]"),
    st.just("a = [1, 2, 3,]"),
    st.just("a = [\n  1,\n  # c\n  2,\n]"),
    st.just("a = 1\r\nb = 2\r\n"),
    st.just("\ta = 1"),
    st.just("a = " + "k" * 10000),
)
```