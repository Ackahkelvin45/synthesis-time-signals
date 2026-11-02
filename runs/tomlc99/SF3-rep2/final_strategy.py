from hypothesis import strategies as st
import json

# ---------- helpers ----------

_ws = st.sampled_from([" ", "\t", "  ", "\t\t", ""])

_basic_safe = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"\n\r\x00',
)

_unicode_safe = st.characters(
    blacklist_categories=("Cs", "Cc"),
    blacklist_characters='\\"\n\r\x00',
    min_codepoint=0x80,
)

_esc = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
     "\\u0000", "\\uFFFF", "\\u00e9", "\\U0001F600", "\\U00000041",
     "\\u0041", "\\u007f", "\\u0080", "\\u07ff", "\\u0800", "\\ud7ff",
     "\\ue000", "\\uffff", "\\U00010000", "\\U0010FFFF",
     "\\u00A0", "\\u2028", "\\u2029"]
)

def _basic_string_body():
    return st.one_of(_basic_safe, _unicode_safe, _esc)

basic_string = st.lists(_basic_string_body(), max_size=12).map(
    lambda cs: '"' + "".join(cs) + '"'
)

literal_string = st.lists(
    st.one_of(
        st.characters(blacklist_characters="'\n\r\x00"),
        _unicode_safe,
    ),
    max_size=12,
).map(lambda cs: "'" + "".join(cs) + "'")

ml_basic_string = st.lists(
    st.one_of(_basic_safe, _unicode_safe, _esc, st.just("\n"), st.just("\r\n")),
    max_size=10,
).map(lambda cs: '"""' + "".join(cs) + '"""')

ml_literal_string = st.lists(
    st.one_of(
        st.characters(blacklist_characters="'\x00"),
        _unicode_safe,
        st.just("\n"),
        st.just("\r\n"),
    ),
    max_size=10,
).map(lambda cs: "'''" + "".join(cs) + "'''")

# ---------- integers ----------

_dec_int = st.one_of(
    st.integers(min_value=0, max_value=9).map(str),
    st.integers(min_value=-(10**25), max_value=10**25).map(str),
    st.just("007"),
    st.just("0"),
    st.just("+0"),
    st.just("-0"),
    st.just("1_000"),
    st.just("9" * 40),
    st.just("1" + "_0" * 30),
)

_hex_int = st.one_of(
    st.integers(min_value=0, max_value=2**70).map(lambda n: "0x" + format(n, "x")),
    st.just("0xDEADBEEF"),
    st.just("0x0"),
    st.just("0xdead_beef"),
    st.just("0x" + "f" * 40),
)

_oct_int = st.one_of(
    st.integers(min_value=0, max_value=2**70).map(lambda n: "0o" + format(n, "o")),
    st.just("0o0"),
    st.just("0o777"),
    st.just("0o7_7_7"),
)

_bin_int = st.one_of(
    st.integers(min_value=0, max_value=2**70).map(lambda n: "0b" + format(n, "b")),
    st.just("0b0"),
    st.just("0b1010"),
    st.just("0b1_0_1"),
)

integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

# ---------- floats ----------

_float = st.one_of(
    st.floats(allow_nan=False, allow_infinity=False).map(repr),
    st.just("1."),
    st.just(".5"),
    st.just("+1.0"),
    st.just("-0.0"),
    st.just("1e309"),
    st.just("1e-309"),
    st.just("6.626e-34"),
    st.just("1_000.0"),
    st.just("1.0_1"),
    st.just("0e0"),
    st.just("1E+10"),
)

_inf_nan = st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])

floating_point = st.one_of(_float, _inf_nan)

# ---------- booleans ----------

boolean = st.sampled_from(["true", "false"])

# ---------- date-times ----------

_date = st.one_of(
    st.sampled_from([
        "1979-05-27", "0000-00-00", "1979-02-30", "9999-12-31",
        "2024-01-01", "1979-13-45", "2000-02-29", "1900-02-29",
        "2024-02-29", "2023-02-29", "1970-01-01", "0001-01-01",
        "9999-12-31", "2024-12-31", "2024-01-31", "2024-04-31",
    ])
)

