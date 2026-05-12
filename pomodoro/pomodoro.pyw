"""桌面番茄钟 - Tkinter 单文件实现。 test v2"""
from __future__ import annotations

import json
import threading
from datetime import date
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

try:
    import winsound  # Windows 提示音
except ImportError:
    winsound = None

CONFIG_PATH = Path.home() / ".pomodoro_config.json"

DEFAULT_CONFIG = {
    "work_minutes": 25,
    "short_break_minutes": 5,
    "long_break_minutes": 13,
    "sessions_until_long_break": 4,
    "auto_start": True,
    "always_on_top": False,
    "today": "",
    "today_completed": 0,
}

BG = "#1e1e2e"
FG = "#cdd6f4"
MUTED = "#6c7086"
SECONDARY = "#313244"
ACCENT = "#cba6f7"
WORK_COLOR = "#f38ba8"
SHORT_BREAK_COLOR = "#a6e3a1"
LONG_BREAK_COLOR = "#89b4fa"

PHASES = {
    "work": ("专注", WORK_COLOR),
    "short_break": ("短休息", SHORT_BREAK_COLOR),
    "long_break": ("长休息", LONG_BREAK_COLOR),
}


def format_mm_ss(total_seconds: int) -> str:
    """将剩余秒数格式化为 MM:SS；负数按 0 处理。"""
    s = max(0, int(total_seconds))
    m, sec = divmod(s, 60)
    return f"{m:02d}:{sec:02d}"


