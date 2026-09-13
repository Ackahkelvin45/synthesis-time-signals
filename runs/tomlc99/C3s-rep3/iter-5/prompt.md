Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- small building blocks ----------

_ws = st.sampled_from(["", " ", "\t", "  "])
_comment_text = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\n\r\x00"),
    max_size=20,
)
_comment = st.one_of(
    st.just(""),
    _comment_text.map(lambda s: "#" + s),
)

_nl = st.sampled_from(["\n", "\r\n"])

# ---------- keys ----------

_unquoted_char = st.sampled_from(
    list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
)
_unquoted_key = st.text(_unquoted_char, min_size=1, max_size=12)

_basic_str_char = st.one_of(
    st.characters(blacklist_categories=("Cs",), blacklist_characters='"\\\n\r\x00'),
    st.sampled_from(["\\n", "\\t", "\\r", "\\b", "\\f", "\\\\", '\\"', "\\/"]),
    st.integers(min_value=0, max_value=0x10FFFF).map(lambda n: "\\u%04X" % (n & 0xFFFF)),
    st.sampled_from(["\x01", "\x02", "\x1f", "\x7f"]),
)
_basic_string = st.lists(_basic_str_char, max_size=8).map(
    lambda parts: '"' + "".join(parts) + '"'
)
_literal_string = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="'\n\r\x00"),
    max_size=8,
).map(lambda s: "'" + s + "'")

_quoted_key = st.one_of(_basic_string, _literal_string)

_simple_key = st.one_of(_unquoted_key, _quoted_key)

_dotted_key = st.lists(_simple_key, min_size=2, max_size=3).map(lambda ks: ".".join(ks))

_key = st.one_of(_simple_key, _dotted_key)

# ---------- scalars ----------

_dec_int = st.one_of(
    st.integers(min_value=-(2 ** 70), max_value=2 ** 70).map(str),
    st.sampled_from(["0", "-0", "+0", "007", "1_000", "123456789012345678901234567890"]),
)
_hex_int = st.sampled_from(["0x0", "0xDEAD_beef", "0xFF", "0x1_2_3"])
_oct_int = st.sampled_from(["0o0", "0o777", "0o1_7"])
_bin_int = st.sampled_from(["0b0", "0b1010", "0b1_0_1"])
_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

_float = st.one_of(
    st.floats(allow_nan=False, allow_infinity=False).map(repr),
    st.sampled_from(
        [
            "1.",
            ".5",
            "1e309",
            "-1e309",
            "1E-10",
            "3.14",
            "1_0.0_1",
            "0.0",
            "-0.0",
        ]
    ),
)
_inf_nan = st.sampled_from(["inf", "-inf", "+inf", "nan", "-nan", "+nan"])
_floating_point = st.one_of(_float, _inf_nan)

_bool = st.sampled_from(["true", "false"])

_date = st.sampled_from(
    [
        "1979-05-27",
        "1979-02-30",
        "0000-00-00",
        "9999-12-31",
    ]
)
_local_time = st.sampled_from(["07:32:00", "00:00:00.000001", "23:59:59.999999"])
_local_dt = st.sampled_from(
    [
        "1979-05-27T07:32:00",
        "1979-05-27t07:32:00.999",
        "1979-05-27 07:32:00",
    ]
)
_offset_dt = st.sampled_from(
    [
        "1979-05-27T07:32:00Z",
        "1979-05-27T00:32:00-07:00",
        "1979-05-27 07:32:00+00:00",
    ]
)
_date_time = st.one_of(_date, _local_time, _local_dt, _offset_dt)

_ml_basic = st.lists(
    st.one_of(
        st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00"),
        st.sampled_from(["\\\n", "\\n", "\\u0041"]),
    ),
    max_size=6,
).map(lambda parts: '"""' + "".join(parts) + '"""')

_ml_literal = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00"),
    max_size=10,
).map(lambda s: "'''" + s + "'''")

_string = st.one_of(_basic_string, _literal_string, _ml_basic, _ml_literal)

# ---------- recursive structures ----------

# leaf values (non-container)
_leaf_value = st.one_of(
    _string,
    _integer,
    _floating_point,
    _bool,
    _date_time,
)

# forward-declared recursive value strategy
_value = st.deferred(lambda: _value_strategy)

def _make_inline_table(inner):
    def build(pairs):
        if not pairs:
            return "{}"
        body = ", ".join("%s = %s" % (k, v) for (k, v) in pairs)
        return "{" + body + "}"
    return st.lists(
        st.tuples(_key, inner),
        max_size=3,
    ).map(build)

def _make_array(inner):
    def build(items):
        if not items:
            return "[]"
        return "[" + ", ".join(items) + "]"
    return st.lists(inner, max_size=4).map(build)

# Build value strategy using recursive with depth control.
# We combine: leaves, arrays of values, inline tables of values.
_value_strategy = st.one_of(
    _leaf_value,
    st.recursive(
        _leaf_value,
        lambda children: st.one_of(
            _make_array(children),
            _make_inline_table(children),
        ),
        max_leaves=20,
    ),
)

# ---------- key/value lines ----------

_kv_line = st.builds(
    lambda k, v, c: "%s = %s%s" % (k, v, c),
    _key,
    _value,
    _comment,
)

# table headers
_standard_table = _key.map(lambda k: "[%s]" % k)
_array_table = _key.map(lambda k: "[[%s]]" % k)
_table = st.one_of(_standard_table, _array_table)

# ---------- documents ----------

def _join_lines(lines):
    return "\n".join(lines)

_line = st.one_of(
    _kv_line,
    _table,
    _comment,
)

_document = st.lists(_line, max_size=8).map(_join_lines)

# ---------- malformed / edge-case variants ----------

def _mangle_one(s):
    """Produce a near-valid-but-malformed variant of a document."""
    if not s:
        return s
    # choose a mutation index safely
    n = len(s)
    i = n // 2
    ch = s[i]
    if ch in "[]{}":
        # drop a delimiter
        return s[:i] + s[i + 1:]
    if ch == '"':
        # unterminated string: drop closing quote if present
        if s.count('"') % 2 == 1:
            return s  # already unbalanced
        # remove last quote
        j = s.rfind('"')
        return s[:j] + s[j + 1:]
    if ch in "=":
        # doubled equals
        return s[:i] + "==" + s[i + 1:]
    # stray token
    return s[:i] + "@" + s[i:]

_malformed = _document.map(_mangle_one)

# empty / comment-only docs, no trailing newline
_empty_doc = st.just("")
_comment_only = st.lists(_comment, min_size=1, max_size=3).map("\n".join)

# deep nesting band 1500-2048
_deep_depth = st.integers(min_value=1500, max_value=2048)

def _deep_array(depth):
    return "a = " + ("[" * depth) + ("]" * depth)

_deep_doc = _deep_depth.map(_deep_array)

def _deep_inline(depth):
    # nested inline tables: {a = {a = ... }}
    return "a = " + ("{a = " * depth) + "1" + ("}" * depth)

_deep_inline_doc = _deep_depth.map(_deep_inline)

# duplicate keys (rejected but interesting)
_dup_keys = st.builds(
    lambda k, v: "%s = %s\n%s = %s" % (k, v, k, v),
    _unquoted_key,
    _leaf_value,
)

# non-ASCII bare key (rejected)
_nonascii_key = st.just("kéy = 1")

# newline inside inline table (rejected)
_nl_inline = st.just("a = {b = 1,\nc = 2}")

# invalid escape (rejected)
_bad_escape = st.just('a = "x\\qy"')

# unterminated string (rejected)
_unterminated = st.just('a = "unterminated')

# value on next line (rejected)
_val_next_line = st.just("a =\n1")

# trailing comma in inline table (accepted, deviation)
_trailing_comma_inline = st.just("a = {b = 1,}")

# leading zeros (accepted, deviation)
_leading_zero = st.just("a = 007")

# float no digits (accepted, deviation)
_float_odd = st.just("a = 1.")

# calendar-invalid date (accepted, deviation)
_bad_date = st.just("a = 1979-02-30")

# raw control char in string (accepted, deviation)
_ctrl_in_string = st.just('a = "x\x01y"')

# control char in comment (accepted, deviation)
_ctrl_in_comment = st.just("# comment\x02")

# empty quoted key
_empty_key = st.just('"" = 1')