_time = st.one_of(
    st.sampled_from([
        "07:32:00", "00:00:00", "23:59:59.999999", "07:32:00.1",
        "99:99:99", "12:00:00.000000001", "00:00:00.0", "23:59:60",
        "24:00:00", "12:34:56.123456789", "01:02:03.000000000",
    ])
)

_offset = st.sampled_from(["Z", "z", "+00:00", "-07:00", "+23:59", "-00:00",
                           "+05:30", "-12:00", "+14:00"])

_sep = st.sampled_from(["T", "t", " "])

def _mk_dt(parts):
    return "".join(parts)

datetime_ = st.one_of(
    st.tuples(_date, _sep, _time, _offset).map(_mk_dt),
    st.tuples(_date, _sep, _time).map(_mk_dt),
    _date,
    _time,
)

# ---------- keys ----------

_unquoted_key = st.one_of(
    st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-",
            min_size=1, max_size=8),
    st.just("a"),
    st.just("key"),
    st.just("x" * 100),
    st.just("k" * 10000),
    st.just("-"),
    st.just("_"),
    st.just("123"),
)

_quoted_key = st.one_of(basic_string, literal_string, st.just('""'))

simple_key = st.one_of(_unquoted_key, _quoted_key)

def _dotted_key(parts):
    return ".".join(parts)

dotted_key = st.lists(simple_key, min_size=2, max_size=4).map(_dotted_key)

key = st.one_of(simple_key, dotted_key)

# ---------- comments ----------

_comment_text = st.lists(
    st.one_of(
        st.characters(blacklist_characters="\n\r\x00"),
        _unicode_safe,
    ),
    max_size=20,
).map(lambda cs: "#" + "".join(cs))

comment_opt = st.one_of(st.just(""), _comment_text)

# ---------- recursive values: arrays and inline tables ----------

def _join_array(parts):
    inner = ",".join(parts)
    return "[" + inner + "]"

def _join_inline(parts):
    inner = ", ".join(parts)
    return "{" + inner + "}"

_simple_value_no_container = st.one_of(
    basic_string,
    ml_basic_string,
    literal_string,
    ml_literal_string,
    integer,
    floating_point,
    boolean,
    datetime_,
)

def _make_recursive_value():
    base = _simple_value_no_container
    def extend(children):
        arr = st.lists(children, max_size=4).map(_join_array)
        inner = st.lists(
            st.tuples(key, children).map(lambda t: t[0] + " = " + t[1]),
            max_size=4,
        ).map(_join_inline)
        return st.one_of(arr, inner)
    return st.recursive(base, extend, max_leaves=30)

_recursive_value = _make_recursive_value()

value = _recursive_value

_empty_containers = st.sampled_from(["[]", "{}", "[ ]", "{ }", "[\n]", "[\n\n]"])

value = st.one_of(value, _empty_containers)

_deep_array = st.integers(min_value=1, max_value=2048).map(
    lambda n: "[" * n + "]" * n
)

value = st.one_of(value, _deep_array)

# ---------- key-value lines ----------

key_value = st.tuples(key, value).map(lambda t: t[0] + " = " + t[1])

# ---------- tables ----------

_standard_table = key.map(lambda k: "[" + k + "]")
_array_table = key.map(lambda k: "[[" + k + "]]")

table = st.one_of(_standard_table, _array_table)

# ---------- expressions ----------

expression = st.one_of(
    st.tuples(key_value, comment_opt).map(lambda t: t[0] + (" " + t[1] if t[1] else "")),
    st.tuples(table, comment_opt).map(lambda t: t[0] + (" " + t[1] if t[1] else "")),
    comment_opt,
)

# ---------- malformed / near-valid inputs ----------

