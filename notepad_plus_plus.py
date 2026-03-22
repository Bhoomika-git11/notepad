import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font
import os, re

# ── Theme ──────────────────────────────────────────────────────────────────────
THEME = {
    "bg":         "#2b2b2b",
    "tab_bar":    "#252526",
    "tab_bg":     "#2d2d2d",
    "tab_active": "#1e1e1e",
    "tab_border": "#007acc",
    "editor_bg":  "#1e1e1e",
    "editor_fg":  "#d4d4d4",
    "line_bg":    "#252526",
    "line_fg":    "#858585",
    "menu_bg":    "#3c3f41",
    "menu_fg":    "#d4d4d4",
    "toolbar_bg": "#333333",
    "status_bg":  "#007acc",
    "status_fg":  "#ffffff",
    "select_bg":  "#264f78",
    "cursor":     "#aeafad",
    "accent":     "#007acc",
    "find_bg":    "#2d2d2d",
    "find_fg":    "#d4d4d4",
    "btn_bg":     "#3c3c3c",
    "btn_hover":  "#505050",
}

SYNTAX = {
    "keyword":   "#569cd6",
    "string":    "#ce9178",
    "comment":   "#6a9955",
    "number":    "#b5cea8",
    "function":  "#dcdcaa",
    "class":     "#4ec9b0",
    "decorator": "#c586c0",
    "builtin":   "#4ec9b0",
}

PY_KEYWORDS  = r"\b(False|None|True|and|as|assert|async|await|break|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield)\b"
PY_BUILTINS  = r"\b(print|len|range|int|str|float|list|dict|set|tuple|bool|type|input|open|enumerate|zip|map|filter|sorted|reversed|sum|min|max|abs|round|isinstance|issubclass|hasattr|getattr|setattr|delattr|repr|id|hex|oct|bin|chr|ord|format|vars|dir|help|super|object|property|staticmethod|classmethod|Exception|ValueError|TypeError|KeyError|IndexError|AttributeError|ImportError|OSError|RuntimeError|StopIteration)\b"
PY_DECORATORS = r"@\w+"
PY_COMMENTS   = r"#[^\n]*"
PY_STRINGS3   = r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\''
PY_STRINGS1   = r'"[^"\n\\]*(?:\\.[^"\n\\]*)*"|\'[^\'\n\\]*(?:\\.[^\'\n\\]*)*\''
PY_NUMBERS    = r"\b\d+(\.\d+)?\b"
PY_FUNCS      = r"\bdef\s+(\w+)"
PY_CLASSES    = r"\bclass\s+(\w+)"


