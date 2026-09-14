from hypothesis import strategies as st
import json

# ---------- primitives ----------

# Characters that are safe to emit raw (no NUL).
_safe_chars = st.characters(
    blacklist_categories=(),
    blacklist_characters="\x00",
)

_ascii_printable = st.characters(min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters="\x00")

# Non-ASCII text (codepoints > 127), avoiding surrogates and NUL.
_non_ascii = st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF, blacklist_categories=("Cs",))

# Control bytes (excluding NUL) that the parser tolerates in strings/comments.
_control_bytes = st.integers(min_value=1, max_value=0x1F).map(chr).filter(lambda c: c != "\x00")

# ---------- escape sequences ----------

_hex_digit = st.sampled_from("0123456789abcdefABCDEF")

_unicode_escape = st.builds(
    lambda h: "\\u" + h,
    st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4),
)

_ex_unicode_escape = st.builds(
    lambda h: "\\U" + h,
    st.text(alphabet="0123456789abcdefABCDEF", min_size=8, max_size=8),
)

_simple_escape = st.sampled_from(["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_escape = st.one_of(_simple_escape, _unicode_escape, _ex_unicode_escape)

# Invalid escapes (near-valid-but-malformed), e.g. \q, \x41.
_invalid_escape = st.builds(
    lambda c: "\\" + c,
    st.sampled_from("qxyzuvwXaeg0"),
)

# ---------- strings ----------

_basic_char = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters='"\\'),
    _non_ascii,
    _control_bytes,
)

_basic_string_body = st.lists(
    st.one_of(_basic_char, _escape), min_size=0, max_size=12
).map("".join)

_basic_string = _basic_string_body.map(lambda s: '"' + s + '"')

# Unterminated basic string (missing closing quote).
_unterminated_basic = _basic_string_body.map(lambda s: '"' + s)

_literal_char = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters="'"),
    _non_ascii,
    _control_bytes,
)

_literal_string_body = st.lists(_literal_char, min_size=0, max_size=12).map("".join)

_literal_string = _literal_string_body.map(lambda s: "'" + s + "'")

# Multiline basic string: content may include newlines; escapes allowed; raw " not allowed alone.
_ml_basic_char = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters='"\\'),
    _non_ascii,
    _control_bytes,
    st.just("\n"),
    st.just("\r\n"),
)

_ml_basic_body = st.lists(
    st.one_of(_ml_basic_char, _escape), min_size=0, max_size=16
).map("".join)

_ml_basic_string = _ml_basic_body.map(lambda s: '"""' + s + '"""')

# Multiline literal string.
_ml_literal_char = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters="'"),
    _non_ascii,
    _control_bytes,
    st.just("\n"),
    st.just("\r\n"),
)

_ml_literal_body = st.lists(_ml_literal_char, min_size=0, max_size=16).map("".join)

_ml_literal_string = _ml_literal_body.map(lambda s: "'''" + s + "'''")

_string = st.one_of(
    _basic_string,
    _literal_string,
    _ml_basic_string,
    _ml_literal_string,
)

# ---------- keys ----------

_unquoted_key_chars = st.sampled_from(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
)

_unquoted_key = st.text(alphabet=_unquoted_key_chars, min_size=1, max_size=10)

# Non-ASCII bare key (rejected by parser, near-valid malformed).
_bad_bare_key = st.builds(
    lambda a, b: a + b,
    st.text(alphabet=_unquoted_key_chars, min_size=0, max_size=4),
    _non_ascii.map(lambda c: c),
)

_quoted_key = st.one_of(_basic_string, _literal_string)

_simple_key = st.one_of(_unquoted_key, _quoted_key)

_dotted_key = st.lists(_simple_key, min_size=2, max_size=3).map(".".join)

_key = st.one_of(_simple_key, _dotted_key)

# ---------- numbers ----------

_underscore = st.just("_")

_digit = st.sampled_from("0123456789")
_digit_1_9 = st.sampled_from("123456789")
_hex_digit = st.sampled_from("0123456789abcdefABCDEF")
_oct_digit = st.sampled_from("01234567")
_bin_digit = st.sampled_from("01")