_malformed = st.sampled_from([
    "a = [1, 2",
    "a = {b = 1",
    "a = {b = 1,}",
    "a = [1, 2,]",
    "[t",
    "[[t]",
    "a = [[1, 2]]",
    "a = {{b = 1}}",
    "[t]]",
    "[[t]]]",
    'a = "unterminated',
    "a = 'unterminated",
    'a = """unterminated',
    "a = '''unterminated",
    "a = ",
    "= 1",
    "a 1",
    "a = 1 2",
    "a = ,",
    "a = [1 2]",
    "a = {b = 1 c = 2}",
    "a = 1\na = 2",
    "[t]\n[t]",
    "a = {b = 1,\nc = 2}",
    'a = "\\q"',
    "a =\n1",
    "café = 1",
    "a = 007",
    "a = 1.",
    "a = .5",
    'a = "x\x01y"',
    "# comment with \x01 control",
    "a = {b = 1,}",
    "a = 1979-02-30",
    'a = "\u00e9\u4e2d\U0001F600"',
    'a = "\u2028\u2029"',
    'a = "\u0080\u07ff\u0800"',
    "a = '\u00e9\u4e2d\U0001F600'",
    "a = '''\u00e9\u4e2d\U0001F600'''",
    'a = """\u00e9\u4e2d\U0001F600"""',
    "# \u00e9\u4e2d\U0001F600 comment",
    'a = "\ud800"',
    'a = "\udc00\ud800"',
    "a = '\ud800'",
    'a = "\xc0\x80"',
    'a = "\xe0\x80\x80"',
    'a = "\xf0\x80\x80\x80"',
    'a = "\xff"',
    'a = "\xed\xa0\x80"',
    "\ufeffa = 1",
    "a = 1\ufeff",
    "a = 2024-02-29T00:00:00Z",
    "a = 2023-02-29T00:00:00Z",
    "a = 1979-05-27T07:32:00.999999-07:00",
    "a = 1979-05-27 07:32:00z",
    "a = 24:00:00",
    "a = 23:59:60",
    "a = " + "[" * 300 + "]" * 300,
    "a = " + "[" * 2048 + "]" * 2048,
])

# ---------- document ----------

def _join_exprs(exprs):
    return "\n".join(exprs)

_unicode_document = st.lists(
    st.one_of(
        key_value,
        table,
        comment_opt,
    ),
    min_size=1,
    max_size=6,
).map(_join_exprs)

# Targeted documents that specifically exercise the least-covered functions:
# toml_utf8_to_ucs, norm_lit_str, toml_rtos, toml_timestamp_at.
# Each is a full valid (or near-valid) document so the parser reaches the
# relevant code path rather than bailing out early.
_targeted_document = st.one_of(
    st.sampled_from([
        'a = "hello"',
        "a = 'hello'",
        'a = """multi\nline"""',
        "a = '''multi\nline'''",
        'a = "\\u00e9\\U0001F600"',
        "a = 'plain literal é中😀'",
        'a = """\\t\\n\\r\\\\"""',
        "a = '''\t\n\r\\'''",
        'a = ""',
        "a = ''",
        'a = """x"""',
        "a = '''x'''",
        'a = "\\u0000"',
        'a = "\\U0010FFFF"',
    ]),
    st.sampled_from([
        'a = "\\u00e9"',
        'a = "\\u4e2d"',
        'a = "\\U0001F600"',
        'a = "\\u0080"',
        'a = "\\u07ff"',
        'a = "\\u0800"',
        'a = "\\uffff"',
        'a = "\\U00010000"',
        'a = "\\U0010FFFF"',
        'a = "é"',
        'a = "中"',
        'a = "😀"',
        'a = "\u0080\u07ff\u0800\uffff"',
        'a = "\U00010000\U0010FFFF"',
        'a = "\\u00e9\\u4e2d\\U0001F600"',
        'a = "\\uD7FF\\uE000"',
        'a = "\\uD800"',
        'a = "\\uDFFF"',
        'a = "\\uFFFF"',
        'a = "\\U0000FFFF"',
        'a = "\\U00110000"',
        'a = "\\UFFFFFFFF"',
    ]),
    st.sampled_from([
        "a = '''\nhello'''",
        "a = '''\n\nhello\n\n'''",
        "a = '''hello\\nworld'''",
        "a = '''line1\nline2\nline3'''",
        "a = '''\r\nfoo\r\n'''",
        "a = '''\\'''",
        "a = ''''''''",
        "a = '''''''''",
        "a = '''x''y'''",
        "a = '''\\t\\n'''",
        "a = '''é中😀'''",
        "a = '''\u2028\u2029'''",
        "a = '''\n'''",
        "a = '''\n\n'''",
        "a = '''a\nb'''",
        "a = '''a\r\nb'''",
    ]),
    st.sampled_from([
        "a = 1979-05-27T07:32:00Z",
        "a = 1979-05-27T07:32:00.999999-07:00",
        "a = 1979-05-27T00:32:00.999999",
        "a = 1979-05-27",
        "a = 07:32:00",
        "a = 07:32:00.999999",
        "a = 1979-05-27 07:32:00",
        "a = 1979-05-27t07:32:00z",
        "a = 0000-01-01T00:00:00Z",
        "a = 9999-12-31T23:59:59.999999+23:59",
        "a = 1979-05-27T07:32:00+00:00",
        "a = 1979-05-27T07:32:00-00:00",
        "a = 1979-05-27T07:32:00.123456789Z",
        "a = 1979-02-30T00:00:00Z",
        "a = 2024-02-29T23:59:60Z",
        "a = 1979-05-27T24:00:00Z",
        "a = 1979-13-01T00:00:00Z",
        "a = 1979-05-27T07:32:00.Z",
        "a = 1979-05-27T07:32:00.1234567890123Z",
        "a = 1979-05-27T07:32Z",
        "a = 1979-05-27T07:32:00.5",
    ]),
)

