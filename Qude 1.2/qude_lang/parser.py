from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Union
from .lexer import Token, Lexer
import re

# AST Nodes
@dataclass
class Program:
    statements: List['Stmt']

class Stmt: ...

@dataclass
class StartStmt(Stmt):
    token: Token

@dataclass
class StopStmt(Stmt):
    token: Token

@dataclass
class ConsoleWrite(Stmt):
    expr: 'Expr'

@dataclass
class InputStmt(Stmt):
    prompt: 'Expr'

@dataclass
class Assign(Stmt):
    name: str
    expr: 'Expr'

@dataclass
class MathStmt(Stmt):
    expr: 'Expr'

@dataclass
class WindowOpen(Stmt):
    token: Token

@dataclass
class WindowTitle(Stmt):
    title: 'Expr'

@dataclass
class WindowSize(Stmt):
    width: 'Expr'
    height: 'Expr'

@dataclass
class WindowResizable(Stmt):
    value: 'Expr'

@dataclass
class WindowFullscreen(Stmt):
    value: 'Expr'

@dataclass
class WindowBg(Stmt):
    color: 'Expr'

@dataclass
class InsertText(Stmt):
    text: 'Expr'
    name: str

@dataclass
class InsertButton(Stmt):
    name: str

@dataclass
class InsertInput(Stmt):
    name: str

@dataclass
class WidgetText(Stmt):
    name: str
    value: 'Expr'

@dataclass
class WidgetTextColor(Stmt):
    name: str
    value: 'Expr'

@dataclass
class WidgetBgColor(Stmt):
    name: str
    value: 'Expr'

@dataclass
class WidgetFontFamily(Stmt):
    name: str
    value: 'Expr'

@dataclass
class WidgetFontSize(Stmt):
    name: str
    value: 'Expr'

@dataclass
class WidgetSize(Stmt):
    name: str
    width: 'Expr'
    height: 'Expr'

@dataclass
class WidgetPos(Stmt):
    name: str
    x: 'Expr'
    y: 'Expr'

@dataclass
class EventBlock(Stmt):
    header: str
    action: 'Stmt'

# Expressions
class Expr: ...

@dataclass
class StringLit(Expr):
    value: str

@dataclass
class NumberLit(Expr):
    value: float

@dataclass
class VarRef(Expr):
    name: str

@dataclass
class Binary(Expr):
    left: Expr
    op: str
    right: Expr


