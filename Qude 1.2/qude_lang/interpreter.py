from __future__ import annotations
import re
import tkinter as tk
from tkinter import simpledialog
from tkinter import font as tkfont
from typing import Any, Dict, Optional, Tuple
from .parser import (
    Program, StartStmt, StopStmt, ConsoleWrite, InputStmt, Assign, MathStmt,
    WindowOpen, WindowTitle, WindowSize, WindowResizable, WindowFullscreen, WindowBg,
    InsertText, InsertButton, InsertInput,
    WidgetText, WidgetTextColor, WidgetBgColor, WidgetFontFamily, WidgetFontSize,
    WidgetSize, WidgetPos, EventBlock,
    StringLit, NumberLit, VarRef, Binary, Expr, Stmt,
)

class QudeAstInterpreter:
    def __init__(self, console_write, ide_root: tk.Tk) -> None:
        self.console_write = console_write
        self.ide_root = ide_root
        self.window: Optional[tk.Toplevel] = None
        self.widgets: Dict[str, tk.Widget] = {}
        self.widget_fonts: Dict[str, tkfont.Font] = {}
        self.widget_sizes: Dict[str, Tuple[int, int]] = {}
        self.vars: Dict[str, Any] = {}
        self.running = False

    def run(self, program: Program) -> None:
        for stmt in program.statements:
            self._exec_stmt(stmt)

    def _exec_stmt(self, stmt: Stmt) -> None:
        if isinstance(stmt, StartStmt):
            self.running = True
            return
        if isinstance(stmt, StopStmt):
            self.running = False
            return
        if not self.running:
            return

        if isinstance(stmt, ConsoleWrite):
            self.console_write(str(self._eval(stmt.expr)))
            return
        if isinstance(stmt, InputStmt):
            prompt = str(self._eval(stmt.prompt))
            parent = self.window if self.window is not None else self.ide_root
            ans = simpledialog.askstring("Qude Input", prompt, parent=parent)
            self.vars['data'] = ans if ans is not None else ''
            return
        if isinstance(stmt, Assign):
            self.vars[stmt.name] = self._eval(stmt.expr)
            return
        if isinstance(stmt, MathStmt):
            self.console_write(str(self._eval(stmt.expr)))
            return
        if isinstance(stmt, WindowOpen):
            self._ensure_window()
            return
        if isinstance(stmt, WindowTitle):
            self._ensure_window()
            if self.window is not None:
                try:
                    self.window.title(str(self._eval(stmt.title)))
                except Exception:
                    pass
            return
        if isinstance(stmt, WindowSize):
            self._ensure_window()
            w = int(self._eval(stmt.width))
            h = int(self._eval(stmt.height))
            if self.window is not None:
                try:
                    self.window.geometry(f"{w}x{h}")
                except Exception:
                    pass
            return
        if isinstance(stmt, WindowResizable):
            self._ensure_window()
            val = bool(self._truthy(self._eval(stmt.value)))
            if self.window is not None:
                try:
                    self.window.resizable(val, val)
                except Exception:
                    pass
            return
        if isinstance(stmt, WindowFullscreen):
            self._ensure_window()
            val = bool(self._truthy(self._eval(stmt.value)))
            if self.window is not None:
                try:
                    self.window.attributes("-fullscreen", val)
                except Exception:
                    pass
            return
        if isinstance(stmt, WindowBg):
            self._ensure_window()
            if self.window is not None:
                try:
                    self.window.configure(bg=str(self._eval(stmt.color)))
                except Exception:
                    pass
            return
        if isinstance(stmt, InsertText):
            self._ensure_window()
            lbl = tk.Label(self.window, text=str(self._eval(stmt.text)))
            lbl.place(x=0, y=0)
            self.widgets[stmt.name] = lbl
            self.widget_fonts[stmt.name] = tkfont.Font(family='TkDefaultFont', size=12)
            lbl.configure(font=self.widget_fonts[stmt.name])
            return
        if isinstance(stmt, InsertButton):
            self._ensure_window()
            btn = tk.Button(self.window, text="button")
            btn.place(x=0, y=0)
            self.widgets[stmt.name] = btn
            self.widget_fonts[stmt.name] = tkfont.Font(family='TkDefaultFont', size=12)
            btn.configure(font=self.widget_fonts[stmt.name])
            return
        if isinstance(stmt, InsertInput):
            self._ensure_window()
            ent = tk.Entry(self.window)
            ent.place(x=0, y=0)
            self.widgets[stmt.name] = ent
            self.widget_fonts[stmt.name] = tkfont.Font(family='TkDefaultFont', size=12)
            ent.configure(font=self.widget_fonts[stmt.name])
            return
        if isinstance(stmt, WidgetText):
            w = self.widgets.get(stmt.name)
            if w and isinstance(w, (tk.Button, tk.Label)):
                try:
                    w.configure(text=str(self._eval(stmt.value)))
                except Exception:
                    pass
            return
        if isinstance(stmt, WidgetTextColor):
            w = self.widgets.get(stmt.name)
            if w:
                try:
                    w.configure(fg=str(self._eval(stmt.value)))
                except Exception:
                    pass
            return
        if isinstance(stmt, WidgetBgColor):
            w = self.widgets.get(stmt.name)
            if w:
                try:
                    w.configure(bg=str(self._eval(stmt.value)))
                except Exception:
                    pass
            return
        if isinstance(stmt, WidgetFontFamily):
            if stmt.name in self.widget_fonts:
                f = self.widget_fonts[stmt.name]
                try:
                    f.configure(family=str(self._eval(stmt.value)))
                    self.widgets[stmt.name].configure(font=f)
                except Exception:
                    pass
            return
        if isinstance(stmt, WidgetFontSize):
            if stmt.name in self.widget_fonts:
                f = self.widget_fonts[stmt.name]
                try:
                    f.configure(size=int(self._eval(stmt.value)))
                    self.widgets[stmt.name].configure(font=f)
                except Exception:
                    pass
            return
        if isinstance(stmt, WidgetSize):
            w = self.widgets.get(stmt.name)
            if w:
                width = int(self._eval(stmt.width))
                height = int(self._eval(stmt.height))
                self.widget_sizes[stmt.name] = (width, height)
                info = w.place_info()
                x = int(info.get('x', 0) or 0)
                y = int(info.get('y', 0) or 0)
                try:
                    w.place(x=x, y=y, width=width, height=height)
                except Exception:
                    pass
            return
        if isinstance(stmt, WidgetPos):
            w = self.widgets.get(stmt.name)
            if w:
                x = int(self._eval(stmt.x))
                y = int(self._eval(stmt.y))
                size = self.widget_sizes.get(stmt.name, (None, None))
                try:
                    if size[0] is None:
                        w.place(x=x, y=y)
                    else:
                        w.place(x=x, y=y, width=size[0], height=size[1])
                except Exception:
                    pass
            return
        if isinstance(stmt, EventBlock):
            self._register_event(stmt.header, stmt.action)
            return

    def _register_event(self, header: str, action: Stmt) -> None:
        # <option>LeftClickEvent:
        m_opt = re.match(r"\s*<([^>]+)>(LeftClickEvent|RightClickEvent):\s*$", header)
        if m_opt:
            # Option-based events are not implemented in MVP engine
            self.console_write("[Warn] Warn option events not yet supported in new engine")
            return
        # name.MatchEvent == 'text':
        m_match = re.match(r"\s*(\w+)\.MatchEvent\s*==\s*(.+):\s*$", header)
        if m_match:
            name = m_match.group(1)
            expected = self._eval_text_expr(m_match.group(2))
            w = self.widgets.get(name)
            if not w or not isinstance(w, tk.Entry):
                self.console_write(f"[Error] MatchEvent requires inputter widget: {name}")
                return
            def on_change(_e=None):
                try:
                    if w.get() == str(expected):
                        self._exec_stmt(action)
                except Exception as ex:
                    self.console_write(f"[Error] Event: {ex}")
            w.bind('<KeyRelease>', lambda e: on_change(e), add='+')
            return
        # name.LeftClickEvent:
        m = re.match(r"\s*(\w+)\.(LeftClickEvent|RightClickEvent):\s*$", header)
        if not m:
            self.console_write('[Error] Bad event header')
            return
        name = m.group(1)
        evt = m.group(2)
        w = self.widgets.get(name)
        if not w:
            self.console_write(f"[Error] Unknown widget: {name}")
            return
        def handler(_e=None):
            try:
                self._exec_stmt(action)
            except Exception as ex:
                self.console_write(f"[Error] Event: {ex}")
        if evt == 'LeftClickEvent':
            w.bind('<Button-1>', handler, add='+')
        else:
            w.bind('<Button-3>', handler, add='+')

    def _ensure_window(self) -> None:
        if self.window is None or not self.window.winfo_exists():
            self.window = tk.Toplevel(self.ide_root)
            self.window.title('Qude App')
            self.window.geometry('400x300')
            try:
                self.window.lift()
                self.window.focus_force()
                self.window.attributes('-topmost', True)
                self.window.after(250, lambda: self.window.attributes('-topmost', False))
            except Exception:
                pass

    # -------- Expr eval --------
    def _eval(self, expr: Expr) -> Any:
        if isinstance(expr, StringLit):
            if expr.value.lower() == 'taqe.data':
                return self.vars.get('data', '')
            return expr.value
        if isinstance(expr, NumberLit):
            return expr.value
        if isinstance(expr, VarRef):
            return self.vars.get(expr.name, 0)
        if isinstance(expr, Binary):
            l = self._eval(expr.left)
            r = self._eval(expr.right)
            return self._apply_bin(l, r, expr.op)
        return None

    def _eval_text_expr(self, text: str) -> Any:
        text = text.strip()
        if (len(text) >= 2 and ((text[0] == "'" and text[-1] == "'") or (text[0] == '"' and text[-1] == '"'))):
            return text[1:-1]
        if re.fullmatch(r"\d+(?:\.\d+)?", text):
            return float(text)
        return self.vars.get(text, text)

    def _apply_bin(self, l: Any, r: Any, op: str) -> Any:
        try:
            if op == '+':
                return l + r
            if op == '-':
                return l - r
            if op == '*':
                return l * r
            if op == '/':
                return l / r
        except Exception:
            pass
        return 0

    def _truthy(self, v: Any) -> bool:
        if isinstance(v, str):
            return v.strip().lower() in ('true','tr','1','yes','y')
        return bool(v)
