from hypothesis import strategies as st
import json

# ---------- basic leaves ----------

def _no_nul(s):
    return s.replace("\x00", "")

# characters for strings: avoid raw NUL (harness skips), but allow other controls
_ascii_print = st.characters(min_codepoint=0x20, max_codepoint=0x7E)
_ascii_ctrl = st.characters(min_codepoint=0x01, max_codepoint=0x1F)
_ascii_del = st.just("\x7f")
_nonascii = st.characters(min_codepoint=0xA0, max_codepoint=0x10FFFF)
_ctrl = st.one_of(_ascii_ctrl, _ascii_del)

_esc_simple = st.sampled_from(['"', "\\", "/", "b", "f", "n", "r", "t"])
_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)
_hex8 = st.text(alphabet="0123456789abcdefABCDEF", min_size=8, max_size=8)

_escape = st.one_of(
    _esc_simple.map(lambda c: "\\" + c),
    _hex4.map(lambda h: "\\u" + h),
    _hex8.map(lambda h: "\\U" + h),
)

# content pieces for basic strings
_basic_piece = st.one_of(
    _ascii_print.filter(lambda c: c not in '"\\'),
    _nonascii,
    _ctrl,
    _escape,
    st.just("\t"),
)

# content pieces for literal strings (no escapes, no quote, no newline)
_literal_piece = st.one_of(
    _ascii_print.filter(lambda c: c != "'"),
    _nonascii,
    _ctrl,
    st.just("\t"),
)

def _basic_string():
    return st.lists(_basic_piece, max_size=12).map(lambda ps: '"' + "".join(ps) + '"')

def _literal_string():
    return st.lists(_literal_piece, max_size=12).map(lambda ps: "'" + "".join(ps) + "'")

# multiline basic: content may contain newlines and quotes-but-not-triple
_ml_basic_piece = st.one_of(
    _basic_piece,
    st.just("\n"),
    st.just("\r\n"),
    st.just('"'),
    st.just('""'),
)

def _ml_basic_string():
    return st.lists(_ml_basic_piece, max_size=10).map(
        lambda ps: '"""' + "".join(ps) + '"""'
    )

# multiline literal: content may contain anything except '''
_ml_literal_piece = st.one_of(
    _literal_piece,
    st.just("\n"),
    st.just("\r\n"),
    st.just('"'),
    st.just("'"),
    st.just("''"),
)

def _ml_literal_string():
    return st.lists(_ml_literal_piece, max_size=10).map(
        lambda ps: "'''" + "".join(ps) + "'''"
    )

_string = st.one_of(
    _basic_string(),
    _literal_string(),
    _ml_basic_string(),
    _ml_literal_string(),
)

# ---------- numbers ----------

_digit = st.characters(min_codepoint=0x30, max_codepoint=0x39)
_digit_1_9 = st.characters(min_codepoint=0x31, max_codepoint=0x39)

def _dec_int_body():
    # allow leading zeros (parser accepts), underscores, extremes
    plain = st.text(alphabet="0123456789", min_size=1, max_size=25)
    underscored = st.tuples(
        _digit_1_9,
        st.lists(
            st.tuples(st.sampled_from("0123456789"), st.just("_"), st.sampled_from("0123456789")),
            min_size=0,
            max_size=6,
        ).map(lambda triples: "".join(a + b + c for (a, b, c) in triples)),
    ).map(lambda t: t[0] + t[1])
    return st.one_of(plain, underscored)

_sign = st.sampled_from(["", "+", "-"])

_dec_int = st.tuples(_sign, _dec_int_body()).map(lambda t: t[0] + t[1])

_hex_digit = st.sampled_from(list("0123456789abcdefABCDEF"))
_hex_int = st.tuples(
    st.just("0x"),
    _hex_digit,
    st.lists(_hex_digit, max_size=20).map(lambda cs: "".join(cs)),
).map(lambda t: t[0] + t[1] + t[2])

_oct_digit = st.sampled_from(list("01234567"))
_oct_int = st.tuples(
    st.just("0o"),
    _oct_digit,
    st.lists(_oct_digit, max_size=20).map(lambda cs: "".join(cs)),
).map(lambda t: t[0] + t[1] + t[2])

_bin_digit = st.sampled_from(["0", "1"])
_bin_int = st.tuples(
    st.just("0b"),
    _bin_digit,
    st.lists(_bin_digit, max_size=20).map(lambda cs: "".join(cs)),
).map(lambda t: t[0] + t[1] + t[2])

