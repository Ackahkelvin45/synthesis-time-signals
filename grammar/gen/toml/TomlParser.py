# Generated from /Users/kelvinackah/Desktop/projects/research/agentic_fuzzing/grammar/TomlParser.g4 by ANTLR 4.13.2
# encoding: utf-8
from antlr4 import *
from io import StringIO
import sys
if sys.version_info[1] > 5:
	from typing import TextIO
else:
	from typing.io import TextIO

def serializedATN():
    return [
        4,1,32,181,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,2,6,7,
        6,2,7,7,7,2,8,7,8,2,9,7,9,2,10,7,10,2,11,7,11,2,12,7,12,2,13,7,13,
        2,14,7,14,2,15,7,15,2,16,7,16,2,17,7,17,2,18,7,18,2,19,7,19,2,20,
        7,20,2,21,7,21,2,22,7,22,2,23,7,23,2,24,7,24,1,0,1,0,1,0,5,0,54,
        8,0,10,0,12,0,57,9,0,1,0,1,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,3,1,68,
        8,1,1,2,3,2,71,8,2,1,3,1,3,1,3,1,3,1,4,1,4,3,4,79,8,4,1,5,1,5,3,
        5,83,8,5,1,6,1,6,1,7,1,7,1,8,1,8,1,8,4,8,92,8,8,11,8,12,8,93,1,9,
        1,9,1,9,1,9,1,9,1,9,1,9,3,9,103,8,9,1,10,1,10,1,11,1,11,1,12,1,12,
        1,13,1,13,1,14,1,14,1,15,1,15,3,15,117,8,15,1,15,1,15,1,15,1,16,
        1,16,1,16,1,16,1,16,1,16,1,16,1,16,1,16,1,16,1,16,3,16,133,8,16,
        3,16,135,8,16,1,17,3,17,138,8,17,1,17,5,17,141,8,17,10,17,12,17,
        144,9,17,1,18,1,18,3,18,148,8,18,5,18,150,8,18,10,18,12,18,153,9,
        18,1,19,1,19,3,19,157,8,19,1,20,1,20,1,20,1,20,1,21,1,21,1,21,1,
        21,1,22,3,22,168,8,22,1,23,1,23,1,23,1,23,1,23,3,23,175,8,23,1,24,
        1,24,1,24,1,24,1,24,0,0,25,0,2,4,6,8,10,12,14,16,18,20,22,24,26,
        28,30,32,34,36,38,40,42,44,46,48,0,5,1,0,11,12,2,0,11,12,17,18,1,
        0,22,25,1,0,19,21,1,0,26,29,178,0,50,1,0,0,0,2,67,1,0,0,0,4,70,1,
        0,0,0,6,72,1,0,0,0,8,78,1,0,0,0,10,82,1,0,0,0,12,84,1,0,0,0,14,86,
        1,0,0,0,16,88,1,0,0,0,18,102,1,0,0,0,20,104,1,0,0,0,22,106,1,0,0,
        0,24,108,1,0,0,0,26,110,1,0,0,0,28,112,1,0,0,0,30,114,1,0,0,0,32,
        134,1,0,0,0,34,142,1,0,0,0,36,151,1,0,0,0,38,156,1,0,0,0,40,158,
        1,0,0,0,42,162,1,0,0,0,44,167,1,0,0,0,46,169,1,0,0,0,48,176,1,0,
        0,0,50,55,3,2,1,0,51,52,5,2,0,0,52,54,3,2,1,0,53,51,1,0,0,0,54,57,
        1,0,0,0,55,53,1,0,0,0,55,56,1,0,0,0,56,58,1,0,0,0,57,55,1,0,0,0,
        58,59,5,0,0,1,59,1,1,0,0,0,60,61,3,6,3,0,61,62,3,4,2,0,62,68,1,0,
        0,0,63,64,3,38,19,0,64,65,3,4,2,0,65,68,1,0,0,0,66,68,3,4,2,0,67,
        60,1,0,0,0,67,63,1,0,0,0,67,66,1,0,0,0,68,3,1,0,0,0,69,71,5,3,0,
        0,70,69,1,0,0,0,70,71,1,0,0,0,71,5,1,0,0,0,72,73,3,8,4,0,73,74,5,
        8,0,0,74,75,3,18,9,0,75,7,1,0,0,0,76,79,3,10,5,0,77,79,3,16,8,0,
        78,76,1,0,0,0,78,77,1,0,0,0,79,9,1,0,0,0,80,83,3,14,7,0,81,83,3,
        12,6,0,82,80,1,0,0,0,82,81,1,0,0,0,83,11,1,0,0,0,84,85,5,13,0,0,
        85,13,1,0,0,0,86,87,7,0,0,0,87,15,1,0,0,0,88,91,3,10,5,0,89,90,5,
        9,0,0,90,92,3,10,5,0,91,89,1,0,0,0,92,93,1,0,0,0,93,91,1,0,0,0,93,
        94,1,0,0,0,94,17,1,0,0,0,95,103,3,20,10,0,96,103,3,22,11,0,97,103,
        3,24,12,0,98,103,3,26,13,0,99,103,3,28,14,0,100,103,3,30,15,0,101,
        103,3,42,21,0,102,95,1,0,0,0,102,96,1,0,0,0,102,97,1,0,0,0,102,98,
        1,0,0,0,102,99,1,0,0,0,102,100,1,0,0,0,102,101,1,0,0,0,103,19,1,
        0,0,0,104,105,7,1,0,0,105,21,1,0,0,0,106,107,7,2,0,0,107,23,1,0,
        0,0,108,109,7,3,0,0,109,25,1,0,0,0,110,111,5,16,0,0,111,27,1,0,0,
        0,112,113,7,4,0,0,113,29,1,0,0,0,114,116,5,4,0,0,115,117,3,32,16,
        0,116,115,1,0,0,0,116,117,1,0,0,0,117,118,1,0,0,0,118,119,3,34,17,
        0,119,120,5,6,0,0,120,31,1,0,0,0,121,122,3,34,17,0,122,123,3,18,
        9,0,123,124,3,36,18,0,124,125,5,10,0,0,125,126,3,32,16,0,126,127,
        3,34,17,0,127,135,1,0,0,0,128,129,3,34,17,0,129,130,3,18,9,0,130,
        132,3,36,18,0,131,133,5,10,0,0,132,131,1,0,0,0,132,133,1,0,0,0,133,
        135,1,0,0,0,134,121,1,0,0,0,134,128,1,0,0,0,135,33,1,0,0,0,136,138,
        5,3,0,0,137,136,1,0,0,0,137,138,1,0,0,0,138,139,1,0,0,0,139,141,
        5,2,0,0,140,137,1,0,0,0,141,144,1,0,0,0,142,140,1,0,0,0,142,143,
        1,0,0,0,143,35,1,0,0,0,144,142,1,0,0,0,145,147,5,2,0,0,146,148,5,
        3,0,0,147,146,1,0,0,0,147,148,1,0,0,0,148,150,1,0,0,0,149,145,1,
        0,0,0,150,153,1,0,0,0,151,149,1,0,0,0,151,152,1,0,0,0,152,37,1,0,
        0,0,153,151,1,0,0,0,154,157,3,40,20,0,155,157,3,48,24,0,156,154,
        1,0,0,0,156,155,1,0,0,0,157,39,1,0,0,0,158,159,5,4,0,0,159,160,3,
        8,4,0,160,161,5,6,0,0,161,41,1,0,0,0,162,163,5,15,0,0,163,164,3,
        44,22,0,164,165,5,31,0,0,165,43,1,0,0,0,166,168,3,46,23,0,167,166,
        1,0,0,0,167,168,1,0,0,0,168,45,1,0,0,0,169,170,3,8,4,0,170,171,5,
        8,0,0,171,174,3,18,9,0,172,173,5,10,0,0,173,175,3,46,23,0,174,172,
        1,0,0,0,174,175,1,0,0,0,175,47,1,0,0,0,176,177,5,5,0,0,177,178,3,
        8,4,0,178,179,5,7,0,0,179,49,1,0,0,0,17,55,67,70,78,82,93,102,116,
        132,134,137,142,147,151,156,167,174
    ]

