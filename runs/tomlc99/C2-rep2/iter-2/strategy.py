from hypothesis import strategies as st
import json

# ---------- low-level character helpers ----------

def _no_nul(s: str) -> bool:
    return "\x00" not in s

_safe_text = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters="\x00",
    ),
    max_size=8,
)

# ---------- keys ----------

_unquoted_key = st.from_regex(r"[A-Za-z0-9_-]{1,12}", fullmatch=True)

_basic_key_string = st.builds(
    lambda inner: '"' + inner + '"',
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters='"\\\n\x00',
        ),
        max_size=8,
    ),
)

_literal_key_string = st.builds(
    lambda inner: "'" + inner + "'",
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters="'\n\x00",
        ),
        max_size=8,
    ),
)

_simple_key = st.one_of(
    _unquoted_key,
    _basic_key_string,
    _literal_key_string,
    st.just('""'),
)

_dotted_key = st.lists(_simple_key, min_size=2, max_size=4).map(".".join)

_key = st.one_of(_simple_key, _dotted_key)

# ---------- strings ----------

_escapes = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

_unicode_escape = st.integers(min_value=0, max_value=0xFFFF).map(
    lambda n: "\\u%04X" % n
)

_ex_unicode_escape = st.integers(min_value=0, max_value=0x10FFFF).map(
    lambda n: "\\U%08X" % n
)

_escape = st.one_of(_escapes, _unicode_escape, _ex_unicode_escape)

_basic_char = st.one_of(
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters='"\\\n\x00',
        ),
        min_size=1,
        max_size=1,
    ),
    _escape,
)

_basic_string = st.builds(
    lambda parts: '"' + "".join(parts) + '"',
    st.lists(_basic_char, max_size=8),
)

_ml_basic_char = st.one_of(
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters="\\\x00",
        ),
        min_size=1,
        max_size=1,
    ),
    _escape,
    st.just("\\\n"),
)

_ml_basic_string = st.builds(
    lambda parts: '"""' + "".join(parts) + '"""',
    st.lists(_ml_basic_char, max_size=8),
)

_literal_string = st.builds(
    lambda inner: "'" + inner + "'",
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters="'\n\x00",
        ),
        max_size=8,
    ),
)

_ml_literal_string = st.builds(
    lambda inner: "'''" + inner + "'''",
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters="\x00",
        ),
        max_size=8,
    ),
)

_string = st.one_of(
    _basic_string,
    _ml_basic_string,
    _literal_string,
    _ml_literal_string,
    st.just('""'),
    st.just("''"),
)

# ---------- numbers ----------

_dec_int = st.one_of(
    st.integers(min_value=-10**30, max_value=10**30).map(str),
    st.sampled_from(
        [
            "0",
            "-0",
            "+0",
            "007",
            "1_000",
            "9_223_372_036_854_775_807",
            "-9_223_372_036_854_775_808",
            "99999999999999999999999999999999999999",
            "-99999999999999999999999999999999999999",
        ]
    ),
)

_hex_int = st.one_of(
    st.from_regex(r"0x[0-9A-Fa-f]{1,16}", fullmatch=True),
    st.sampled_from(["0x0", "0xDEADBEEF", "0xdead_beef", "0xFFFFFFFFFFFFFFFF"]),
)

_oct_int = st.one_of(
    st.from_regex(r"0o[0-7]{1,16}", fullmatch=True),
    st.sampled_from(["0o0", "0o777", "0o7_7_7"]),
)

_bin_int = st.one_of(
    st.from_regex(r"0b[01]{1,16}", fullmatch=True),
    st.sampled_from(["0b0", "0b1", "0b1010_1010"]),
)

_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

_float = st.one_of(
    st.sampled_from(
        [
            "1.0",
            "3.1415",
            "-0.01",
            "5e+22",
            "1e6",
            "-2E-2",
            "6.626e-34",
            "1.",
            ".5",
            "1e309",
            "-1e309",
            "0.0",
            "1_000.000_1",
            "224_617.445_991_228",
        ]
    ),
    st.builds(
        lambda a, b: a + "." + b,
        st.integers(min_value=-10**6, max_value=10**6).map(str),
        st.integers(min_value=0, max_value=10**6).map(str),
    ),
    st.builds(
        lambda a, e: a + "e" + e,
        st.integers(min_value=-10**6, max_value=10**6).map(str),
        st.integers(min_value=-309, max_value=309).map(str),
    ),
)