# ---------- improved fuzzing: structured generators for least-covered paths ----------

# toml_utf8_to_ucs: exercise the multibyte UTF-8 decoder with a wide range of
# code points, both as raw literal bytes and as \u/\U escapes. The decoder is
# reached for every non-ASCII byte in a string, so generate strings whose
# content is drawn from codepoint boundaries (1/2/3/4-byte UTF-8 lengths).
_utf8_boundary_cps = st.sampled_from([
    0x00, 0x7F, 0x80, 0x7FF, 0x800, 0xFFFF, 0x10000, 0x10FFFF,
    0xE9, 0x4E2D, 0x1F600, 0xD7FF, 0xE000, 0xFFFD, 0x2028, 0x2029,
    0x0080, 0x07FF, 0x0800, 0xFFFF,
])

def _cp_to_raw(cp):
    return chr(cp)

def _cp_to_uescape(cp):
    if cp <= 0xFFFF:
        return "\\u%04x" % cp
    return "\\U%08x" % cp

_utf8_raw_string = st.lists(
    _utf8_boundary_cps.map(_cp_to_raw), min_size=1, max_size=8,
).map(lambda cs: 'a = "' + "".join(cs) + '"')

_utf8_esc_string = st.lists(
    _utf8_boundary_cps.map(_cp_to_uescape), min_size=1, max_size=8,
).map(lambda cs: 'a = "' + "".join(cs) + '"')

_utf8_lit_string = st.lists(
    _utf8_boundary_cps.map(_cp_to_raw), min_size=1, max_size=8,
).map(lambda cs: "a = '" + "".join(cs) + "'")

_utf8_ml_string = st.lists(
    _utf8_boundary_cps.map(_cp_to_raw), min_size=1, max_size=8,
).map(lambda cs: 'a = """' + "".join(cs) + '"""')

_utf8_ml_lit_string = st.lists(
    _utf8_boundary_cps.map(_cp_to_raw), min_size=1, max_size=8,
).map(lambda cs: "a = '''" + "".join(cs) + "'''")

# norm_lit_str: literal-string normalization. Multiline literal strings get
# leading-newline trimming and CRLF handling; single-line literals get escape
# processing. Generate bodies with newlines, CRLFs, backslashes, and quotes
# at various positions.
_ml_lit_body_char = st.one_of(
    st.characters(blacklist_characters="'\x00"),
    st.just("\n"),
    st.just("\r\n"),
    st.just("\\"),
    st.just("''"),
)

