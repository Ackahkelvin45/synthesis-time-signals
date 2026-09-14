from hypothesis import strategies as st
import json

# ---------- helpers ----------

def _join(parts):
    return "".join(parts)

# ---------- scalars ----------

_hex_digit = st.sampled_from("0123456789abcdefABCDEF")
_oct_digit = st.sampled_from("01234567")
_bin_digit = st.sampled_from("01")
_dec_digit = st.sampled_from("0123456789")

# unquoted key chars (ASCII only per parser reality)
_key_char = st.sampled_from(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
)

unquoted_key = st.text(_key_char, min_size=1, max_size=12)

# basic string content: allow escapes, non-ASCII, control bytes (except NUL)
_esc_simple = st.sampled_from(["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

def _unicode_escape():
    return st.tuples(
        st.just("\\u"),
        _hex_digit, _hex_digit, _hex_digit, _hex_digit,
    ).map(_join)

def _ex_unicode_escape():
    return st.tuples(
        st.just("\\U"),
        _hex_digit, _hex_digit, _hex_digit, _hex_digit,
        _hex_digit, _hex_digit, _hex_digit, _hex_digit,
    ).map(_join)

_esc = st.one_of(_esc_simple, _unicode_escape(), _ex_unicode_escape())

# chars allowed raw inside a basic string (no quote, no backslash, no newline, no NUL)
_basic_raw_char = st.characters(
    blacklist_categories=["Cs"],
    blacklist_characters=['"', "\\", "\n", "\r", "\x00"],
)

basic_string_inner = st.one_of(
    st.text(_basic_raw_char, min_size=0, max_size=20),
    st.lists(st.one_of(_esc, st.text(_basic_raw_char, max_size=5)), max_size=8).map(_join),
)

basic_string = st.tuples(st.just('"'), basic_string_inner, st.just('"')).map(_join)

# literal string: no single quote, no newline, no NUL
_literal_raw_char = st.characters(
    blacklist_categories=["Cs"],
    blacklist_characters=["'", "\n", "\r", "\x00"],
)
literal_string = st.tuples(
    st.just("'"),
    st.text(_literal_raw_char, min_size=0, max_size=20),
    st.just("'"),
).map(_join)

# multiline basic string: """ ... """ ; content may include newlines, quotes (not triple)
_ml_basic_char = st.one_of(
    st.characters(
        blacklist_categories=["Cs"],
        blacklist_characters=["\x00"],
    ),
    _esc,
)
ml_basic_string = st.tuples(
    st.just('"""'),
    st.lists(_ml_basic_char, max_size=15).map(_join),
    st.just('"""'),
).map(_join)

# multiline literal string: ''' ... '''
_ml_literal_char = st.characters(
    blacklist_categories=["Cs"],
    blacklist_characters=["\x00"],
)
ml_literal_string = st.tuples(
    st.just("'''"),
    st.text(_ml_literal_char, min_size=0, max_size=15),
    st.just("'''"),
).map(_join)

any_string = st.one_of(basic_string, literal_string, ml_basic_string, ml_literal_string)

# quoted key (basic or literal string)
quoted_key = st.one_of(basic_string, literal_string)

simple_key = st.one_of(quoted_key, unquoted_key)

def _dotted_key():
    return st.tuples(
        simple_key,
        st.lists(simple_key, min_size=1, max_size=3).map(lambda ks: "".join("." + k for k in ks)),
    ).map(_join)

dotted_key = _dotted_key()

key = st.one_of(simple_key, dotted_key)

# ---------- numbers ----------

def _dec_int():
    digits = st.text(_dec_digit, min_size=1, max_size=20)
    sign = st.sampled_from(["", "+", "-"])
    return st.tuples(sign, digits).map(_join)

def _dec_int_underscore():
    # digit (digit|_digit)*
    return st.tuples(
        st.sampled_from(["", "+", "-"]),
        _dec_digit,
        st.lists(st.one_of(_dec_digit, st.tuples(st.just("_"), _dec_digit).map(_join)), max_size=10).map(_join),
    ).map(_join)

def _hex_int():
    return st.tuples(
        st.just("0x"),
        _hex_digit,
        st.lists(st.one_of(_hex_digit, st.tuples(st.just("_"), _hex_digit).map(_join)), max_size=10).map(_join),
    ).map(_join)

def _oct_int():
    return st.tuples(
        st.just("0o"),
        _oct_digit,
        st.lists(st.one_of(_oct_digit, st.tuples(st.just("_"), _oct_digit).map(_join)), max_size=10).map(_join),
    ).map(_join)

def _bin_int():
    return st.tuples(
        st.just("0b"),
        _bin_digit,
        st.lists(st.one_of(_bin_digit, st.tuples(st.just("_"), _bin_digit).map(_join)), max_size=10).map(_join),
    ).map(_join)

# leading-zero integer (accepted by parser)
_leading_zero_int = st.tuples(
    st.sampled_from(["", "+", "-"]),
    st.just("0"),
    st.text(_dec_digit, min_size=1, max_size=10),
).map(_join)

integer = st.one_of(
    _dec_int(),
    _dec_int_underscore(),
    _hex_int(),
    _oct_int(),
    _bin_int(),
    _leading_zero_int,
)

def _float():
    # simple float: digits . digits with optional exp
    int_part = st.one_of(
        st.text(_dec_digit, min_size=1, max_size=10),
        st.just(""),  # .5 form
    )
    frac_part = st.one_of(
        st.text(_dec_digit, min_size=1, max_size=10),
        st.just(""),  # 1. form
    )
    exp = st.one_of(
        st.just(""),
        st.tuples(
            st.sampled_from(["e", "E"]),
            st.sampled_from(["", "+", "-"]),
            st.text(_dec_digit, min_size=1, max_size=3),
        ).map(_join),
    )
    return st.tuples(
        st.sampled_from(["", "+", "-"]),
        int_part,
        st.just("."),
        frac_part,
        exp,
    ).map(_join).filter(lambda s: len(s) > 1)

_extreme_float = st.sampled_from([
    "1e309", "-1e309", "1e-309", "1e999", "1.7976931348623157e308",
    "1_000.000_1", "0.0", "-0.0", "1e0", "1E+10", "1e-10",
])

inf_nan = st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])