_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

# floats: cover 1. .5 1e10 1.5e-3 1e309 etc.
_frac_part = st.text(alphabet="0123456789", min_size=0, max_size=10)
_exp_part = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0123456789", min_size=1, max_size=6),
).map(lambda t: t[0] + t[1] + t[2])

def _float():
    int_part = st.text(alphabet="0123456789", min_size=0, max_size=10)
    with_dot = st.tuples(int_part, st.just("."), _frac_part).map(
        lambda t: t[0] + t[1] + t[2]
    )
    with_exp = st.tuples(int_part, _exp_part).map(lambda t: t[0] + t[1])
    with_both = st.tuples(int_part, st.just("."), _frac_part, _exp_part).map(
        lambda t: t[0] + t[1] + t[2] + t[3]
    )
    return st.tuples(_sign, st.one_of(with_dot, with_exp, with_both)).map(
        lambda t: t[0] + t[1]
    )

_inf = st.tuples(_sign, st.just("inf")).map(lambda t: t[0] + t[1])
_nan = st.tuples(_sign, st.just("nan")).map(lambda t: t[0] + t[1])

_floating = st.one_of(_float(), _inf, _nan)

# ---------- booleans ----------

_boolean = st.sampled_from(["true", "false"])

# ---------- date-times ----------

def _digits(n):
    return st.text(alphabet="0123456789", min_size=n, max_size=n)

_year = _digits(4)
_month = _digits(2)
_day = _digits(2)
_hour = _digits(2)
_minute = _digits(2)
_second = _digits(2)
_secfrac = st.tuples(st.just("."), st.text(alphabet="0123456789", min_size=1, max_size=9)).map(
    lambda t: t[0] + t[1]
)

_full_date = st.tuples(_year, st.just("-"), _month, st.just("-"), _day).map(
    lambda t: t[0] + t[1] + t[2] + t[3] + t[4]
)
_partial_time = st.tuples(
    _hour, st.just(":"), _minute, st.just(":"), _second, st.one_of(st.just(""), _secfrac)
).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4] + t[5])
_delim = st.sampled_from(["T", "t", " "])
_num_offset = st.tuples(
    st.sampled_from(["+", "-"]), _hour, st.just(":"), _minute
).map(lambda t: t[0] + t[1] + t[2] + t[3])
_offset = st.one_of(st.just("Z"), _num_offset)

_offset_date_time = st.tuples(_full_date, _delim, _partial_time, _offset).map(
    lambda t: t[0] + t[1] + t[2] + t[3]
)
_local_date_time = st.tuples(_full_date, _delim, _partial_time).map(
    lambda t: t[0] + t[1] + t[2]
)
_local_date = _full_date
_local_time = _partial_time

_date_time = st.one_of(
    _offset_date_time, _local_date_time, _local_date, _local_time
)

# ---------- keys ----------

_unquoted_key = st.text(
    alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-",
    min_size=1,
    max_size=10,
)

_quoted_key = st.one_of(_basic_string(), _literal_string())

_simple_key = st.one_of(_unquoted_key, _quoted_key)

_dotted_key = st.lists(_simple_key, min_size=2, max_size=4).map(
    lambda ks: ".".join(ks)
)

_key = st.one_of(_simple_key, _dotted_key)

# ---------- recursive values: arrays and inline tables ----------

def _value(depth):
    if depth <= 0:
        return st.one_of(
            _string, _integer, _floating, _boolean, _date_time
        )
    return st.one_of(
        _string,
        _integer,
        _floating,
        _boolean,
        _date_time,
        _array(depth - 1),
        _inline_table(depth - 1),
    )

def _array(depth):
    inner = _value(depth)
    # array values separated by comma, optional trailing comma, optional newlines
    elements = st.lists(inner, max_size=5)
    return elements.map(lambda vs: "[" + ", ".join(vs) + "]")

def _inline_table(depth):
    inner = _value(depth)
    kv = st.tuples(_key, st.just(" = "), inner).map(lambda t: t[0] + t[1] + t[2])
    entries = st.lists(kv, max_size=4)
    return entries.map(lambda kvs: "{" + ", ".join(kvs) + "}")

# top-level value with bounded recursion
_value_top = st.recursive(
    st.one_of(_string, _integer, _floating, _boolean, _date_time),
    lambda children: st.one_of(
        st.lists(children, max_size=5).map(lambda vs: "[" + ", ".join(vs) + "]"),
        st.lists(
            st.tuples(_key, st.just(" = "), children).map(lambda t: t[0] + t[1] + t[2]),
            max_size=4,
        ).map(lambda kvs: "{" + ", ".join(kvs) + "}"),
    ),
    max_leaves=40,
)