_ml_lit_string = st.lists(
    _ml_lit_body_char, min_size=0, max_size=10,
).map(lambda cs: "a = '''" + "".join(cs) + "'''")

# Leading newline variants specifically target the trimming branch.
_ml_lit_leading_nl = st.sampled_from([
    "a = '''\nx'''",
    "a = '''\r\nx'''",
    "a = '''\n\nx'''",
    "a = '''\r\n\r\nx'''",
    "a = '''\n\n\n'''",
    "a = '''\r\n'''",
    "a = '''\n'''",
])

# toml_rtos: string-to-value conversion for every scalar type, plus the
# string-decoding helpers. Generate well-formed scalars in key=value form.
_rtos_scalar = st.one_of(
    st.integers(min_value=-(10**18), max_value=10**18).map(
        lambda n: "a = " + str(n)),
    st.floats(allow_nan=False, allow_infinity=False).map(
        lambda f: "a = " + repr(f)),
    st.sampled_from([
        "a = true", "a = false",
        "a = inf", "a = -inf", "a = nan",
        "a = 0x1f", "a = 0o17", "a = 0b101",
        "a = 1979-05-27T07:32:00Z",
    ]),
)

# toml_timestamp_at: generate timestamps with boundary values for each field
# (year, month, day, hour, minute, second, fractional, offset) to hit every
# branch of the timestamp parser.
_ts_year = st.sampled_from(["0000", "0001", "1970", "1979", "2024", "9999"])
_ts_month = st.sampled_from(["00", "01", "02", "12", "13"])
_ts_day = st.sampled_from(["00", "01", "28", "29", "30", "31", "32"])
_ts_hour = st.sampled_from(["00", "01", "12", "23", "24"])
_ts_min = st.sampled_from(["00", "30", "59", "60"])
_ts_sec = st.sampled_from(["00", "30", "59", "60", "61"])
_ts_frac = st.sampled_from(["", ".0", ".5", ".123456", ".123456789", ".1234567890123"])
_ts_off = st.sampled_from(["", "Z", "z", "+00:00", "-00:00", "+23:59",
                           "-23:59", "+14:00", "-12:00"])

def _mk_timestamp(parts):
    y, mo, d, h, mi, s, fr, off = parts
    return "a = " + y + "-" + mo + "-" + d + "T" + h + ":" + mi + ":" + s + fr + off

_ts_full = st.tuples(
    _ts_year, _ts_month, _ts_day, _ts_hour, _ts_min, _ts_sec, _ts_frac, _ts_off,
).map(_mk_timestamp)

_ts_date_only = st.tuples(_ts_year, _ts_month, _ts_day).map(
    lambda t: "a = " + t[0] + "-" + t[1] + "-" + t[2])

_ts_time_only = st.tuples(_ts_hour, _ts_min, _ts_sec, _ts_frac).map(
    lambda t: "a = " + t[0] + ":" + t[1] + ":" + t[2] + t[3])

_targeted_document = st.one_of(
    _targeted_document,
    _utf8_raw_string,
    _utf8_esc_string,
    _utf8_lit_string,
    _utf8_ml_string,
    _utf8_ml_lit_string,
    _ml_lit_string,
    _ml_lit_leading_nl,
    _rtos_scalar,
    _ts_full,
    _ts_date_only,
    _ts_time_only,
)

# ---------- full-document generator for toml_parse_file ----------

# toml_parse_file takes a whole file stream. Generate multi-line documents with
# tables, key-values, comments, and blank lines so the file-level parse loop
# (table tracking, array-of-tables state, duplicate detection) is exercised.
_file_line = st.one_of(
    key_value,
    table,
    comment_opt,
    st.just(""),
)

_file_document = st.lists(
    _file_line, min_size=1, max_size=12,
).map(_join_exprs)

document = st.one_of(
    st.lists(expression, min_size=0, max_size=8).map(_join_exprs),
    _unicode_document,
    _malformed,
    _targeted_document,
    _file_document,
)

strategy = document