floating_point = st.one_of(_float(), _extreme_float, inf_nan)

boolean = st.sampled_from(["true", "false"])

# ---------- dates ----------

def _two_digits():
    return st.text(_dec_digit, min_size=2, max_size=2)

def _four_digits():
    return st.text(_dec_digit, min_size=4, max_size=4)

def _partial_time():
    return st.tuples(
        _two_digits(), st.just(":"), _two_digits(), st.just(":"), _two_digits(),
        st.one_of(st.just(""), st.tuples(st.just("."), st.text(_dec_digit, min_size=1, max_size=6)).map(_join)),
    ).map(_join)

def _full_date():
    return st.tuples(_four_digits(), st.just("-"), _two_digits(), st.just("-"), _two_digits()).map(_join)

def _offset():
    return st.one_of(
        st.just("Z"),
        st.tuples(
            st.sampled_from(["+", "-"]), _two_digits(), st.just(":"), _two_digits(),
        ).map(_join),
    )

def _offset_date_time():
    return st.tuples(
        _full_date(),
        st.sampled_from(["T", "t", " "]),
        _partial_time(),
        _offset(),
    ).map(_join)

def _local_date_time():
    return st.tuples(
        _full_date(),
        st.sampled_from(["T", "t", " "]),
        _partial_time(),
    ).map(_join)

def _local_date():
    return _full_date()

def _local_time():
    return _partial_time()

# calendar-invalid dates accepted by parser
_invalid_date = st.sampled_from([
    "1979-02-30", "2023-13-01", "2023-00-00", "0000-00-00", "9999-99-99",
])

date_time = st.one_of(
    _offset_date_time(),
    _local_date_time(),
    _local_date(),
    _local_time(),
    _invalid_date,
)

# ---------- recursive values ----------

def _comment():
    return st.tuples(
        st.just("#"),
        st.text(
            st.characters(blacklist_categories=["Cs"], blacklist_characters=["\x00", "\n", "\r"]),
            min_size=0, max_size=30,
        ),
    ).map(_join)

comment = _comment()

# We'll build arrays and inline tables with st.recursive.
# Note: values inside arrays/inline tables must not contain raw newlines in inline tables.

