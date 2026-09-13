```python
from hypothesis import strategies as st

# ---------- character pools ----------
_bare_key_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
_ascii_print = "".join(chr(c) for c in range(0x20, 0x7F))
_escapes = ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
_unicode_esc = st.integers(min_value=0, max_value=0xFFFF).map(
    lambda n: "\\u%04X" % n
)
_ex_unicode_esc = st.integers(min_value=0x10000, max_value=0x10FFFF).map(
    lambda n: "\\U%08X" % n
)


def _basic_char():
    return st.one_of(
        st.sampled_from(list(_ascii_print)),
        st.sampled_from(["\t", "\x01", "\x1f", "\x7f"]),
        st.sampled_from(_escapes),
        _unicode_esc,
        _ex_unicode_esc,
        st.characters(min_codepoint=0x80, max_codepoint=0x2FFF),
    )


def _basic_string_body():
    return st.lists(_basic_char(), min_size=0, max_size=8).map("".join)


def _literal_char():
    return st.one_of(
        st.sampled_from(list(_ascii_print)),
        st.sampled_from(["\t", "\x01", "\x1f", "\x7f"]),
        st.characters(min_codepoint=0x80, max_codepoint=0x2FFF),
    )


def _literal_string_body():
    return st.lists(_literal_char(), min_size=0, max_size=8).map("".join)


# ---------- strings ----------
basic_string = _basic_string_body().map(lambda s: '"' + s + '"')
literal_string = _literal_string_body().map(lambda s: "'" + s + "'")


def _ml_basic_body():
    return st.lists(_basic_char(), min_size=0, max_size=6).map("".join)


def _ml_literal_body():
    return st.lists(_literal_char(), min_size=0, max_size=6).map("".join)


ml_basic_string = _ml_basic_body().map(lambda s: '"""' + s + '"""')
ml_literal_string = _ml_literal_body().map(lambda s: "'''" + s + "'''")

string_value = st.one_of(
    basic_string, literal_string, ml_basic_string, ml_literal_string
)

# ---------- integers ----------
_dec_int = st.one_of(
    st.integers(min_value=-10**30, max_value=10**30).map(str),
    st.sampled_from(
        ["0", "-0", "+0", "007", "000123", "1_000", "10_000_000", "9" * 40]
    ),
)

_hex_digits = "0123456789abcdefABCDEF"
_oct_digits = "01234567"
_bin_digits = "01"


def _digit_run(alphabet, min_len=1, max_len=8):
    return st.lists(
        st.sampled_from(list(alphabet)), min_size=min_len, max_size=max_len
    ).map("".join)


_hex_int = _digit_run(_hex_digits).map(lambda d: "0x" + d)
_oct_int = _digit_run(_oct_digits).map(lambda d: "0o" + d)
_bin_int = _digit_run(_bin_digits).map(lambda d: "0b" + d)

_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

# ---------- floats ----------
_frac = st.one_of(
    _digit_run("0123456789", 1, 6).map(lambda d: "." + d),
    st.just("."),
)
_exp = st.one_of(
    st.tuples(
        st.sampled_from(["e", "E"]),
        st.sampled_from(["", "+", "-"]),
        _digit_run("0123456789", 1, 4),
    ).map(lambda t: t[0] + t[1] + t[2]),
    st.just(""),
)


def _float():
    return st.tuples(
        st.one_of(
            _digit_run("0123456789", 1, 6),
            st.just(""),
        ),
        _frac,
        _exp,
    ).map(lambda t: t[0] + t[1] + t[2])


_float_special = st.sampled_from(
    ["inf", "+inf", "-inf", "nan", "+nan", "-nan", "1e309", "1e-309", "0.0"]
)

floating_point = st.one_of(_float(), _float_special)

# ---------- booleans ----------
boolean = st.sampled_from(["true", "false"])
_bool_value = st.sampled_from(["true", "false"])

# ---------- date-times ----------
_year = st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n)
_month = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_day = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_hour = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_minute = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_second = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)


def _full_date():
    return st.tuples(_year, _month, _day).map(lambda t: t[0] + "-" + t[1] + "-" + t[2])


def _partial_time():
    return st.tuples(_hour, _minute, _second).map(
        lambda t: t[0] + ":" + t[1] + ":" + t[2]
    )


_secfrac = _digit_run("0123456789", 1, 6).map(lambda d: "." + d)
_offset = st.one_of(
    st.just("Z"),
    st.tuples(
        st.sampled_from(["+", "-"]), _hour, _minute
    ).map(lambda t: t[0] + t[1] + ":" + t[2]),
)
_delim = st.sampled_from(["T", "t", " "])

_offset_date_time = st.tuples(
    _full_date(),
    _delim,
    _partial_time(),
    st.one_of(_secfrac, st.just("")),
    _offset,
).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4])

_local_date_time = st.tuples(
    _full_date(), _delim, _partial_time(), st.one_of(_secfrac, st.just(""))
).map(lambda t: t[0] + t[1] + t[2] + t[3])

_local_date = _full_date()

_local_time = st.tuples(_partial_time(), st.one_of(_secfrac, st.just(""))).map(
    lambda t: t[0] + t[1]
)

date_time = st.one_of(
    _offset_date_time, _local_date_time, _local_date, _local_time
)

# ---------- keys ----------
_unquoted_key = st.lists(
    st.sampled_from(list(_bare_key_chars)), min_size=1, max_size=8
).map("".join)

_quoted_key = st.one_of(basic_string, literal_string)

_simple_key = st.one_of(_unquoted_key, _quoted_key)

_dotted_key = st.lists(_simple_key, min_size=2, max_size=3).map(".".join)

key = st.one_of(_simple_key, _dotted_key)

# ---------- values (recursive) ----------
_scalar_value = st.one_of(
    string_value, _integer, floating_point, _bool_value, date_time
)


def _array_values_inner(inner):
    return st.lists(inner, min_size=0, max_size=4).map(
        lambda xs: "[" + ", ".join(xs) + "]"
    )


def _inline_table_inner(inner):
    def build(pairs):
        return "{" + ", ".join(pairs) + "}"

    pair = st.tuples(key, inner).map(lambda t: t[0] + " = " + t[1])
    return st.lists(pair, min_size=0, max_size=3).map(build)


value = st.recursive(
    _scalar_value,
    lambda inner: st.one_of(
        _array_values_inner(inner),
        _inline_table_inner(inner),
    ),
    max_leaves=12,
)

# ---------- statements / documents ----------
_key_value = st.tuples(key, value).map(lambda t: t[0] + " = " + t[1])

_standard_table = key.map(lambda k: "[" + k + "]")
_array_table = key.map(lambda k: "[[" + k + "]]")

_comment = st.one_of(
    st.just("#"),
    st.lists(
        st.one_of(
            st.sampled_from(list(_ascii_print)),
            st.sampled_from(["\t", "\x01", "\x7f"]),
            st.characters(min_codepoint=0x80, max_codepoint=0x2FFF),
        ),
        min_size=0,
        max_size=12,
    ).map(lambda cs: "#" + "".join(cs)),
)

_expression = st.one_of(
    _key_value,
    _standard_table,
    _array_table,
    _comment,
)


def _document():
    return st.lists(_expression, min_size=0, max_size=6).map("\n".join)


# ---------- edge-case / malformed generators ----------
def _deep_array(depth):
    return "[" * depth + "]" * depth


_deep_array_st = st.integers(min_value=1500, max_value=2048).map(_deep_array)


def _deep_inline(depth):
    return "{a = " * depth + "1" + "}" * depth


_deep_inline_st = st.integers(min_value=200, max_value=600).map(_deep_inline)

_edge_documents = st.sampled_from(
    [
        "",
        "\n",
        "\r\n",
        "# only a comment",
        "# comment\n",
        "a = 1",
        "a = 1\n",
        "a = 1\r\nb = 2\r\n",
        "[t]\n",
        "[[a]]\n",
        "[[a]]\n[[a]]\n",
        '"" = 1',
        "a = {b = 1,}",
        "a = {b = 1, c = 2,}",
        "a = [1, 2, 3,]",
        "a = []",
        "a = {}",
        "a = 007",
        "a = 1.",
        "a = .5",
        "a = 1979-02-30",
        "a = 1979-05-27 07:32:00Z",
        "a = 1979-05-27T07:32:00",
        "a = 07:32:00",
        "a = 1979-05-27",
        "a = inf",
        "a = -inf",
        "a = nan",
        "a = 0xDEADBEEF",
        "a = 0o755",
        "a = 0b1010",
        "a = 1_000_000",
        "a = 1e309",
        "a = 9223372036854775808",
        "a = \"\\u0000\"",
        'a = "x\x01y"',
        "a = 'literal\\path'",
        'a = """multi\nline"""',
        "a = '''multi\nline'''",
        "a.b.c = 1",
        '"quoted key" = 1',
        "'lit key' = 1",
        "a = 1\na = 2",
        "[t]\n[t]\n",
        "a = [1, [2, [3, [4]]]]",
        "a = {b = {c = {d = 1}}}",
        "a = [1,\n # comment\n 2]",
        "a = ",
        "= 1",
        "a =",
        "a = [1, 2",
        "a = {b = 1",
        'a = "unterminated',
        "a = 'unterminated",
        "a = [1 2]",
        "a = {b = 1 c = 2}",
        "a = {b = 1\nc = 2}",
        "a = 1 2",
        "a b = 1",
        "a = \\q",
        "[a\n",
        "[[a]\n",
        "a = ]",
        "a = }",
        "a = ,",
        "a = .",
        "a = true",
        "a = false",
        "a = True",
        "a = FALSE",
        "[t]\nb = true\nc = false",
        "a = [true, false]",
        "a = {b = true, c = false}",
    ]
)


def _complete_doc():
    return _document()


@st.composite
def _doc_with_edge(draw):
    kind = draw(st.integers(min_value=0, max_value=3))
    if kind == 0:
        return draw(_complete_doc())
    if kind == 1:
        return draw(_edge_documents)
    if kind == 2:
        return draw(_deep_array_st)
    return draw(_deep_inline_st)


strategy = st.one_of(
    _doc_with_edge(),
    _edge_documents,
    _complete_doc(),
    _bool_value.map(lambda b: "a = " + b),
)
```