class Parser:
    def __init__(self, code: str) -> None:
        self.tokens: List[Token] = Lexer(code).tokenize()
        self.i = 0

    def parse(self) -> Program:
        stmts: List[Stmt] = []
        while not self._peek_kind("EOF"):
            if self._peek_kind("EOL"):
                self._advance()
                continue
            stmts.append(self._parse_statement())
        return Program(stmts)

    # Statement parsing is line-oriented and uses regex matching on the raw text per line for MVP
    def _parse_statement(self) -> Stmt:
        # For simplicity, reconstruct the remainder of the line from tokens until EOL
        line_tokens: List[Token] = []
        while not self._peek_kind("EOL") and not self._peek_kind("EOF"):
            line_tokens.append(self._advance())
        # consume EOL if present
        if self._peek_kind("EOL"):
            self._advance()
        text = "".join(t.text for t in line_tokens).strip()

        # Start/Stop
        if text in ("Qude.prompt", "qude.str()", "q>"):
            return StartStmt(line_tokens[0] if line_tokens else Token("KW","Qude.prompt",1,1))
        if text in ("Qude.kill/", "qude.end", "q<"):
            return StopStmt(line_tokens[0] if line_tokens else Token("KW","Qude.kill/",1,1))

        # Console write: Qonsol.write('...') | qonsol.write | qons.wrt
        m = re.match(r"^(?:Qonsol\.write|qonsol\.write|qons\.wrt)\((.*)\)$", text)
        if m:
            return ConsoleWrite(self._parse_expr_from_text(m.group(1)))

        # Input: taQe.putt('> ') | tq.put | q£
        m = re.match(r"^(?:taQe\.putt|tq\.put|q£)\((.*)\)$", text)
        if m:
            return InputStmt(self._parse_expr_from_text(m.group(1)))

        # Assign: Qurr x = expr | qrr | q$
        m = re.match(r"^(?:Qurr|qrr|q\$)\s+(\w+)\s*=\s*(.+)$", text)
        if m:
            return Assign(m.group(1), self._parse_expr_from_text(m.group(2)))

        # Math: matq(expr) | m;(expr)
        m = re.match(r"^(?:matq|m;)\((.*)\)$", text)
        if m:
            return MathStmt(self._parse_expr_from_text(m.group(1)))

        # Window open
        if text in ("Qwindow.qoll()", "qwd.qll()", "qwww()"):
            return WindowOpen(Token("IDENT","Qwindow.qoll",1,1))

        # Window title
        m = re.match(r"^(?:Qwindow\.uptext|qwd\.uptxt|qw\.utxt)\((.*)\)$", text)
        if m:
            return WindowTitle(self._parse_expr_from_text(m.group(1)))

        # Window size
        m = re.match(r"^(?:Qwindow\.geometry\.size|qwd\.geom\.sz|qw\.ge\.sz)\((.*)\)$", text)
        if m:
            args = self._split_args(m.group(1))
            if len(args) != 2:
                raise SyntaxError("geometry.size expects 2 args")
            return WindowSize(self._parse_expr_from_text(args[0]), self._parse_expr_from_text(args[1]))

        # Window resizable
        m = re.match(r"^(?:Qwindow\.resizable|qwd\.reszbl|qw\.resz)\s*=\s*(.*)$", text)
        if m:
            return WindowResizable(self._parse_expr_from_text(m.group(1)))

        # Window fullscreen
        m = re.match(r"^(?:Qwindow\.fullscreen|qwd\.fullsc|qw\.fls)\s*=\s*(.*)$", text)
        if m:
            return WindowFullscreen(self._parse_expr_from_text(m.group(1)))

        # Window background color
        m = re.match(r"^(?:Qwindow\.background\.color|qwd\.bg\.clr|qw\.bgc)\((.*)\)$", text)
        if m:
            return WindowBg(self._parse_expr_from_text(m.group(1)))

        # Insert text: insert.text('...') as name
        m = re.match(r"^(?:insert\.text|ins\.txt|i\.tx)\((.*)\)\s+as\s+(\w+)$", text)
        if m:
            return InsertText(self._parse_expr_from_text(m.group(1)), m.group(2))

        # Insert button: insert.button() as name
        m = re.match(r"^(?:insert\.button|ins\.btn|i\.bt)\(\)\s+as\s+(\w+)$", text)
        if m:
            return InsertButton(m.group(1))

        # Insert input: insert.inputter() as name
        m = re.match(r"^(?:insert\.inputter)\(\)\s+as\s+(\w+)$", text)
        if m:
            return InsertInput(m.group(1))

        # Widget ops
        m = re.match(r"^(\w+)\.(?:text|txt|tx)\((.*)\)$", text)
        if m:
            return WidgetText(m.group(1), self._parse_expr_from_text(m.group(2)))
        m = re.match(r"^(\w+)\.(?:text\.color|txt\.clr|t\$)\((.*)\)$", text)
        if m:
            return WidgetTextColor(m.group(1), self._parse_expr_from_text(m.group(2)))
        m = re.match(r"^(\w+)\.(?:background\.color|bg\.clr|bgc)\((.*)\)$", text)
        if m:
            return WidgetBgColor(m.group(1), self._parse_expr_from_text(m.group(2)))
        m = re.match(r"^(\w+)\.(?:font\.font|fnt\.font|ffnt)\((.*)\)$", text)
        if m:
            return WidgetFontFamily(m.group(1), self._parse_expr_from_text(m.group(2)))
        m = re.match(r"^(\w+)\.(?:size|font\.size|fnt\.sz|fsz)\s*=\s*(.*)$", text)
        if m:
            return WidgetFontSize(m.group(1), self._parse_expr_from_text(m.group(2)))
        m = re.match(r"^(\w+)\.(?:geometry\.size|geom\.sz|ge\.sz)\((.*)\)$", text)
        if m:
            args = self._split_args(m.group(2))
            if len(args) != 2:
                raise SyntaxError("geometry.size expects 2 args")
            return WidgetSize(m.group(1), self._parse_expr_from_text(args[0]), self._parse_expr_from_text(args[1]))
        m = re.match(r"^(\w+)\.(?:cordinates|cordint|c\$)\((.*)\)$", text)
        if m:
            args = self._split_args(m.group(2))
            if len(args) != 2:
                raise SyntaxError("cordinates expects 2 args")
            return WidgetPos(m.group(1), self._parse_expr_from_text(args[0]), self._parse_expr_from_text(args[1]))

        # Event block (MVP: header on this line; next non-empty line is single action)
        if text == "event;":
            # Gather next two logical lines from token stream (already consumed EOL)
            header = self._gather_next_line_text()
            action = self._parse_statement()  # parse action as a normal statement
            return EventBlock(header, action)

        # Fallback: unknown
        raise SyntaxError(f"Unrecognized syntax: {text}")

    def _gather_next_line_text(self) -> str:
        parts: List[str] = []
        while not self._peek_kind("EOL") and not self._peek_kind("EOF"):
            parts.append(self._advance().text)
        if self._peek_kind("EOL"):
            self._advance()
        return "".join(parts).strip()

    def _split_args(self, s: str) -> List[str]:
        parts: List[str] = []
        cur = ""
        depth = 0
        in_str = False
        quote = ''
        for ch in s:
            if in_str:
                cur += ch
                if ch == quote:
                    in_str = False
                continue
            if ch in ("'", '"'):
                in_str = True
                quote = ch
                cur += ch
                continue
            if ch == '(':
                depth += 1
                cur += ch
                continue
            if ch == ')':
                depth -= 1
                cur += ch
                continue
            if ch == ',' and depth == 0:
                parts.append(cur.strip())
                cur = ""
                continue
            cur += ch
        if cur.strip():
            parts.append(cur.strip())
        return parts

    def _parse_expr_from_text(self, text: str) -> Expr:
        text = text.strip()
        # string literal
        if (len(text) >= 2 and ((text[0] == "'" and text[-1] == "'") or (text[0] == '"' and text[-1] == '"'))):
            return StringLit(text[1:-1])
        # number
        if re.fullmatch(r"\d+(?:\.\d+)?", text):
            return NumberLit(float(text))
        # simple binary ops + - * /
        for op in ['+','-','*','/']:
            # split only on first outermost occurrence (no parentheses handling for MVP)
            idx = self._find_top_level_op(text, op)
            if idx != -1:
                left = text[:idx].strip()
                right = text[idx+1:].strip()
                return Binary(self._parse_expr_from_text(left), op, self._parse_expr_from_text(right))
        # variable
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", text):
            return VarRef(text)
        # fallback: treat as string
        return StringLit(text)

    def _find_top_level_op(self, s: str, op: str) -> int:
        depth = 0
        in_str = False
        quote = ''
        for i,ch in enumerate(s):
            if in_str:
                if ch == quote:
                    in_str = False
                continue
            if ch in ("'", '"'):
                in_str = True
                quote = ch
                continue
            if ch == '(':
                depth += 1
                continue
            if ch == ')':
                depth -= 1
                continue
            if depth == 0 and ch == op:
                return i
        return -1