# Decimal integer with optional sign, underscores, possible leading zeros.
_dec_int = st.builds(
    lambda sign, digits: sign + digits,
    st.one_of(st.just(""), st.just("+"), st.just("-")),
    st.one_of(
        st.text(alphabet="0123456789", min_size=1, max_size=20),
        st.builds(
            lambda a, b: a + "_" + b,
            st.text(alphabet="0123456789", min_size=1, max_size=10),
            st.text(alphabet="0123456789", min_size=1, max_size=10),
        ),
        st.just("007"),
        st.just("0"),
        st.just("00"),
        st.just("1_000"),
    ),
)

_hex_int = st.builds(
    lambda h: "0x" + h,
    st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=16),
)

_oct_int = st.builds(
    lambda o: "0o" + o,
    st.text(alphabet="01234567", min_size=1, max_size=16),
)

_bin_int = st.builds(
    lambda b: "0b" + b,
    st.text(alphabet="01", min_size=1, max_size=16),
)

_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

# Floats including extreme exponents and malformed variants.
_float = st.one_of(
    st.builds(
        lambda a, b, c: a + "." + b + c,
        st.text(alphabet="0123456789", min_size=1, max_size=6),
        st.text(alphabet="0123456789", min_size=0, max_size=6),
        st.one_of(
            st.just(""),
            st.builds(
                lambda s, e: s + "e" + e,
                st.one_of(st.just(""), st.just("+"), st.just("-")),
                st.text(alphabet="0123456789", min_size=1, max_size=4),
            ),
        ),
    ),
    st.just("1."),
    st.just(".5"),
    st.just("1e309"),
    st.just("-1e309"),
    st.just("1e-309"),
    st.just("1_000.000_1"),
    st.just("3.141592653589793"),
    st.just("0.0"),
    st.just("-0.0"),
)

_inf_nan = st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])

_floating_point = st.one_of(_float, _inf_nan)

# ---------- booleans ----------

_bool = st.sampled_from(["true", "false"])

# ---------- dates ----------

_year = st.builds(lambda a, b: a + b, _digit, _digit).map(lambda s: "20" + s)

_month = st.sampled_from(["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "00", "13", "99"])
_day = st.sampled_from(["01", "02", "15", "28", "29", "30", "31", "00", "32", "99"])
_hour = st.sampled_from(["00", "01", "12", "23", "24", "99"])
_minute = st.sampled_from(["00", "01", "30", "59", "60", "99"])
_second = st.sampled_from(["00", "01", "30", "59", "60", "99"])
_secfrac = st.builds(lambda d: "." + d, st.text(alphabet="0123456789", min_size=1, max_size=6))
_offset = st.one_of(st.just("Z"), st.just("z"), st.builds(lambda s, h, m: s + h + ":" + m, st.sampled_from(["+", "-"]), _hour, _minute))

_full_date = st.builds(lambda y, m, d: y + "-" + m + "-" + d, _year, _month, _day)
_partial_time = st.builds(lambda h, m, s, f: h + ":" + m + ":" + s + f, _hour, _minute, _second, st.one_of(st.just(""), _secfrac))

_offset_date_time = st.builds(lambda d, sep, t, o: d + sep + t + o, _full_date, st.sampled_from(["T", "t", " "]), _partial_time, _offset)
_local_date_time = st.builds(lambda d, sep, t: d + sep + t, _full_date, st.sampled_from(["T", "t", " "]), _partial_time)
_local_date = _full_date
_local_time = _partial_time

_date_time = st.one_of(_offset_date_time, _local_date_time, _local_date, _local_time)

# ---------- recursive structures ----------

# We build arrays and inline tables using st.recursive so the grammar's
# recursion is preserved. Depth is controlled by the recursive branch.

# A value strategy will be built recursively; define a placeholder via
# st.deferred to allow mutual recursion between arrays, inline tables, and values.

_value = st.deferred(lambda: _value_impl)

# Leaf (non-container) values.
_leaf_value = st.one_of(
    _string,
    _integer,
    _floating_point,
    _bool,
    _date_time,
    # malformed leaf: unterminated string
    _unterminated_basic,
    # invalid escape inside a basic string
    st.builds(lambda s: '"' + s + '"', _invalid_escape),
)

# Container values: arrays and inline tables. These recurse.
_array_value = st.recursive(
    _leaf_value,
    lambda children: st.one_of(
        # array of children
        st.lists(children, min_size=0, max_size=4).map(
            lambda vs: "[" + ", ".join(vs) + "]"
        ),
        # array with trailing comma
        st.lists(children, min_size=1, max_size=4).map(
            lambda vs: "[" + ", ".join(vs) + ",]"
        ),
        # multiline array with comments
        st.lists(children, min_size=0, max_size=3).map(
            lambda vs: "[\n" + ",\n".join(vs) + "\n]"
        ),
        # empty array
        st.just("[]"),
        # inline table
        st.lists(
            st.tuples(_key, children), min_size=0, max_size=4
        ).map(
            lambda kvs: "{" + ", ".join(k + " = " + v for k, v in kvs) + "}"
        ),
        # inline table with trailing comma
        st.lists(
            st.tuples(_key, children), min_size=1, max_size=4
        ).map(
            lambda kvs: "{" + ", ".join(k + " = " + v for k, v in kvs) + ",}"
        ),
        # empty inline table
        st.just("{}"),
    ),
    max_leaves=20,
)

# The value implementation: leaf or container.
_value_impl = st.one_of(_leaf_value, _array_value)

# ---------- key/value lines ----------

_key_value = st.builds(
    lambda k, v: k + " = " + v,
    _key,
    _value,
)

# Malformed key/value variants.
_malformed_kv = st.one_of(
    # missing equals
    st.builds(lambda k, v: k + " " + v, _key, _value),
    # doubled equals
    st.builds(lambda k, v: k + " == " + v, _key, _value),
    # missing value
    st.builds(lambda k: k + " =", _key),
    # stray token
    st.builds(lambda k, v: k + " = " + v + " extra", _key, _value),
    # bare non-ASCII key
    st.builds(lambda k, v: k + " = " + v, _bad_bare_key, _value),
    # newline after equals
    st.builds(lambda k, v: k + " =\n" + v, _key, _value),
)

# ---------- tables ----------

_standard_table = st.builds(
    lambda k: "[" + k + "]",
    _key,
)

_array_table = st.builds(
    lambda k: "[[" + k + "]]",
    _key,
)

# Malformed table variants.
_malformed_table = st.one_of(
    # missing closing bracket
    st.builds(lambda k: "[" + k, _key),
    # doubled opening bracket for standard table
    st.builds(lambda k: "[[" + k + "]", _key),
    # missing closing double bracket
    st.builds(lambda k: "[[" + k, _key),
)

# ---------- comments ----------

_comment_char = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters="\n"),
    _non_ascii,
    _control_bytes,
)

_comment = st.lists(_comment_char, min_size=0, max_size=20).map(
    lambda cs: "#" + "".join(cs)
)

# ---------- expressions and document ----------

# An expression is a key/value, table, or comment line.
_expression = st.one_of(
    _key_value,
    _standard_table,
    _array_table,
    _comment,
    _malformed_kv,
    _malformed_table,
)

# Document: one or more expressions separated by newlines, optional trailing newline.
_document = st.lists(_expression, min_size=0, max_size=8).map(
    lambda exprs: "\n".join(exprs)
)

# Also allow documents with CRLF separators.
_document_crlf = st.lists(_expression, min_size=0, max_size=6).map(
    lambda exprs: "\r\n".join(exprs)
)

# Documents with trailing newline.
_document_trailing_nl = st.lists(_expression, min_size=1, max_size=6).map(
    lambda exprs: "\n".join(exprs) + "\n"
)

# Deep nesting: arrays nested to a controlled depth within the steer band.
# We build a nested array string directly for depth control.
# Depth between 1500 and 2048 as per adaptation notes.
_deep_depth = st.integers(min_value=1500, max_value=2048)

_deep_array = st.builds(
    lambda depth, leaf: "[" * depth + leaf + "]" * depth,
    _deep_depth,
    _leaf_value,
)

# Deep inline tables: nested inline tables.
_deep_inline = st.builds(
    lambda depth, leaf: "{a = " * depth + leaf + "}" * depth,
    st.integers(min_value=100, max_value=500),
    _leaf_value,
)