class PomodoroApp:
    """番茄钟应用程序主类"""
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.config = self._load_config()
        self._reset_today_if_needed()

        self.phase = "work"
        self.remaining = self._phase_seconds(self.phase)
        self.total = self.remaining
        self.running = False
        self.completed_sessions = 0
        self._after_id: str | None = None

        self._build_ui()
        self._apply_always_on_top()
        self._refresh()

    # ---------- 配置管理 ----------
    def _load_config(self) -> dict:
        """加载配置文件，仅合并默认配置中定义的键"""
        cfg = DEFAULT_CONFIG.copy()
        try:
            if CONFIG_PATH.exists():
                data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    cfg.update({k: data[k] for k in data if k in DEFAULT_CONFIG})
        except Exception:
            pass
        return cfg

    def _save_config(self) -> None:
        """保存配置文件到用户目录"""
        try:
            CONFIG_PATH.write_text(
                json.dumps(self.config, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _reset_today_if_needed(self) -> None:
        """检查并重置每日完成数"""
        today = date.today().isoformat()
        if self.config.get("today") != today:
            self.config["today"] = today
            self.config["today_completed"] = 0
            self._save_config()

    def _phase_seconds(self, phase: str) -> int:
        """将阶段时长转换为秒数"""
        key = {
            "work": "work_minutes",
            "short_break": "short_break_minutes",
            "long_break": "long_break_minutes",
        }[phase]
        return int(self.config[key]) * 60

    # ---------- UI 构建 ----------
    def _build_ui(self) -> None:
        self.root.title("番茄钟")
        self.root.geometry("420x580")
        self.root.minsize(420, 580)
        self.root.configure(bg=BG)

        top = tk.Frame(self.root, bg=BG)
        top.pack(pady=(22, 6))

        self.phase_label = tk.Label(
            top, text="专注", font=("Microsoft YaHei UI", 20, "bold"),
            bg=BG, fg=WORK_COLOR,
        )
        self.phase_label.pack()

        self.session_label = tk.Label(
            top, text="", font=("Microsoft YaHei UI", 11), bg=BG, fg=MUTED,
        )
        self.session_label.pack(pady=(4, 0))

        self.canvas_size = 300
        self.canvas = tk.Canvas(
            self.root, width=self.canvas_size, height=self.canvas_size,
            bg=BG, highlightthickness=0,
        )
        self.canvas.pack(pady=8)
        cx = cy = self.canvas_size // 2
        self.time_text_id = self.canvas.create_text(
            cx, cy, text=format_mm_ss(self.remaining),
            font=("Segoe UI", 52, "bold"), fill=FG,
        )

        btns = tk.Frame(self.root, bg=BG)
        btns.pack(pady=(8, 4))
        self.start_btn = self._mkbtn(btns, "开始", self.toggle_run, primary=True)
        self.start_btn.grid(row=0, column=0, padx=6)
        self._mkbtn(btns, "重置", self.reset).grid(row=0, column=1, padx=6)
        self._mkbtn(btns, "跳过", self.skip).grid(row=0, column=2, padx=6)

        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill="x", padx=24, pady=(14, 0))

        tk.Button(
            bar, text="设置", command=self.open_settings,
            font=("Microsoft YaHei UI", 10), bg=BG, fg=MUTED,
            activebackground=BG, activeforeground=FG, bd=0, cursor="hand2",
        ).pack(side="left")

        self.top_var = tk.BooleanVar(value=self.config["always_on_top"])
        tk.Checkbutton(
            bar, text="窗口置顶", variable=self.top_var, command=self._toggle_top,
            font=("Microsoft YaHei UI", 10), bg=BG, fg=MUTED,
            activebackground=BG, activeforeground=FG,
            selectcolor=SECONDARY, bd=0,
        ).pack(side="right")

        self.stats_label = tk.Label(
            self.root, text="", font=("Microsoft YaHei UI", 10),
            bg=BG, fg=MUTED,
        )
        self.stats_label.pack(side="bottom", pady=14)

    def _mkbtn(self, parent, text, cmd, primary=False) -> tk.Button:
        if primary:
            return tk.Button(
                parent, text=text, command=cmd,
                font=("Microsoft YaHei UI", 12, "bold"),
                bg=ACCENT, fg=BG, activebackground=ACCENT, activeforeground=BG,
                bd=0, padx=28, pady=9, cursor="hand2",
            )
        return tk.Button(
            parent, text=text, command=cmd,
            font=("Microsoft YaHei UI", 12),
            bg=SECONDARY, fg=FG, activebackground=SECONDARY, activeforeground=FG,
            bd=0, padx=22, pady=9, cursor="hand2",
        )

    # ---------- 画面刷新 ----------
    def _draw_ring(self) -> None:
        self.canvas.delete("ring")
        cx = cy = self.canvas_size // 2
        r = 130
        self.canvas.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            outline=SECONDARY, width=12, tags="ring",
        )
        if self.total > 0:
            pct = (self.total - self.remaining) / self.total
            extent = -360 * pct
            if extent != 0:
                color = PHASES[self.phase][1]
                self.canvas.create_arc(
                    cx - r, cy - r, cx + r, cy + r,
                    start=90, extent=extent,
                    outline=color, width=12, style="arc", tags="ring",
                )
        self.canvas.tag_raise(self.time_text_id)

    def _refresh(self) -> None:
        time_text = format_mm_ss(self.remaining)
        self.canvas.itemconfig(self.time_text_id, text=time_text)

        name, color = PHASES[self.phase]
        self.phase_label.config(text=name, fg=color)

        cycle = max(int(self.config["sessions_until_long_break"]), 1)
        if self.phase == "work":
            n = (self.completed_sessions % cycle) + 1
            self.session_label.config(text=f"第 {n} 个番茄  ·  本轮 {cycle} 个")
        else:
            self.session_label.config(text="休息一下 ☕")

        self.stats_label.config(
            text=f"今日完成: {self.config['today_completed']}  ·  本次启动: {self.completed_sessions}",
        )
        self.root.title(f"{time_text} - {name}")
        self._draw_ring()

    # ---------- 计时逻辑 ----------
    def toggle_run(self) -> None:
        if self.running:
            self.pause()
        else:
            self.start()

    def start(self) -> None:
        if self.remaining <= 0:
            self.remaining = self._phase_seconds(self.phase)
            self.total = self.remaining
        self.running = True
        self.start_btn.config(text="暂停")
        self._tick()

    def pause(self) -> None:
        self.running = False
        self.start_btn.config(text="继续")
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _tick(self) -> None:
        if not self.running:
            return
        if self.remaining <= 0:
            self._complete_phase()
            return
        self.remaining -= 1
        self._refresh()
        self._after_id = self.root.after(1000, self._tick)

    def reset(self) -> None:
        self.pause()
        self.remaining = self._phase_seconds(self.phase)
        self.total = self.remaining
        self.start_btn.config(text="开始")
        self._refresh()

    def skip(self) -> None:
        self.pause()
        self._advance_phase()
        self.start_btn.config(text="开始")
        self._refresh()

    def _complete_phase(self) -> None:
        self.running = False
        self._play_alert()
        if self.phase == "work":
            self.completed_sessions += 1
            self.config["today_completed"] = int(self.config.get("today_completed", 0)) + 1
            self._save_config()
        self._advance_phase()
        self._refresh()
        if self.config["auto_start"]:
            self.start()
        else:
            self.start_btn.config(text="开始")
            self._notify_phase_change()

    def _advance_phase(self) -> None:
        if self.phase == "work":
            cycle = max(int(self.config["sessions_until_long_break"]), 1)
            if self.completed_sessions > 0 and self.completed_sessions % cycle == 0:
                self.phase = "long_break"
            else:
                self.phase = "short_break"
        else:
            self.phase = "work"
        self.remaining = self._phase_seconds(self.phase)
        self.total = self.remaining

    def _play_alert(self) -> None:
        def beep() -> None:
            try:
                if winsound is not None:
                    for _ in range(2):
                        winsound.MessageBeep(winsound.MB_ICONASTERISK)
                else:
                    self.root.bell()
            except Exception:
                pass

        threading.Thread(target=beep, daemon=True).start()

    def _notify_phase_change(self) -> None:
        name = PHASES[self.phase][0]
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        except Exception:
            pass
        messagebox.showinfo("番茄钟", f"该 {name} 啦！", parent=self.root)

    # ---------- 窗口置顶控制 ----------
    def _toggle_top(self) -> None:
        self.config["always_on_top"] = bool(self.top_var.get())
        self._save_config()
        self._apply_always_on_top()

    def _apply_always_on_top(self) -> None:
        self.root.attributes("-topmost", bool(self.config["always_on_top"]))

    # ---------- 设置窗口 ----------
    def open_settings(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("设置")
        win.configure(bg=BG)
        win.geometry("360x340")
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)

        fields = [
            ("专注时长（分钟）", "work_minutes"),
            ("短休息（分钟）", "short_break_minutes"),
            ("长休息（分钟）", "long_break_minutes"),
            ("几个番茄后长休息", "sessions_until_long_break"),
        ]
        vars_: dict[str, tk.StringVar] = {}
        for i, (label, key) in enumerate(fields):
            tk.Label(
                win, text=label, bg=BG, fg=FG,
                font=("Microsoft YaHei UI", 10),
            ).grid(row=i, column=0, sticky="w", padx=22, pady=8)
            var = tk.StringVar(value=str(self.config[key]))
            vars_[key] = var
            tk.Entry(
                win, textvariable=var,
                bg=SECONDARY, fg=FG, insertbackground=FG, bd=0,
                font=("Segoe UI", 11), width=8, justify="center",
            ).grid(row=i, column=1, padx=22, pady=8, sticky="e")

        auto_var = tk.BooleanVar(value=self.config["auto_start"])
        tk.Checkbutton(
            win, text="结束后自动开始下一阶段",
            variable=auto_var,
            bg=BG, fg=FG, activebackground=BG, activeforeground=FG,
            selectcolor=SECONDARY, bd=0, font=("Microsoft YaHei UI", 10),
        ).grid(row=len(fields), column=0, columnspan=2,
               sticky="w", padx=22, pady=(10, 0))

        def save() -> None:
            try:
                new_vals = {}
                for key, var in vars_.items():
                    v = int(var.get())
                    if v < 1 or v > 600:
                        raise ValueError
                    new_vals[key] = v
            except ValueError:
                messagebox.showerror("错误", "请输入 1 - 600 之间的整数", parent=win)
                return
            self.config.update(new_vals)
            self.config["auto_start"] = bool(auto_var.get())
            self._save_config()
            if not self.running:
                self.remaining = self._phase_seconds(self.phase)
                self.total = self.remaining
                self._refresh()
            win.destroy()

        bar = tk.Frame(win, bg=BG)
        bar.grid(row=len(fields) + 1, column=0, columnspan=2, pady=20)
        tk.Button(
            bar, text="保存", command=save,
            bg=ACCENT, fg=BG, bd=0, padx=22, pady=6,
            font=("Microsoft YaHei UI", 10, "bold"), cursor="hand2",
        ).pack(side="left", padx=10)
        tk.Button(
            bar, text="取消", command=win.destroy,
            bg=SECONDARY, fg=FG, bd=0, padx=22, pady=6,
            font=("Microsoft YaHei UI", 10), cursor="hand2",
        ).pack(side="left", padx=10)


def main() -> None:
    root = tk.Tk()
    PomodoroApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