# ── Editor pane ────────────────────────────────────────────────────────────────
class EditorPane(tk.Frame):
    def __init__(self, master, filepath=None):
        super().__init__(master, bg=THEME["editor_bg"])
        self.filepath = filepath
        self.modified = False
        self.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        self.linenums = tk.Text(
            self, width=4, padx=6, pady=4, state="disabled", wrap="none",
            cursor="arrow", bg=THEME["line_bg"], fg=THEME["line_fg"],
            relief="flat", font=("Consolas", 11),
            selectbackground=THEME["line_bg"],
        )
        self.linenums.grid(row=0, column=0, sticky="ns")

        vbar = ttk.Scrollbar(self, orient="vertical")
        hbar = ttk.Scrollbar(self, orient="horizontal")
        vbar.grid(row=0, column=2, sticky="ns")
        hbar.grid(row=1, column=1, sticky="ew")

        self.editor = tk.Text(
            self, wrap="none", undo=True, padx=6, pady=4,
            bg=THEME["editor_bg"], fg=THEME["editor_fg"],
            insertbackground=THEME["cursor"],
            selectbackground=THEME["select_bg"],
            relief="flat", font=("Consolas", 11),
            yscrollcommand=lambda *a: (vbar.set(*a), self._sync_lines()),
            xscrollcommand=hbar.set,
        )
        self.editor.grid(row=0, column=1, sticky="nsew")
        vbar.config(command=self._on_vscroll)
        hbar.config(command=self.editor.xview)

        self.editor.bind("<KeyRelease>", self._on_key)
        self.editor.bind("<MouseWheel>", self._on_scroll)
        self.editor.bind("<Button-4>",   self._on_scroll)
        self.editor.bind("<Button-5>",   self._on_scroll)
        self.editor.bind("<<Modified>>", self._on_modified)

        # right-click context menu
        self._ctx = tk.Menu(self.editor, tearoff=False,
                            bg=THEME["menu_bg"], fg=THEME["menu_fg"],
                            activebackground=THEME["accent"], activeforeground="#fff",
                            relief="flat")
        for lbl, evt in [("Cut        Ctrl+X", "<<Cut>>"),
                         ("Copy      Ctrl+C",  "<<Copy>>"),
                         ("Paste      Ctrl+V", "<<Paste>>")]:
            self._ctx.add_command(label=lbl,
                command=lambda e=evt: self.editor.event_generate(e))
        self._ctx.add_separator()
        self._ctx.add_command(label="Select All  Ctrl+A",
            command=lambda: self.editor.tag_add("sel", "1.0", "end"))
        self._ctx.add_separator()
        self._ctx.add_command(label="Undo  Ctrl+Z",
            command=lambda: self.editor.edit_undo())
        self._ctx.add_command(label="Redo  Ctrl+Y",
            command=lambda: self.editor.edit_redo())
        self.editor.bind("<Button-3>", self._show_ctx)

        self._setup_tags()
        self._update_lines()
        self._on_modified_cb = None

    def _show_ctx(self, event):
        try:    self._ctx.tk_popup(event.x_root, event.y_root)
        finally: self._ctx.grab_release()

    def _setup_tags(self):
        e = self.editor
        e.tag_configure("keyword",   foreground=SYNTAX["keyword"])
        e.tag_configure("string",    foreground=SYNTAX["string"])
        e.tag_configure("comment",   foreground=SYNTAX["comment"])
        e.tag_configure("number",    foreground=SYNTAX["number"])
        e.tag_configure("function",  foreground=SYNTAX["function"])
        e.tag_configure("class_",    foreground=SYNTAX["class"])
        e.tag_configure("decorator", foreground=SYNTAX["decorator"])
        e.tag_configure("builtin",   foreground=SYNTAX["builtin"])
        e.tag_configure("found",     background="#515c47", foreground="#fff")
        e.tag_configure("current",   background="#264f78")

    def _on_vscroll(self, *a):
        self.editor.yview(*a); self._sync_lines()

    def _on_scroll(self, _=None):
        self._sync_lines()

    def _sync_lines(self):
        self.linenums.yview_moveto(self.editor.yview()[0])

    def _on_key(self, _=None):
        self._update_lines(); self._highlight()

    def _on_modified(self, _=None):
        if self.editor.edit_modified():
            self.modified = True
            self.editor.edit_modified(False)
            if self._on_modified_cb:
                self._on_modified_cb()

    def _update_lines(self):
        content = self.editor.get("1.0", "end-1c")
        lines = content.count("\n") + 1
        self.linenums.config(state="normal")
        self.linenums.delete("1.0", "end")
        self.linenums.insert("1.0", "\n".join(str(i) for i in range(1, lines+1)))
        self.linenums.config(state="disabled", width=max(3, len(str(lines)))+1)

    def _highlight(self):
        e = self.editor
        for tag in ("keyword","string","comment","number","function","class_","decorator","builtin"):
            e.tag_remove(tag, "1.0", "end")
        text = e.get("1.0", "end-1c")

        def apply(pat, tag, grp=0):
            for m in re.finditer(pat, text, re.MULTILINE):
                s, en = m.start(grp), m.end(grp)
                ls = text[:s].count("\n")+1;  cs = s  - text[:s].rfind("\n")  - 1
                le = text[:en].count("\n")+1; ce = en - text[:en].rfind("\n") - 1
                e.tag_add(tag, f"{ls}.{cs}", f"{le}.{ce}")

        apply(PY_STRINGS3,   "string")
        apply(PY_STRINGS1,   "string")
        apply(PY_COMMENTS,   "comment")
        apply(PY_DECORATORS, "decorator")
        apply(PY_KEYWORDS,   "keyword")
        apply(PY_BUILTINS,   "builtin")
        apply(PY_FUNCS,      "function", 1)
        apply(PY_CLASSES,    "class_",   1)
        apply(PY_NUMBERS,    "number")

    def get_text(self):
        return self.editor.get("1.0", "end-1c")

    def set_text(self, text):
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", text)
        self._update_lines(); self._highlight()
        self.modified = False


# ── Custom Tab Bar ─────────────────────────────────────────────────────────────
class TabBar(tk.Frame):
    def __init__(self, master, on_select, on_close):
        super().__init__(master, bg=THEME["tab_bar"], height=32)
        self.pack_propagate(False)
        self._on_select = on_select
        self._on_close  = on_close
        self._tabs = []   # list of dicts
        self._active = None

    def add(self, title, pane):
        frame = tk.Frame(self, bg=THEME["tab_bg"], padx=0, pady=0,
                         highlightthickness=0)
        frame.pack(side="left", fill="y", padx=(0, 1))

        title_lbl = tk.Label(frame, text=title,
                             bg=THEME["tab_bg"], fg="#aaaaaa",
                             font=("Segoe UI", 9), padx=10, pady=0)
        title_lbl.pack(side="left", fill="y")

        close_lbl = tk.Label(frame, text=" x ",
                             bg=THEME["tab_bg"], fg="#666666",
                             font=("Segoe UI", 9, "bold"), padx=4, pady=0,
                             cursor="hand2")
        close_lbl.pack(side="left", fill="y")

        tab = {"title": title, "pane": pane,
               "frame": frame, "lbl": title_lbl, "x": close_lbl}
        self._tabs.append(tab)

        for w in (frame, title_lbl):
            w.bind("<Button-1>", lambda e, p=pane: self._on_select(p))

        close_lbl.bind("<Button-1>", lambda e, p=pane: self._on_close(p))
        close_lbl.bind("<Enter>",
            lambda e, c=close_lbl, f=frame: [
                c.config(fg="#ff5555", bg="#3a3a3a"),
                f.config(bg="#3a3a3a")])
        close_lbl.bind("<Leave>",
            lambda e, t=tab: self._style(t))

        self.select(pane)

    def select(self, pane):
        self._active = pane
        for t in self._tabs:
            self._style(t)

    def remove(self, pane):
        for i, t in enumerate(self._tabs):
            if t["pane"] is pane:
                t["frame"].destroy()
                self._tabs.pop(i)
                return

    def refresh(self, pane):
        for t in self._tabs:
            if t["pane"] is pane:
                pre  = "* " if pane.modified else ""
                name = os.path.basename(pane.filepath) if pane.filepath else t["title"]
                t["lbl"].config(text=pre + name)
                self._style(t)
                return

    def _style(self, tab):
        on = tab["pane"] is self._active
        bg = THEME["tab_active"] if on else THEME["tab_bg"]
        fg = "#ffffff" if on else "#aaaaaa"
        xfg = "#999999" if on else "#555555"
        tab["frame"].config(bg=bg,
            highlightbackground=THEME["tab_border"] if on else bg,
            highlightthickness=1 if on else 0)
        tab["lbl"].config(bg=bg, fg=fg)
        tab["x"].config(bg=bg, fg=xfg)


# ── Find & Replace bar ─────────────────────────────────────────────────────────
class FindBar(tk.Frame):
    def __init__(self, master, get_editor):
        super().__init__(master, bg=THEME["find_bg"], pady=4)
        self.get_editor = get_editor
        self._results, self._idx = [], -1
        p = dict(padx=4, pady=2)

        tk.Label(self, text="Find:", bg=THEME["find_bg"], fg=THEME["find_fg"],
                 font=("Segoe UI", 9)).pack(side="left", **p)
        self.fv = tk.StringVar()
        fe = tk.Entry(self, textvariable=self.fv, width=22,
                      bg=THEME["editor_bg"], fg=THEME["editor_fg"],
                      insertbackground=THEME["cursor"], relief="flat",
                      font=("Consolas", 10))
        fe.pack(side="left", **p)
        fe.bind("<Return>",    lambda e: self.find_next())
        fe.bind("<KeyRelease>",lambda e: self._do_find())
        self.fe = fe

        tk.Label(self, text="Replace:", bg=THEME["find_bg"], fg=THEME["find_fg"],
                 font=("Segoe UI", 9)).pack(side="left", **p)
        self.rv = tk.StringVar()
        tk.Entry(self, textvariable=self.rv, width=18,
                 bg=THEME["editor_bg"], fg=THEME["editor_fg"],
                 insertbackground=THEME["cursor"], relief="flat",
                 font=("Consolas", 10)).pack(side="left", **p)

        for txt, cmd in [("Prev", self.find_prev), ("Next", self.find_next),
                         ("Replace", self.replace_one), ("All", self.replace_all),
                         ("Close", self.hide)]:
            tk.Button(self, text=txt, command=cmd,
                      bg=THEME["btn_bg"], fg=THEME["find_fg"], relief="flat",
                      activebackground=THEME["btn_hover"], activeforeground="#fff",
                      font=("Segoe UI", 9), padx=6, pady=1,
                      cursor="hand2").pack(side="left", **p)

        self.cnt = tk.Label(self, text="", bg=THEME["find_bg"],
                            fg=THEME["line_fg"], font=("Segoe UI", 9))
        self.cnt.pack(side="left", **p)
        self.cv = tk.BooleanVar()
        tk.Checkbutton(self, text="Aa", variable=self.cv, command=self._do_find,
                       bg=THEME["find_bg"], fg=THEME["find_fg"],
                       selectcolor=THEME["editor_bg"],
                       activebackground=THEME["find_bg"],
                       font=("Segoe UI", 9)).pack(side="left", **p)
        self.rx = tk.BooleanVar()
        tk.Checkbutton(self, text=".*", variable=self.rx, command=self._do_find,
                       bg=THEME["find_bg"], fg=THEME["find_fg"],
                       selectcolor=THEME["editor_bg"],
                       activebackground=THEME["find_bg"],
                       font=("Segoe UI", 9)).pack(side="left", **p)

    def show(self):
        self.pack(fill="x", side="bottom")
        self.fe.focus_set()

    def hide(self):
        self._clear(); self.pack_forget()

    def _clear(self):
        e = self.get_editor()
        if e:
            e.tag_remove("found",   "1.0", "end")
            e.tag_remove("current", "1.0", "end")

    def _do_find(self):
        e = self.get_editor()
        if not e: return
        self._clear(); self._results = []; self._idx = -1
        q = self.fv.get()
        if not q: self.cnt.config(text=""); return
        text  = e.get("1.0", "end-1c")
        flags = 0 if self.cv.get() else re.IGNORECASE
        try:
            pat = q if self.rx.get() else re.escape(q)
            for m in re.finditer(pat, text, flags):
                s, en = m.start(), m.end()
                ls = text[:s].count("\n")+1;  cs = s  - (text[:s].rfind("\n")+1)
                le = text[:en].count("\n")+1; ce = en - (text[:en].rfind("\n")+1)
                self._results.append((f"{ls}.{cs}", f"{le}.{ce}"))
                e.tag_add("found", f"{ls}.{cs}", f"{le}.{ce}")
        except re.error: pass
        n = len(self._results)
        self.cnt.config(text=f"{n} match{'es' if n!=1 else ''}")

    def _jump(self):
        e = self.get_editor()
        if not e or not self._results: return
        s, en = self._results[self._idx]
        e.tag_remove("current","1.0","end")
        e.tag_add("current", s, en); e.see(s)
        self.cnt.config(text=f"{self._idx+1}/{len(self._results)}")

    def find_next(self):
        if not self._results: self._do_find()
        if not self._results: return
        self._idx = (self._idx+1) % len(self._results); self._jump()

    def find_prev(self):
        if not self._results: self._do_find()
        if not self._results: return
        self._idx = (self._idx-1) % len(self._results); self._jump()

    def replace_one(self):
        e = self.get_editor()
        if not e or not self._results: return
        if self._idx < 0: self.find_next(); return
        s, en = self._results[self._idx]
        e.delete(s, en); e.insert(s, self.rv.get()); self._do_find()

    def replace_all(self):
        e = self.get_editor()
        if not e: return
        self._do_find()
        for s, en in reversed(self._results):
            e.delete(s, en); e.insert(s, self.rv.get())
        self._do_find()


