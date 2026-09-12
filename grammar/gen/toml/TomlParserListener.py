# Generated from /Users/kelvinackah/Desktop/projects/research/agentic_fuzzing/grammar/TomlParser.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .TomlParser import TomlParser
else:
    from TomlParser import TomlParser

# This class defines a complete listener for a parse tree produced by TomlParser.
class TomlParserListener(ParseTreeListener):

    # Enter a parse tree produced by TomlParser#document.
    def enterDocument(self, ctx:TomlParser.DocumentContext):
        pass

    # Exit a parse tree produced by TomlParser#document.
    def exitDocument(self, ctx:TomlParser.DocumentContext):
        pass


    # Enter a parse tree produced by TomlParser#expression.
    def enterExpression(self, ctx:TomlParser.ExpressionContext):
        pass

    # Exit a parse tree produced by TomlParser#expression.
    def exitExpression(self, ctx:TomlParser.ExpressionContext):
        pass


    # Enter a parse tree produced by TomlParser#comment.
    def enterComment(self, ctx:TomlParser.CommentContext):
        pass

    # Exit a parse tree produced by TomlParser#comment.
    def exitComment(self, ctx:TomlParser.CommentContext):
        pass


    # Enter a parse tree produced by TomlParser#key_value.
    def enterKey_value(self, ctx:TomlParser.Key_valueContext):
        pass

    # Exit a parse tree produced by TomlParser#key_value.
    def exitKey_value(self, ctx:TomlParser.Key_valueContext):
        pass


    # Enter a parse tree produced by TomlParser#key.
    def enterKey(self, ctx:TomlParser.KeyContext):
        pass

    # Exit a parse tree produced by TomlParser#key.
    def exitKey(self, ctx:TomlParser.KeyContext):
        pass


    # Enter a parse tree produced by TomlParser#simple_key.
    def enterSimple_key(self, ctx:TomlParser.Simple_keyContext):
        pass

    # Exit a parse tree produced by TomlParser#simple_key.
    def exitSimple_key(self, ctx:TomlParser.Simple_keyContext):
        pass


    # Enter a parse tree produced by TomlParser#unquoted_key.
    def enterUnquoted_key(self, ctx:TomlParser.Unquoted_keyContext):
        pass

    # Exit a parse tree produced by TomlParser#unquoted_key.
    def exitUnquoted_key(self, ctx:TomlParser.Unquoted_keyContext):
        pass


    # Enter a parse tree produced by TomlParser#quoted_key.
    def enterQuoted_key(self, ctx:TomlParser.Quoted_keyContext):
        pass

    # Exit a parse tree produced by TomlParser#quoted_key.
    def exitQuoted_key(self, ctx:TomlParser.Quoted_keyContext):
        pass


    # Enter a parse tree produced by TomlParser#dotted_key.
    def enterDotted_key(self, ctx:TomlParser.Dotted_keyContext):
        pass

    # Exit a parse tree produced by TomlParser#dotted_key.
    def exitDotted_key(self, ctx:TomlParser.Dotted_keyContext):
        pass


    # Enter a parse tree produced by TomlParser#value.
    def enterValue(self, ctx:TomlParser.ValueContext):
        pass

    # Exit a parse tree produced by TomlParser#value.
    def exitValue(self, ctx:TomlParser.ValueContext):
        pass


    # Enter a parse tree produced by TomlParser#string.
    def enterString(self, ctx:TomlParser.StringContext):
        pass

    # Exit a parse tree produced by TomlParser#string.
    def exitString(self, ctx:TomlParser.StringContext):
        pass


    # Enter a parse tree produced by TomlParser#integer.
    def enterInteger(self, ctx:TomlParser.IntegerContext):
        pass

    # Exit a parse tree produced by TomlParser#integer.
    def exitInteger(self, ctx:TomlParser.IntegerContext):
        pass


    # Enter a parse tree produced by TomlParser#floating_point.
    def enterFloating_point(self, ctx:TomlParser.Floating_pointContext):
        pass

    # Exit a parse tree produced by TomlParser#floating_point.
    def exitFloating_point(self, ctx:TomlParser.Floating_pointContext):
        pass


    # Enter a parse tree produced by TomlParser#bool_.
    def enterBool_(self, ctx:TomlParser.Bool_Context):
        pass

    # Exit a parse tree produced by TomlParser#bool_.
    def exitBool_(self, ctx:TomlParser.Bool_Context):
        pass


    # Enter a parse tree produced by TomlParser#date_time.
    def enterDate_time(self, ctx:TomlParser.Date_timeContext):
        pass

    # Exit a parse tree produced by TomlParser#date_time.
    def exitDate_time(self, ctx:TomlParser.Date_timeContext):
        pass


    # Enter a parse tree produced by TomlParser#array_.
    def enterArray_(self, ctx:TomlParser.Array_Context):
        pass

    # Exit a parse tree produced by TomlParser#array_.
    def exitArray_(self, ctx:TomlParser.Array_Context):
        pass


    # Enter a parse tree produced by TomlParser#array_values.
    def enterArray_values(self, ctx:TomlParser.Array_valuesContext):
        pass

    # Exit a parse tree produced by TomlParser#array_values.
    def exitArray_values(self, ctx:TomlParser.Array_valuesContext):
        pass


    # Enter a parse tree produced by TomlParser#comment_or_nl.
    def enterComment_or_nl(self, ctx:TomlParser.Comment_or_nlContext):
        pass

    # Exit a parse tree produced by TomlParser#comment_or_nl.
    def exitComment_or_nl(self, ctx:TomlParser.Comment_or_nlContext):
        pass


    # Enter a parse tree produced by TomlParser#nl_or_comment.
    def enterNl_or_comment(self, ctx:TomlParser.Nl_or_commentContext):
        pass

    # Exit a parse tree produced by TomlParser#nl_or_comment.
    def exitNl_or_comment(self, ctx:TomlParser.Nl_or_commentContext):
        pass


    # Enter a parse tree produced by TomlParser#table.
    def enterTable(self, ctx:TomlParser.TableContext):
        pass

    # Exit a parse tree produced by TomlParser#table.
    def exitTable(self, ctx:TomlParser.TableContext):
        pass


    # Enter a parse tree produced by TomlParser#standard_table.
    def enterStandard_table(self, ctx:TomlParser.Standard_tableContext):
        pass

    # Exit a parse tree produced by TomlParser#standard_table.
    def exitStandard_table(self, ctx:TomlParser.Standard_tableContext):
        pass


    # Enter a parse tree produced by TomlParser#inline_table.
    def enterInline_table(self, ctx:TomlParser.Inline_tableContext):
        pass

    # Exit a parse tree produced by TomlParser#inline_table.
    def exitInline_table(self, ctx:TomlParser.Inline_tableContext):
        pass


    # Enter a parse tree produced by TomlParser#inline_table_keyvals.
    def enterInline_table_keyvals(self, ctx:TomlParser.Inline_table_keyvalsContext):
        pass

    # Exit a parse tree produced by TomlParser#inline_table_keyvals.
    def exitInline_table_keyvals(self, ctx:TomlParser.Inline_table_keyvalsContext):
        pass


    # Enter a parse tree produced by TomlParser#inline_table_keyvals_non_empty.
    def enterInline_table_keyvals_non_empty(self, ctx:TomlParser.Inline_table_keyvals_non_emptyContext):
        pass

    # Exit a parse tree produced by TomlParser#inline_table_keyvals_non_empty.
    def exitInline_table_keyvals_non_empty(self, ctx:TomlParser.Inline_table_keyvals_non_emptyContext):
        pass


    # Enter a parse tree produced by TomlParser#array_table.
    def enterArray_table(self, ctx:TomlParser.Array_tableContext):
        pass

    # Exit a parse tree produced by TomlParser#array_table.
    def exitArray_table(self, ctx:TomlParser.Array_tableContext):
        pass



del TomlParser