def _value_no_newline():
    """Values safe inside inline tables (no raw newlines)."""
    return st.one_of(
        basic_string,
        literal_string,
        integer,
        floating_point,
        boolean,
        date_time,
    )

def _inline_table_leaf():
    # empty inline table or one with simple key=value pairs
    def _pair():
        return st.tuples(
            key,
            st.just("="),
            _value_no_newline(),
        ).map(_join)
    return st.one_of(
        st.just("{}"),
        st.tuples(
            st.just("{"),
            st.lists(_pair(), min_size=1, max_size=4).map(lambda ps: ", ".join(ps)),
            st.just("}"),
        ).map(_join),
        # trailing comma (accepted by parser)
        st.tuples(
            st.just("{"),
            st.lists(_pair(), min_size=1, max_size=4).map(lambda ps: ", ".join(ps) + ","),
            st.just("}"),
        ).map(_join),
    )

def _array_leaf():
    # array with simple values, possibly multiline with comments
    def _elem():
        return st.one_of(
            any_string,
            integer,
            floating_point,
            boolean,
            date_time,
        )
    return st.one_of(
        st.just("[]"),
        st.tuples(
            st.just("["),
            st.lists(_elem(), min_size=1, max_size=5).map(lambda es: ", ".join(es)),
            st.just("]"),
        ).map(_join),
        # trailing comma
        st.tuples(
            st.just("["),
            st.lists(_elem(), min_size=1, max_size=5).map(lambda es: ", ".join(es) + ","),
            st.just("]"),
        ).map(_join),
        # multiline with comment
        st.tuples(
            st.just("[\n"),
            st.lists(
                st.tuples(_elem(), st.just(",\n")).map(_join),
                min_size=1, max_size=4,
            ).map(_join),
            st.just("]"),
        ).map(_join),
        st.tuples(
            st.just("[\n# comment\n"),
            st.lists(
                st.tuples(_elem(), st.just(",\n")).map(_join),
                min_size=1, max_size=4,
            ).map(_join),
            st.just("]"),
        ).map(_join),
    )

# recursive value: arrays and inline tables can nest
def _value_recursive(children):
    return st.one_of(
        any_string,
        integer,
        floating_point,
        boolean,
        date_time,
        # array containing recursive values
        st.tuples(
            st.just("["),
            st.lists(children, min_size=0, max_size=4).map(lambda es: ", ".join(es)),
            st.just("]"),
        ).map(_join),
        st.tuples(
            st.just("["),
            st.lists(children, min_size=1, max_size=4).map(lambda es: ", ".join(es) + ","),
            st.just("]"),
        ).map(_join),
        # inline table containing recursive values
        st.tuples(
            st.just("{"),
            st.lists(
                st.tuples(key, st.just("="), children).map(_join),
                min_size=1, max_size=3,
            ).map(lambda ps: ", ".join(ps)),
            st.just("}"),
        ).map(_join),
        st.tuples(
            st.just("{"),
            st.lists(
                st.tuples(key, st.just("="), children).map(_join),
                min_size=1, max_size=3,
            ).map(lambda ps: ", ".join(ps) + ","),
            st.just("}"),
        ).map(_join),
    )

value = st.recursive(
    st.one_of(
        any_string,
        integer,
        floating_point,
        boolean,
        date_time,
        st.just("[]"),
        st.just("{}"),
    ),
    _value_recursive,
    max_leaves=30,
)

# ---------- key-value / tables / document ----------

def _key_value():
    return st.tuples(key, st.just(" = "), value).map(_join)

key_value = _key_value()

def _standard_table():
    return st.tuples(st.just("["), key, st.just("]")).map(_join)

def _array_table():
    return st.tuples(st.just("[["), key, st.just("]]")).map(_join)

table_header = st.one_of(_standard_table(), _array_table())

# expression: key_value | table | comment
def _expression():
    return st.one_of(
        st.tuples(key_value, st.one_of(st.just(""), st.tuples(st.just(" "), comment).map(_join))).map(_join),
        st.tuples(table_header, st.one_of(st.just(""), st.tuples(st.just(" "), comment).map(_join))).map(_join),
        comment,
        st.just(""),
    )

expression = _expression()

# document: expression (NL expression)*
def _document():
    return st.tuples(
        expression,
        st.lists(
            st.tuples(st.just("\n"), expression).map(_join),
            max_size=8,
        ).map(_join),
    ).map(_join)