class TomlParser ( Parser ):

    grammarFileName = "TomlParser.g4"

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    sharedContextCache = PredictionContextCache()

    literalNames = [ "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                     "'['", "'[['", "']'", "']]'", "'='", "'.'", "','", 
                     "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                     "'{'", "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                     "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                     "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                     "<INVALID>", "<INVALID>", "<INVALID>", "'}'" ]

    symbolicNames = [ "<INVALID>", "WS", "NL", "COMMENT", "L_BRACKET", "DOUBLE_L_BRACKET", 
                      "R_BRACKET", "DOUBLE_R_BRACKET", "EQUALS", "DOT", 
                      "COMMA", "BASIC_STRING", "LITERAL_STRING", "UNQUOTED_KEY", 
                      "VALUE_WS", "L_BRACE", "BOOLEAN", "ML_BASIC_STRING", 
                      "ML_LITERAL_STRING", "FLOAT", "INF", "NAN", "DEC_INT", 
                      "HEX_INT", "OCT_INT", "BIN_INT", "OFFSET_DATE_TIME", 
                      "LOCAL_DATE_TIME", "LOCAL_DATE", "LOCAL_TIME", "INLINE_TABLE_WS", 
                      "R_BRACE", "ARRAY_WS" ]

    RULE_document = 0
    RULE_expression = 1
    RULE_comment = 2
    RULE_key_value = 3
    RULE_key = 4
    RULE_simple_key = 5
    RULE_unquoted_key = 6
    RULE_quoted_key = 7
    RULE_dotted_key = 8
    RULE_value = 9
    RULE_string = 10
    RULE_integer = 11
    RULE_floating_point = 12
    RULE_bool_ = 13
    RULE_date_time = 14
    RULE_array_ = 15
    RULE_array_values = 16
    RULE_comment_or_nl = 17
    RULE_nl_or_comment = 18
    RULE_table = 19
    RULE_standard_table = 20
    RULE_inline_table = 21
    RULE_inline_table_keyvals = 22
    RULE_inline_table_keyvals_non_empty = 23
    RULE_array_table = 24

    ruleNames =  [ "document", "expression", "comment", "key_value", "key", 
                   "simple_key", "unquoted_key", "quoted_key", "dotted_key", 
                   "value", "string", "integer", "floating_point", "bool_", 
                   "date_time", "array_", "array_values", "comment_or_nl", 
                   "nl_or_comment", "table", "standard_table", "inline_table", 
                   "inline_table_keyvals", "inline_table_keyvals_non_empty", 
                   "array_table" ]

    EOF = Token.EOF
    WS=1
    NL=2
    COMMENT=3
    L_BRACKET=4
    DOUBLE_L_BRACKET=5
    R_BRACKET=6
    DOUBLE_R_BRACKET=7
    EQUALS=8
    DOT=9
    COMMA=10
    BASIC_STRING=11
    LITERAL_STRING=12
    UNQUOTED_KEY=13
    VALUE_WS=14
    L_BRACE=15
    BOOLEAN=16
    ML_BASIC_STRING=17
    ML_LITERAL_STRING=18
    FLOAT=19
    INF=20
    NAN=21
    DEC_INT=22
    HEX_INT=23
    OCT_INT=24
    BIN_INT=25
    OFFSET_DATE_TIME=26
    LOCAL_DATE_TIME=27
    LOCAL_DATE=28
    LOCAL_TIME=29
    INLINE_TABLE_WS=30
    R_BRACE=31
    ARRAY_WS=32

    def __init__(self, input:TokenStream, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.13.2")
        self._interp = ParserATNSimulator(self, self.atn, self.decisionsToDFA, self.sharedContextCache)
        self._predicates = None




    class DocumentContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def expression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(TomlParser.ExpressionContext)
            else:
                return self.getTypedRuleContext(TomlParser.ExpressionContext,i)


        def EOF(self):
            return self.getToken(TomlParser.EOF, 0)

        def NL(self, i:int=None):
            if i is None:
                return self.getTokens(TomlParser.NL)
            else:
                return self.getToken(TomlParser.NL, i)

        def getRuleIndex(self):
            return TomlParser.RULE_document

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterDocument" ):
                listener.enterDocument(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitDocument" ):
                listener.exitDocument(self)




    def document(self):

        localctx = TomlParser.DocumentContext(self, self._ctx, self.state)
        self.enterRule(localctx, 0, self.RULE_document)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 50
            self.expression()
            self.state = 55
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==2:
                self.state = 51
                self.match(TomlParser.NL)
                self.state = 52
                self.expression()
                self.state = 57
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 58
            self.match(TomlParser.EOF)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def key_value(self):
            return self.getTypedRuleContext(TomlParser.Key_valueContext,0)


        def comment(self):
            return self.getTypedRuleContext(TomlParser.CommentContext,0)


        def table(self):
            return self.getTypedRuleContext(TomlParser.TableContext,0)


        def getRuleIndex(self):
            return TomlParser.RULE_expression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterExpression" ):
                listener.enterExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitExpression" ):
                listener.exitExpression(self)




    def expression(self):

        localctx = TomlParser.ExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 2, self.RULE_expression)
        try:
            self.state = 67
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [11, 12, 13]:
                self.enterOuterAlt(localctx, 1)
                self.state = 60
                self.key_value()
                self.state = 61
                self.comment()
                pass
            elif token in [4, 5]:
                self.enterOuterAlt(localctx, 2)
                self.state = 63
                self.table()
                self.state = 64
                self.comment()
                pass
            elif token in [-1, 2, 3]:
                self.enterOuterAlt(localctx, 3)
                self.state = 66
                self.comment()
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class CommentContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def COMMENT(self):
            return self.getToken(TomlParser.COMMENT, 0)

        def getRuleIndex(self):
            return TomlParser.RULE_comment

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterComment" ):
                listener.enterComment(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitComment" ):
                listener.exitComment(self)




    def comment(self):

        localctx = TomlParser.CommentContext(self, self._ctx, self.state)
        self.enterRule(localctx, 4, self.RULE_comment)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 70
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==3:
                self.state = 69
                self.match(TomlParser.COMMENT)


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Key_valueContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def key(self):
            return self.getTypedRuleContext(TomlParser.KeyContext,0)


        def EQUALS(self):
            return self.getToken(TomlParser.EQUALS, 0)

        def value(self):
            return self.getTypedRuleContext(TomlParser.ValueContext,0)


        def getRuleIndex(self):
            return TomlParser.RULE_key_value

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterKey_value" ):
                listener.enterKey_value(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitKey_value" ):
                listener.exitKey_value(self)




    def key_value(self):

        localctx = TomlParser.Key_valueContext(self, self._ctx, self.state)
        self.enterRule(localctx, 6, self.RULE_key_value)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 72
            self.key()
            self.state = 73
            self.match(TomlParser.EQUALS)
            self.state = 74
            self.value()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class KeyContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def simple_key(self):
            return self.getTypedRuleContext(TomlParser.Simple_keyContext,0)


        def dotted_key(self):
            return self.getTypedRuleContext(TomlParser.Dotted_keyContext,0)


        def getRuleIndex(self):
            return TomlParser.RULE_key

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterKey" ):
                listener.enterKey(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitKey" ):
                listener.exitKey(self)




    def key(self):

        localctx = TomlParser.KeyContext(self, self._ctx, self.state)
        self.enterRule(localctx, 8, self.RULE_key)
        try:
            self.state = 78
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,3,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 76
                self.simple_key()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 77
                self.dotted_key()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Simple_keyContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def quoted_key(self):
            return self.getTypedRuleContext(TomlParser.Quoted_keyContext,0)


        def unquoted_key(self):
            return self.getTypedRuleContext(TomlParser.Unquoted_keyContext,0)


        def getRuleIndex(self):
            return TomlParser.RULE_simple_key

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterSimple_key" ):
                listener.enterSimple_key(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitSimple_key" ):
                listener.exitSimple_key(self)




    def simple_key(self):

        localctx = TomlParser.Simple_keyContext(self, self._ctx, self.state)
        self.enterRule(localctx, 10, self.RULE_simple_key)
        try:
            self.state = 82
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [11, 12]:
                self.enterOuterAlt(localctx, 1)
                self.state = 80
                self.quoted_key()
                pass
            elif token in [13]:
                self.enterOuterAlt(localctx, 2)
                self.state = 81
                self.unquoted_key()
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Unquoted_keyContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def UNQUOTED_KEY(self):
            return self.getToken(TomlParser.UNQUOTED_KEY, 0)

        def getRuleIndex(self):
            return TomlParser.RULE_unquoted_key

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterUnquoted_key" ):
                listener.enterUnquoted_key(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitUnquoted_key" ):
                listener.exitUnquoted_key(self)




    def unquoted_key(self):

        localctx = TomlParser.Unquoted_keyContext(self, self._ctx, self.state)
        self.enterRule(localctx, 12, self.RULE_unquoted_key)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 84
            self.match(TomlParser.UNQUOTED_KEY)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Quoted_keyContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def BASIC_STRING(self):
            return self.getToken(TomlParser.BASIC_STRING, 0)

        def LITERAL_STRING(self):
            return self.getToken(TomlParser.LITERAL_STRING, 0)

        def getRuleIndex(self):
            return TomlParser.RULE_quoted_key

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterQuoted_key" ):
                listener.enterQuoted_key(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitQuoted_key" ):
                listener.exitQuoted_key(self)




    def quoted_key(self):

        localctx = TomlParser.Quoted_keyContext(self, self._ctx, self.state)
        self.enterRule(localctx, 14, self.RULE_quoted_key)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 86
            _la = self._input.LA(1)
            if not(_la==11 or _la==12):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Dotted_keyContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def simple_key(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(TomlParser.Simple_keyContext)
            else:
                return self.getTypedRuleContext(TomlParser.Simple_keyContext,i)


        def DOT(self, i:int=None):
            if i is None:
                return self.getTokens(TomlParser.DOT)
            else:
                return self.getToken(TomlParser.DOT, i)

        def getRuleIndex(self):
            return TomlParser.RULE_dotted_key

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterDotted_key" ):
                listener.enterDotted_key(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitDotted_key" ):
                listener.exitDotted_key(self)




    def dotted_key(self):

        localctx = TomlParser.Dotted_keyContext(self, self._ctx, self.state)
        self.enterRule(localctx, 16, self.RULE_dotted_key)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 88
            self.simple_key()
            self.state = 91 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 89
                self.match(TomlParser.DOT)
                self.state = 90
                self.simple_key()
                self.state = 93 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not (_la==9):
                    break

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ValueContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def string(self):
            return self.getTypedRuleContext(TomlParser.StringContext,0)


        def integer(self):
            return self.getTypedRuleContext(TomlParser.IntegerContext,0)


        def floating_point(self):
            return self.getTypedRuleContext(TomlParser.Floating_pointContext,0)


        def bool_(self):
            return self.getTypedRuleContext(TomlParser.Bool_Context,0)


        def date_time(self):
            return self.getTypedRuleContext(TomlParser.Date_timeContext,0)


        def array_(self):
            return self.getTypedRuleContext(TomlParser.Array_Context,0)


        def inline_table(self):
            return self.getTypedRuleContext(TomlParser.Inline_tableContext,0)


        def getRuleIndex(self):
            return TomlParser.RULE_value

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterValue" ):
                listener.enterValue(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitValue" ):
                listener.exitValue(self)




    def value(self):

        localctx = TomlParser.ValueContext(self, self._ctx, self.state)
        self.enterRule(localctx, 18, self.RULE_value)
        try:
            self.state = 102
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [11, 12, 17, 18]:
                self.enterOuterAlt(localctx, 1)
                self.state = 95
                self.string()
                pass
            elif token in [22, 23, 24, 25]:
                self.enterOuterAlt(localctx, 2)
                self.state = 96
                self.integer()
                pass
            elif token in [19, 20, 21]:
                self.enterOuterAlt(localctx, 3)
                self.state = 97
                self.floating_point()
                pass
            elif token in [16]:
                self.enterOuterAlt(localctx, 4)
                self.state = 98
                self.bool_()
                pass
            elif token in [26, 27, 28, 29]:
                self.enterOuterAlt(localctx, 5)
                self.state = 99
                self.date_time()
                pass
            elif token in [4]:
                self.enterOuterAlt(localctx, 6)
                self.state = 100
                self.array_()
                pass
            elif token in [15]:
                self.enterOuterAlt(localctx, 7)
                self.state = 101
                self.inline_table()
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class StringContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def BASIC_STRING(self):
            return self.getToken(TomlParser.BASIC_STRING, 0)

        def ML_BASIC_STRING(self):
            return self.getToken(TomlParser.ML_BASIC_STRING, 0)

        def LITERAL_STRING(self):
            return self.getToken(TomlParser.LITERAL_STRING, 0)

        def ML_LITERAL_STRING(self):
            return self.getToken(TomlParser.ML_LITERAL_STRING, 0)

        def getRuleIndex(self):
            return TomlParser.RULE_string

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterString" ):
                listener.enterString(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitString" ):
                listener.exitString(self)




    def string(self):

        localctx = TomlParser.StringContext(self, self._ctx, self.state)
        self.enterRule(localctx, 20, self.RULE_string)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 104
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 399360) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class IntegerContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def DEC_INT(self):
            return self.getToken(TomlParser.DEC_INT, 0)

        def HEX_INT(self):
            return self.getToken(TomlParser.HEX_INT, 0)

        def OCT_INT(self):
            return self.getToken(TomlParser.OCT_INT, 0)

        def BIN_INT(self):
            return self.getToken(TomlParser.BIN_INT, 0)

        def getRuleIndex(self):
            return TomlParser.RULE_integer

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterInteger" ):
                listener.enterInteger(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitInteger" ):
                listener.exitInteger(self)




    def integer(self):

        localctx = TomlParser.IntegerContext(self, self._ctx, self.state)
        self.enterRule(localctx, 22, self.RULE_integer)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 106
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 62914560) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Floating_pointContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def FLOAT(self):
            return self.getToken(TomlParser.FLOAT, 0)

        def INF(self):
            return self.getToken(TomlParser.INF, 0)

        def NAN(self):
            return self.getToken(TomlParser.NAN, 0)

        def getRuleIndex(self):
            return TomlParser.RULE_floating_point

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterFloating_point" ):
                listener.enterFloating_point(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitFloating_point" ):
                listener.exitFloating_point(self)




    def floating_point(self):

        localctx = TomlParser.Floating_pointContext(self, self._ctx, self.state)
        self.enterRule(localctx, 24, self.RULE_floating_point)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 108
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 3670016) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Bool_Context(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def BOOLEAN(self):
            return self.getToken(TomlParser.BOOLEAN, 0)

        def getRuleIndex(self):
            return TomlParser.RULE_bool_

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterBool_" ):
                listener.enterBool_(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitBool_" ):
                listener.exitBool_(self)




    def bool_(self):

        localctx = TomlParser.Bool_Context(self, self._ctx, self.state)
        self.enterRule(localctx, 26, self.RULE_bool_)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 110
            self.match(TomlParser.BOOLEAN)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Date_timeContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def OFFSET_DATE_TIME(self):
            return self.getToken(TomlParser.OFFSET_DATE_TIME, 0)

        def LOCAL_DATE_TIME(self):
            return self.getToken(TomlParser.LOCAL_DATE_TIME, 0)

        def LOCAL_DATE(self):
            return self.getToken(TomlParser.LOCAL_DATE, 0)

        def LOCAL_TIME(self):
            return self.getToken(TomlParser.LOCAL_TIME, 0)

        def getRuleIndex(self):
            return TomlParser.RULE_date_time

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterDate_time" ):
                listener.enterDate_time(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitDate_time" ):
                listener.exitDate_time(self)




    def date_time(self):

        localctx = TomlParser.Date_timeContext(self, self._ctx, self.state)
        self.enterRule(localctx, 28, self.RULE_date_time)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 112
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 1006632960) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Array_Context(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def L_BRACKET(self):
            return self.getToken(TomlParser.L_BRACKET, 0)

        def comment_or_nl(self):
            return self.getTypedRuleContext(TomlParser.Comment_or_nlContext,0)


        def R_BRACKET(self):
            return self.getToken(TomlParser.R_BRACKET, 0)

        def array_values(self):
            return self.getTypedRuleContext(TomlParser.Array_valuesContext,0)


        def getRuleIndex(self):
            return TomlParser.RULE_array_

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterArray_" ):
                listener.enterArray_(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitArray_" ):
                listener.exitArray_(self)




    def array_(self):

        localctx = TomlParser.Array_Context(self, self._ctx, self.state)
        self.enterRule(localctx, 30, self.RULE_array_)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 114
            self.match(TomlParser.L_BRACKET)
            self.state = 116
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,7,self._ctx)
            if la_ == 1:
                self.state = 115
                self.array_values()


            self.state = 118
            self.comment_or_nl()
            self.state = 119
            self.match(TomlParser.R_BRACKET)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Array_valuesContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def comment_or_nl(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(TomlParser.Comment_or_nlContext)
            else:
                return self.getTypedRuleContext(TomlParser.Comment_or_nlContext,i)


        def value(self):
            return self.getTypedRuleContext(TomlParser.ValueContext,0)


        def nl_or_comment(self):
            return self.getTypedRuleContext(TomlParser.Nl_or_commentContext,0)


        def COMMA(self):
            return self.getToken(TomlParser.COMMA, 0)

        def array_values(self):
            return self.getTypedRuleContext(TomlParser.Array_valuesContext,0)


        def getRuleIndex(self):
            return TomlParser.RULE_array_values

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterArray_values" ):
                listener.enterArray_values(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitArray_values" ):
                listener.exitArray_values(self)




    def array_values(self):

        localctx = TomlParser.Array_valuesContext(self, self._ctx, self.state)
        self.enterRule(localctx, 32, self.RULE_array_values)
        self._la = 0 # Token type
        try:
            self.state = 134
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,9,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 121
                self.comment_or_nl()
                self.state = 122
                self.value()
                self.state = 123
                self.nl_or_comment()
                self.state = 124
                self.match(TomlParser.COMMA)
                self.state = 125
                self.array_values()
                self.state = 126
                self.comment_or_nl()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 128
                self.comment_or_nl()
                self.state = 129
                self.value()
                self.state = 130
                self.nl_or_comment()
                self.state = 132
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==10:
                    self.state = 131
                    self.match(TomlParser.COMMA)


                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Comment_or_nlContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def NL(self, i:int=None):
            if i is None:
                return self.getTokens(TomlParser.NL)
            else:
                return self.getToken(TomlParser.NL, i)

        def COMMENT(self, i:int=None):
            if i is None:
                return self.getTokens(TomlParser.COMMENT)
            else:
                return self.getToken(TomlParser.COMMENT, i)

        def getRuleIndex(self):
            return TomlParser.RULE_comment_or_nl

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterComment_or_nl" ):
                listener.enterComment_or_nl(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitComment_or_nl" ):
                listener.exitComment_or_nl(self)




    def comment_or_nl(self):

        localctx = TomlParser.Comment_or_nlContext(self, self._ctx, self.state)
        self.enterRule(localctx, 34, self.RULE_comment_or_nl)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 142
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,11,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 137
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)
                    if _la==3:
                        self.state = 136
                        self.match(TomlParser.COMMENT)


                    self.state = 139
                    self.match(TomlParser.NL) 
                self.state = 144
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,11,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Nl_or_commentContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def NL(self, i:int=None):
            if i is None:
                return self.getTokens(TomlParser.NL)
            else:
                return self.getToken(TomlParser.NL, i)

        def COMMENT(self, i:int=None):
            if i is None:
                return self.getTokens(TomlParser.COMMENT)
            else:
                return self.getToken(TomlParser.COMMENT, i)

        def getRuleIndex(self):
            return TomlParser.RULE_nl_or_comment

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterNl_or_comment" ):
                listener.enterNl_or_comment(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitNl_or_comment" ):
                listener.exitNl_or_comment(self)




    def nl_or_comment(self):

        localctx = TomlParser.Nl_or_commentContext(self, self._ctx, self.state)
        self.enterRule(localctx, 36, self.RULE_nl_or_comment)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 151
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,13,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 145
                    self.match(TomlParser.NL)
                    self.state = 147
                    self._errHandler.sync(self)
                    la_ = self._interp.adaptivePredict(self._input,12,self._ctx)
                    if la_ == 1:
                        self.state = 146
                        self.match(TomlParser.COMMENT)

             
                self.state = 153
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,13,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class TableContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def standard_table(self):
            return self.getTypedRuleContext(TomlParser.Standard_tableContext,0)


        def array_table(self):
            return self.getTypedRuleContext(TomlParser.Array_tableContext,0)


        def getRuleIndex(self):
            return TomlParser.RULE_table

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterTable" ):
                listener.enterTable(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitTable" ):
                listener.exitTable(self)




    def table(self):

        localctx = TomlParser.TableContext(self, self._ctx, self.state)
        self.enterRule(localctx, 38, self.RULE_table)
        try:
            self.state = 156
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [4]:
                self.enterOuterAlt(localctx, 1)
                self.state = 154
                self.standard_table()
                pass
            elif token in [5]:
                self.enterOuterAlt(localctx, 2)
                self.state = 155
                self.array_table()
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Standard_tableContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def L_BRACKET(self):
            return self.getToken(TomlParser.L_BRACKET, 0)

        def key(self):
            return self.getTypedRuleContext(TomlParser.KeyContext,0)


        def R_BRACKET(self):
            return self.getToken(TomlParser.R_BRACKET, 0)

        def getRuleIndex(self):
            return TomlParser.RULE_standard_table

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterStandard_table" ):
                listener.enterStandard_table(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitStandard_table" ):
                listener.exitStandard_table(self)




    def standard_table(self):

        localctx = TomlParser.Standard_tableContext(self, self._ctx, self.state)
        self.enterRule(localctx, 40, self.RULE_standard_table)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 158
            self.match(TomlParser.L_BRACKET)
            self.state = 159
            self.key()
            self.state = 160
            self.match(TomlParser.R_BRACKET)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Inline_tableContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def L_BRACE(self):
            return self.getToken(TomlParser.L_BRACE, 0)

        def inline_table_keyvals(self):
            return self.getTypedRuleContext(TomlParser.Inline_table_keyvalsContext,0)


        def R_BRACE(self):
            return self.getToken(TomlParser.R_BRACE, 0)

        def getRuleIndex(self):
            return TomlParser.RULE_inline_table

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterInline_table" ):
                listener.enterInline_table(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitInline_table" ):
                listener.exitInline_table(self)




    def inline_table(self):

        localctx = TomlParser.Inline_tableContext(self, self._ctx, self.state)
        self.enterRule(localctx, 42, self.RULE_inline_table)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 162
            self.match(TomlParser.L_BRACE)
            self.state = 163
            self.inline_table_keyvals()
            self.state = 164
            self.match(TomlParser.R_BRACE)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Inline_table_keyvalsContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def inline_table_keyvals_non_empty(self):
            return self.getTypedRuleContext(TomlParser.Inline_table_keyvals_non_emptyContext,0)


        def getRuleIndex(self):
            return TomlParser.RULE_inline_table_keyvals

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterInline_table_keyvals" ):
                listener.enterInline_table_keyvals(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitInline_table_keyvals" ):
                listener.exitInline_table_keyvals(self)




    def inline_table_keyvals(self):

        localctx = TomlParser.Inline_table_keyvalsContext(self, self._ctx, self.state)
        self.enterRule(localctx, 44, self.RULE_inline_table_keyvals)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 167
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if (((_la) & ~0x3f) == 0 and ((1 << _la) & 14336) != 0):
                self.state = 166
                self.inline_table_keyvals_non_empty()


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Inline_table_keyvals_non_emptyContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def key(self):
            return self.getTypedRuleContext(TomlParser.KeyContext,0)


        def EQUALS(self):
            return self.getToken(TomlParser.EQUALS, 0)

        def value(self):
            return self.getTypedRuleContext(TomlParser.ValueContext,0)


        def COMMA(self):
            return self.getToken(TomlParser.COMMA, 0)

        def inline_table_keyvals_non_empty(self):
            return self.getTypedRuleContext(TomlParser.Inline_table_keyvals_non_emptyContext,0)


        def getRuleIndex(self):
            return TomlParser.RULE_inline_table_keyvals_non_empty

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterInline_table_keyvals_non_empty" ):
                listener.enterInline_table_keyvals_non_empty(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitInline_table_keyvals_non_empty" ):
                listener.exitInline_table_keyvals_non_empty(self)




    def inline_table_keyvals_non_empty(self):

        localctx = TomlParser.Inline_table_keyvals_non_emptyContext(self, self._ctx, self.state)
        self.enterRule(localctx, 46, self.RULE_inline_table_keyvals_non_empty)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 169
            self.key()
            self.state = 170
            self.match(TomlParser.EQUALS)
            self.state = 171
            self.value()
            self.state = 174
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==10:
                self.state = 172
                self.match(TomlParser.COMMA)
                self.state = 173
                self.inline_table_keyvals_non_empty()


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Array_tableContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def DOUBLE_L_BRACKET(self):
            return self.getToken(TomlParser.DOUBLE_L_BRACKET, 0)

        def key(self):
            return self.getTypedRuleContext(TomlParser.KeyContext,0)


        def DOUBLE_R_BRACKET(self):
            return self.getToken(TomlParser.DOUBLE_R_BRACKET, 0)

        def getRuleIndex(self):
            return TomlParser.RULE_array_table

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterArray_table" ):
                listener.enterArray_table(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitArray_table" ):
                listener.exitArray_table(self)




    def array_table(self):

        localctx = TomlParser.Array_tableContext(self, self._ctx, self.state)
        self.enterRule(localctx, 48, self.RULE_array_table)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 176
            self.match(TomlParser.DOUBLE_L_BRACKET)
            self.state = 177
            self.key()
            self.state = 178
            self.match(TomlParser.DOUBLE_R_BRACKET)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx





