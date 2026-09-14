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
)