# ---------- document structure ----------

_comment_text = st.text(
    alphabet=st.characters(min_codepoint=0x01, max_codepoint=0x7E).filter(
        lambda c: c != "\n"
    ),
    max_size=20,
)
_comment = st.one_of(
    st.just(""),
    _comment_text.map(lambda s: "#" + s),
)

def _line_kv():
    return st.tuples(_key, st.just(" = "), _value_top, _comment).map(
        lambda t: t[0] + t[1] + t[2] + t[3]
    )

def _standard_table():
    return st.tuples(st.just("["), _key, st.just("]"), _comment).map(
        lambda t: t[0] + t[1] + t[2] + t[3]
    )

def _array_table():
    return st.tuples(st.just("[["), _key, st.just("]]"), _comment).map(
        lambda t: t[0] + t[1] + t[2] + t[3]
    )

_expression = st.one_of(_line_kv(), _standard_table(), _array_table(), _comment)

def _document():
    lines = st.lists(_expression, min_size=0, max_size=8)
    return lines.map(lambda ls: "\n".join(ls))

# ---------- malformed / near-valid mutations ----------

def _mutate(doc):
    """Produce near-valid variants by simple textual perturbations."""
    return st.one_of(
        st.just(doc),
        st.just(doc + "\n"),
        st.just(doc + "\r\n"),
        st.just(doc[:-1] if doc else doc),          # drop last char
        st.just(doc + "]"),                          # stray token
        st.just(doc + "{"),
        st.just(doc.replace("=", "==", 1)),          # doubled delimiter
        st.just(doc.replace("=", "", 1)),            # missing delimiter
        st.just(doc + '\nunterminated = "abc'),      # unterminated string
        st.just(doc + "\nstray"),
        st.just(doc + "\n[unclosed"),
        st.just(doc + "\n{inline = 1}"),             # stray inline table at top
    )

def _with_malformed():
    return st.tuples(_document(), st.booleans()).flatmap(
        lambda t: _mutate(t[0]) if t[1] else st.just(t[0])
    )

# ---------- final strategy ----------

def _deep_nesting():
    # concentrate interesting depth in the 1500-2048 band
    depth = st.integers(min_value=1500, max_value=2048)
    return depth.map(lambda d: "a = " + "[" * d + "]" * d)

def _deep_inline():
    depth = st.integers(min_value=1500, max_value=2048)
    return depth.map(
        lambda d: "a = " + "{b = " * d + "1" + "}" * d
    )

def _edge_documents():
    return st.sampled_from([
        "",
        "\n",
        "# only a comment",
        "# comment\n",
        '"" = 1',
        "a = 007",
        "a = 1.",
        "a = .5",
        "a = 1e309",
        "a = -inf",
        "a = nan",
        "a = {b = 1,}",
        "a = 1979-02-30",
        "a = 1979-05-27 07:32:00Z",
        "a = []",
        "a = {}",
        "[t]",
        "[[a]]",
        "a = 0x1_ff",
        "a = 0o7_7",
        "a = 0b1_0",
        'a = "\\u0000"',
        'a = "x\x01y"',
        "a = 'raw\x01'",
        'a = """\nmulti\nline"""',
        "a = '''\nmulti\nline'''",
        "a.b.c = 1",
        'a."b c" = 1',
        "a = [1, 2, 3,]",
        "a = [\n  1, # c\n  2\n]",
        "key = 1\nkey = 2",     # duplicate keys (parser rejects)
        "[t]\n[t]",             # duplicate table
        "a = {b = 1\n}",        # newline in inline table
        "ключ = 1",             # non-ASCII bare key
        "a = \"unterminated",
        "a = 1\nb",
        "= 1",
        "a =",
        "[a\n",
        "a = {b = 1",
    ])

# ---------- NEW: target UTF-8 / timestamp / literal-string code paths ----------

# Exercise toml_utf8_to_ucs: multibyte UTF-8 sequences, including boundaries
# and invalid/truncated sequences embedded in strings and bare positions.
_utf8_valid_codepoints = st.one_of(
    st.integers(min_value=0x80, max_value=0x7FF),       # 2-byte
    st.integers(min_value=0x800, max_value=0xFFFF).filter(
        lambda cp: not (0xD800 <= cp <= 0xDFFF)         # skip surrogates
    ),                                                   # 3-byte
    st.integers(min_value=0x10000, max_value=0x10FFFF), # 4-byte
)

