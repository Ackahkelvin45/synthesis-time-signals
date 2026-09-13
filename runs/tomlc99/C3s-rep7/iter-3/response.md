```python
from hypothesis import strategies as st
import json

# ---------- helpers ----------

_ALPHA = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_DIGIT = "0123456789"
_BARE_CHARS = _ALPHA + _DIGIT + "-_"

# control chars allowed raw (parser accepts them), but no NUL byte anywhere
_CTRL_OK = [chr(c) for c in range(1, 32)] + [chr(127)]


def _join(parts):
    return "".join(parts)


# ---------- keys ----------

_unquoted_key = st.text(alphabet=_BARE_CHARS, min_size=1, max_size=12)

_basic_key_str = st.builds(
    lambda inner: '"' + inner + '"',
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters='"\\\n\r',
        ),
        max_size=8,
    ),
)

_literal_key_str = st.builds(
    lambda inner: "'" + inner + "'",
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters="'\n\r",
        ),
        max_size=8,
    ),
)

_simple_key = st.one_of(
    _unquoted_key,
    _basic_key_str,
    _literal_key_str,
    st.just('""'),  # empty quoted key
)

# ---------- strings (all four quoting forms) ----------

_escapes = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

_uni_escape = st.builds(
    lambda h: "\\u" + h,
    st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4),
)

_exuni_escape = st.builds(
    lambda h: "\\U" + h,
    st.text(alphabet="0123456789abcdefABCDEF", min_size=8, max_size=8),
)

_esc = st.one_of(_escapes, _uni_escape, _exuni_escape)

_basic_inner = st.one_of(
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters='"\\\n\r',
        ),
        max_size=10,
    ),
    _esc,
    st.text(alphabet=_CTRL_OK, max_size=4),
)

_basic_string = st.builds(
    lambda parts: '"' + "".join(parts) + '"',
    st.lists(_basic_inner, max_size=6),
)

_literal_inner = st.one_of(
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters="'\n\r",
        ),
        max_size=10,
    ),
    st.text(alphabet=_CTRL_OK, max_size=4),
)

_literal_string = st.builds(
    lambda parts: "'" + "".join(parts) + "'",
    st.lists(_literal_inner, max_size=6),
)

_ml_basic_inner = st.one_of(
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters='"\\',
        ),
        max_size=10,
    ),
    _esc,
    st.just("\n"),
    st.just('\\\n'),
    st.text(alphabet=_CTRL_OK, max_size=4),
)

_ml_basic_string = st.builds(
    lambda parts: '"""' + "".join(parts) + '"""',
    st.lists(_ml_basic_inner, max_size=6),
)

_ml_literal_inner = st.one_of(
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters="'",
        ),
        max_size=10,
    ),
    st.just("\n"),
    st.text(alphabet=_CTRL_OK, max_size=4),
)

_ml_literal_string = st.builds(
    lambda parts: "'''" + "".join(parts) + "'''",
    st.lists(_ml_literal_inner, max_size=6),
)

_string = st.one_of(
    _basic_string, _literal_string, _ml_basic_string, _ml_literal_string
)

# ---------- integers ----------

_dec_int = st.one_of(
    st.integers(min_value=-(2 ** 63), max_value=2 ** 63),
    st.integers(min_value=-(2 ** 200), max_value=2 ** 200),
    st.just(0),
    st.just(7),
    st.just(-0),
).map(str)

_hex_int = st.builds(
    lambda h: "0x" + h,
    st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=17),
)

_oct_int = st.builds(
    lambda h: "0o" + h,
    st.text(alphabet="01234567", min_size=1, max_size=20),
)

_bin_int = st.builds(
    lambda h: "0b" + h,
    st.text(alphabet="01", min_size=1, max_size=64),
)

_int_with_underscores = st.builds(
    lambda digits: digits,
    st.from_regex(r"[1-9][0-9]_[0-9](_[0-9]){0,5}", fullmatch=True),
).map(lambda s: s.replace("__", "_"))

_integer = st.one_of(
    _dec_int,
    _hex_int,
    _oct_int,
    _bin_int,
    _int_with_underscores,
    st.just("007"),
    st.just("-007"),
)

# ---------- floats ----------

_float = st.one_of(
    st.builds(
        lambda m, e: m + e,
        st.one_of(
            st.just("0.0"),
            st.just("1."),
            st.just(".5"),
            st.just("-0.0"),
            st.just("1e309"),
            st.just("-1e309"),
            st.just("3.141592653589793"),
        ),
        st.one_of(st.just(""), st.just("e10"), st.just("E-5"), st.just("e+300")),
    ),
    st.from_regex(r"[+-]?[0-9]+\.[0-9]+([eE][+-]?[0-9]+)?", fullmatch=True),
    st.from_regex(r"[+-]?[0-9]+[eE][+-]?[0-9]+", fullmatch=True),
    st.sampled_from(["inf", "-inf", "+inf", "nan", "-nan", "+nan"]),
)

# ---------- booleans ----------

_boolean = st.sampled_from(["true", "false"])

# ---------- date-times ----------

_2d = st.from_regex(r"[0-9]{2}", fullmatch=True)
_4d = st.from_regex(r"[0-9]{4}", fullmatch=True)

_local_date = st.builds(
    lambda y, m, d: f"{y}-{m}-{d}", _4d, _2d, _2d
)

_local_time = st.builds(
    lambda h, m, s: f"{h}:{m}:{s}",
    _2d,
    _2d,
    _2d,
)

_local_time_frac = st.builds(
    lambda h, m, s, f: f"{h}:{m}:{s}.{f}",
    _2d,
    _2d,
    _2d,
    st.text(alphabet=_DIGIT, min_size=1, max_size=6),
)

_local_date_time = st.builds(
    lambda d, sep, t: f"{d}{sep}{t}",
    _local_date,
    st.sampled_from(["T", "t", " "]),
    st.one_of(_local_time, _local_time_frac),
)

_offset = st.one_of(
    st.just("Z"),
    st.builds(
        lambda sign, h, m: f"{sign}{h}:{m}",
        st.sampled_from(["+", "-"]),
        _2d,
        _2d,
    ),
)

_offset_date_time = st.builds(
    lambda d, sep, t, o: f"{d}{sep}{t}{o}",
    _local_date,
    st.sampled_from(["T", "t", " "]),
    st.one_of(_local_time, _local_time_frac),
    _offset,
)

_date_time = st.one_of(
    _offset_date_time,
    _local_date_time,
    _local_date,
    _local_time,
    _local_time_frac,
    st.just("1979-02-30"),  # calendar-invalid, accepted
)

# ---------- recursive values ----------

_key = st.one_of(_simple_key, st.builds(
    lambda a, b: a + "." + b,
    _simple_key,
    _simple_key,
))

_scalar_value = st.one_of(
    _string,
    _integer,
    _float,
    _boolean,
    _date_time,
)

# inline table: recursive via st.recursive
def _inline_table_extend(value_st, key_st):
    return st.builds(
        lambda kvs: "{" + ", ".join(kvs) + "}",
        st.lists(
            st.builds(
                lambda k, v: k + " = " + v,
                key_st,
                value_st,
            ),
            min_size=0,
            max_size=4,
        ),
    )


def _array_extend(value_st):
    return st.builds(
        lambda items: "[" + ", ".join(items) + "]",
        st.lists(value_st, min_size=0, max_size=5),
    )


_value = st.recursive(
    _scalar_value,
    lambda children: st.one_of(
        _array_extend(children),
        _inline_table_extend(children, _key),
    ),
    max_leaves=12,
)

# ---------- deep nesting (arrays / inline tables) in the 1500-2048 band ----------

def _deep_array(depth):
    inner = "1"
    for _ in range(depth):
        inner = "[" + inner + "]"
    return inner


def _deep_inline(depth):
    inner = "1"
    for _ in range(depth):
        inner = "{a = " + inner + "}"
    return inner


_deep_nesting = st.one_of(
    st.integers(min_value=1500, max_value=2048).map(_deep_array),
    st.integers(min_value=1500, max_value=2048).map(_deep_inline),
)

_deep_value = st.one_of(_value, _deep_nesting)

# ---------- documents ----------

_key_value = st.builds(
    lambda k, v: k + " = " + v,
    _key,
    _deep_value,
)

_comment = st.builds(
    lambda body: "#" + body,
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters="\n\r",
        ),
        max_size=20,
    ),
)

_standard_table = st.builds(
    lambda k: "[" + k + "]",
    _key,
)

_array_table = st.builds(
    lambda k: "[[" + k + "]]",
    _key,
)

_line = st.one_of(
    _key_value,
    _standard_table,
    _array_table,
    _comment,
    st.just(""),
)

_document = st.builds(
    lambda lines: "\n".join(lines),
    st.lists(_line, min_size=0, max_size=10),
)

# ---------- malformed / near-valid inputs ----------

_malformed = st.sampled_from([
    'a = "unterminated',
    "a = 'unterminated",
    'a = """unterminated',
    "a = [[1, 2, 3",
    "a = [1, 2, 3]]",
    "a = {b = 1",
    "a = {b = 1}}",
    "[table",
    "[[array_table",
    "a = ",
    "= 1",
    "a = 1 2",
    "a = @",
    "a = 1\nb = 2\nc =",
    "a = 1\r\nb = 2",
    "a = 1\n\na = 2",  # duplicate key
    "[t]\n[t]",  # duplicate table
    "a = {b = 1,\n c = 2}",  # newline in inline table
    'a = "\\q"',  # invalid escape
    "a = 1\nb = 2\nc = 3\nkey = 4",  # near-valid
    "a = 1,",  # stray token
    "a = 1;",  # stray token
    "a = 1\nb = 2\nc = 3\n[",  # missing delimiter
    "a = 1\nb = 2\nc = 3\n]",  # doubled delimiter
    "a = 1\nb = 2\nc = 3\n[[t]",  # missing delimiter
    "a = 1\nb = 2\nc = 3\n[t]]",  # doubled delimiter
    "a = 1\nb = 2\nc = 3\n[t\n",  # missing delimiter
    "a = 1\nb = 2\nc = 3\n[t]]\n",  # doubled delimiter
    "a = 1\nb = 2\nc = 3\nt = {",  # incomplete inline table
    "a = 1\nb = 2\nc = 3\nt = [",  # incomplete array
    "a = 1\nb = 2\nc = 3\nt = 1.",  # valid-ish float
    "a = 1\nb = 2\nc = 3\nt = .5",  # valid-ish float
    "a = 1\nb = 2\nc = 3\nt = 007",  # leading zeros
    "a = 1\nb = 2\nc = 3\nt = 1979-02-30",  # calendar-invalid
    "a = 1\nb = 2\nc = 3\nt = {b = 1,}",  # trailing comma in inline table
    "a = 1\nb = 2\nc = 3\nt = [1, 2,]",  # trailing comma in array
    "a = 1\nb = 2\nc = 3\nt = {b = 1, c = 2}",  # valid inline table
    "a = 1\nb = 2\nc = 3\nt = [1, 2, 3]",  # valid array
    "a = 1\nb = 2\nc = 3\nt = \"x\x01y\"",  # raw control char in string
    "a = 1\nb = 2\nc = 3\n# comment with \x01 control\n",  # control in comment
])

# ---------- final strategy ----------

strategy = st.one_of(
    _document,
    _malformed,
    st.builds(
        lambda lines, tail: "\n".join(lines) + tail,
        st.lists(_line, min_size=0, max_size=8),
        st.sampled_from(["", "\n", "\r\n", "\n# trailing comment"]),
    ),
    # NEW: exercise parser branches for dotted keys, quoted dotted segments,
    # whitespace around '=', nested tables, and multiline/edge numeric forms.
    st.builds(
        lambda body: body,
        st.sampled_from([
            'a.b.c = 1',
            'a . b . c = 1',
            '"a".b = 1',
            "'a'.'b' = 1",
            'a."b.c".d = 1',
            'a\t=\t1',
            'a=1',
            '  a = 1  ',
            '[a.b.c]\nx = 1',
            '[a."b.c"]\nx = 1',
            '[[a.b]]\nx = 1',
            '[a]\n[a.b]\n[a.b.c]',
            '[[fruit]]\nname = "apple"\n[[fruit.variety]]\nname = "red"',
            'a = +1',
            'a = +0',
            'a = -0',
            'a = 0xDEADBEEF',
            'a = 0o755',
            'a = 0b1101',
            'a = 1_000_000',
            'a = 1e0',
            'a = 1E0',
            'a = 0.0e0',
            'a = 6.626e-34',
            'a = 224_617.445_991_228',
            'a = true',
            'a = false',
            'a = ""',
            "a = ''",
            'a = """\nmulti\nline\n"""',
            "a = '''\nmulti\nline\n'''",
            'a = """\\\n  continued"""',
            'a = "\\u00e9"',
            'a = "\\U0001F600"',
            'a = "tab\\there"',
            'a = [ ]',
            'a = [1,]',
            'a = { }',
            'a = {b = 1, c = {d = 2}}',
            'a = [[1], [2, 3], []]',
            'a = [1, "two", true, 1979-05-27T07:32:00Z]',
            'a = {x = [1, 2], y = {z = "s"}}',
            'a = 1979-05-27T07:32:00.999999Z',
            'a = 1979-05-27T00:32:00-07:00',
            'a = 1979-05-27 07:32:00',
            'a = 07:32:00',
            'a = 1979-05-27',
            '\ufeffa = 1',
            'a = 1 # trailing',
            '# leading comment\na = 1',
            '\n\n\na = 1\n\n\n',
            'a = "\\"quoted\\""',
            "a = 'lit \\' quote'",
            'a = """has " one quote"""',
            "a = '''has ' one quote'''",
            'a = "\\\\"',
            'a = "\\/"',
            'a = "\\b\\f\\n\\r\\t"',
            # NEW: extra branches — empty/edge documents, whitespace-only,
            # CRLF variants, bare CR, nested array tables, key edge cases,
            # multiline string with quotes at boundaries, and numeric edges.
            '',
            '\n',
            '\r\n',
            '\r',
            '   ',
            '\t\t',
            '#',
            '#\n',
            'a = ""\n',
            'a = 1\r\nb = 2\r\n',
            'a = 1\rb = 2',
            'a = 1\n\rb = 2',
            'a."b" = 1',
            'a.b."c" = 1',
            '"a.b" = 1',
            '"" = 1',
            "'' = 1",
            'a = """quote at end\\""""',
            "a = '''quote at end\\''''",
            'a = """\\""""',
            "a = '''\\''''",
            'a = """line1\nline2\nline3"""',
            "a = '''line1\nline2\nline3'''",
            'a = 0x0',
            'a = 0o0',
            'a = 0b0',
            'a = 0x_1',
            'a = 1_2_3_4',
            'a = -0x1',
            'a = -0o7',
            'a = -0b1',
            'a = 1e-0',
            'a = 1E+0',
            'a = 0e0',
            'a = 0.0',
            'a = -0.0',
            'a = +0.0',
            'a = 00:00:00',
            'a = 23:59:59.999999',
            'a = 1979-05-27T07:32:00.999999+07:00',
            'a = 1979-05-27T07:32:00.999999-07:00',
            'a = 1979-05-27T07:32:00.999999',
            'a = 1979-05-27T07:32:00',
            'a = 1979-05-27t07:32:00z',
            'a = 1979-05-27 07:32:00Z',
            '[[a]]\n[[a]]\n[[a]]',
            '[a]\n[a.b]\n[a.b.c]\n[a.b.c.d]',
            '[a.b]\n[a]',
            '[[a.b]]\n[[a.b]]',
            'a = [\n  1,\n  2,\n]',
            'a = {\n  b = 1,\n}',
            'a = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]',
            'a = {b = 1, c = 2, d = 3, e = 4}',
            'a = [[[[[[[[1]]]]]]]]',
            'a = {b = {c = {d = {e = 1}}}}',
            'a = [{}]',
            'a = [[]]',
            'a = {b = []}',
            'a = {b = {}}',
            'a = "\\u0000"',
            'a = "\\U00000000"',
            'a = "\\uD800"',
            'a = "\\uDFFF"',
            'a = "\\uFFFF"',
            'a = "\\U0010FFFF"',
            'a = "\\U00110000"',
            'a = "\\t\\n\\r\\b\\f"',
            'a = "\\x41"',
            'a = "\\0"',
            'a = "\\a"',
            'a = "\\ "',
            'a = "\\\\\\""',
            'a = "\\"\\\\"',
            'a = 1 # c\n',
            'a = 1\n# c\n',
            '# c\na = 1\n# c',
            'a = 1\n\nb = 2\n\nc = 3',
        ]),
    ),
)
```