# long key
_long_key = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\n\r\x00="),
    min_size=1000,
    max_size=1000,
).map(lambda s: s.replace(" ", "")[:1000]).filter(lambda s: len(s) == 1000).map(
    lambda s: s + " = 1"
)

# CRLF and tab indentation
_crlf_doc = st.just("a = 1\r\nb = 2\r\n")
_tab_indent = st.just("\ta = 1\n")

# super-table after sub-table
_super_after_sub = st.just("[a.b]\nx = 1\n\n[a]\ny = 2\n")

# mixed-type array
_mixed_array = st.just('a = [1, "two", 3.0, true, 1979-05-27]')

# multiline array with comments
_ml_array = st.just("a = [\n  1, # one\n  2, # two\n]")

# empty containers
_empty_containers = st.just("a = []\nb = {}\n[t]\n[[u]]\n")

# all value kinds
_all_kinds = st.just(
    'a = "basic"\n'
    "b = 'literal'\n"
    'c = """ml basic"""\n'
    "d = '''ml literal'''\n"
    "e = 42\n"
    "f = 0xDEAD\n"
    "g = 0o777\n"
    "h = 0b1010\n"
    "i = 3.14\n"
    "j = inf\n"
    "k = nan\n"
    "l = true\n"
    "m = false\n"
    "n = 1979-05-27\n"
    "o = 07:32:00\n"
    "p = 1979-05-27T07:32:00\n"
    "q = 1979-05-27T07:32:00Z\n"
    "r = [1, 2]\n"
    "s = {x = 1}\n"
)

# ---------- extra branch-coverage inputs ----------

# empty-string key forms and edge delimiters
_empty_literal_key = st.just("'' = 1")
_empty_dotted = st.just('a."" = 1')
_leading_dot_key = st.just('a. = 1')
_trailing_dot_key = st.just('.a = 1')
_double_dot_key = st.just('a..b = 1')

# empty table headers and array-table variants
_empty_table = st.just("[]\nx = 1\n")
_empty_array_table = st.just("[[]]\nx = 1\n")
_empty_dotted_table = st.just("[a.]\nx = 1\n")
_dotted_empty_table = st.just("[.a]\nx = 1\n")

# bare CR / lone LF line handling
_bare_cr = st.just("a = 1\rb = 2\n")
_lone_cr_doc = st.just("a = 1\r")

# unterminated multiline strings
_unterm_ml_basic = st.just('a = """unterminated')
_unterm_ml_literal = st.just("a = '''unterminated")
_unterm_literal = st.just("a = 'unterminated")

# invalid unicode escape variants
_bad_unicode_escape = st.just('a = "\\uZZZZ"')
_short_unicode_escape = st.just('a = "\\u12"')
_bad_hex_escape = st.just('a = "\\xZZ"')

# integer overflow / boundary
_big_hex = st.just("a = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF")
_big_oct = st.just("a = 0o777777777777777777777777777777")
_big_bin = st.just("a = 0b" + "1" * 80)
_neg_hex = st.just("a = -0xFF")
_plus_dec = st.just("a = +42")

# float edge forms
_float_exp_only = st.just("a = 1e")
_float_dot_exp = st.just("a = 1.e5")
_float_underscore_bad = st.just("a = 1__0.0")
_float_trailing_underscore = st.just("a = 1.0_")

# date/time edge forms
_date_bad_month = st.just("a = 1979-13-01")
_date_short = st.just("a = 1979-5-27")
_time_bad = st.just("a = 25:00:00")
_dt_bad_offset = st.just("a = 1979-05-27T07:32:00+99:99")

# control characters in keys (bare)
_ctrl_bare_key = st.just("a\x01b = 1")

# equals without value, value without key
_no_value = st.just("a =\n")
_no_key = st.just("= 1\n")
_just_equals = st.just("=\n")

# table header without closing bracket
_unclosed_table = st.just("[abc\nx = 1\n")
_unclosed_array_table = st.just("[[abc]\nx = 1\n")

# comment variations
_comment_no_space = st.just("#comment\n")
_comment_only_hash = st.just("#\n")
_comment_with_crlf = st.just("# c\r\n")