def _utf8_encoded_string():
    # Build a basic string whose content is a valid UTF-8 encoded codepoint
    # (as a Python str the parser will re-encode via toml_rtos).
    return _utf8_valid_codepoints.map(
        lambda cp: 'a = "' + chr(cp) + '"'
    )

def _utf8_invalid_bytes_doc():
    # Raw invalid UTF-8 byte sequences: lone continuation, truncated lead,
    # overlong, and a valid multibyte followed by truncation.
    return st.sampled_from([
        b'a = "\x80"',
        b'a = "\xbf"',
        b'a = "\xc0"',
        b'a = "\xc0\x80"',
        b'a = "\xc1\xbf"',
        b'a = "\xe0\x80\x80"',
        b'a = "\xed\xa0\x80"',     # surrogate half
        b'a = "\xf0\x80\x80\x80"',
        b'a = "\xf4\x90\x80\x80"', # > U+10FFFF
        b'a = "\xf5\x80\x80\x80"',
        b'a = "\xe2\x82"',         # truncated 3-byte
        b'a = "\xe2\x82\xac"',     # valid U+20AC
        b'a = "\xf0\x9f\x92\xa9"', # valid emoji
        b'a = "\xc3"',             # truncated 2-byte
        b'\xff\xfe = 1',           # BOM-ish bytes as bare key
        b'a = "\x80\x80\x80\x80"',
    ]).map(lambda b: b.decode("latin-1"))

# Exercise toml_rtos / norm_lit_str: escape processing and literal-string
# normalization, including edge escapes and raw control/quote content.
_rtos_documents = st.sampled_from([
    'a = "\\\\"',
    'a = "\\""',
    'a = "\\b\\f\\n\\r\\t"',
    'a = "\\u0000"',
    'a = "\\uD800"',            # lone surrogate escape
    'a = "\\uDFFF"',
    'a = "\\U0010FFFF"',
    'a = "\\U00110000"',        # out of range
    'a = "\\U0001F4A9"',
    'a = "\\u12"',              # short hex
    'a = "\\x41"',              # invalid escape
    'a = "\\q"',                # invalid escape
    'a = "tab\there"',
    'a = "line\nbreak"',        # raw newline in basic string (invalid)
    "a = 'lit\\\\eral'",        # backslash in literal
    "a = 'lit\\u0041'",         # \u not processed in literal
    "a = 'ctrl\x01\x7f'",
    'a = """\\\n   continued"""',   # line-ending backslash in ML basic
    'a = """\\   \n  x"""',
    "a = '''raw\n'''",
    'a = """\r\ncrlf"""',
    "a = '''\r\ncrlf'''",
])

# Exercise toml_timestamp_at: malformed timestamps that reach the timestamp
# parser but fail at the various sub-parsers.
_timestamp_documents = st.sampled_from([
    "a = 1979-05-27T07:32:00",
    "a = 1979-05-27T07:32:00Z",
    "a = 1979-05-27T07:32:00.999999Z",
    "a = 1979-05-27T07:32:00.999999+07:00",
    "a = 1979-05-27T07:32:00-07:00",
    "a = 1979-05-27 07:32:00",
    "a = 1979-05-27",
    "a = 07:32:00",
    "a = 07:32:00.5",
    "a = 1979-05-27T07:32",
    "a = 1979-05-27T07",
    "a = 1979-05-27T",
    "a = 1979-05",
    "a = 1979-",
    "a = 1979-13-27",
    "a = 1979-00-00",
    "a = 1979-05-32",
    "a = 1979-05-27T25:00:00",
    "a = 1979-05-27T07:60:00",
    "a = 1979-05-27T07:32:61",
    "a = 1979-05-27T07:32:00+99:99",
    "a = 1979-05-27T07:32:00.Z",
    "a = 1979-05-27T07:32:00.123456789123Z",
    "a = 1979-05-27T07:32:00Z+07:00",
    "a = 0000-00-00T00:00:00Z",
])