# ── Main Application ───────────────────────────────────────────────────────────
class NotepadPP(tk.Tk):
    _counter = 0

    def __init__(self):
        super().__init__()
        self.title("Notepad++")
        self.geometry("1100x720")
        self.configure(bg=THEME["bg"])
        self._panes = []
        self._active = None
        self._build_ui()
        self._bind_shortcuts()
        self.new_tab()

    def _build_ui(self):
        self._style_ttk()
        self._build_menu()
        self._build_toolbar()
        self.tabbar = TabBar(self, on_select=self._switch_to,
                             on_close=self._close_pane)
        self.tabbar.pack(fill="x", side="top")
        self.content = tk.Frame(self, bg=THEME["editor_bg"])
        self.content.pack(fill="both", expand=True)
        self.findbar = FindBar(self.content, self._current_editor)
        self._build_statusbar()

    def _style_ttk(self):
        s = ttk.Style(self); s.theme_use("clam")
        s.configure("TScrollbar", background=THEME["btn_bg"],
                    troughcolor=THEME["editor_bg"], borderwidth=0, arrowsize=12)

    def _build_menu(self):
        bar = tk.Menu(self, bg=THEME["menu_bg"], fg=THEME["menu_fg"],
                      activebackground=THEME["accent"], activeforeground="#fff",
                      relief="flat", bd=0)
        self.config(menu=bar)

        def menu(label, items):
            m = tk.Menu(bar, tearoff=False, bg=THEME["menu_bg"], fg=THEME["menu_fg"],
                        activebackground=THEME["accent"], activeforeground="#fff",
                        relief="flat")
            bar.add_cascade(label=label, menu=m)
            for item in items:
                if item[0] == "---": m.add_separator()
                else:
                    lbl, cmd, *acc = item
                    m.add_command(label=lbl, command=cmd,
                                  **({"accelerator": acc[0]} if acc else {}))

        menu("File", [
            ("New",       self.new_tab,   "Ctrl+N"),
            ("Open...",   self.open_file, "Ctrl+O"),
            ("---",),
            ("Save",      self.save_file, "Ctrl+S"),
            ("Save As...",self.save_as,   "Ctrl+Shift+S"),
            ("---",),
            ("Close Tab", self.close_tab, "Ctrl+W"),
            ("Exit",      self.quit),
        ])
        menu("Edit", [
            ("Undo",       self._undo,       "Ctrl+Z"),
            ("Redo",       self._redo,       "Ctrl+Y"),
            ("---",),
            ("Cut",        self._cut,        "Ctrl+X"),
            ("Copy",       self._copy,       "Ctrl+C"),
            ("Paste",      self._paste,      "Ctrl+V"),
            ("Select All", self._select_all, "Ctrl+A"),
            ("---",),
            ("Find / Replace", self._show_find, "Ctrl+F"),
        ])
        menu("Format", [
            ("Font...",       self._change_font),
            ("Word Wrap",     self._toggle_wrap),
            ("Tab to Spaces", self._tabs_to_spaces),
            ("UPPER CASE",    self._upper),
            ("lower case",    self._lower),
            ("Title Case",    self._title),
        ])
        menu("View", [
            ("Zoom In",    self._zoom_in,    "Ctrl++"),
            ("Zoom Out",   self._zoom_out,   "Ctrl+-"),
            ("Reset Zoom", self._zoom_reset, "Ctrl+0"),
        ])
        menu("Help", [("About", self._about)])

    def _build_toolbar(self):
        tb = tk.Frame(self, bg=THEME["toolbar_bg"], pady=3)
        tb.pack(fill="x")
        self._tip_win = None

        def tip(w, text):
            def enter(_):
                x = w.winfo_rootx() + w.winfo_width()//2
                y = w.winfo_rooty() + w.winfo_height() + 4
                self._tip_win = tw = tk.Toplevel(self)
                tw.wm_overrideredirect(True)
                tw.wm_geometry(f"+{x}+{y}")
                tk.Label(tw, text=text, bg="#ffffe0", fg="#000",
                         relief="solid", bd=1,
                         font=("Segoe UI", 8), padx=6, pady=2).pack()
            def leave(_):
                if self._tip_win:
                    self._tip_win.destroy(); self._tip_win = None
            w.bind("<Enter>", enter); w.bind("<Leave>", leave)

        def btn(icon, cmd, label):
            b = tk.Button(tb, text=icon, command=cmd,
                          bg=THEME["toolbar_bg"], fg=THEME["menu_fg"],
                          relief="flat", padx=7, pady=3,
                          activebackground=THEME["btn_hover"],
                          activeforeground="#fff",
                          font=("Segoe UI", 10), cursor="hand2")
            b.pack(side="left", padx=1)
            tip(b, label); return b

        def sep():
            tk.Frame(tb, width=1, bg="#555").pack(
                side="left", fill="y", padx=4, pady=3)

        btn("🗋",  self.new_tab,    "New  (Ctrl+N)")
        btn("📂",  self.open_file,  "Open  (Ctrl+O)")
        btn("💾",  self.save_file,  "Save  (Ctrl+S)")
        sep()
        btn("↩",   self._undo,      "Undo  (Ctrl+Z)")
        btn("↪",   self._redo,      "Redo  (Ctrl+Y)")
        sep()
        btn("✂",   self._cut,       "Cut  (Ctrl+X)")
        btn("⎘",   self._copy,      "Copy  (Ctrl+C)")
        btn("📋",  self._paste,     "Paste  (Ctrl+V)")
        sep()
        btn("🔍",  self._show_find, "Find / Replace  (Ctrl+F)")
        sep()
        btn("⊕",   self._zoom_in,   "Zoom In  (Ctrl++)")
        btn("⊖",   self._zoom_out,  "Zoom Out  (Ctrl+-)")
        btn("↺",   self._zoom_reset,"Reset Zoom  (Ctrl+0)")

    def _build_statusbar(self):
        sb = tk.Frame(self, bg=THEME["status_bg"])
        sb.pack(fill="x", side="bottom")
        self.sl = tk.Label(sb, text="", bg=THEME["status_bg"], fg=THEME["status_fg"],
                           font=("Segoe UI", 8), anchor="w", padx=8)
        self.sl.pack(side="left")
        self.pl = tk.Label(sb, text="Ln 1, Col 1",
                           bg=THEME["status_bg"], fg=THEME["status_fg"],
                           font=("Segoe UI", 8), anchor="e", padx=8)
        self.pl.pack(side="right")
        tk.Label(sb, text="UTF-8", bg=THEME["status_bg"], fg=THEME["status_fg"],
                 font=("Segoe UI", 8), anchor="e", padx=8).pack(side="right")

    # ── Tab management ─────────────────────────────────────────────────────────
    def new_tab(self, filepath=None, content=None):
        NotepadPP._counter += 1
        title = os.path.basename(filepath) if filepath else f"new {NotepadPP._counter}"
        pane = EditorPane(self.content, filepath=filepath)
        pane.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._panes.append(pane)
        pane._on_modified_cb = lambda p=pane: self._on_pane_modified(p)
        if content is not None:
            pane.set_text(content)
            pane.modified = False
        self.tabbar.add(title, pane)
        self._switch_to(pane)
        return pane

    def _on_pane_modified(self, pane):
        self.tabbar.refresh(pane)

    def _switch_to(self, pane):
        for p in self._panes:
            p.place_forget()
        pane.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.findbar.lift()
        self._active = pane
        self.tabbar.select(pane)
        pane.editor.bind("<KeyRelease>",    lambda e: self._update_status())
        pane.editor.bind("<ButtonRelease>", lambda e: self._update_status())
        self._update_status()

    def _close_pane(self, pane):
        if len(self._panes) <= 1:
            return  # don't close the last tab
        if pane.modified:
            name = os.path.basename(pane.filepath) if pane.filepath else "Untitled"
            ans = messagebox.askyesnocancel("Close", f"Save '{name}' before closing?")
            if ans is None: return
            if ans:
                self._active = pane
                self.save_file()
        self.tabbar.remove(pane)
        self._panes.remove(pane)
        pane.destroy()
        if not self._panes: self.new_tab()
        else: self._switch_to(self._panes[-1])

    def _current_pane(self):
        return self._active

    def _current_editor(self):
        p = self._current_pane()
        return p.editor if p else None

    def _update_status(self):
        e = self._current_editor()
        if not e: return
        ln, col = map(int, e.index("insert").split("."))
        self.pl.config(text=f"Ln {ln}, Col {col+1}")
        p = self._current_pane()
        self.sl.config(text=os.path.abspath(p.filepath) if p and p.filepath else "Untitled")

    # ── File ops ───────────────────────────────────────────────────────────────
    def open_file(self, path=None):
        if path is None:
            path = filedialog.askopenfilename(
                filetypes=[("All Files","*.*"),("Python","*.py"),
                           ("Text","*.txt"),("Markdown","*.md")])
        if not path: return
        for p in self._panes:
            if p.filepath and os.path.abspath(p.filepath)==os.path.abspath(path):
                self._switch_to(p); return
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as ex:
            messagebox.showerror("Open", str(ex)); return
        pane = self.new_tab(path, content)
        self.tabbar.refresh(pane)
        self._update_status()

    def save_file(self):
        p = self._current_pane()
        if not p: return
        if not p.filepath: self.save_as(); return
        self._write(p)

    def save_as(self):
        p = self._current_pane()
        if not p: return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("All Files","*.*"),("Python","*.py"),("Text","*.txt")])
        if not path: return
        p.filepath = path
        self._write(p)

    def _write(self, p):
        try:
            with open(p.filepath, "w", encoding="utf-8") as f:
                f.write(p.get_text())
            p.modified = False
            self.tabbar.refresh(p)
            self._update_status()
        except Exception as ex:
            messagebox.showerror("Save", str(ex))

    def close_tab(self):
        p = self._current_pane()
        if p: self._close_pane(p)

    # ── Edit ───────────────────────────────────────────────────────────────────
    def _undo(self):
        e = self._current_editor()
        if e:
            try: e.edit_undo()
            except: pass

    def _redo(self):
        e = self._current_editor()
        if e:
            try: e.edit_redo()
            except: pass

    def _cut(self):
        e = self._current_editor()
        if e: e.event_generate("<<Cut>>")

    def _copy(self):
        e = self._current_editor()
        if e: e.event_generate("<<Copy>>")

    def _paste(self):
        e = self._current_editor()
        if e: e.event_generate("<<Paste>>")

    def _select_all(self):
        e = self._current_editor()
        if e: e.tag_add("sel", "1.0", "end")

    # ── Format ─────────────────────────────────────────────────────────────────
    def _change_font(self):
        p = self._current_pane()
        if not p: return
        top = tk.Toplevel(self); top.title("Font")
        top.configure(bg=THEME["bg"]); top.grab_set(); top.resizable(False, False)
        sv = tk.IntVar(value=11)
        tk.Label(top, text="Family:", bg=THEME["bg"], fg=THEME["menu_fg"],
                 font=("Segoe UI",9)).grid(row=0,column=0,padx=10,pady=8,sticky="w")
        fl = tk.Listbox(top, listvariable=tk.StringVar(value=list(font.families())),
                        height=10, width=28, bg=THEME["editor_bg"], fg=THEME["editor_fg"],
                        selectbackground=THEME["accent"], relief="flat", font=("Segoe UI",9))
        fl.grid(row=1,column=0,padx=10,sticky="ew")
        tk.Label(top, text="Size:", bg=THEME["bg"], fg=THEME["menu_fg"],
                 font=("Segoe UI",9)).grid(row=0,column=1,padx=10,pady=8,sticky="w")
        tk.Spinbox(top, from_=6, to=72, textvariable=sv, width=5,
                   bg=THEME["editor_bg"], fg=THEME["editor_fg"],
                   buttonbackground=THEME["btn_bg"], relief="flat",
                   font=("Consolas",11)).grid(row=1,column=1,padx=10,sticky="n")

        def apply():
            sel = fl.curselection()
            fam = fl.get(sel[0]) if sel else "Consolas"
            f = (fam, sv.get())
            p.editor.config(font=f); p.linenums.config(font=f); top.destroy()

        tk.Button(top, text="Apply", command=apply,
                  bg=THEME["accent"], fg="#fff", relief="flat",
                  font=("Segoe UI",9), padx=14, pady=4,
                  cursor="hand2").grid(row=2,column=0,columnspan=2,pady=10)

    def _toggle_wrap(self):
        e = self._current_editor()
        if e: e.config(wrap="word" if e.cget("wrap")=="none" else "none")

    def _tabs_to_spaces(self):
        e = self._current_editor()
        if not e: return
        t = e.get("1.0","end-1c").replace("\t","    ")
        e.delete("1.0","end"); e.insert("1.0",t)

    def _transform(self, fn):
        e = self._current_editor()
        if not e: return
        try: s, en = e.index("sel.first"), e.index("sel.last")
        except: return
        e.delete(s,en); e.insert(s, fn(e.get(s,en)))

    def _upper(self): self._transform(str.upper)
    def _lower(self): self._transform(str.lower)
    def _title(self): self._transform(str.title)

    # ── View ───────────────────────────────────────────────────────────────────
    def _zoom(self, d):
        p = self._current_pane()
        if not p: return
        f  = font.Font(font=p.editor.cget("font"))
        sz = max(6, min(72, f.actual("size")+d))
        nf = (f.actual("family"), sz)
        p.editor.config(font=nf); p.linenums.config(font=nf)

    def _zoom_in(self):    self._zoom(+1)
    def _zoom_out(self):   self._zoom(-1)
    def _zoom_reset(self):
        p = self._current_pane()
        if p:
            p.editor.config(font=("Consolas",11))
            p.linenums.config(font=("Consolas",11))

    def _show_find(self):
        self.findbar.show()

    def _about(self):
        messagebox.showinfo("About Notepad++",
            "Notepad++ Clone  -  Python + Tkinter\n\n"
            "Tabs with [x] close buttons\n"
            "Python syntax highlighting\n"
            "Line numbers, Find & Replace\n"
            "Toolbar with tooltips\n"
            "Right-click context menu\n"
            "Zoom, Font picker, Word Wrap")

    def _bind_shortcuts(self):
        b = self.bind
        b("<Control-n>",     lambda e: self.new_tab())
        b("<Control-o>",     lambda e: self.open_file())
        b("<Control-s>",     lambda e: self.save_file())
        b("<Control-S>",     lambda e: self.save_as())
        b("<Control-w>",     lambda e: self.close_tab())
        b("<Control-f>",     lambda e: self._show_find())
        b("<Control-equal>", lambda e: self._zoom_in())
        b("<Control-minus>", lambda e: self._zoom_out())
        b("<Control-0>",     lambda e: self._zoom_reset())
        b("<Control-z>",     lambda e: self._undo())
        b("<Control-y>",     lambda e: self._redo())
        b("<Control-a>",     lambda e: self._select_all())
        b("<Escape>",        lambda e: self.findbar.hide())


if __name__ == "__main__":
    app = NotepadPP()
    app.mainloop()