# nested array with trailing comma
_arr_trailing_comma = st.just("a = [1, 2,]\n")
_arr_leading_comma = st.just("a = [,1]\n")
_arr_double_comma = st.just("a = [1,,2]\n")

# inline table edge forms
_inline_no_value = st.just("a = {b = }\n")
_inline_missing_comma = st.just("a = {b = 1 c = 2}\n")
_inline_double_comma = st.just("a = {b = 1,, c = 2}\n")
_inline_leading_comma = st.just("a = {, b = 1}\n")
_inline_unclosed = st.just("a = {b = 1\n")

# array unclosed
_arr_unclosed = st.just("a = [1, 2\n")

# table then key on same line
_table_kv_same_line = st.just("[t] x = 1\n")

# whitespace-only key
_ws_key = st.just("   = 1\n")

# BOM prefix
_bom_doc = st.just("\ufeffa = 1\n")

# very long comment
_long_comment = st.just("#" + "x" * 5000 + "\n")

# null byte in various positions
_nul_in_comment = st.just("# a\x00b\n")
_nul_in_key = st.just("a\x00b = 1\n")

# duplicate table headers
_dup_table = st.just("[a]\nx = 1\n[a]\ny = 2\n")

# array-of-tables then standard
_array_then_std = st.just("[[a]]\nx = 1\n[a]\ny = 2\n")

# key with equals in quoted string
_eq_in_str_key = st.just('"a=b" = 1\n')

# bare key with dot only
_dot_only_key = st.just(". = 1\n")

# multiline basic with escapes and quotes
_ml_basic_quotes = st.just('a = """he said \\"hi\\""""\n')

# multiline literal with quotes
_ml_literal_quotes = st.just("a = '''it's'''\n")

# nested inline in array
_nested_inline_array = st.just("a = [{b = 1}, {c = 2}]\n")

# array in inline table
_array_in_inline = st.just("a = {b = [1, 2]}\n")

# very deep dotted key
_deep_dotted_key = st.just(".".join("k%d" % i for i in range(50)) + " = 1\n")

# empty document with only newlines
_newlines_only = st.just("\n\n\n")

# CR-only line endings throughout
_cr_only_doc = st.just("a = 1\rb = 2\rc = 3\r")

_extra_branches = st.one_of(
    _empty_literal_key,
    _empty_dotted,
    _leading_dot_key,
    _trailing_dot_key,
    _double_dot_key,
    _empty_table,
    _empty_array_table,
    _empty_dotted_table,
    _dotted_empty_table,
    _bare_cr,
    _lone_cr_doc,
    _unterm_ml_basic,
    _unterm_ml_literal,
    _unterm_literal,
    _bad_unicode_escape,
    _short_unicode_escape,
    _bad_hex_escape,
    _big_hex,
    _big_oct,
    _big_bin,
    _neg_hex,
    _plus_dec,
    _float_exp_only,
    _float_dot_exp,
    _float_underscore_bad,
    _float_trailing_underscore,
    _date_bad_month,
    _date_short,
    _time_bad,
    _dt_bad_offset,
    _ctrl_bare_key,
    _no_value,
    _no_key,
    _just_equals,
    _unclosed_table,
    _unclosed_array_table,
    _comment_no_space,
    _comment_only_hash,
    _comment_with_crlf,
    _arr_trailing_comma,
    _arr_leading_comma,
    _arr_double_comma,
    _inline_no_value,
    _inline_missing_comma,
    _inline_double_comma,
    _inline_leading_comma,
    _inline_unclosed,
    _arr_unclosed,
    _table_kv_same_line,
    _ws_key,
    _bom_doc,
    _long_comment,
    _nul_in_comment,
    _nul_in_key,
    _dup_table,
    _array_then_std,
    _eq_in_str_key,
    _dot_only_key,
    _ml_basic_quotes,
    _ml_literal_quotes,
    _nested_inline_array,
    _array_in_inline,
    _deep_dotted_key,
    _newlines_only,
    _cr_only_doc,
)

# ---------- NEW: branch-coverage boosters ----------