# Exercise toml_parse_file: documents that look like file-level inputs,
# including BOM, CRLF line endings, and trailing whitespace.
_file_like_documents = st.sampled_from([
    "\ufeffa = 1",
    "\ufeff[t]\nx = 1",
    "a = 1\r\nb = 2\r\n",
    "[t]\r\nx = 1\r\n",
    "a = 1   \n   b = 2",
    "a = 1\t\n",
    "a = 1\n\n\n",
    "# leading\n# comments\n\na = 1",
    "a.b.c.d.e = 1",
    "a = 1\n[t]\nb = 2\n[[u]]\nc = 3",
    "a = 1\n  \n  b = 2",
    "\n\n\n",
    "   ",
    "\t\t",
])

def _targeted_paths():
    return st.one_of(
        _utf8_encoded_string(),
        _utf8_invalid_bytes_doc(),
        _rtos_documents,
        _timestamp_documents,
        _file_like_documents,
    )

# ---------- NEW: targeted generators for least-covered functions ----------

# toml_utf8_to_ucs: generate strings whose content is a sequence of
# codepoints at UTF-8 boundary values, so the decoder exercises 1/2/3/4-byte
# branches and the "too long"/"surrogate"/"overlong" error branches.
_utf8_boundary_codepoints = st.sampled_from([
    0x00, 0x01, 0x7F,            # 1-byte boundaries
    0x80, 0x7FF,                 # 2-byte boundaries
    0x800, 0xFFFD, 0xFFFF,       # 3-byte boundaries
    0xD7FF, 0xE000,              # just outside surrogate range
    0x10000, 0x10FFFF,           # 4-byte boundaries
    0x1F4A9,                     # emoji
])

def _utf8_boundary_string():
    return st.lists(
        _utf8_boundary_codepoints, min_size=1, max_size=6
    ).map(lambda cps: 'a = "' + "".join(chr(c) for c in cps) + '"')

def _utf8_boundary_quoted_key():
    return st.lists(
        _utf8_boundary_codepoints, min_size=1, max_size=4
    ).map(lambda cps: '"' + "".join(chr(c) for c in cps) + '" = 1')

# toml_rtos: a generator that mixes valid escapes, invalid escapes, and raw
# control characters inside basic strings, plus literal-string variants so
# both branches of the escape/normalize logic run.
_rtos_escape_piece = st.one_of(
    _esc_simple.map(lambda c: "\\" + c),
    _hex4.map(lambda h: "\\u" + h),
    _hex8.map(lambda h: "\\U" + h),
    st.sampled_from(["\\x", "\\q", "\\ ", "\\\n", "\\\r\n", "\\u12", "\\U00110000"]),
    _ascii_print.filter(lambda c: c not in '"\\'),
    _ctrl,
)

def _rtos_basic_string():
    return st.lists(_rtos_escape_piece, min_size=1, max_size=8).map(
        lambda ps: 'a = "' + "".join(ps) + '"'
    )

_rtos_literal_piece = st.one_of(
    _ascii_print.filter(lambda c: c != "'"),
    _ctrl,
    st.just("\\"),
    st.just("\\u0041"),
    st.just("\\n"),
)

def _rtos_literal_string():
    return st.lists(_rtos_literal_piece, min_size=1, max_size=8).map(
        lambda ps: "a = '" + "".join(ps) + "'"
    )

def _rtos_ml_basic_string():
    pieces = st.one_of(
        _rtos_escape_piece,
        st.just("\n"),
        st.just("\r\n"),
        st.just("\\\n"),
        st.just("\\   \n"),
        st.just('"'),
    )
    return st.lists(pieces, min_size=1, max_size=8).map(
        lambda ps: 'a = """' + "".join(ps) + '"""'
    )

def _rtos_docs():
    return st.one_of(
        _rtos_basic_string(),
        _rtos_literal_string(),
        _rtos_ml_basic_string(),
    )

# norm_lit_str: literal strings with control chars, backslashes, quotes,
# and newlines in multiline form, to exercise the normalization branches.
_norm_lit_piece = st.one_of(
    _ascii_print.filter(lambda c: c != "'"),
    _ctrl,
    st.just("\\"),
    st.just("\\u"),
    st.just("\\U"),
    st.just("\\n"),
    st.just("\\t"),
    st.just("\t"),
)

def _norm_lit_single():
    return st.lists(_norm_lit_piece, min_size=0, max_size=10).map(
        lambda ps: "a = '" + "".join(ps) + "'"
    )

def _norm_lit_multi():
    pieces = st.one_of(
        _norm_lit_piece,
        st.just("\n"),
        st.just("\r\n"),
        st.just('"'),
        st.just("'"),
        st.just("''"),
        st.just("\\\n"),
    )
    return st.lists(pieces, min_size=0, max_size=10).map(
        lambda ps: "a = '''" + "".join(ps) + "'''"
    )