# Documents containing deep nesting.
_deep_document = st.builds(
    lambda k, v: k + " = " + v,
    _key,
    st.one_of(_deep_array, _deep_inline),
)

# ---------- UTF-8 decoding coverage (toml_utf8_to_ucs) ----------

# Multi-byte UTF-8 sequences embedded in strings force the parser to decode
# raw UTF-8 bytes into UCS codepoints. Cover 1-, 2-, 3-, and 4-byte encodings,
# plus boundary codepoints and malformed/truncated sequences.
_utf8_codepoint = st.sampled_from([
    0x01, 0x7F,              # 1-byte
    0x80, 0x7FF,             # 2-byte boundaries
    0x800, 0xFFFF,           # 3-byte boundaries
    0x10000, 0x10FFFF,       # 4-byte boundaries
    0x20AC, 0x4E2D, 0x1F600, # common multibyte chars
])

_utf8_char = _utf8_codepoint.map(chr)

_utf8_string = st.lists(_utf8_char, min_size=1, max_size=8).map(
    lambda cs: '"' + "".join(cs) + '"'
)

_utf8_key = st.lists(_utf8_char, min_size=1, max_size=4).map(
    lambda cs: '"' + "".join(cs) + '"'
)

_utf8_comment = st.lists(_utf8_char, min_size=1, max_size=8).map(
    lambda cs: "#" + "".join(cs)
)

_utf8_document = st.builds(
    lambda k, v: k + " = " + v,
    _utf8_key,
    st.one_of(_utf8_string, st.just("1"), _bool),
)

# Focused UTF-8 decoding coverage: drive toml_utf8_to_ucs directly through
# string bodies containing raw multibyte UTF-8 codepoints across all byte
# length classes, boundary codepoints, and surrogate-range codepoints.
_utf8_boundary_codepoints = st.sampled_from([
    0x00, 0x01, 0x7F, 0x80, 0x81, 0xBF, 0xC0, 0xC1, 0xC2, 0xDF,
    0xE0, 0xE1, 0xEF, 0xF0, 0xF4, 0xF5, 0xFF,
    0x07FF, 0x0800, 0x0FFF, 0x1000, 0xFFFF, 0x10000, 0x10001,
    0x10FFFF,
    0xD7FF, 0xE000,
])

_utf8_boundary_char = _utf8_boundary_codepoints.map(chr)

# Raw (unescaped) multibyte content inside a basic string body.
_utf8_raw_string = st.lists(_utf8_boundary_char, min_size=1, max_size=12).map(
    lambda cs: '"' + "".join(cs) + '"'
)

# Multibyte content inside a literal string body.
_utf8_raw_literal = st.lists(_utf8_boundary_char, min_size=1, max_size=12).map(
    lambda cs: "'" + "".join(cs) + "'"
)

# Multibyte content inside a multiline basic string body.
_utf8_raw_ml = st.lists(_utf8_boundary_char, min_size=1, max_size=12).map(
    lambda cs: '"""' + "".join(cs) + '"""'
)

# Multibyte content in a comment (parser must decode comments too).
_utf8_raw_comment = st.lists(_utf8_boundary_char, min_size=1, max_size=12).map(
    lambda cs: "#" + "".join(cs)
)

# Multibyte content in a bare document value position.
_utf8_raw_doc = st.builds(
    lambda k, v: k + " = " + v,
    st.lists(_utf8_boundary_char, min_size=1, max_size=4).map(
        lambda cs: '"' + "".join(cs) + '"'
    ),
    st.one_of(_utf8_raw_string, _utf8_raw_literal, _utf8_raw_ml),
)

# Multibyte content spread across a whole document (key, value, comment).
_utf8_mixed_document = st.builds(
    lambda k, v, c: k + " = " + v + "\n" + c,
    st.lists(_utf8_boundary_char, min_size=1, max_size=4).map(
        lambda cs: '"' + "".join(cs) + '"'
    ),
    st.one_of(_utf8_raw_string, _utf8_raw_literal, _utf8_raw_ml),
    _utf8_raw_comment,
)

