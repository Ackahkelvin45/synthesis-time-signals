```python
import json
from hypothesis import strategies as st

# ---------- helpers ----------

def _join(parts):
    return "".join(parts)

def _join_comma(parts):
    return ",".join(parts)

# ---------- keys ----------

_unquoted_key_char = st.sampled_from(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
)

_unquoted_key = st.text(_unquoted_key_char, min_size=1, max_size=12)

_basic_key_esc = st.sampled_from(
    ['\\"', "\\\\", "\\b", "\\f", "\\n", "\\r", "\\t", "\\/"]
)

_unicode_esc = st.integers(min_value=0, max_value=0x10FFFF).map(
    lambda n: "\\u%04X" % (n & 0xFFFF)
)

_basic_key_body_char = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E).filter(
        lambda c: c not in '"\\'
    ),
    st.characters(min_codepoint=0x80, max_codepoint=0x2FFF),
    _basic_key_esc,
    _unicode_esc,
)

_basic_key = st.lists(_basic_key_body_char, max_size=8).map(
    lambda cs: '"' + "".join(cs) + '"'
)

_literal_key_body_char = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E).filter(lambda c: c != "'"),
    st.characters(min_codepoint=0x80, max_codepoint=0x2FFF),
)

_literal_key = st.lists(_literal_key_body_char, max_size=8).map(
    lambda cs: "'" + "".join(cs) + "'"
)

_simple_key = st.one_of(_unquoted_key, _basic_key, _literal_key)

_dotted_key = st.lists(_simple_key, min_size=2, max_size=3).map(
    lambda ks: ".".join(ks)
)

_key = st.one_of(_simple_key, _dotted_key)

# ---------- strings (four quoting forms) ----------

_esc = st.sampled_from(
    ['\\"', "\\\\", "\\b", "\\f", "\\n", "\\r", "\\t", "\\/"]
)

_unicode_esc4 = st.integers(min_value=0, max_value=0xFFFF).map(
    lambda n: "\\u%04X" % n
)
_unicode_esc8 = st.integers(min_value=0, max_value=0x10FFFF).map(
    lambda n: "\\U%08X" % n
)

_basic_char = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E).filter(
        lambda c: c not in '"\\'
    ),
    st.characters(min_codepoint=0x80, max_codepoint=0x2FFF),
    _esc,
    _unicode_esc4,
    _unicode_esc8,
)

_basic_string = st.lists(_basic_char, max_size=10).map(
    lambda cs: '"' + "".join(cs) + '"'
)

_literal_char = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E).filter(lambda c: c != "'"),
    st.characters(min_codepoint=0x80, max_codepoint=0x2FFF),
)

_literal_string = st.lists(_literal_char, max_size=10).map(
    lambda cs: "'" + "".join(cs) + "'"
)

_ml_basic_char = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E).filter(
        lambda c: c not in '"\\'
    ),
    st.characters(min_codepoint=0x80, max_codepoint=0x2FFF),
    st.just("\n"),
    st.just("\t"),
    _esc,
    _unicode_esc4,
    _unicode_esc8,
)

_ml_basic_string = st.lists(_ml_basic_char, max_size=14).map(
    lambda cs: '"""' + "".join(cs) + '"""'
)

_ml_literal_char = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E).filter(
        lambda c: c != "'"
    ),
    st.characters(min_codepoint=0x80, max_codepoint=0x2FFF),
    st.just("\n"),
    st.just("\t"),
)

_ml_literal_string = st.lists(_ml_literal_char, max_size=14).map(
    lambda cs: "'''" + "".join(cs) + "'''"
)

_string = st.one_of(
    _basic_string,
    _literal_string,
    _ml_basic_string,
    _ml_literal_string,
)

# ---------- numbers ----------

_dec_int = st.one_of(
    st.integers(min_value=-(2 ** 70), max_value=2 ** 70).map(str),
    st.sampled_from(
        [
            "0",
            "-0",
            "+0",
            "007",
            "000",
            "1_000",
            "1_2_3",
            "9223372036854775807",
            "-9223372036854775808",
            "9223372036854775808",
            "18446744073709551616",
            "99999999999999999999999999999999",
        ]
    ),
)

_hex_int = st.one_of(
    st.sampled_from(
        ["0x0", "0xDEADBEEF", "0xdeadbeef", "0xFF_FF", "0x1_2_3", "0xabcdefABCDEF"]
    ),
    st.integers(min_value=0, max_value=2 ** 64).map(lambda n: "0x%X" % n),
)

_oct_int = st.one_of(
    st.sampled_from(["0o0", "0o777", "0o1_2_3", "0o01234567"]),
    st.integers(min_value=0, max_value=2 ** 32).map(lambda n: "0o%o" % n),
)

_bin_int = st.one_of(
    st.sampled_from(["0b0", "0b1", "0b1_0_1", "0b101010"]),
    st.integers(min_value=0, max_value=2 ** 32).map(lambda n: "0b" + format(n, "b")),
)

_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

_float = st.one_of(
    st.sampled_from(
        [
            "1.0",
            "-0.0",
            "+1.5",
            "1.",
            ".5",
            "3.14159",
            "1e10",
            "1E10",
            "1e+10",
            "1e-10",
            "1.5e10",
            "1.5E-10",
            "1_000.000_1",
            "1e309",
            "-1e309",
            "1e-309",
            "0.0",
            "6.626e-34",
            "224_617.445_991_228",
        ]
    ),
    st.tuples(
        st.integers(min_value=-1000, max_value=1000),
        st.integers(min_value=0, max_value=999999),
    ).map(lambda t: "%d.%06d" % t),
    st.tuples(
        st.integers(min_value=-100, max_value=100),
        st.integers(min_value=-300, max_value=300),
    ).map(lambda t: "%de%d" % t),
)

_inf_nan = st.sampled_from(
    ["inf", "+inf", "-inf", "nan", "+nan", "-nan"]
)

_floating_point = st.one_of(_float, _inf_nan)

_bool_ = st.sampled_from(["true", "false"])

# ---------- dates ----------

_date = st.tuples(
    st.integers(min_value=0, max_value=9999),
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
).map(lambda t: "%04d-%02d-%02d" % t)

_time = st.tuples(
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
).map(lambda t: "%02d:%02d:%02d" % t)

_secfrac = st.integers(min_value=0, max_value=999999).map(lambda n: ".%06d" % n)

_partial_time = st.tuples(_time, st.one_of(st.none(), _secfrac)).map(
    lambda t: t[0] + (t[1] or "")
)

_offset = st.one_of(
    st.just("Z"),
    st.just("z"),
    st.tuples(
        st.sampled_from(["+", "-"]),
        st.integers(min_value=0, max_value=23),
        st.integers(min_value=0, max_value=59),
    ).map(lambda t: "%s%02d:%02d" % t),
)

_delim = st.sampled_from(["T", "t", " "])

_offset_date_time = st.tuples(_date, _delim, _partial_time, _offset).map(
    lambda t: t[0] + t[1] + t[2] + t[3]
)

_local_date_time = st.tuples(_date, _delim, _partial_time).map(
    lambda t: t[0] + t[1] + t[2]
)

_local_date = _date
_local_time = _partial_time

_date_time = st.one_of(
    _offset_date_time,
    _local_date_time,
    _local_date,
    _local_time,
)

# ---------- recursive values: arrays and inline tables ----------

def _value_strategy(children):
    return st.one_of(
        _string,
        _integer,
        _floating_point,
        _bool_,
        _date_time,
        children,
    )

def _array_children(children):
    value = _value_strategy(children)

    simple_elems = st.lists(
        value,
        max_size=4,
    ).map(lambda vs: "[" + ", ".join(vs) + "]")

    trailing = st.lists(
        value,
        min_size=1,
        max_size=4,
    ).map(lambda vs: "[" + ", ".join(vs) + ",]")

    empty = st.just("[]")

    multiline = st.lists(
        value,
        max_size=4,
    ).map(
        lambda vs: "[\n"
        + "".join("  " + v + ",\n" for v in vs)
        + "]"
    )

    return st.one_of(empty, simple_elems, trailing, multiline)

def _inline_table_children(children):
    value = _value_strategy(children)

    def _kv(pair):
        return pair[0] + " = " + pair[1]

    pair = st.tuples(_key, value).map(_kv)

    non_empty = st.lists(pair, min_size=1, max_size=4).map(
        lambda ps: "{" + ", ".join(ps) + "}"
    )

    trailing = st.lists(pair, min_size=1, max_size=4).map(
        lambda ps: "{" + ", ".join(ps) + ",}"
    )

    empty = st.just("{}")

    return st.one_of(empty, non_empty, trailing)

_value = st.recursive(
    _value_strategy(st.nothing()),
    lambda children: st.one_of(
        _array_children(children),
        _inline_table_children(children),
    ),
    max_leaves=12,
)

# ---------- key/value lines, tables, comments ----------

_comment_text = st.one_of(
    st.text(
        st.characters(min_codepoint=0x20, max_codepoint=0x7E),
        max_size=20,
    ),
    st.text(
        st.characters(min_codepoint=0x80, max_codepoint=0x2FFF),
        max_size=10,
    ),
    st.just("control:\x01\x02\x1f"),
)

_comment = st.one_of(
    st.just(""),
    _comment_text.map(lambda t: "#" + t),
)

def _kv_line(pair):
    key, value, comment = pair
    line = key + " = " + value
    if comment:
        line += " " + comment
    return line

_kv_line = st.tuples(_key, _value, _comment).map(_kv_line)

_standard_table = st.lists(_key, min_size=1, max_size=3).map(
    lambda ks: "[" + ".".join(ks) + "]"
)

_array_table = st.lists(_key, min_size=1, max_size=3).map(
    lambda ks: "[[" + ".".join(ks) + "]]"
)

# ---------- malformed / near-valid fragments ----------

def _malformed_pairs():
    return [
        'a = "unterminated',
        "a = 'unterminated",
        'a = """unterminated',
        "a = '''unterminated",
        "a = [1, 2",
        "a = {b = 1",
        "a = {b = 1,",
        "a = 1 2",
        "a = = 1",
        "a = ",
        "= 1",
        "a 1",
        "[t",
        "[t]]",
        "[[t]",
        "[[t]]]",
        "a = [1,,2]",
        "a = {,}",
        "a = {b = }",
        "a = 1\nb = ",
        "a = \"x\\qy\"",
        "a = 1.2.3",
        "a = 0x",
        "a = 0b2",
        "a = 0o8",
        "a = 01:02",
        "a = 1979-05-27T",
        "a = \"\"\"x\"\"",
        "a = '''x''",
        "a = +",
        "a = -",
        "a = e10",
        "a = .",
        "a = ..",
        "a = {: 1}",
        "a = {b = 1\nc = 2}",
        "a = [1,\n]",
        "a = tru",
        "a = truee",
        "a = nann",
        "a = inff",
        "[t]\n[t]",
        "a = 1\na = 2",
        "a = 1\n[t]\na = 2\n[t]",
        "a.b = 1\na.b = 2",
        "a = 1\n[a]\nb = 2",
        "[a]\n[a.b]\n[a]",
        "a = [\n1,\n2\n",
        "a = {b = {c = 1}",
        "a = [[1], [2]",
        "a = [1] extra",
        "a = 1 # comment\n= 2",
        "a = 1\n\n= 2",
        "a = 1\r\nb = 2\r\nc = 3",
        "a = \"\"\"\nmulti\nline\n\"\"\"",
        "a = '''\nmulti\nline\n'''",
        "a = \"\"\"x\"\"\"\"",
        "a = '''x''''",
        "a = \"\"\"\"\"\"\"",
        "a = '''''''",
        "a = 1e",
        "a = 1e+",
        "a = 1e+_",
        "a = 1_",
        "a = _1",
        "a = 1__0",
        "a = 0x_1",
        "a = 0b_1",
        "a = 0o_1",
        "a = 1.2e",
        "a = 1.2e+",
        "a = 1.2.3.4",
        "a = T",
        "a = Z",
        "a = 12:",
        "a = :12",
        "a = 12:34:",
        "a = -1979-05-27",
        "a = 1979-05-27T07:32:00.",
        "a = 1979-05-27T07:32:00+",
        "a = 1979-05-27T07:32:00+07:",
        "a = 1979-05-27T07:32:00Z extra",
    ]

_malformed = st.sampled_from(_malformed_pairs())

# ---------- deep nesting band (1500-2048) ----------

def _deep_array_strategy():
    return st.integers(min_value=1500, max_value=2048).map(
        lambda n: "a = " + "[" * n + "]" * n
    )

def _deep_inline_strategy():
    return st.integers(min_value=1500, max_value=2048).map(
        lambda n: "a = " + "{b = " * n + "1" + "}" * n
    )

_deep = st.one_of(_deep_array_strategy(), _deep_inline_strategy())

# ---------- document assembly ----------

_expression = st.one_of(
    _kv_line,
    _standard_table,
    _array_table,
    _comment,
)

_document = st.lists(_expression, min_size=0, max_size=10).map(
    lambda lines: "\n".join(lines)
)

_empty_or_comment_doc = st.one_of(
    st.just(""),
    st.just("\n"),
    st.just("# only a comment"),
    st.just("# c1\n# c2\n"),
    st.just("\r\n"),
    st.just("   \t  "),
)

_duplicate_doc = st.one_of(
    st.just("a = 1\na = 2"),
    st.just("[t]\nx = 1\n[t]\ny = 2"),
    st.just("[[a]]\n[[a]]\n[a]"),
    st.just("a.b = 1\na.b = 2"),
    st.just("a = 1\n[a]\nb = 2"),
)

_unicode_key_doc = st.just("caf\u00e9 = 1")

_doc_with_no_trailing_nl = _kv_line

_long_key = st.just("k" * 10000 + " = 1")

_crlf_doc = st.lists(_expression, min_size=1, max_size=5).map(
    lambda lines: "\r\n".join(lines)
)

_tab_indent_doc = st.lists(_kv_line, min_size=1, max_size=5).map(
    lambda lines: "\n".join("\t" + line for line in lines)
)

strategy = st.one_of(
    _document,
    _empty_or_comment_doc,
    _malformed,
    _deep,
    _duplicate_doc,
    _unicode_key_doc,
    _doc_with_no_trailing_nl,
    _long_key,
    _crlf_doc,
    _tab_indent_doc,
)
```