def _norm_lit_docs():
    return st.one_of(_norm_lit_single(), _norm_lit_multi())

# toml_timestamp_at: structured timestamp generators that vary each
# component independently, hitting the sub-parsers for date, time, secfrac,
# offset, and the combination logic.
_ts_year = st.one_of(
    _digits(4),
    st.sampled_from(["0000", "9999", "1979", "2024"]),
)
_ts_month = st.one_of(
    _digits(2),
    st.sampled_from(["00", "01", "12", "13", "99"]),
)
_ts_day = st.one_of(
    _digits(2),
    st.sampled_from(["00", "01", "28", "29", "30", "31", "32", "99"]),
)
_ts_hour = st.one_of(
    _digits(2),
    st.sampled_from(["00", "23", "24", "25", "99"]),
)
_ts_minute = st.one_of(
    _digits(2),
    st.sampled_from(["00", "59", "60", "99"]),
)
_ts_second = st.one_of(
    _digits(2),
    st.sampled_from(["00", "59", "60", "61", "99"]),
)
_ts_secfrac = st.one_of(
    st.just(""),
    st.tuples(st.just("."), st.text(alphabet="0123456789", min_size=1, max_size=12)).map(
        lambda t: t[0] + t[1]
    ),
)

def _ts_date():
    return st.tuples(_ts_year, st.just("-"), _ts_month, st.just("-"), _ts_day).map(
        lambda t: t[0] + t[1] + t[2] + t[3] + t[4]
    )

def _ts_time():
    return st.tuples(
        _ts_hour, st.just(":"), _ts_minute, st.just(":"), _ts_second, _ts_secfrac
    ).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4] + t[5])

def _ts_offset():
    return st.one_of(
        st.just("Z"),
        st.just("z"),
        st.tuples(
            st.sampled_from(["+", "-"]),
            st.one_of(_digits(2), st.sampled_from(["00", "23", "24", "99"])),
            st.just(":"),
            st.one_of(_digits(2), st.sampled_from(["00", "59", "60", "99"])),
        ).map(lambda t: t[0] + t[1] + t[2] + t[3]),
        st.tuples(
            st.sampled_from(["+", "-"]),
            _digits(2),
            _digits(2),
        ).map(lambda t: t[0] + t[1] + t[2]),
    )

def _ts_doc():
    date = _ts_date()
    time = _ts_time()
    offset = _ts_offset()
    delim = st.sampled_from(["T", "t", " "])
    return st.one_of(
        st.tuples(date, delim, time, offset).map(
            lambda t: "a = " + t[0] + t[1] + t[2] + t[3]
        ),
        st.tuples(date, delim, time).map(
            lambda t: "a = " + t[0] + t[1] + t[2]
        ),
        date.map(lambda d: "a = " + d),
        time.map(lambda t: "a = " + t),
        st.tuples(date, delim).map(lambda t: "a = " + t[0] + t[1]),
    )

# toml_parse_file: file-shaped documents with BOM, CRLF, comments, tables,
# array tables, and trailing garbage, to exercise the file driver path.
def _file_doc():
    header = st.one_of(
        st.just(""),
        st.just("\ufeff"),
        st.just("\ufeff# bom comment\n"),
    )
    body = st.lists(_expression, min_size=0, max_size=10)
    eol = st.sampled_from(["\n", "\r\n"])
    trailer = st.one_of(
        st.just(""),
        st.just("\n"),
        st.just("\r\n"),
        st.just("   \n"),
        st.just("\t\t\r\n"),
    )
    return st.tuples(header, body, eol, trailer).map(
        lambda t: t[0] + t[2].join(t[1]) + t[3]
    )

def _parse_file_docs():
    return st.one_of(
        _file_doc(),
        _file_like_documents,
        st.tuples(
            st.just("\ufeff"),
            _document(),
        ).map(lambda t: t[0] + t[1]),
    )

def _least_covered_targets():
    return st.one_of(
        _utf8_boundary_string(),
        _utf8_boundary_quoted_key(),
        _rtos_docs(),
        _norm_lit_docs(),
        _ts_doc(),
        _parse_file_docs(),
    )

def _build():
    bodies = st.one_of(
        _with_malformed(),
        _deep_nesting(),
        _deep_inline(),
        _edge_documents(),
        _targeted_paths(),
        _least_covered_targets(),
    )
    return bodies.map(_no_nul)

strategy = _build()