# A pure raw-multibyte blob: no TOML syntax, forces the lexer to decode
# every byte sequence through toml_utf8_to_ucs before failing.
_utf8_raw_blob = st.lists(_utf8_boundary_char, min_size=1, max_size=24).map(
    "".join
)

# ---------- focused toml_utf8_to_ucs coverage ----------

# toml_utf8_to_ucs decodes a single UTF-8 sequence. To exercise every branch
# we need raw bytes spanning the full lead-byte / continuation-byte space,
# including valid sequences, truncated sequences, overlong encodings, and
# invalid continuation bytes. We emit these raw bytes directly (not as
# pre-decoded Python str characters) so the parser's byte-level decoder runs.

# Lead bytes covering: 1-byte ASCII, 2-byte leads (C2-DF), 3-byte leads
# (E0-EF), 4-byte leads (F0-F4), plus invalid leads (80-BF, C0, C1, F5-FF).
_lead_bytes = st.sampled_from([
    0x01, 0x41, 0x7F,             # 1-byte
    0x80, 0x81, 0xBF,             # invalid continuation-as-lead
    0xC0, 0xC1,                   # overlong 2-byte leads
    0xC2, 0xDF,                   # valid 2-byte leads
    0xE0, 0xE1, 0xEF,             # valid 3-byte leads
    0xF0, 0xF4,                   # valid 4-byte leads
    0xF5, 0xFF,                   # invalid 4-byte leads
])

# Continuation bytes: valid range 80-BF plus invalid values.
_cont_bytes = st.sampled_from([
    0x80, 0x81, 0x8F, 0x90, 0x9F, 0xA0, 0xAF, 0xB0, 0xBF,  # valid 80-BF
    0x00, 0x01, 0x41, 0x7F, 0xC0, 0xFF,                     # invalid continuations
])

# Build a raw byte sequence as a Python str where each character is a byte
# value that will be re-encoded to UTF-8 by the test harness. Since the
# harness writes the str to a file as UTF-8, codepoints < 0x80 become single
# bytes; to force multi-byte raw sequences we emit the actual Unicode
# codepoints whose UTF-8 encoding starts with the desired lead byte.
#
# We instead construct sequences of Unicode codepoints whose UTF-8 encodings
# collectively exercise every branch of toml_utf8_to_ucs: valid 1/2/3/4-byte
# sequences, boundary codepoints, and lone surrogates are excluded (Python
# cannot encode them). Truncated sequences are produced by emitting a
# lead-byte codepoint followed by ASCII, which the decoder sees as a
# truncated multi-byte sequence.

# Valid multi-byte codepoints across all length classes and boundaries.
_valid_utf8_cp = st.sampled_from([
    0x00, 0x01, 0x09, 0x0A, 0x0D, 0x20, 0x41, 0x7E, 0x7F,   # 1-byte
    0x80, 0x81, 0xBF, 0xC0, 0xC1, 0xC2, 0xDF,               # 2-byte region
    0x7FF, 0x800, 0x801, 0xE0, 0xE1, 0xEF, 0xFFF, 0x1000,   # 3-byte region
    0xFFFF, 0x10000, 0x10001, 0x10FFFF,                     # 4-byte region
    0xD7FF, 0xE000, 0x20AC, 0x4E2D, 0x1F600, 0x1F64F,      # notable chars
])

_valid_utf8_char = _valid_utf8_cp.map(chr)

# A raw string body packed with multibyte codepoints, emitted inside TOML
# string syntax so the lexer invokes toml_utf8_to_ucs on each sequence.
_utf8_decode_string = st.lists(_valid_utf8_char, min_size=1, max_size=16).map(
    lambda cs: '"' + "".join(cs) + '"'
)

# Same content in a literal string.
_utf8_decode_literal = st.lists(_valid_utf8_char, min_size=1, max_size=16).map(
    lambda cs: "'" + "".join(cs) + "'"
)

# Same content in a multiline basic string.
_utf8_decode_ml = st.lists(_valid_utf8_char, min_size=1, max_size=16).map(
    lambda cs: '"""' + "".join(cs) + '"""'
)

# Same content in a comment.
_utf8_decode_comment = st.lists(_valid_utf8_char, min_size=1, max_size=16).map(
    lambda cs: "#" + "".join(cs)
)

