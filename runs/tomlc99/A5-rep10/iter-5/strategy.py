from hypothesis import strategies as st
import json

# ---------- small helpers ----------

def _join(parts):
    return "".join(parts)

# ---------- basic lexical atoms ----------

_alpha = st.sampled_from(list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"))
_digit = st.sampled_from(list("0123456789"))
_keychar = st.sampled_from(list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"))

_unquoted_key = st.lists(_keychar, min_size=1, max_size=10).map(_join)

# ASCII text without quotes/backslash/newline for basic strings
_basic_char = st.sampled_from(
    list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 !#$%&()*+,-./:;<=>?@[]^_`{|}~")
) | st.integers(min_value=1, max_value=0x10FFFF).map(chr).filter(
    lambda c: c not in '"\\\n\r' and c != "\x00"
)

# raw control characters (allowed by parser inside strings/comments)
_control_char = st.integers(min_value=1, max_value=31).map(chr)

_esc_simple = st.sampled_from(list('"\\/bfnrt'))
_esc_unicode = st.tuples(
    st.just("u"),
    st.lists(st.sampled_from(list("0123456789abcdefABCDEF")), min_size=4, max_size=4).map(_join),
).map(_join)
_esc_exunicode = st.tuples(
    st.just("U"),
    st.lists(st.sampled_from(list("0123456789abcdefABCDEF")), min_size=8, max_size=8).map(_join),
).map(_join)
_escape = st.one_of(_esc_simple, _esc_unicode, _esc_exunicode).map(lambda s: "\\" + s)

_basic_body_char = st.one_of(_basic_char, _control_char, _escape)

# ---------- strings (four quoting forms) ----------

_basic_string = st.lists(_basic_body_char, max_size=12).map(
    lambda cs: '"' + _join(cs) + '"'
)

_literal_body_char = st.one_of(
    st.sampled_from(list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 !#$%&()*+,-./:;<=>?@[]^_`{|}~\"\\")),
    st.integers(min_value=1, max_value=0x10FFFF).map(chr).filter(lambda c: c not in "'\n\r" and c != "\x00"),
    _control_char,
)

_literal_string = st.lists(_literal_body_char, max_size=12).map(
    lambda cs: "'" + _join(cs) + "'"
)

_ml_basic_body_char = st.one_of(
    _basic_body_char,
    st.just("\n"),
    st.just("\r\n"),
)
_ml_basic_string = st.lists(_ml_basic_body_char, max_size=12).map(
    lambda cs: '"""' + _join(cs) + '"""'
)

_ml_literal_char = st.one_of(
    _literal_body_char,
    st.just("\n"),
    st.just("\r\n"),
)
_ml_literal_string = st.lists(_ml_literal_char, max_size=12).map(
    lambda cs: "'''" + _join(cs) + "'''"
)

_string_strategy = st.one_of(
    _basic_string,
    _literal_string,
    _ml_basic_string,
    _ml_literal_string,
)

# ---------- numbers ----------

_dec_digits = st.lists(_digit, min_size=1, max_size=18).map(_join)
_dec_int = st.tuples(
    st.sampled_from(["", "+", "-"]),
    _dec_digits,
).map(_join)

_hex_digit = st.sampled_from(list("0123456789abcdefABCDEF"))
_hex_int = st.tuples(
    st.just("0x"),
    st.lists(_hex_digit, min_size=1, max_size=16).map(_join),
).map(_join)

_oct_digit = st.sampled_from(list("01234567"))
_oct_int = st.tuples(
    st.just("0o"),
    st.lists(_oct_digit, min_size=1, max_size=16).map(_join),
).map(_join)

_bin_digit = st.sampled_from(list("01"))
_bin_int = st.tuples(
    st.just("0b"),
    st.lists(_bin_digit, min_size=1, max_size=32).map(_join),
).map(_join)

_int_strategy = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

_exp_part = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.lists(_digit, min_size=1, max_size=3).map(_join),
).map(_join)

_frac_part = st.tuples(
    st.just("."),
    st.lists(_digit, min_size=1, max_size=6).map(_join),
).map(_join)

_float_strategy = st.one_of(
    st.tuples(_dec_int, _frac_part).map(_join),
    st.tuples(_dec_int, _exp_part).map(_join),
    st.tuples(_dec_int, _frac_part, _exp_part).map(_join),
    st.just("inf"),
    st.just("-inf"),
    st.just("+inf"),
    st.just("nan"),
    st.just("-nan"),
    st.just("+nan"),
    # parser-lenient forms
    st.tuples(st.sampled_from(["1", "2", "0", "-1"]), st.just(".")).map(_join),
    st.tuples(st.just("."), st.lists(_digit, min_size=1, max_size=6).map(_join)).map(_join),
)

# ---------- booleans ----------

_bool_strategy = st.sampled_from(["true", "false"])

# ---------- date-times ----------

def _pad2(n):
    return "%02d" % n

_year = st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n)
_month = st.integers(min_value=0, max_value=99).map(_pad2)
_day = st.integers(min_value=0, max_value=99).map(_pad2)
_hour = st.integers(min_value=0, max_value=99).map(_pad2)
_minute = st.integers(min_value=0, max_value=99).map(_pad2)
_second = st.integers(min_value=0, max_value=99).map(_pad2)
_secfrac = st.lists(_digit, min_size=1, max_size=6).map(lambda d: "." + _join(d))

_full_date = st.tuples(_year, st.just("-"), _month, st.just("-"), _day).map(_join)
_partial_time = st.tuples(_hour, st.just(":"), _minute, st.just(":"), _second,
                          st.one_of(st.just(""), _secfrac)).map(_join)
_offset = st.one_of(
    st.just("Z"),
    st.tuples(st.sampled_from(["+", "-"]), _hour, st.just(":"), _minute).map(_join),
)
_delim = st.sampled_from(["T", "t", " "])

_offset_date_time = st.tuples(_full_date, _delim, _partial_time, _offset).map(_join)
_local_date_time = st.tuples(_full_date, _delim, _partial_time).map(_join)
_local_date = _full_date
_local_time = _partial_time

_datetime_strategy = st.one_of(
    _offset_date_time,
    _local_date_time,
    _local_date,
    _local_time,
)

# ---------- keys ----------

_quoted_key = st.one_of(_basic_string, _literal_string)

_simple_key = st.one_of(_unquoted_key, _quoted_key)

# ---------- recursive values ----------

def _array_strategy():
    inner = st.one_of(
        _string_strategy,
        _int_strategy,
        _float_strategy,
        _bool_strategy,
        _datetime_strategy,
        _value_strategy,
    )
    return st.lists(inner, max_size=6).map(lambda vs: "[" + ", ".join(vs) + "]")

def _inline_table_strategy():
    def _kv():
        return st.tuples(
            _simple_key,
            st.just(" = "),
            _value_strategy,
        ).map(_join)
    return st.lists(_kv(), max_size=4).map(lambda kvs: "{" + ", ".join(kvs) + "}")

_value_strategy = st.one_of(
    _string_strategy,
    _int_strategy,
    _float_strategy,
    _bool_strategy,
    _datetime_strategy,
    st.deferred(_array_strategy),
    st.deferred(_inline_table_strategy),
)

# ---------- key/value pairs ----------

def _key_strategy():
    simple = _simple_key
    dotted = st.lists(simple, min_size=2, max_size=4).map(lambda ks: ".".join(ks))
    return st.one_of(simple, dotted)

def _key_value_line():
    return st.tuples(
        _key_strategy(),
        st.just(" = "),
        _value_strategy,
    ).map(_join)

# ---------- tables ----------

def _table_header():
    return st.tuples(
        st.just("["),
        _key_strategy(),
        st.just("]"),
    ).map(_join)

def _array_table_header():
    return st.tuples(
        st.just("[["),
        _key_strategy(),
        st.just("]]"),
    ).map(_join)

def _comment():
    body = st.lists(
        st.one_of(
            st.sampled_from(list("abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()")),
            _control_char,
        ),
        max_size=20,
    ).map(_join)
    return body.map(lambda s: "#" + s)

# ---------- document ----------

def _document():
    line = st.one_of(
        _key_value_line(),
        _table_header(),
        _array_table_header(),
        _comment(),
        st.just(""),
    )
    return st.lists(line, min_size=0, max_size=8).map(
        lambda lines: "\n".join(lines)
    )

# ---------- malformed / edge-case inputs ----------

def _malformed_strategy():
    samples = [
        # missing / doubled delimiters
        "[table",
        "[[array]",
        "a = [1, 2",
        "a = {b = 1",
        "a = {b = 1,",
        "a = ]",
        "a = }",
        # unterminated strings
        'a = "unterminated',
        "a = 'unterminated",
        'a = """unterminated',
        "a = '''unterminated",
        # stray token
        "a = ",
        " = 1",
        "a 1",
        "a = = 1",
        "a = 1 2",
        # newline inside inline table (rejected)
        "a = {b = 1,\nc = 2}",
        # invalid escape
        'a = "\\q"',
        # bare non-ascii key
        "caf\u00e9 = 1",
        # duplicate keys / tables
        "a = 1\na = 2",
        "[t]\n[t]",
        # value on next line
        "a =\n1",
        # empty key
        '"" = 1',
        # leading zeros / lenient floats
        "a = 007",
        "a = 1.",
        "a = .5",
        # control chars in strings and comments
        'a = "x\x01y"',
        "# comment \x02",
        # calendar-invalid date
        "a = 1979-02-30",
        # deep-ish nesting (well below stack overflow threshold)
        "a = " + "[" * 100 + "]" * 100,
        # empty containers
        "a = []",
        "a = {}",
        "[t]",
        "[[a]]",
        # NUL-free unicode escape
        'a = "\\u0000"',
        # long key
        ("k" * 10000) + " = 1",
        # CRLF
        "a = 1\r\nb = 2",
        # tab indentation
        "\ta = 1",
        # no trailing newline
        "a = 1",
    ]
    return st.sampled_from(samples)

# ---------- recursive deep nesting strategy ----------

def _deep_value_strategy():
    # concentrate depth in 1500-2048 band for arrays and inline tables
    depth = st.integers(min_value=1500, max_value=2048)

    def build_array(d):
        if d <= 0:
            return "[]"
        return "[" + build_array(d - 1) + "]"

    def build_inline(d):
        if d <= 0:
            return "{}"
        return "{a = " + build_inline(d - 1) + "}"

    return st.one_of(
        depth.map(build_array),
        depth.map(build_inline),
    )

# ---------- structurally-valid document generator ----------

def _valid_document():
    # Generate a coherent TOML document: a sequence of top-level key/value
    # pairs, then optional tables with their own key/value pairs. This
    # exercises the parser's structural handling (scoping, table headers)
    # rather than just random line soup.
    def _top_kv():
        return _key_value_line()

    def _table_block():
        header = st.one_of(_table_header(), _array_table_header())
        body = st.lists(_key_value_line(), max_size=4).map(
            lambda ls: "\n".join(ls)
        )
        return st.tuples(header, body).map(
            lambda hb: hb[0] + ("\n" + hb[1] if hb[1] else "")
        )

    top = st.lists(_top_kv(), max_size=4).map(lambda ls: "\n".join(ls))
    tables = st.lists(_table_block(), max_size=3).map(lambda ls: "\n".join(ls))

    def _assemble(tk, tb):
        parts = []
        if tk:
            parts.append(tk)
        if tb:
            parts.append(tb)
        return "\n".join(parts)

    return st.tuples(top, tables).map(lambda p: _assemble(p[0], p[1]))

# ---------- mutation strategy (fuzz valid docs) ----------

_MUTATION_CHARS = list("[]{}=,.\"'#\n\r\t\\ 0123456789abcxyz+-_")

def _mutate(s):
    # Apply a small number of random character-level mutations to a
    # structurally-valid document, producing near-miss inputs that are
    # more likely to reach deep parser states than pure random soup.
    if not s:
        return st.just(s)
    n = len(s)

    def _sub(i):
        return st.tuples(st.just(i), st.sampled_from(_MUTATION_CHARS)).map(
            lambda ic: s[: ic[0]] + ic[1] + s[ic[0] + 1:]
        )

    def _ins(i):
        return st.tuples(st.just(i), st.sampled_from(_MUTATION_CHARS)).map(
            lambda ic: s[: ic[0]] + ic[1] + s[ic[0]:]
        )

    def _del(i):
        return st.just(i).map(lambda j: s[:j] + s[j + 1:])

    def _dup(i):
        return st.just(i).map(lambda j: s[:j] + s[j] + s[j:])

    idx = st.integers(min_value=0, max_value=max(0, n - 1))
    ops = st.one_of(
        idx.flatmap(_sub),
        idx.flatmap(_ins),
        idx.flatmap(_del),
        idx.flatmap(_dup),
    )
    return st.lists(ops, min_size=1, max_size=4).map(lambda fs: _join(fs))

_mutation_strategy = _valid_document().flatmap(_mutate)

# ---------- final strategy ----------

# Improve the fuzzer by:
#  * weighting toward structurally valid and near-valid documents, which
#    reach deeper parser states than pure line soup,
#  * adding a splice strategy that combines two valid documents and
#    injects delimiter-heavy tokens to trigger boundary bugs,
#  * keeping the malformed and deep-nesting cases for coverage of error
#    paths and recursion limits.

_DELIM_TOKENS = ["[", "]", "[[", "]]", "{", "}", "=", ",", ".", '"', "'",
                 '"""', "'''", "#", "\n", "\r\n", "\\"]

def _splice_strategy():
    def _splice(a, b):
        # Cut at random-ish positions and interleave delimiter tokens.
        if not a:
            return b
        if not b:
            return a
        i = len(a) // 2
        j = len(b) // 2
        return a[:i] + b[j:]
    return st.tuples(_valid_document(), _valid_document()).map(
        lambda ab: _splice(ab[0], ab[1])
    )

def _delimiter_injection():
    def _inject(doc, toks):
        if not doc:
            return _join(toks)
        pos = len(doc) // 2
        return doc[:pos] + _join(toks) + doc[pos:]
    return st.tuples(
        _valid_document(),
        st.lists(st.sampled_from(_DELIM_TOKENS), min_size=1, max_size=6),
    ).map(lambda dt: _inject(dt[0], dt[1]))

strategy = st.one_of(
    # weight valid / near-valid docs more heavily than raw soup
    _valid_document(),
    _valid_document(),
    _mutation_strategy,
    _mutation_strategy,
    _splice_strategy(),
    _delimiter_injection(),
    _document(),
    _malformed_strategy(),
    _deep_value_strategy().map(lambda v: "a = " + v),
).map(lambda s: s if isinstance(s, str) else str(s))