_inf_nan = st.sampled_from(
    ["inf", "+inf", "-inf", "nan", "+nan", "-nan"]
)

_floating_point = st.one_of(_float, _inf_nan)

# ---------- booleans ----------

_bool = st.sampled_from(["true", "false"])

# ---------- dates ----------

_year = st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n)
_month = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_day = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_hour = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_minute = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_second = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_secfrac = st.integers(min_value=1, max_value=999999).map(lambda n: "." + str(n))

_full_date = st.builds(
    lambda y, m, d: y + "-" + m + "-" + d, _year, _month, _day
)

_partial_time = st.builds(
    lambda h, m, s, f: h + ":" + m + ":" + s + f,
    _hour,
    _minute,
    _second,
    st.one_of(st.just(""), _secfrac),
)

_offset = st.one_of(
    st.just("Z"),
    st.just("z"),
    st.builds(
        lambda sign, h, m: sign + h + ":" + m,
        st.sampled_from(["+", "-"]),
        _hour,
        _minute,
    ),
)

_delim = st.sampled_from(["T", "t", " "])

_offset_date_time = st.builds(
    lambda d, sep, t, off: d + sep + t + off,
    _full_date,
    _delim,
    _partial_time,
    _offset,
)

_local_date_time = st.builds(
    lambda d, sep, t: d + sep + t, _full_date, _delim, _partial_time
)

_local_date = _full_date

_local_time = _partial_time

_date_time = st.one_of(
    _offset_date_time,
    _local_date_time,
    _local_date,
    _local_time,
    st.sampled_from(
        [
            "1979-05-27T07:32:00Z",
            "1979-05-27T00:32:00-07:00",
            "1979-05-27 07:32:00Z",
            "1979-05-27T07:32:00",
            "1979-05-27",
            "07:32:00",
            "1979-02-30",
            "0000-00-00",
        ]
    ),
)

# ---------- recursive values ----------

def _join_value_parts(parts):
    return "".join(parts)


def _array_str(inner_values, comments):
    # inner_values: list of value strings
    # comments: list of comment strings (may be empty)
    pieces = ["["]
    for v in inner_values:
        pieces.append("\n")
        pieces.append(v)
        pieces.append(",")
    if comments:
        for c in comments:
            pieces.append("\n")
            pieces.append(c)
    pieces.append("\n]")
    return "".join(pieces)


def _inline_table_str(pairs):
    # pairs: list of (key, value) strings
    body = ", ".join(k + " = " + v for (k, v) in pairs)
    return "{" + body + "}"


def _make_array(values, comments):
    return _array_str(values, comments)


def _make_inline_table(pairs):
    return _inline_table_str(pairs)


_value = st.deferred(lambda: _value_impl)

_value_impl = st.one_of(
    _string,
    _integer,
    _floating_point,
    _bool,
    _date_time,
    _array,
    _inline_table,
)

_array_inner = st.lists(_value, max_size=4)

_array_comment = st.builds(
    lambda c: "#" + c,
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters="\n\x00",
        ),
        max_size=8,
    ),
)

_array_comment_list = st.lists(_array_comment, max_size=2)

_array = st.builds(_make_array, _array_inner, _array_comment_list)

_inline_pair = st.tuples(_key, _value).map(lambda kv: (kv[0], kv[1]))

_inline_pairs = st.lists(_inline_pair, max_size=4)

_inline_table = st.builds(_make_inline_table, _inline_pairs)

# ---------- statements / documents ----------

_key_value = st.builds(
    lambda k, v: k + " = " + v, _key, _value
)

_comment = st.builds(
    lambda c: "#" + c,
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters="\n\x00",
        ),
        max_size=16,
    ),
)

_standard_table = st.builds(
    lambda k: "[" + k + "]", _key
)

_array_table = st.builds(
    lambda k: "[[" + k + "]]", _key
)

_table = st.one_of(_standard_table, _array_table)

_expression = st.one_of(
    _key_value,
    _table,
    _comment,
    st.just(""),
)

_line_sep = st.sampled_from(["\n", "\r\n"])

_document = st.builds(
    lambda exprs, seps: "".join(
        e + (seps[i] if i < len(seps) else "\n")
        for i, e in enumerate(exprs)
    ),
    st.lists(_expression, min_size=0, max_size=10),
    st.lists(_line_sep, min_size=0, max_size=12),
)