# Same content in a quoted key.
_utf8_decode_key = st.lists(_valid_utf8_char, min_size=1, max_size=8).map(
    lambda cs: '"' + "".join(cs) + '"'
)

# A document exercising toml_utf8_to_ucs in key, value, and comment slots.
_utf8_decode_document = st.builds(
    lambda k, v, c: k + " = " + v + "\n" + c,
    _utf8_decode_key,
    st.one_of(_utf8_decode_string, _utf8_decode_literal, _utf8_decode_ml),
    _utf8_decode_comment,
)

# A bare blob of multibyte codepoints with no TOML syntax: forces the lexer
# to run toml_utf8_to_ucs over every byte before failing on syntax.
_utf8_decode_blob = st.lists(_valid_utf8_char, min_size=1, max_size=32).map(
    "".join
)

# A single multibyte codepoint alone (minimal trigger for the decoder).
_utf8_decode_single = _valid_utf8_char

# Multibyte codepoints as a bare (unquoted) key, which the parser must still
# decode before rejecting.
_utf8_decode_bare = st.lists(_valid_utf8_char, min_size=1, max_size=6).map(
    "".join
)

# ---------- toml_utf8_to_ucs focused strategy ----------

# The decoder is invoked on raw bytes. To hit its branches we need:
#  - valid 1/2/3/4-byte sequences (all lead-byte ranges)
#  - boundary codepoints at each length transition
#  - truncated sequences (lead byte followed by ASCII)
#  - invalid continuation bytes
# We approximate truncated/invalid sequences by combining a multi-byte
# codepoint with ASCII control characters that terminate the sequence early.
_utf8_truncated = st.builds(
    lambda lead, tail: lead + tail,
    _valid_utf8_char,
    st.sampled_from(["", "x", "\n", " ", "=", '"', "'"]),
)

_utf8_truncated_string = st.lists(
    st.one_of(_valid_utf8_char, _utf8_truncated), min_size=1, max_size=12
).map(lambda cs: '"' + "".join(cs) + '"')

# A strategy that emits raw multibyte sequences in every syntactic position
# the parser decodes, maximizing toml_utf8_to_ucs branch coverage.
_utf8_decode_focus = st.one_of(
    _utf8_decode_string,
    _utf8_decode_literal,
    _utf8_decode_ml,
    _utf8_decode_comment,
    _utf8_decode_key,
    _utf8_decode_document,
    _utf8_decode_blob,
    _utf8_decode_single,
    _utf8_decode_bare,
    _utf8_truncated_string,
)

# Top-level strategy: mix of complete documents and edge-case focused documents.
strategy = st.one_of(
    _document,
    _document_crlf,
    _document_trailing_nl,
    _deep_document,
    # empty document
    st.just(""),
    # comment-only document
    _comment,
    # document with a single empty table
    st.just("[t]"),
    # document with a single array of tables
    st.just("[[a]]"),
    # document with empty quoted key
    st.just('"" = 1'),
    # document with a super-table defined after sub-table
    st.just("[a.b]\nx = 1\n[a]\ny = 2"),
    # document with a very long key
    st.builds(lambda k: k + " = 1", st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1000, max_size=1000)),
    # document with CRLF and tab indentation
    st.just("\t[a]\r\n\tx = 1\r\n"),
    # UTF-8 decoding coverage: multibyte codepoints in strings/keys/comments
    _utf8_string,
    _utf8_comment,
    _utf8_document,
    st.builds(lambda k, v: k + " = " + v, _utf8_key, _utf8_string),
    st.builds(lambda a, b: a + "\n" + b, _utf8_document, _utf8_comment),
    # Focused toml_utf8_to_ucs coverage: raw multibyte bytes across all
    # UTF-8 length classes and boundary codepoints, in every syntactic slot.
    _utf8_raw_string,
    _utf8_raw_literal,
    _utf8_raw_ml,
    _utf8_raw_comment,
    _utf8_raw_doc,
    _utf8_mixed_document,
    _utf8_raw_blob,
    # Direct toml_utf8_to_ucs coverage: valid 1/2/3/4-byte sequences,
    # boundary codepoints, and truncated sequences in every decoder slot.
    _utf8_decode_focus,
)