# Multiline strings with line-ending backslash continuation and CRLF inside.
_ml_continuation = st.just('a = """line1 \\\n   line2"""\n')
_ml_crlf_content = st.just('a = """x\r\ny"""\n')
_ml_leading_newline = st.just('a = """\nhello"""\n')
_ml_quote_runs = st.just('a = """a""b"""\n')
_ml_literal_quote_runs = st.just("a = '''a''b'''\n")
_ml_literal_newline = st.just("a = '''\nline'''\n")

# Whitespace/comment interleaving in arrays and inline tables.
_arr_ws_comment = st.just("a = [ 1 , # c\n 2 ]\n")
_arr_newlines_only = st.just("a = [\n\n]\n")
_inline_ws = st.just("a = {  b  =  1  }\n")

# Whitespace and comments between key and equals / equals and value.
_ws_around_eq = st.just("a   =   1\n")
_ws_before_eq_comment = st.just("a # c\n= 1\n")
_ws_after_eq_comment = st.just("a = # c\n1\n")

# Leading/trailing whitespace on lines and around table headers.
_ws_before_table = st.just("  [t]\nx = 1\n")
_ws_after_table = st.just("[t]  \nx = 1\n")
_ws_around_array_table = st.just("  [[t]]  \nx = 1\n")
_ws_before_kv = st.just("   a = 1\n")
_trailing_ws_kv = st.just("a = 1   \n")

# Comment placement variants.
_comment_inline_after_value = st.just("a = 1 # trailing\n")
_comment_inline_after_table = st.just("[t] # c\nx = 1\n")
_comment_between_kv = st.just("a = 1\n# mid\nb = 2\n")

# Bare keys that exercise the character-class boundaries.
_key_with_dash = st.just("a-b_c = 1\n")
_key_digits_only = st.just("123 = 1\n")
_key_leading_underscore = st.just("_a = 1\n")

# Dotted keys with quoted segments and whitespace around dots.
_dotted_quoted = st.just('a."b".c = 1\n')
_dotted_ws = st.just("a . b = 1\n")

# Empty and whitespace-only documents.
_ws_only_doc = st.just("   \t  \n")
_ws_and_comments = st.just("  # c\n\n\t\n")

# Values with leading whitespace / newlines after equals.
_val_leading_ws = st.just("a =    1\n")
_val_leading_nl = st.just("a =\n\n1\n")

# Array-of-tables with dotted names and standard table nesting.
_aot_dotted = st.just("[[a.b.c]]\nx = 1\n")
_aot_then_sub = st.just("[[a]]\n[a.b]\nx = 1\n")

# Numbers with unusual but valid forms.
_int_plus = st.just("a = +1\n")
_int_neg_zero = st.just("a = -0\n")
_float_exp_plus = st.just("a = 1e+5\n")
_float_exp_neg = st.just("a = 1e-5\n")
_float_upper_e = st.just("a = 1E5\n")

# Booleans with surrounding whitespace.
_bool_ws = st.just("a =   true  \n")

# Date/time with lowercase t and z.
_dt_lower_tz = st.just("a = 1979-05-27t07:32:00z\n")
_dt_offset_no_colon = st.just("a = 1979-05-27T07:32:00-0700\n")

# Strings with all escape kinds in one.
_str_all_escapes = st.just('a = "\\b\\t\\n\\f\\r\\"\\\\\\/"\n')

# Multiline basic string with escaped triple quote.
_ml_escaped_triple = st.just('a = """x\\"""y"""\n')

# Table header with whitespace inside brackets.
_table_inner_ws = st.just("[ t ]\nx = 1\n")
_array_table_inner_ws = st.just("[[ t ]]\nx = 1\n")

# Key with all allowed bare-key chars.
_bare_key_full = st.just("aZ09_- = 1\n")

# Long dotted key at boundary.
_dotted_many = st.just(".".join("a" for _ in range(20)) + " = 1\n")

# Multiple values on separate lines with mixed endings.
_mixed_endings = st.just("a = 1\r\nb = 2\nc = 3\r")

# Comment-only line with CRLF and trailing spaces.
_comment_crlf_ws = st.just("# c  \r\n")

# Empty inline table and array with whitespace.
_empty_inline_ws = st.just("a = {  }\n")
_empty_array_ws = st.just("a = [  ]\n")

# Nested arrays with mixed types and trailing comma.
_nested_arr_mixed = st.just("a = [[1, 2], [3.0, true], []]\n")