document = _document()

# ---------- edge-case / malformed inputs ----------

_empty_doc = st.just("")
_comment_only = st.tuples(st.just("#"), st.text(
    st.characters(blacklist_categories=["Cs"], blacklist_characters=["\x00", "\n", "\r"]),
    max_size=20,
)).map(_join)

# deeply nested arrays (steer band 1500-2048)
def _deep_array(depth):
    return "[" * depth + "]" * depth

_deep_nesting = st.integers(min_value=1500, max_value=2048).map(_deep_array)

# deep inline tables
def _deep_inline(depth):
    return "{" + "a = {" * depth + "}" * (depth + 1)

_deep_inline_nesting = st.integers(min_value=100, max_value=500).map(_deep_inline)

# duplicate keys
_dup_key = st.tuples(
    st.just("a = 1\na = 2"),
).map(_join)

_dup_table = st.just("[a]\n[a]")

# malformed: missing delimiter
_missing_bracket = st.sampled_from([
    "[a\nb = 1",
    "a = 1\n[b",
    "a = [1, 2",
    "a = {b = 1",
    "a = 1\n[[c]",
])

_doubled_delimiter = st.sampled_from([
    "a = 1\n[[a]]\n[[a]]",
    "a = [[1, 2]]",
    "a = {b = 1}}",
    "a = [1, 2]]",
])

_unterminated_string = st.sampled_from([
    'a = "unterminated',
    "a = 'unterminated",
    'a = """unterminated',
    "a = '''unterminated",
])

_stray_token = st.sampled_from([
    "a = 1\nb",
    "= 1",
    "a =",
    "a",
    "a = 1\n}",
    "a = 1\n]",
    "a = 1\n,",
    "a = 1\n.",
])

_malformed = st.one_of(
    _missing_bracket,
    _doubled_delimiter,
    _unterminated_string,
    _stray_token,
    _dup_key,
    _dup_table,
)

# non-ASCII bare key (rejected)
_non_ascii_key = st.tuples(
    st.text(st.characters(min_codepoint=0x80, max_codepoint=0x10FFFF,
                          blacklist_categories=["Cs"], blacklist_characters=["\x00"]),
            min_size=1, max_size=4),
    st.just(" = 1"),
).map(_join)

# newline inside inline table (rejected)
_newline_inline = st.sampled_from([
    "a = {b = 1,\nc = 2}",
    "a = {b = 1\n}",
])

# invalid escape
_invalid_escape = st.sampled_from([
    'a = "\\q"',
    'a = "\\x41"',
    'a = "\\u12"',
])

_malformed_extra = st.one_of(
    _non_ascii_key,
    _newline_inline,
    _invalid_escape,
)

# ---------- final strategy ----------

strategy = st.one_of(
    document,
    _empty_doc,
    _comment_only,
    _deep_nesting,
    _deep_inline_nesting,
    _malformed,
    _malformed_extra,
    # complete documents with edge scalars
    st.tuples(
        st.just("a = "),
        st.one_of(
            st.sampled_from(["007", "1.", ".5", "1e309", "1979-02-30", "0x_1", "1_000"]),
            basic_string,
            ml_basic_string,
            ml_literal_string,
        ),
    ).map(_join),
    # CRLF document
    st.tuples(
        st.just("a = 1\r\n"),
        st.just("[b]\r\n"),
        st.just("c = true"),
    ).map(_join),
    # no trailing newline
    st.just("a = 1"),
    # empty quoted key
    st.just('"" = 1'),
    # super-table after sub-table
    st.just("[a.b]\nx = 1\n[a]\ny = 2"),
    # long key
    st.text(_key_char, min_size=10000, max_size=10000).map(lambda k: k + " = 1"),
    # embedded control bytes in string
    st.tuples(
        st.just('a = "'),
        st.text(st.characters(min_codepoint=1, max_codepoint=0x1F,
                              blacklist_categories=["Cs"],
                              blacklist_characters=["\x00", '"', "\\", "\n", "\r"]),
                min_size=1, max_size=5),
        st.just('"'),
    ).map(_join),
    # \u0000 escape inside string
    st.just('a = "\\u0000"'),
    # raw tab in string
    st.just('a = "x\ty"'),
)