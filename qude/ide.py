import os
import re
import tempfile
import sys
import subprocess
import shutil
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter import font as tkfont
from .interpreter import QudeInterpreter
try:
    from PIL import Image, ImageTk  # type: ignore
except Exception:
    Image = None  # type: ignore
    ImageTk = None  # type: ignore


class QudeIDE:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Qude IDE (Prototype)")
        self.root.geometry("1100x700")
        self.current_file: str | None = None
        self.theme = 'dark'

        # Create and set app icon (prefer q.ico, then q.png, else fallback)
        self.icon_bitmap_path: str | None = None
        self.app_icon = None
        # 1) Try ICO first
        base_dirs = [
            os.path.dirname(__file__),
            os.path.dirname(os.path.dirname(__file__)),
        ]
        if getattr(sys, "_MEIPASS", None):
            base_dirs.insert(0, getattr(sys, "_MEIPASS"))
        ico_paths = [os.path.join(d, 'q.ico') for d in base_dirs]
        found = False
        for p in ico_paths:
            if os.path.exists(p):
                try:
                    self._apply_icon_from_path(p)
                    found = True
                    break
                except Exception:
                    pass
        # 2) Try PNG if ICO not found
        if not found:
            png_paths = [os.path.join(d, 'q.png') for d in base_dirs]
            for p in png_paths:
                if os.path.exists(p):
                    try:
                        self._apply_icon_from_path(p)
                        found = True
                        break
                    except Exception:
                        self.app_icon = None
        if self.app_icon is None:
            self.app_icon = self._create_q_icon()
        try:
            self.root.iconphoto(True, self.app_icon)
        except Exception:
            pass
        # Also set iconbitmap for Windows taskbar when ICO is known
        try:
            if self.icon_bitmap_path and os.path.exists(self.icon_bitmap_path):
                self.root.iconbitmap(self.icon_bitmap_path)
        except Exception:
            pass

        # Optional splash with ICO (if available)
        try:
            self._show_splash_ico()
        except Exception:
            pass

        self._build_ui()
        self.interpreter = QudeInterpreter(
            self._console_write,
            self.root,
            icon_image=self.app_icon,
            icon_bitmap_path=self.icon_bitmap_path,
        )

    def _build_ui(self) -> None:
        self._apply_dark_theme()

        # Menu bar
        menubar = tk.Menu(self.root, tearoff=False)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Yeni", command=self._new_file, accelerator="Ctrl+N")
        file_menu.add_command(label="Aç...", command=self._open_file, accelerator="Ctrl+O")
        file_menu.add_command(label="Kaydet", command=self._save_file, accelerator="Ctrl+S")
        file_menu.add_command(label="Farklı Kaydet...", command=self._save_file_as, accelerator="Ctrl+Shift+S")
        file_menu.add_separator()
        file_menu.add_command(label="Çıkış", command=self.root.quit)
        menubar.add_cascade(label="Dosya", menu=file_menu)

        run_menu = tk.Menu(menubar, tearoff=False)
        run_menu.add_command(label="Çalıştır", command=self.run_script, accelerator="F5")
        run_menu.add_command(label="Önizle", command=self.run_preview, accelerator="F6")
        run_menu.add_separator()
        run_menu.add_command(label="Yayınla (.exe)", command=self._publish_exe)
        menubar.add_cascade(label="Çalıştır", menu=run_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="Yardım", command=self._show_help)
        menubar.add_cascade(label="Yardım", menu=help_menu)

        # Settings menu
        settings_menu = tk.Menu(menubar, tearoff=False)
        theme_menu = tk.Menu(settings_menu, tearoff=False)
        theme_menu.add_command(label="Koyu", command=lambda: self._set_theme('dark'))
        theme_menu.add_command(label="Açık", command=lambda: self._set_theme('light'))
        settings_menu.add_cascade(label="Tema", menu=theme_menu)
        icon_menu = tk.Menu(settings_menu, tearoff=False)
        icon_menu.add_command(label="Simge Yükle (PNG/ICO)...", command=self._load_icon_file)
        settings_menu.add_cascade(label="Simge", menu=icon_menu)
        settings_menu.add_separator()
        settings_menu.add_command(label="Yazı Boyutu...", command=self._open_font_settings)
        settings_menu.add_separator()
        settings_menu.add_command(label="Sürüm", command=self._show_version)
        settings_menu.add_separator()
        settings_menu.add_command(label="Yardım", command=self._show_help)
        menubar.add_cascade(label="Ayarlar", menu=settings_menu)

        self.root.config(menu=menubar)

        # Shortcuts
        self.root.bind_all("<Control-n>", lambda e: self._new_file())
        self.root.bind_all("<Control-o>", lambda e: self._open_file())
        self.root.bind_all("<Control-s>", lambda e: self._save_file())
        self.root.bind_all("<Control-S>", lambda e: self._save_file_as())
        self.root.bind_all("<F5>", lambda e: self.run_script())
        self.root.bind_all("<F6>", lambda e: self.run_preview())
        self.root.bind_all("<Control-KP_Add>", lambda e: self._zoom_in())
        self.root.bind_all("<Control-=>", lambda e: self._zoom_in())
        self.root.bind_all("<Control-minus>", lambda e: self._zoom_out())
        self.root.bind_all("<Control-KP_Subtract>", lambda e: self._zoom_out())
        self.root.bind_all("<Control-0>", lambda e: self._zoom_reset())

        # Main layout with left tree, center editor, right preview, bottom console
        main = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True)

        # Center: editor with dark theme and syntax highlighting
        center_frame = ttk.Frame(main)
        self.editor_font = tkfont.Font(family='Consolas', size=15)
        self.editor = tk.Text(
            center_frame,
            wrap="none",
            undo=True,
            bg="#1e1f22",
            fg="#e6e6e6",
            insertbackground="#e6e6e6",
            padx=8,
            pady=8,
            relief=tk.FLAT,
            font=self.editor_font,
        )
        self.editor.pack(fill=tk.BOTH, expand=True)
        self._setup_editor_highlight()
        self._bind_autoclose()
        main.add(center_frame, weight=4)

        # Right: live preview area
        right_frame = ttk.Frame(main, width=320)
        lbl_preview = ttk.Label(right_frame, text="Önizleme")
        lbl_preview.pack(anchor="w", padx=8, pady=(6, 0))
        btn_preview = ttk.Button(right_frame, text="Önizlemeyi Aç/Yenile (F6)", command=self.run_preview)
        btn_preview.pack(anchor="w", padx=8, pady=(4, 6))
        self.preview_outer = ttk.Frame(right_frame)
        self.preview_outer.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        # actual drawing surface uses plain tk.Frame for easier bg control
        self.preview_area = tk.Frame(self.preview_outer, bg="#111315")
        self.preview_area.pack(fill=tk.BOTH, expand=True)
        main.add(right_frame, weight=2)

        # Bottom: console (dark) with fixed pixel height
        console_frame = ttk.Frame(self.root, height=180)
        console_frame.pack(fill=tk.X, side=tk.BOTTOM)
        try:
            console_frame.pack_propagate(False)
        except Exception:
            pass
        ttk.Label(console_frame, text="Konsol").pack(anchor="w", padx=8)
        self.console_font = tkfont.Font(family='Consolas', size=14)
        self.console = tk.Text(
            console_frame,
            state="disabled",
            bg="#111315",
            fg="#eeeeee",
            insertbackground="#eeeeee",
            padx=8,
            relief=tk.FLAT,
            font=self.console_font,
        )
        self.console.tag_configure("warn", foreground="#e5c07b")
        self.console.tag_configure("error", foreground="#e06c75")
        self.console.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        # Seed editor with a sample
        self._seed_sample()
        self._highlight_all()

    def _seed_sample(self) -> None:
        sample = (
            "Qude.prompt\n"

            "Qonsol.write('hello world!')\n"
            
            "Qude.kill/\n"
        )
        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", sample)

    def _console_write(self, text: str) -> None:
        self.console.configure(state="normal")
        tag = None
        if text.startswith('[Warn]'):
            tag = 'warn'
        elif text.startswith('[Error]'):
            tag = 'error'
        if tag:
            self.console.insert(tk.END, text + "\n", tag)
        else:
            self.console.insert(tk.END, text + "\n")
        self.console.see(tk.END)
        self.console.configure(state="disabled")

    def _show_help(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Qude Yardım")
        win.geometry("800x600")
        try:
            if self.icon_bitmap_path:
                win.iconbitmap(self.icon_bitmap_path)
        except Exception:
            pass
        try:
            if self.app_icon is not None:
                win.iconphoto(True, self.app_icon)
        except Exception:
            pass

        container = ttk.Frame(win)
        container.pack(fill=tk.BOTH, expand=True)

        topbar = ttk.Frame(container)
        topbar.pack(fill=tk.X, padx=10, pady=(10, 6))
        lbl = ttk.Label(topbar, text="Ara:")
        lbl.pack(side=tk.LEFT)
        search_var = tk.StringVar()
        ent = ttk.Entry(topbar, textvariable=search_var, width=30)
        ent.pack(side=tk.LEFT, padx=6)
        btn = ttk.Button(topbar, text="Bul")
        btn.pack(side=tk.LEFT)

        nb = ttk.Notebook(container)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        def make_tab(title: str, body: str) -> None:
            frame = ttk.Frame(nb)
            nb.add(frame, text=title)
            txt = tk.Text(
                frame,
                wrap="word",
                bg="#1e1f22" if self.theme == 'dark' else "#ffffff",
                fg="#e6e6e6" if self.theme == 'dark' else "#202225",
                insertbackground="#e6e6e6" if self.theme == 'dark' else "#202225",
                padx=10,
                pady=10,
                relief=tk.FLAT,
            )
            txt.pack(fill=tk.BOTH, expand=True)
            try:
                help_font = tkfont.Font(family='Segoe UI', size=12)
                txt.configure(font=help_font)
            except Exception:
                pass
            txt.insert("1.0", body)
            txt.configure(state="disabled")
            help_texts.append(txt)

        intro = (
            "Qude 1.1 Yardım\n\n"
            "Başlat/Bitir:\n"
            "  Qude.prompt | qude.str() | q>\n"
            "  Qude.kill/ | qude.end | q<\n\n"
            "Değişkenler ve Matematik:\n"
            "  Qurr x = 15 | qrr | q$\n"
            "  matq(5 + 5) | m;(5 + 5)\n\n"
            "Yeni (1.1):\n"
            "  insert.inputter() as input1  -> Girdi kutusu (Entry) ekler\n"
            "  input1.MatchEvent == 'yazi'  -> Eşleşince aksiyonu tetikler\n"
            "  warn.screen('mesaj' <tamam>) -> Uyarı ekranı ve seçenek düğmesi\n"
            "  <tamam>LeftClickEvent:       -> Uyarı seçenek eventi\n"
            "  kill.wwindow/                -> Uyarı ekranını kapat\n"
            "  kill.qwindow/                -> Ana pencereyi kapat\n"
            "  Wwindow.uptext('Başlık')     -> Uyarı penceresi başlığı\n"
            "  Wwindow.background.color('#333')\n\n"
            "Kısayollar:\n  Ctrl+N Yeni  |  Ctrl+O Aç  |  Ctrl+S Kaydet  |  Ctrl+Shift+S Farklı Kaydet  |  F5 Çalıştır  |  F6 Önizle\n"
            "Yayınla: Çalıştır > Yayınla (.exe)\n"
        )

        konsol = (
            "Konsol (Yaz/Veri Al)\n\n"
            "Yazdırma:\n"
            "  Qonsol.write('metin') | qonsol.write | qons.wrt\n"
            "  Örnek: Qonsol.write('Merhaba Dünya!')\n\n"
            "Girdi Alma:\n"
            "  taQe.putt('> ') | tq.put | q£\n"
            "  Diyalog penceresi açılır, cevap 'data' değişkenine yazılır.\n"
            "  Örnek akış:\n"
            "    taQe.putt('Adın?')\n"
            "    if data = 'Ali': then Qonsol.write('Merhaba Ali')\n"
        )

        pencere = (
            "Pencere İşlemleri\n\n"
            "Aç/Kapat:\n"
            "  Qwindow.qoll() | qwd.qll() | qwww()\n\n"
            "Başlık:\n"
            "  Qwindow.uptext('Başlık') | qwd.uptxt | qw.utxt\n\n"
            "Boyut:\n"
            "  Qwindow.geometry.size(w, h) | qwd.geom.sz | qw.ge.sz\n"
            "  Örnek: Qwindow.geometry.size(300, 200)\n\n"
            "Yeniden Boyutlandırma:\n"
            "  Qwindow.resizable = true|false | qwd.reszbl | qw.resz\n\n"
            "Tam Ekran:\n"
            "  Qwindow.fullscreen = true|false | qwd.fullsc | qw.fls\n\n"
            "Arkaplan Rengi:\n"
            "  Qwindow.background.color('renk') | qwd.bg.clr | qw.bgc\n\n"
            "Kapatma (1.1):\n"
            "  kill.qwindow/  -> Ana pencereyi kapatır\n"
        )

        yazi = (
            "Yazı (Label)\n\n"
            "Oluşturma:\n"
            "  insert.text('Metin') as text1 | ins.txt | i.tx\n\n"
            "Renk ve Yazı Tipi:\n"
            "  text1.font.color('renk') | text1.fnt.clr | text1.f$\n"
            "  text1.font.font('Aile') | text1.fnt.font | text1.ffnt\n"
            "  text1.font.size = 15 | text1.fnt.sz = 15 | text1.fsz = 15\n\n"
            "Arkaplan:\n"
            "  text1.background.color('renk') | text1.bg.clr | text1.bgc\n\n"
            "Konumlandırma:\n"
            "  text1.cordinates(x, y) | text1.cordint | text1.c$\n"
            "  Örnek: text1.cordinates(40, 60)\n"
        )

        buton = (
            "Buton\n\n"
            "Oluşturma:\n"
            "  insert.button() as button1 | ins.btn | i.bt\n\n"
            "Metin ve Stil:\n"
            "  button1.text('metin') | button1.txt | button1.tx\n"
            "  button1.font.font('Aile') | button1.fnt.font | button1.ffnt\n"
            "  button1.font.size = 15 | button1.fnt.sz = 15 | button1.fsz = 15\n"
            "  button1.text.color('renk') | button1.txt.clr | button1.t$\n"
            "  button1.background.color('renk') | button1.bg.clr | button1.bgc\n\n"
            "Boyut ve Konum:\n"
            "  button1.geometry.size(w, h) | button1.geom.sz | button1.ge.sz\n"
            "  button1.cordinates(x, y) | button1.cordint | button1.c$\n"
        )

        inputtab = (
            "Input (Girdi Kutusu)\n\n"
            "Oluşturma (1.1):\n"
            "  insert.inputter() as input1\n\n"
            "Stil:\n"
            "  input1.font.size = 14\n"
            "  input1.font.font('Segoe UI')\n"
            "  input1.font.color('#eee')\n"
            "  input1.background.color('#222')\n\n"
            "Konumlandırma:\n"
            "  input1.geometry.size(200, 28)\n"
            "  input1.cordinates(40, 60)\n\n"
            "Event (MatchEvent):\n"
            "  event;\n"
            "      input1.MatchEvent == 'tamam':\n"
            "      warn.screen('işlem başarılı' <ok>)\n"
        )

        eventler = (
            "Eventler (Olaylar)\n\n"
            "Blok Yapısı:\n"
            "  event;\n"
            "      button1.LeftClickEvent:\n"
            "      Qonsol.write('left clicked!')\n\n"
            "Desteklenen Olaylar:\n"
            "  LeftClickEvent  -> Sol tık\n"
            "  RightClickEvent -> Sağ tık\n\n"
            "Yeni (1.1):\n"
            "  MatchEvent: input1.MatchEvent == 'yazi':\n"
            "    Girdi kutusu değeri eşleşince aksiyonu tetikler.\n"
            "  warn.screen('metin' <secenek>):\n"
            "    Küçük uyarı penceresi oluşturur.\n"
            "  <secenek>LeftClickEvent: / <secenek>RightClickEvent:\n"
            "    Uyarı üzerindeki seçenek düğmesi tıklama eventleri.\n"
            "  kill.wwindow/:\n"
            "    Uyarı penceresini kapatır.\n"
            "  Wwindow.uptext('Başlık'), Wwindow.background.color('#333')\n"
            "    Uyarı penceresi özellikleri.\n\n"
            "İpucu:\n"
            "  warn.screen satırı eventlerden önce gelmeli; <secenek> etiketi birebir aynı olmalı.\n"
        )

        help_texts: list[tk.Text] = []
        make_tab("Genel", intro)
        make_tab("Konsol", konsol)
        make_tab("Pencere", pencere)
        make_tab("Yazı", yazi)
        make_tab("Buton", buton)
        make_tab("Input", inputtab)
        make_tab("Event", eventler)

        def do_search() -> None:
            query = search_var.get().strip()
            if not query:
                return
            cur_tab = nb.index(nb.select())
            if cur_tab < 0 or cur_tab >= len(help_texts):
                return
            txt = help_texts[cur_tab]
            txt.configure(state="normal")
            txt.tag_remove("_find", "1.0", tk.END)
            start = "1.0"
            while True:
                pos = txt.search(query, start, stopindex=tk.END, nocase=True)
                if not pos:
                    break
                end = f"{pos}+{len(query)}c"
                txt.tag_add("_find", pos, end)
                start = end
            txt.tag_configure("_find", background="#3a6ea5", foreground="#ffffff")
            txt.configure(state="disabled")
            try:
                first = txt.tag_nextrange("_find", "1.0")
                if first:
                    txt.see(first[0])
            except Exception:
                pass

        btn.configure(command=do_search)
        ent.bind("<Return>", lambda e: do_search())

        win.transient(self.root)
        win.grab_set()
        win.focus_set()

    def _open_font_settings(self) -> None:
        dlg = tk.Toplevel(self.root)
        dlg.title("Yazı Boyutu")
        dlg.geometry("380x220")
        try:
            if self.icon_bitmap_path:
                dlg.iconbitmap(self.icon_bitmap_path)
        except Exception:
            pass
        try:
            if self.app_icon is not None:
                dlg.iconphoto(True, self.app_icon)
        except Exception:
            pass

        frm = ttk.Frame(dlg)
        frm.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        ttk.Label(frm, text="Editör Yazı Boyutu").pack(anchor="w")
        editor_scale = ttk.Scale(frm, from_=8, to=28, orient=tk.HORIZONTAL)
        editor_scale.set(self.editor_font.actual("size"))
        editor_scale.pack(fill=tk.X, pady=(2, 8))

        ttk.Label(frm, text="Konsol Yazı Boyutu").pack(anchor="w")
        console_scale = ttk.Scale(frm, from_=8, to=28, orient=tk.HORIZONTAL)
        console_scale.set(self.console_font.actual("size"))
        console_scale.pack(fill=tk.X, pady=(2, 8))

        def on_change(_: str = "") -> None:
            try:
                self.editor_font.configure(size=int(float(editor_scale.get())))
                self.console_font.configure(size=int(float(console_scale.get())))
            except Exception:
                pass

        editor_scale.configure(command=on_change)
        console_scale.configure(command=on_change)

        btns = ttk.Frame(frm)
        btns.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btns, text="Sıfırla", command=lambda: self._zoom_reset()).pack(side=tk.LEFT)
        ttk.Button(btns, text="Kapat", command=dlg.destroy).pack(side=tk.RIGHT)

        dlg.transient(self.root)
        dlg.grab_set()
        dlg.focus_set()

    def _zoom_in(self) -> None:
        try:
            self.editor_font.configure(size=self.editor_font.actual("size") + 1)
            self.console_font.configure(size=self.console_font.actual("size") + 1)
        except Exception:
            pass

    def _zoom_out(self) -> None:
        try:
            self.editor_font.configure(size=max(8, self.editor_font.actual("size") - 1))
            self.console_font.configure(size=max(8, self.console_font.actual("size") - 1))
        except Exception:
            pass

    def _zoom_reset(self) -> None:
        try:
            self.editor_font.configure(size=15)
            self.console_font.configure(size=14)
        except Exception:
            pass

    def run_script(self) -> None:
        code = self.editor.get("1.0", tk.END)
        # Clear console
        self.console.configure(state="normal")
        self.console.delete("1.0", tk.END)
        self.console.configure(state="disabled")

        # Enforce start/stop requirement
        lines = [ln.strip() for ln in code.splitlines()]
        has_start = any(ln in ("Qude.prompt", "qude.str()", "q>") for ln in lines)
        has_stop = any(ln in ("Qude.kill/", "qude.end", "q<") for ln in lines)
        if not has_start or not has_stop:
            if not has_start and not has_stop:
                self._console_write("[Error] Kod 'başlat' ve 'bitir' komutlarını içermiyor (Qude.prompt / Qude.kill/).")
            elif not has_start:
                self._console_write("[Error] Kod 'başlat' komutu eksik: Qude.prompt (veya qude.str(), q>)")
            else:
                self._console_write("[Error] Kod 'bitir' komutu eksik: Qude.kill/ (veya qude.end, q<)")
            return

        try:
            # ensure normal window mode
            self.interpreter.preview_mode = False
            self.interpreter.preview_root = None
            # If previously in preview, interpreter.window may be a Frame.
            # Reset to force creating a new Toplevel window for normal run (F5).
            self.interpreter.window = None
            self.interpreter.run(code)
        except Exception as e:
            self._console_write(f"[Error] {e}")

    def run_preview(self) -> None:
        code = self.editor.get("1.0", tk.END)
        # Clear console
        self.console.configure(state="normal")
        self.console.delete("1.0", tk.END)
        self.console.configure(state="disabled")

        # Enforce start/stop requirement
        lines = [ln.strip() for ln in code.splitlines()]
        has_start = any(ln in ("Qude.prompt", "qude.str()", "q>") for ln in lines)
        has_stop = any(ln in ("Qude.kill/", "qude.end", "q<") for ln in lines)
        if not has_start or not has_stop:
            if not has_start and not has_stop:
                self._console_write("[Error] Kod 'başlat' ve 'bitir' komutlarını içermiyor (Qude.prompt / Qude.kill/).")
            elif not has_start:
                self._console_write("[Error] Kod 'başlat' komutu eksik: Qude.prompt (veya qude.str(), q>)")
            else:
                self._console_write("[Error] Kod 'bitir' komutu eksik: Qude.kill/ (veya qude.end, q<)")
            return

        # Prepare preview area
        self._clear_preview()
        try:
            self.interpreter.preview_mode = True
            self.interpreter.preview_root = self.preview_area
            self.interpreter.run(code)
        except Exception as e:
            self._console_write(f"[Error] {e}")

    def run(self) -> None:
        self.root.mainloop()

    def _show_version(self) -> None:
        try:
            messagebox.showinfo("Sürüm", "Qude 1.1")
        except Exception:
            pass

    def _publish_exe(self) -> None:
        code = self.editor.get("1.0", tk.END)
        save_path = filedialog.asksaveasfilename(
            title="EXE Olarak Yayınla",
            defaultextension=".exe",
            filetypes=[("Windows Uygulaması", "*.exe"), ("Tüm Dosyalar", "*.*")],
        )
        if not save_path:
            return
        app_name = os.path.splitext(os.path.basename(save_path))[0]

        # Check pyinstaller
        try:
            subprocess.run([sys.executable, "-m", "PyInstaller", "--version"], capture_output=True, text=True, check=True)
        except Exception:
            messagebox.showerror("Hata", "PyInstaller bulunamadı. Lütfen 'pip install pyinstaller' ile kurun.")
            return

        # Temp build folder
        tmpdir = tempfile.mkdtemp(prefix="qude_build_")
        try:
            runner_path = os.path.join(tmpdir, "pack_runner.py")
            with open(runner_path, "w", encoding="utf-8") as f:
                f.write(
                    "import tkinter as tk\n"
                    "from qude.interpreter import QudeInterpreter\n"
                    "\n"
                    "CODE = " + repr(code) + "\n"
                    "\n"
                    "def main():\n"
                    "    root = tk.Tk()\n"
                    "    try:\n"
                    "        root.withdraw()\n"
                    "    except Exception:\n"
                    "        pass\n"
                    "    def cw(msg: str):\n"
                    "        print(msg)\n"
                    "    interp = QudeInterpreter(cw, root)\n"
                    "    interp.preview_mode = False\n"
                    "    interp.preview_root = None\n"
                    "    interp.window = None\n"
                    "    interp.run(CODE)\n"
                    "    root.mainloop()\n"
                    "\n"
                    "if __name__ == '__main__':\n"
                    "    main()\n"
                )

            # Ensure local 'qude' package is available to the build by copying it next to runner
            try:
                pkg_src = os.path.dirname(__file__)
                pkg_dst = os.path.join(tmpdir, "qude")
                if os.path.isdir(pkg_dst):
                    shutil.rmtree(pkg_dst, ignore_errors=True)
                shutil.copytree(pkg_src, pkg_dst)
            except Exception as e:
                self._console_write(f"[Warn] Paket kopyalanamadı: {e}")

            # Build args
            args = [
                sys.executable, "-m", "PyInstaller",
                "--noconfirm", "--onefile", "--windowed",
                "--name", app_name,
                "--paths", tmpdir,
            ]
            if self.icon_bitmap_path and os.path.exists(self.icon_bitmap_path):
                # Prefer ICO if available
                args.extend(["--icon", self.icon_bitmap_path])
            # else try to locate q.ico near package
            else:
                ico_try = None
                for d in [os.path.dirname(__file__), os.path.dirname(os.path.dirname(__file__))]:
                    p = os.path.join(d, "q.ico")
                    if os.path.exists(p):
                        ico_try = p
                        break
                if ico_try:
                    args.extend(["--icon", ico_try])
            args.append(runner_path)

            # Log to console
            self._console_write(f"[Warn] Yayınlama başlıyor: {app_name}.exe")
            proc = subprocess.run(args, cwd=tmpdir, text=True, capture_output=True)
            if proc.stdout:
                for ln in proc.stdout.splitlines():
                    if ln.strip():
                        self._console_write(ln)
            if proc.returncode != 0:
                if proc.stderr:
                    self._console_write("[Error] PyInstaller:")
                    for ln in proc.stderr.splitlines():
                        if ln.strip():
                            self._console_write(ln)
                messagebox.showerror("Hata", "Yayınlama başarısız oldu. Konsolu kontrol edin.")
                return

            # Move output
            built_exe = os.path.join(tmpdir, "dist", f"{app_name}.exe")
            if not os.path.exists(built_exe):
                messagebox.showerror("Hata", "Oluşturulan EXE bulunamadı.")
                return
            try:
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                shutil.copy2(built_exe, save_path)
            except Exception as e:
                messagebox.showerror("Hata", f"EXE taşınamadı: {e}")
                return

            self._console_write(f"[Warn] Yayınlandı: {save_path}")
            messagebox.showinfo("Tamamlandı", f"Uygulama oluşturuldu:\n{save_path}")
        finally:
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass

    def _clear_preview(self) -> None:
        for child in self.preview_area.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass

    # ---------- Editor Auto-close ----------
    def _bind_autoclose(self) -> None:
        self.editor.bind("(", self._on_keypress_autoclose)
        self.editor.bind("[", self._on_keypress_autoclose)
        self.editor.bind("{", self._on_keypress_autoclose)
        self.editor.bind("'", self._on_keypress_autoclose)
        self.editor.bind('"', self._on_keypress_autoclose)

    def _on_keypress_autoclose(self, event) -> str:
        pairs = {
            '(': ')',
            '[': ']',
            '{': '}',
            "'": "'",
            '"': '"',
        }
        ch = event.char
        close = pairs.get(ch)
        if not close:
            return ""
        # Insert pair and move cursor back
        idx = self.editor.index(tk.INSERT)
        self.editor.insert(idx, ch + close)
        # move cursor one step left (before the closing char)
        self.editor.mark_set(tk.INSERT, f"{idx}+1c")
        return "break"

    # ---------- Theme ----------
    def _apply_dark_theme(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        # General colors
        bg = "#202225"
        fg = "#e6e6e6"
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TButton", padding=6)
        self.root.configure(bg=bg)

    def _apply_light_theme(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        bg = "#f2f2f2"
        fg = "#202225"
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TButton", padding=6)
        self.root.configure(bg=bg)

    def _set_theme(self, mode: str) -> None:
        self.theme = mode
        if mode == 'dark':
            self._apply_dark_theme()
            # widgets
            self.editor.configure(bg="#1e1f22", fg="#e6e6e6", insertbackground="#e6e6e6")
            self.console.configure(bg="#111315", fg="#eeeeee", insertbackground="#eeeeee")
        else:
            self._apply_light_theme()
            self.editor.configure(bg="#ffffff", fg="#202225", insertbackground="#202225")
            self.console.configure(bg="#f7f7f7", fg="#202225", insertbackground="#202225")
        # Re-highlight to ensure contrast remains fine
        self._highlight_all()

    # ---------- Icon ----------
    def _create_q_icon(self) -> tk.PhotoImage:
        img = tk.PhotoImage(width=32, height=32)
        bg = "#202225"
        fg = "#ffffff"
        # fill background
        for x in range(32):
            for y in range(32):
                img.put(bg, (x, y))
        # draw a block 'Q'
        for x in range(6, 26):
            img.put(fg, (x, 6))
            img.put(fg, (x, 25))
        for y in range(6, 26):
            img.put(fg, (6, y))
            img.put(fg, (25, y))
        # inner clear to create border
        for x in range(8, 24):
            for y in range(8, 24):
                img.put(bg, (x, y))
        # tail of Q (diagonal)
        for d in range(0, 6):
            x = 20 + d
            y = 20 + d
            if 0 <= x < 32 and 0 <= y < 32:
                img.put(fg, (x, y))
        return img

    def _load_icon_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Simge Seç (PNG/ICO)",
            filetypes=[("İkon Dosyası", "*.ico"), ("PNG", "*.png"), ("Tüm Dosyalar", "*.*")],
        )
        if not path:
            return
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext == ".ico":
                # Prefer ICO for Windows taskbar icon
                self.root.iconbitmap(path)
                self.icon_bitmap_path = path
                # keep a small photoimage too for widgets that rely on iconphoto
                try:
                    self.app_icon = tk.PhotoImage(width=32, height=32)
                    self.root.iconphoto(True, self.app_icon)
                except Exception:
                    pass
            else:
                # PNG: apply photo and try to convert to ICO for taskbar if Pillow is available
                self._apply_icon_from_path(path)
            # Update interpreter so child windows inherit
            self.interpreter.icon_image = self.app_icon
            self.interpreter.icon_bitmap_path = self.icon_bitmap_path
        except Exception as e:
            messagebox.showerror("Hata", f"Simge uygulanamadı: {e}")

    def _apply_icon_from_path(self, png_or_ico_path: str) -> None:
        ext = os.path.splitext(png_or_ico_path)[1].lower()
        if ext == ".ico":
            try:
                self.root.iconbitmap(png_or_ico_path)
                self.icon_bitmap_path = png_or_ico_path
            except Exception:
                pass
            try:
                self.app_icon = tk.PhotoImage(width=32, height=32)
                self.root.iconphoto(True, self.app_icon)
            except Exception:
                pass
            return
        # PNG path
        # Apply photo icon for title bar
        self.app_icon = tk.PhotoImage(file=png_or_ico_path)
        try:
            self.root.iconphoto(True, self.app_icon)
        except Exception:
            pass
        # Try convert PNG -> ICO using Pillow if available
        try:
            from PIL import Image  # type: ignore
            img = Image.open(png_or_ico_path)
            # ensure RGBA and size reasonable
            sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128)]
            tmp_ico = os.path.join(tempfile.gettempdir(), "qude_app_icon.ico")
            img.save(tmp_ico, sizes=sizes, format='ICO')
            self.root.iconbitmap(tmp_ico)
            self.icon_bitmap_path = tmp_ico
        except Exception:
            # Pillow yoksa veya dönüştürme başarısızsa iconbitmap uygulanamayabilir
            self.icon_bitmap_path = None

    # ---------- Splash (ICO) ----------
    def _locate_preferred_ico(self) -> str | None:
        # prefer an explicitly set ICO
        if self.icon_bitmap_path and os.path.exists(self.icon_bitmap_path):
            return self.icon_bitmap_path
        # else search common locations for q.ico
        base_dirs = [
            os.path.dirname(__file__),
            os.path.dirname(os.path.dirname(__file__)),
        ]
        if getattr(sys, "_MEIPASS", None):
            base_dirs.insert(0, getattr(sys, "_MEIPASS"))
        for d in base_dirs:
            p = os.path.join(d, "q.ico")
            if os.path.exists(p):
                return p
        return None

    def _show_splash_ico(self, duration_ms: int = 1500) -> None:
        ico_path = self._locate_preferred_ico()
        if not ico_path:
            return
        splash = tk.Toplevel(self.root)
        splash.overrideredirect(True)
        # Load ICO as image if Pillow is available; otherwise skip image splash
        img_obj = None
        if Image and ImageTk:
            try:
                img = Image.open(ico_path)
                # choose the largest available size/frame
                if hasattr(img, "n_frames"):
                    best = None
                    best_area = -1
                    for i in range(getattr(img, "n_frames", 1)):
                        img.seek(i)
                        w, h = img.size
                        if w * h > best_area:
                            best = img.copy()
                            best_area = w * h
                    img = best if best is not None else img
                # scale up moderately for visibility if too small
                w, h = img.size
                scale = 4 if max(w, h) <= 32 else 2 if max(w, h) <= 64 else 1
                if scale > 1:
                    img = img.resize((w * scale, h * scale), Image.LANCZOS)
                img_obj = ImageTk.PhotoImage(img)
            except Exception:
                img_obj = None
        if img_obj is None:
            # no pillow or failed -> minimal text splash
            frm = ttk.Frame(splash, padding=12)
            lbl = ttk.Label(frm, text="Qude", font=("Segoe UI", 16))
            frm.pack(fill=tk.BOTH, expand=True)
            lbl.pack()
        else:
            lbl = tk.Label(splash, image=img_obj, borderwidth=0, highlightthickness=0)
            lbl.image = img_obj  # keep ref
            lbl.pack()
        splash.update_idletasks()
        # center on screen
        sw = splash.winfo_screenwidth()
        sh = splash.winfo_screenheight()
        ww = splash.winfo_reqwidth()
        wh = splash.winfo_reqheight()
        x = (sw - ww) // 2
        y = (sh - wh) // 2
        splash.geometry(f"{ww}x{wh}+{x}+{y}")
        # auto-close
        self.root.after(duration_ms, splash.destroy)

    # ---------- File Ops ----------
    def _set_title(self) -> None:
        name = os.path.basename(self.current_file) if self.current_file else "Adsız"
        self.root.title(f"Qude IDE (Prototype) - {name}")

    def _new_file(self) -> None:
        self.editor.delete("1.0", tk.END)
        self.current_file = None
        self._set_title()
        self._highlight_all()

    def _open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Dosya Aç",
            filetypes=[("Qude Script", "*.q"), ("Tüm Dosyalar", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.editor.delete("1.0", tk.END)
            self.editor.insert("1.0", content)
            self.current_file = path
            self._set_title()
            self._highlight_all()
        except Exception as e:
            messagebox.showerror("Hata", f"Dosya açılamadı: {e}")

    def _save_file(self) -> None:
        if not self.current_file:
            return self._save_file_as()
        try:
            with open(self.current_file, "w", encoding="utf-8") as f:
                f.write(self.editor.get("1.0", tk.END))
        except Exception as e:
            messagebox.showerror("Hata", f"Kaydedilemedi: {e}")

    def _save_file_as(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Farklı Kaydet",
            defaultextension=".q",
            filetypes=[("Qude Script", "*.q"), ("Tüm Dosyalar", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.editor.get("1.0", tk.END))
            self.current_file = path
            self._set_title()
        except Exception as e:
            messagebox.showerror("Hata", f"Kaydedilemedi: {e}")

    # ---------- Syntax Highlight ----------
    def _setup_editor_highlight(self) -> None:
        # Base tokens
        self.editor.tag_configure("num", foreground="#ff66ff")  # numbers
        self.editor.tag_configure("str", foreground="#ffd166")  # strings

        # Define all language tokens (each will get a unique color)
        tokens = [
            # Çekirdek/Oturum
            "Qude.prompt", "qude.str()", "q>", "Qude.kill/", "qude.end", "q<",
            # Konsol
            "Qonsol.write", "qonsol.write", "qons.wrt",
            # Girdi Alma
            "taQe.putt", "tq.put", "q£",
            # Değişken/Matematik
            "Qurr", "qrr", "q$", "matq", "m;",
            # Pencere ve özellikler
            "Qwindow", "qwd", "qw",
            "uptext", "uptxt", "utxt",
            "geometry.size", "geom.sz", "ge.sz",
            "background.color", "bg.clr", "bgc",
            "resizable", "fullscreen",
            # Yazı (Label)
            "insert.text", "ins.txt", "i.tx",
            "font.color", "fnt.clr", "f$",
            "font.font", "fnt.font", "ffnt",
            "font.size", "fnt.sz", "fsz",
            "cordinates", "cordint", "c$",
            # Buton
            "insert.button", "ins.btn", "i.bt",
            "text", "txt", "tx",
            "text.color", "txt.clr", "t$",
            # Inputter
            "insert.inputter",
            # Warn screen and Wwindow
            "warn.screen", "Wwindow",
            # Kill commands
            "kill.qwindow/", "kill.wwindow/",
            # Match event
            "MatchEvent",
            # Event sistemi
            "event;", "LeftClickEvent", "RightClickEvent",
        ]

        # Generate an aesthetic distinct color palette and map to tokens
        palette = [
            "#e57373", "#f06292", "#ba68c8", "#9575cd", "#7986cb", "#64b5f6",
            "#4fc3f7", "#4dd0e1", "#4db6ac", "#81c784", "#aed581", "#dce775",
            "#fff176", "#ffd54f", "#ffb74d", "#ff8a65", "#a1887f", "#90a4ae",
            "#ff8c00", "#00c853", "#2979ff", "#8e24aa", "#ff5c8d", "#64dd17",
            "#1565c0", "#7e57c2", "#26a69a", "#42a5f5", "#26c6da", "#66bb6a",
        ]
        self._token_colors: dict[str, str] = {}
        for i, tok in enumerate(tokens):
            color = palette[i % len(palette)]
            self._token_colors[tok] = color
            tag = self._token_to_tag(tok)
            self.editor.tag_configure(tag, foreground=color)

        # Fallback for general function-like tokens
        self.editor.tag_configure("fn", foreground="#2ee07d")
        self.editor.bind("<<Modified>>", self._on_edit_modified)

        # Raise per-token tags above fallback and ensure strings/numbers on top
        try:
            self.editor.tag_raise("str")
            self.editor.tag_raise("num")
            for tok in tokens:
                self.editor.tag_raise(self._token_to_tag(tok), "fn")
        except Exception:
            pass

    def _on_edit_modified(self, _evt=None) -> None:
        # reset modified flag
        if self.editor.edit_modified():
            self._highlight_all()
            self.editor.edit_modified(False)

    def _highlight_all(self) -> None:
        text = self.editor.get("1.0", tk.END)
        # Clear existing tags
        clear_tags = ["fn", "num", "str"]
        if hasattr(self, "_token_colors"):
            clear_tags.extend(self._token_to_tag(t) for t in self._token_colors.keys())
        for tag in clear_tags:
            self.editor.tag_remove(tag, "1.0", tk.END)

        # Strings
        for m in re.finditer(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"", text):
            self._tag_range(m.start(), m.end(), "str")

        # Numbers
        for m in re.finditer(r"\b\d+(?:\.\d+)?\b", text):
            self._tag_range(m.start(), m.end(), "num")

        # Per-token patterns (exact literal search using regex-escaped tokens)
        if hasattr(self, "_token_colors"):
            for tok in self._token_colors.keys():
                pat = re.escape(tok)
                for m in re.finditer(pat, text):
                    self._tag_range(m.start(), m.end(), self._token_to_tag(tok))

        # Function-like shared properties (fallback)
        fn_patterns = [
            r"uptext|uptxt|utxt|geometry\.size|geom\.sz|ge\.sz|background\.color|bg\.clr|bgc|font\.color|fnt\.clr|f\$|font\.font|fnt\.font|ffnt|font\.size|fnt\.sz|fsz|text|txt|tx|text\.color|txt\.clr|t\$|cordinates|cordint|c\$",
        ]
        for pat in fn_patterns:
            for m in re.finditer(pat, text):
                self._tag_range(m.start(), m.end(), "fn")

    def _token_to_tag(self, token: str) -> str:
        # Create a safe tag name from token
        return "tok_" + re.sub(r"[^A-Za-z0-9_]+", "_", token)

    def _index_from_abs(self, abs_index: int) -> str:
        # Convert absolute index in full text to Tk text index
        prev = self.editor.get("1.0", tk.END)
        line = 1
        col = 0
        count = 0
        for ch in prev:
            if count == abs_index:
                return f"{line}.{col}"
            if ch == "\n":
                line += 1
                col = 0
            else:
                col += 1
            count += 1
        return f"{line}.{col}"

    def _tag_range(self, start_abs: int, end_abs: int, tag: str) -> None:
        start_index = self._index_from_abs(start_abs)
        end_index = self._index_from_abs(end_abs)
        self.editor.tag_add(tag, start_index, end_index)
