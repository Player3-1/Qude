import re
import webbrowser
import tkinter as tk
from tkinter import simpledialog
from tkinter import font as tkfont
from typing import Any, Callable, Dict, Optional, Tuple


class QudeInterpreter:
    def __init__(
        self,
        console_write: Callable[[str], None],
        ide_root: tk.Tk,
        icon_image: Optional[tk.PhotoImage] = None,
        icon_bitmap_path: Optional[str] = None,
    ) -> None:
        self.console_write = console_write
        self.ide_root = ide_root
        self.icon_image = icon_image
        self.icon_bitmap_path = icon_bitmap_path
        self.window: Optional[tk.Toplevel] = None
        self.widgets: Dict[str, tk.Widget] = {}
        self.widget_fonts: Dict[str, tkfont.Font] = {}
        self.widget_sizes: Dict[str, Tuple[int, int]] = {}
        self.vars: Dict[str, Any] = {}
        self.running = False
        # preview embedding
        self.preview_mode: bool = False
        self.preview_root: Optional[tk.Widget] = None
        # warn screen state
        self.warn_window: Optional[tk.Widget] = None
        self.warn_option_widgets: Dict[str, tk.Widget] = {}
        # link targets
        self.link_targets: Dict[str, str] = {}

    def run(self, code: str) -> None:
        lines = [ln.rstrip() for ln in code.splitlines()]
        i = 0
        skip_else_chain: Optional[bool] = None  # None=no active chain; True=branch executed; False=not yet

        while i < len(lines):
            raw = lines[i]
            line = raw.strip()

            if not line or line.startswith('#') or line.startswith('//'):
                i += 1
                continue

            if self._is_start(line):
                self.running = True
                i += 1
                skip_else_chain = None
                continue
            if self._is_stop(line):
                self.running = False
                i += 1
                skip_else_chain = None
                continue
            if not self.running:
                i += 1
                continue

            # Event block: event; \n <indented event> \n <indented action>
            if line.lower() == 'event;':
                evt_line, act_line, consumed = self._consume_event_block(lines, i + 1)
                if evt_line is None or act_line is None:
                    self.console_write('[Error] Incomplete event block')
                    i += 1
                else:
                    self._register_event_block(evt_line, act_line)
                    i = consumed
                continue

            # If/Elif/Else single-line actions
            if line.lower().startswith('if '):
                cond_ok, action = self._parse_if_like(line)
                if cond_ok is None:
                    self.console_write('[Error] Bad if syntax')
                    skip_else_chain = None
                else:
                    if cond_ok and action:
                        self._execute_line(action)
                        skip_else_chain = True
                    else:
                        skip_else_chain = False
                i += 1
                continue

            if line.lower().startswith('elif '):
                cond_ok, action = self._parse_if_like(line)
                if skip_else_chain is None:
                    i += 1
                    continue
                if skip_else_chain:
                    i += 1
                    continue
                if cond_ok and action:
                    self._execute_line(action)
                    skip_else_chain = True
                else:
                    skip_else_chain = False
                i += 1
                continue

            if line.lower().startswith('else'):
                if skip_else_chain is None:
                    i += 1
                    continue
                if not skip_else_chain:
                    m = re.match(r"^else\s*:\s*(?:then\s+)?(.+)$", line, re.IGNORECASE)
                    if m and m.group(1).strip():
                        self._execute_line(m.group(1).strip())
                i += 1
                continue

            self._execute_line(line)
            i += 1

    # Aliases
    def _is_start(self, line: str) -> bool:
        return line in ('Qude.prompt', 'qude.str()', 'q>')

    def _is_stop(self, line: str) -> bool:
        return line in ('Qude.kill/', 'qude.end', 'q<')

    # Execution dispatch
    def _execute_line(self, line: str) -> None:
        if not line:
            return

        # Console write
        m = re.match(r"^(Qonsol\.write|qonsol\.write|qons\.wrt)\((.*)\)$", line)
        if m:
            arg = self._eval_arg(m.group(2))
            self.console_write(str(arg))
            return

        # Input -> stores to 'data'
        m = re.match(r"^(taQe\.putt|tq\.put|q£)\((.*)\)$", line)
        if m:
            prompt = self._eval_arg(m.group(2))
            if self.window is None:
                parent = self.ide_root
            else:
                parent = self.window
            ans = simpledialog.askstring("Qude Input", str(prompt), parent=parent)
            self.vars['data'] = ans if ans is not None else ''
            return

        # Variables assignment: Qurr x = expr
        m = re.match(r"^(Qurr|qrr|q\$)\s+(\w+)\s*=\s*(.+)$", line)
        if m:
            name = m.group(2)
            expr = m.group(3)
            self.vars[name] = self._eval_expr(expr)
            return

        # Variables assignment alias: variable x = expr
        m = re.match(r"^(variable)\s+(\w+)\s*=\s*(.+)$", line, re.IGNORECASE)
        if m:
            name = m.group(2)
            expr = m.group(3)
            self.vars[name] = self._eval_expr(expr)
            return

        # Math: matq(expr) or m;(expr)
        m = re.match(r"^(matq|m;)\((.*)\)$", line)
        if m:
            val = self._eval_expr(m.group(2))
            self.console_write(str(val))
            return

        # Window open
        if line in ("Qwindow.qoll()", "qwd.qll()", "qwww()"):
            self._ensure_window()
            return

        # Window title
        m = re.match(r"^(Qwindow\.uptext|qwd\.uptxt|qw\.utxt)\((.*)\)$", line)
        if m:
            title = str(self._eval_arg(m.group(2)))
            self._ensure_window()
            if not self.preview_mode and isinstance(self.window, tk.Toplevel):
                self.window.title(title)
            return

        # Window size
        m = re.match(r"^(Qwindow\.geometry\.size|qwd\.geom\.sz|qw\.ge\.sz)\((.*)\)$", line)
        if m:
            w, h = self._parse_two_ints(m.group(2))
            self._ensure_window()
            if not self.preview_mode and isinstance(self.window, tk.Toplevel):
                self.window.geometry(f"{w}x{h}")
            else:
                try:
                    # best-effort sizing inside preview
                    self.window.configure(width=w, height=h)
                    self.window.pack_propagate(False)
                except Exception:
                    pass
            return

        # Window resizable flags
        m = re.match(r"^(Qwindow\.resizable|qwd\.reszbl|qw\.resz)\s*=\s*(.*)$", line)
        if m:
            val = self._parse_bool(m.group(2))
            self._ensure_window()
            if not self.preview_mode and isinstance(self.window, tk.Toplevel):
                self.window.resizable(val, val)
            return

        # Window fullscreen
        m = re.match(r"^(Qwindow\.fullscreen|qwd\.fullsc|qw\.fls)\s*=\s*(.*)$", line)
        if m:
            val = self._parse_bool(m.group(2))
            self._ensure_window()
            if not self.preview_mode and isinstance(self.window, tk.Toplevel):
                self.window.attributes("-fullscreen", val)
            return

        # Window background color
        m = re.match(r"^(Qwindow\.background\.color|qwd\.bg\.clr|qw\.bgc)\((.*)\)$", line)
        if m:
            color = str(self._eval_arg(m.group(2)))
            self._ensure_window()
            try:
                self.window.configure(bg=color)
            except Exception:
                pass
            return

        # Kill windows
        if line.strip() == "kill.qwindow/":
            try:
                if self.window is not None and self.window.winfo_exists():
                    self.window.destroy()
            except Exception:
                pass
            self.window = None
            return
        if line.strip() == "kill.wwindow/":
            try:
                if self.warn_window is not None and self.warn_window.winfo_exists():
                    self.warn_window.destroy()
            except Exception:
                pass
            self.warn_window = None
            self.warn_option_widgets = {}
            # Refocus main window so it doesn't fall behind
            try:
                if self.window is not None and self.window.winfo_exists():
                    self.window.lift()
                    self.window.focus_force()
                    self.window.attributes('-topmost', True)
                    self.window.after(200, lambda: self.window.attributes('-topmost', False))
            except Exception:
                pass
            return

        # Wwindow properties (warn window)
        m = re.match(r"^(Wwindow\.uptext)\((.*)\)$", line)
        if m:
            title = str(self._eval_arg(m.group(2)))
            self._set_warn_title(title)
            return
        m = re.match(r"^(Wwindow\.background\.color)\((.*)\)$", line)
        if m:
            color = str(self._eval_arg(m.group(2)))
            self._set_warn_bg(color)
            return

        # Insert text
        m = re.match(r"^(insert\.text|ins\.txt|i\.tx)\((.*)\)\s+as\s+(\w+)$", line)
        if m:
            content = str(self._eval_arg(m.group(2)))
            name = m.group(3)
            self._ensure_window()
            lbl = tk.Label(self.window, text=content)
            lbl.place(x=0, y=0)
            self.widgets[name] = lbl
            self.widget_fonts[name] = tkfont.Font(family='TkDefaultFont', size=12)
            lbl.configure(font=self.widget_fonts[name])
            return

        # Insert link (Label styled as hyperlink)
        m = re.match(r"^(insert\.link)\(\)\s+as\s+(\w+)$", line)
        if m:
            name = m.group(2)
            self._ensure_window()
            lbl = tk.Label(self.window, text="link", fg="#1a73e8", cursor="hand2")
            lbl.place(x=0, y=0)
            self.widgets[name] = lbl
            self.widget_fonts[name] = tkfont.Font(family='TkDefaultFont', size=12, underline=1)
            lbl.configure(font=self.widget_fonts[name])
            return

        # Insert button
        m = re.match(r"^(insert\.button|ins\.btn|i\.bt)\(\)\s+as\s+(\w+)$", line)
        if m:
            name = m.group(2)
            self._ensure_window()
            btn = tk.Button(self.window, text="button")
            btn.place(x=0, y=0)
            self.widgets[name] = btn
            self.widget_fonts[name] = tkfont.Font(family='TkDefaultFont', size=12)
            btn.configure(font=self.widget_fonts[name])
            return

        # Insert inputter (Entry)
        m = re.match(r"^(insert\.inputter)\(\)\s+as\s+(\w+)$", line)
        if m:
            name = m.group(2)
            self._ensure_window()
            ent = tk.Entry(self.window)
            ent.place(x=0, y=0)
            self.widgets[name] = ent
            self.widget_fonts[name] = tkfont.Font(family='TkDefaultFont', size=12)
            ent.configure(font=self.widget_fonts[name])
            return

        # Warn screen: warn.screen('message' <option>)
        m = re.match(r"^warn\.screen\(\s*([\"\'].*?[\"\'])\s*<([^>]+)>\s*\)$", line)
        if m:
            msg = str(self._eval_arg(m.group(1)))
            option = m.group(2).strip()
            self._open_warn_screen(msg, option)
            return


        # Widget operations
        self._execute_widget_line(line)

    def _execute_widget_line(self, line: str) -> None:
        # name.font.color = 'red' | name.fnt.clr('red') | name.f$('red')
        m = re.match(r"^(\w+)\.(font\.color|fnt\.clr|f\$)\((.*)\)$", line)
        if m:
            name = m.group(1)
            color = str(self._eval_arg(m.group(3)))
            w = self.widgets.get(name)
            if w:
                w.configure(fg=color)
            return

        # name.font.font('Comic Sans MS') | name.fnt.font('...') | name.ffnt('...')
        m = re.match(r"^(\w+)\.(font\.font|fnt\.font|ffnt)\((.*)\)$", line)
        if m:
            name = m.group(1)
            fam = str(self._eval_arg(m.group(3)))
            if name in self.widget_fonts:
                f = self.widget_fonts[name]
                f.configure(family=fam)
                self.widgets[name].configure(font=f)
            return

        m = re.match(r"^(\w+)\.size\s*=\s*(.*)$", line)
        if m:
            name = m.group(1)
            size = int(self._eval_expr(m.group(2)))
            if name in self.widget_fonts:
                f = self.widget_fonts[name]
                f.configure(size=size)
                self.widgets[name].configure(font=f)
            return

        # name.font.size = 15 | name.fnt.sz = 15 | name.fsz = 15
        m = re.match(r"^(\w+)\.(font\.size|fnt\.sz|fsz)\s*=\s*(.*)$", line)
        if m:
            name = m.group(1)
            size = int(self._eval_expr(m.group(3)))
            if name in self.widget_fonts:
                f = self.widget_fonts[name]
                f.configure(size=size)
                self.widgets[name].configure(font=f)
            return

        # name.background.color = 'red' | name.bg.clr('red') | name.bgc('red')
        m = re.match(r"^(\w+)\.(background\.color|bg\.clr|bgc)\((.*)\)$", line)
        if m:
            name = m.group(1)
            color = str(self._eval_arg(m.group(3)))
            w = self.widgets.get(name)
            if w:
                w.configure(bg=color)
            return

        # name.text('click me') | name.txt('click me') | button.tx('click me')
        m = re.match(r"^(\w+)\.(text|txt|tx)\((.*)\)$", line)
        if m:
            name = m.group(1)
            txt = str(self._eval_arg(m.group(3)))
            w = self.widgets.get(name)
            if w:
                if isinstance(w, tk.Button) or isinstance(w, tk.Label):
                    w.configure(text=txt)
            return

        # name.link('https://...') -> assign URL and bind click
        m = re.match(r"^(\w+)\.(link)\((.*)\)$", line)
        if m:
            name = m.group(1)
            url = str(self._eval_arg(m.group(3)))
            w = self.widgets.get(name)
            if w and isinstance(w, tk.Label):
                self.link_targets[name] = url
                try:
                    w.configure(fg="#1a73e8", cursor="hand2")
                    if name in self.widget_fonts:
                        f = self.widget_fonts[name]
                        try:
                            f.configure(underline=1)
                            w.configure(font=f)
                        except Exception:
                            pass
                except Exception:
                    pass

                def _open_url(_e=None, _u=url):
                    try:
                        webbrowser.open(_u)
                    except Exception:
                        self.console_write(f"[Error] URL açılamadı: {_u}")

                try:
                    w.bind('<Button-1>', _open_url, add='+')
                except Exception:
                    pass
            return

        # name.text.color('red') | name.txt.clr('red') | name.t$('red')
        m = re.match(r"^(\w+)\.(text\.color|txt\.clr|t\$)\((.*)\)$", line)
        if m:
            name = m.group(1)
            color = str(self._eval_arg(m.group(3)))
            w = self.widgets.get(name)
            if w:
                w.configure(fg=color)
            return

        # name.geometry.size(100,100) | name.geom.sz | name.ge.sz
        m = re.match(r"^(\w+)\.(geometry\.size|geom\.sz|ge\.sz)\((.*)\)$", line)
        if m:
            name = m.group(1)
            w = self.widgets.get(name)
            if w:
                width, height = self._parse_two_ints(m.group(3))
                self.widget_sizes[name] = (width, height)
                info = w.place_info()
                x = int(info.get('x', 0) or 0)
                y = int(info.get('y', 0) or 0)
                w.place(x=x, y=y, width=width, height=height)
            return

        # name.cordinates(100, 100) | name.cordint | name.c$(x, y)
        m = re.match(r"^(\w+)\.(cordinates|cordint|c\$)\((.*)\)$", line)
        if m:
            name = m.group(1)
            w = self.widgets.get(name)
            if w:
                x, y = self._parse_two_ints(m.group(3))
                size = self.widget_sizes.get(name, (None, None))
                if size[0] is None:
                    w.place(x=x, y=y)
                else:
                    w.place(x=x, y=y, width=size[0], height=size[1])
            return

        # Unknown line -> ignore gracefully
        self.console_write(f"[Warn] Unrecognized: {line}")

    def _register_event_block(self, evt_line: str, action_line: str) -> None:
        # Patterns supported:
        #   name.LeftClickEvent:
        #   name.RightClickEvent:
        #   name.MatchEvent == 'text':
        #   <option>LeftClickEvent:   (warn.screen option button)

        # Option button in warn screen
        m_opt = re.match(r"\s*<([^>]+)>(LeftClickEvent|RightClickEvent):\s*$", evt_line)
        if m_opt:
            option = m_opt.group(1).strip()
            evt = m_opt.group(2)
            w = self.warn_option_widgets.get(option)
            if not w:
                self.console_write(f"[Error] Unknown warn option: {option}")
                return

            def handler_opt(_e=None):
                try:
                    self._execute_line(action_line.strip())
                except Exception as ex:
                    self.console_write(f"[Error] Event: {ex}")

            if evt == 'LeftClickEvent':
                w.bind('<Button-1>', handler_opt, add='+')
            else:
                w.bind('<Button-3>', handler_opt, add='+')
            return

        # MatchEvent
        m_match = re.match(r"\s*(\w+)\.MatchEvent\s*==\s*(.+):\s*$", evt_line)
        if m_match:
            name = m_match.group(1)
            expected_raw = m_match.group(2).strip()
            expected_val = self._eval_arg(expected_raw)
            w = self.widgets.get(name)
            if not w or not isinstance(w, tk.Entry):
                self.console_write(f"[Error] MatchEvent requires inputter widget: {name}")
                return

            def on_change(_e=None):
                try:
                    if w.get() == str(expected_val):
                        self._execute_line(action_line.strip())
                except Exception as ex:
                    self.console_write(f"[Error] Event: {ex}")

            # Bind on key release for simplicity
            w.bind('<KeyRelease>', on_change, add='+')
            return

        # Click events on named widget
        m = re.match(r"\s*(\w+)\.(LeftClickEvent|RightClickEvent):\s*$", evt_line)
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
                self._execute_line(action_line.strip())
            except Exception as ex:
                self.console_write(f"[Error] Event: {ex}")

        if evt == 'LeftClickEvent':
            w.bind('<Button-1>', handler, add='+')
        elif evt == 'RightClickEvent':
            w.bind('<Button-3>', handler, add='+')

    # Helpers
    def _ensure_window(self) -> None:
        # In preview mode, create/ensure an embedded Frame as the window
        if self.preview_mode:
            parent = self.preview_root if self.preview_root else self.ide_root
            if self.window is None or not self.window.winfo_exists() or self.window.master is not parent:
                # reset previous
                try:
                    if self.window is not None and self.window.winfo_exists():
                        self.window.destroy()
                except Exception:
                    pass
                self.window = tk.Frame(parent, bg='#222')
                # Fill the preview area
                try:
                    self.window.pack(fill=tk.BOTH, expand=True)
                except Exception:
                    self.window.place(x=0, y=0, relwidth=1.0, relheight=1.0)
                # clear widget state for fresh render
                self.widgets = {}
                self.widget_fonts = {}
                self.widget_sizes = {}
            return

        # Normal mode: Toplevel window
        if self.window is None or not self.window.winfo_exists():
            self.window = tk.Toplevel(self.ide_root)
            self.window.title('Qude App')
            self.window.geometry('400x300')
            self.window.configure(bg='#222')
            # Prefer ICO for taskbar when available
            try:
                if self.icon_bitmap_path:
                    self.window.iconbitmap(self.icon_bitmap_path)
            except Exception:
                pass
            try:
                if self.icon_image is not None:
                    self.window.iconphoto(True, self.icon_image)
            except Exception:
                pass
            # Bring to front
            try:
                self.window.lift()
                self.window.focus_force()
                self.window.attributes('-topmost', True)
                # remove always-on-top shortly after to avoid sticking on top
                self.window.after(250, lambda: self.window.attributes('-topmost', False))
            except Exception:
                pass


    def _open_warn_screen(self, message: str, option: str) -> None:
        # Reset previous warn screen
        try:
            if self.warn_window is not None and self.warn_window.winfo_exists():
                self.warn_window.destroy()
        except Exception:
            pass
        self.warn_window = None
        self.warn_option_widgets = {}

        if self.preview_mode:
            parent = self.preview_root if self.preview_root else self.ide_root
            frm = tk.Frame(parent, bg='#333', bd=1, relief='ridge')
            self.warn_window = frm
            # content
            lbl = tk.Label(frm, text=message, bg='#333', fg='#fff')
            btn = tk.Label(frm, text=option, bg='#555', fg='#fff', padx=12, pady=6)
            lbl.pack(padx=12, pady=(12, 8))
            btn.pack(padx=12, pady=(0, 12))
            # place centered
            try:
                frm.place(relx=0.5, rely=0.5, anchor='center')
                try:
                    frm.lift()
                except Exception:
                    try:
                        frm.tkraise()
                    except Exception:
                        pass
            except Exception:
                frm.pack()
        else:
            top = tk.Toplevel(self.ide_root)
            top.title('Uyarı')
            top.geometry('300x150')
            top.configure(bg='#333')
            # icon
            try:
                if self.icon_bitmap_path:
                    top.iconbitmap(self.icon_bitmap_path)
            except Exception:
                pass
            try:
                if self.icon_image is not None:
                    top.iconphoto(True, self.icon_image)
            except Exception:
                pass
            self.warn_window = top
            # content
            lbl = tk.Label(top, text=message, bg='#333', fg='#fff')
            btn = tk.Label(top, text=option, bg='#555', fg='#fff', padx=12, pady=6)
            lbl.pack(padx=12, pady=(12, 8))
            btn.pack(padx=12, pady=(0, 12))
            # modal-like
            try:
                top.transient(self.ide_root)
                top.grab_set()
                top.lift()
                top.focus_force()
                top.attributes('-topmost', True)
                top.after(250, lambda: top.attributes('-topmost', False))
            except Exception:
                pass

        # register option widget for event syntax <option>LeftClickEvent:
        self.warn_option_widgets[option] = btn

    # Wwindow property setters (warn window similar to Qwindow)
    def _set_warn_title(self, title: str) -> None:
        if self.warn_window is not None and isinstance(self.warn_window, tk.Toplevel):
            try:
                self.warn_window.title(title)
            except Exception:
                pass

    def _set_warn_bg(self, color: str) -> None:
        if self.warn_window is not None:
            try:
                self.warn_window.configure(bg=color)
            except Exception:
                pass

    def _consume_event_block(self, lines: list[str], start_idx: int) -> Tuple[Optional[str], Optional[str], int]:
        i = start_idx
        while i < len(lines) and not lines[i].strip():
            i += 1
        if i >= len(lines):
            return None, None, i
        evt_line = lines[i]
        i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1
        if i >= len(lines):
            return evt_line, None, i
        act_line = lines[i]
        return evt_line, act_line, i + 1

    def _parse_two_ints(self, arg: str) -> Tuple[int, int]:
        parts = self._split_args(arg)
        if len(parts) != 2:
            raise ValueError('Expected two arguments')
        return int(self._eval_expr(parts[0])), int(self._eval_expr(parts[1]))

    def _parse_bool(self, s: str) -> bool:
        val = s.strip().lower()
        return val in ('true', 'tr', '1', 'yes', 'y')

    def _eval_arg(self, s: str) -> Any:
        s = s.strip()
        # alias: taqe.data -> data
        if s.lower() == 'taqe.data':
            return self.vars.get('data', '')
        if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
            return s[1:-1]
        if s in self.vars:
            return self.vars[s]
        try:
            if '.' in s:
                return float(s)
            return int(s)
        except Exception:
            return s

    def _eval_expr(self, expr: str) -> Any:
        expr = expr.strip()
        # alias: taqe.data -> data for expression resolution
        expr = re.sub(r"\btaqe\.data\b", "data", expr, flags=re.IGNORECASE)
        # Replace variable names with values for simple arithmetic
        def repl_var(match: re.Match) -> str:
            name = match.group(0)
            if name in self.vars:
                val = self.vars[name]
                if isinstance(val, (int, float)):
                    return str(val)
                return repr(val)
            return name

        safe = re.sub(r"\b[a-zA-Z_]\w*\b", repl_var, expr)
        try:
            return eval(safe, {"__builtins__": {}}, {})
        except Exception:
            return self._eval_arg(expr)

    def _split_args(self, arg: str) -> list:
        parts = []
        current = ''
        depth = 0
        in_str = False
        quote = ''
        for ch in arg:
            if in_str:
                current += ch
                if ch == quote:
                    in_str = False
            else:
                if ch in ('"', "'"):
                    in_str = True
                    quote = ch
                    current += ch
                elif ch == '(':
                    depth += 1
                    current += ch
                elif ch == ')':
                    depth -= 1
                    current += ch
                elif ch == ',' and depth == 0:
                    parts.append(current.strip())
                    current = ''
                else:
                    current += ch
        if current.strip():
            parts.append(current.strip())
        return parts

    def _parse_if_like(self, line: str) -> Tuple[Optional[bool], Optional[str]]:
        # Patterns:
        # if data = '123': then Qonsol.write('...')
        # elif data = '1234': then Qonsol.write('...')
        # else: Qonsol.write('...')  (not used in sample, we ignore)
        m = re.match(r"^(if|elif)\s+(.+?)\s*:\s*then\s+(.+)$", line, re.IGNORECASE)
        if not m:
            return None, None
        cond = m.group(2).strip()
        action = m.group(3).strip()
        # Only support equality with '=' in spec
        m2 = re.match(r"^(.+?)\s*=\s*(.+)$", cond)
        if not m2:
            return None, None
        left = self._eval_expr(m2.group(1))
        right = self._eval_expr(m2.group(2))
        return bool(left == right), action