# ---------- malformed / edge-case documents ----------

_malformed = st.one_of(
    # unterminated basic string
    st.builds(
        lambda s: "a = \"" + s,
        st.text(
            alphabet=st.characters(
                blacklist_categories=("Cs",),
                blacklist_characters='"\n\x00',
            ),
            max_size=8,
        ),
    ),
    # unterminated literal string
    st.builds(
        lambda s: "a = '" + s,
        st.text(
            alphabet=st.characters(
                blacklist_categories=("Cs",),
                blacklist_characters="'\n\x00",
            ),
            max_size=8,
        ),
    ),
    # missing closing bracket
    st.just("[table\n"),
    # doubled delimiter
    st.just("[[table]]]\n"),
    # stray token
    st.just("a = = 1\n"),
    # value on next line
    st.just("a =\n1\n"),
    # invalid escape
    st.just('a = "\\q"\n'),
    # non-ASCII bare key
    st.just("café = 1\n"),
    # newline inside inline table
    st.just("a = {b = 1,\nc = 2}\n"),
)

# ---------- deep nesting ----------

def _deep_array(depth):
    return "[" * depth + "]" * depth


def _deep_inline_table(depth):
    inner = "x = 1"
    for _ in range(depth):
        inner = "{a = " + inner + "}"
    return inner


_deep_array_doc = st.integers(min_value=1, max_value=2048).map(
    lambda d: "a = " + _deep_array(d) + "\n"
)

_deep_inline_doc = st.integers(min_value=1, max_value=200).map(
    lambda d: "a = " + _deep_inline_table(d) + "\n"
)

# ---------- duplicate keys / tables ----------

_duplicate_keys = st.builds(
    lambda k: k + " = 1\n" + k + " = 2\n", _unquoted_key
)

_duplicate_tables = st.builds(
    lambda k: "[" + k + "]\n[" + k + "]\n", _unquoted_key
)

# ---------- empty / comment-only ----------

_empty_doc = st.just("")

_comment_only = st.builds(
    lambda c: "#" + c + "\n",
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters="\n\x00",
        ),
        max_size=16,
    ),
)

# ---------- control bytes in strings/comments ----------

_control_char = st.integers(min_value=1, max_value=31).map(chr)

_control_in_string = st.builds(
    lambda c: 'a = "x' + c + 'y"\n', _control_char
)

_control_in_comment = st.builds(
    lambda c: "#" + c + "\n", _control_char
)

# ---------- final strategy ----------

strategy = st.one_of(
    _document,
    _malformed,
    _deep_array_doc,
    _deep_inline_doc,
    _duplicate_keys,
    _duplicate_tables,
    _empty_doc,
    _comment_only,
    _control_in_string,
    _control_in_comment,
    st.sampled_from(
        [
            "a = 007\n",
            "a = 1.\n",
            "a = .5\n",
            'a = "x\x01y"\n',
            "# comment\x01\n",
            "a = {b = 1,}\n",
            "a = 1979-02-30\n",
            'a = "\\u0000"\n',
            'a = "\\U0001F600"\n',
            "a = inf\n",
            "a = -inf\n",
            "a = nan\n",
            "a = -nan\n",
            "a = 0xDEADBEEF\n",
            "a = 0o777\n",
            "a = 0b1010\n",
            "a = 1_000_000\n",
            "a = 1e309\n",
            "a = 99999999999999999999999999999999\n",
            '"" = 1\n',
            "a.b.c = 1\n",
            "['a']\n",
            '[["a"]]\n',
            "a = []\n",
            "a = {}\n",
            "a = [1, 2, 3,]\n",
            "a = [[1], [2]]\n",
            "a = [{b = 1}]\n",
            "a = 1979-05-27T07:32:00Z\n",
            "a = 1979-05-27 07:32:00Z\n",
            "a = 1979-05-27T07:32:00\n",
            "a = 1979-05-27\n",
            "a = 07:32:00\n",
            "a = true\n",
            "a = false\n",
            "a = '''multi\nline'''\n",
            'a = """multi\nline"""\n',
            "a = 'literal'\n",
            'a = "basic"\n',
            "[table]\nkey = 1\n",
            "[[array]]\nkey = 1\n",
            "a = 1 # comment\n",
            "\n\n\n",
            "\t a = 1\n",
            "a = 1",
        ]
    ),
)