# Inline table with dotted keys inside.
_inline_dotted = st.just("a = {b.c = 1}\n")

# Table header followed immediately by EOF (no newline).
_table_eof = st.just("[t]")
_kv_eof = st.just("a = 1")

# Key-value with comment and no newline at end.
_kv_comment_eof = st.just("a = 1 # c")

# Value that is a bare `inf`/`nan` with sign and whitespace.
_inf_ws = st.just("a =   -inf  \n")
_nan_ws = st.just("a =   +nan  \n")

# Unicode escapes in basic strings of all forms.
_unicode_escapes = st.just('a = "\\u0041\\U0001F600"\n')

# Keys with numbers and dots.
_key_num_dot = st.just("a1.2b = 1\n")

# Bare CR inside a basic string (invalid) and inside comment.
_cr_in_string = st.just('a = "x\ry"\n')
_cr_in_comment = st.just("# x\ry\n")

# Extremely long array (many elements) to exercise list paths.
_long_array = st.just("a = [" + ", ".join(str(i) for i in range(200)) + "]\n")

# Extremely long inline table.
_long_inline = st.just(
    "a = {" + ", ".join("k%d = %d" % (i, i) for i in range(100)) + "}\n"
)

# Deeply dotted table header.
_deep_table_dotted = st.just("[" + ".".join("k%d" % i for i in range(30)) + "]\n")

_branch_boosters = st.one_of(
    _ml_continuation,
    _ml_crlf_content,
    _ml_leading_newline,
    _ml_quote_runs,
    _ml_literal_quote_runs,
    _ml_literal_newline,
    _arr_ws_comment,
    _arr_newlines_only,
    _inline_ws,
    _ws_around_eq,
    _ws_before_eq_comment,
    _ws_after_eq_comment,
    _ws_before_table,
    _ws_after_table,
    _ws_around_array_table,
    _ws_before_kv,
    _trailing_ws_kv,
    _comment_inline_after_value,
    _comment_inline_after_table,
    _comment_between_kv,
    _key_with_dash,
    _key_digits_only,
    _key_leading_underscore,
    _dotted_quoted,
    _dotted_ws,
    _ws_only_doc,
    _ws_and_comments,
    _val_leading_ws,
    _val_leading_nl,
    _aot_dotted,
    _aot_then_sub,
    _int_plus,
    _int_neg_zero,
    _float_exp_plus,
    _float_exp_neg,
    _float_upper_e,
    _bool_ws,
    _dt_lower_tz,
    _dt_offset_no_colon,
    _str_all_escapes,
    _ml_escaped_triple,
    _table_inner_ws,
    _array_table_inner_ws,
    _bare_key_full,
    _dotted_many,
    _mixed_endings,
    _comment_crlf_ws,
    _empty_inline_ws,
    _empty_array_ws,
    _nested_arr_mixed,
    _inline_dotted,
    _table_eof,
    _kv_eof,
    _kv_comment_eof,
    _inf_ws,
    _nan_ws,
    _unicode_escapes,
    _key_num_dot,
    _cr_in_string,
    _cr_in_comment,
    _long_array,
    _long_inline,
    _deep_table_dotted,
)

# ---------- combine everything ----------

strategy = st.one_of(
    _document,
    _malformed,
    _empty_doc,
    _comment_only,
    _deep_doc,
    _deep_inline_doc,
    _dup_keys,
    _nonascii_key,
    _nl_inline,
    _bad_escape,
    _unterminated,
    _val_next_line,
    _trailing_comma_inline,
    _leading_zero,
    _float_odd,
    _bad_date,
    _ctrl_in_string,
    _ctrl_in_comment,
    _empty_key,
    _long_key,
    _crlf_doc,
    _tab_indent,
    _super_after_sub,
    _mixed_array,
    _ml_array,
    _empty_containers,
    _all_kinds,
    _extra_branches,
    _branch_boosters,
)
```

Here is the code coverage its last run achieved on the parser (measured with instrumentation):
{
  "branch_coverage_pct": 70.36,
  "region_coverage_pct": 71.8
}

Make EXACTLY ONE change to the strategy: **increase_branch_coverage** — branch coverage is 70.4%; reach parser code the current inputs never execute.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.