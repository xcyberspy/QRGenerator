import customtkinter as ctk
import qrcode
from qrcode.constants import ERROR_CORRECT_H
from PIL import Image, ImageTk, ImageDraw
import pyperclip
import validators
import os
import threading
from tkinter import filedialog, colorchooser, messagebox

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_NAME = "QR Generator"
DEFAULT_QR_COLOR = "#000000"
PREVIEW_SIZE = 280

BG         = "#0A0A0A"
PANEL      = "#111111"
BORDER     = "#1F1F1F"
INPUT_BG   = "#0D0D0D"
INPUT_BRD  = "#2A2A2A"
ACCENT     = "#4DA6FF"
TEXT       = "#FFFFFF"
MUTED      = "#AAAAAA"
PREVIEW_BG = "#0D0D0D"
GREEN      = "#4CAF50"
PURPLE     = "#9B7FD4"


def normalize_url(text):
    s = text.strip()
    if s.lower().startswith("www."):
        return "https://" + s
    return s

def is_url(text):
    return validators.url(text) is True

def validate_input(text):
    if not text or not text.strip():
        return False, "Input cannot be empty."
    return True, ""

def generate_qr_image(data, qr_color="#000000", bg_color="#FFFFFF", logo_path=None):
    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_H, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color=qr_color, back_color=bg_color).convert("RGBA")
    if logo_path and os.path.isfile(logo_path):
        img = embed_logo(img, logo_path)
    return img

def embed_logo(qr_img, logo_path):
    logo = Image.open(logo_path).convert("RGBA")
    qr_w, qr_h = qr_img.size
    max_size = int(qr_w * 0.15)
    logo.thumbnail((max_size, max_size), Image.LANCZOS)
    lw, lh = logo.size
    pad = 4
    bg = Image.new("RGBA", (lw + pad*2, lh + pad*2), (255, 255, 255, 255))
    mask = Image.new("L", bg.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, bg.size[0]-1, bg.size[1]-1], radius=10, fill=255)
    bg.putalpha(mask)
    bg.paste(logo, (pad, pad), logo)
    pos = ((qr_w - bg.size[0]) // 2, (qr_h - bg.size[1]) // 2)
    out = qr_img.copy()
    out.paste(bg, pos, bg)
    return out

def resize_for_preview(img, size=PREVIEW_SIZE):
    r = img.copy()
    r.thumbnail((size, size), Image.LANCZOS)
    return ctk.CTkImage(light_image=r, dark_image=r, size=(size, size))


class QRGenerator(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.qr_image = None
        self.logo_path = None
        self.qr_color = DEFAULT_QR_COLOR
        self._pulse_running = False
        self._url_check_timer = None
        self._last_char_count = 0
        
        self.project_logo = None
        logo_file = os.path.join(os.path.dirname(__file__), "qr-code.png")
        if os.path.isfile(logo_file):
            logo_img = Image.open(logo_file)
            logo_img.thumbnail((28, 28), Image.LANCZOS)
            self.project_logo = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(28, 28))

        self.title(APP_NAME)
        self.geometry("920x660")
        self.minsize(820, 580)
        self.configure(fg_color=BG)
        
        icon_file = os.path.join(os.path.dirname(__file__), "icon.ico")
        if os.path.isfile(icon_file):
            self.iconbitmap(icon_file)
        
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window_width = 920
        window_height = 660
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")

        self._build_ui()

    def _build_ui(self):
        self._build_topbar()
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=(0, 14))
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=2)
        content.grid_rowconfigure(0, weight=1)
        self._build_left(content)
        self._build_right(content)
        self._build_statusbar()

    def _build_topbar(self):
        bar = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0, height=58)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tf = ctk.CTkFrame(bar, fg_color="transparent")
        tf.pack(side="left", padx=20, pady=10)
        if self.project_logo:
            ctk.CTkLabel(tf, text="", image=self.project_logo).pack(side="left")
        else:
            ctk.CTkLabel(tf, text="⬛", font=ctk.CTkFont(size=22), text_color=ACCENT).pack(side="left")
        ctk.CTkLabel(tf, text="  QR Generator",
                     font=ctk.CTkFont(family="Courier New", size=18, weight="bold"),
                     text_color="#FFFFFF").pack(side="left")

    def _build_left(self, parent):
        left = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=14, border_width=1, border_color=BORDER)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self._section(left, "01", "Content")
        self.input_box = ctk.CTkTextbox(
            left, height=90, corner_radius=10,
            fg_color=INPUT_BG, border_color=INPUT_BRD, border_width=1,
            font=ctk.CTkFont(family="Courier New", size=13),
            text_color=TEXT, wrap="word")
        self.input_box.pack(fill="x", padx=18, pady=(0, 4))
        self.input_box.insert("0.0", "https://example.com or any text…")
        self.input_box.bind("<FocusIn>", self._clear_placeholder)
        self.input_box.bind("<KeyRelease>", self._on_input_change)

        badge_row = ctk.CTkFrame(left, fg_color="transparent")
        badge_row.pack(fill="x", padx=20, pady=(2, 8))
        
        self.url_badge = ctk.CTkLabel(badge_row, text="", font=ctk.CTkFont(size=11), text_color=ACCENT, height=16)
        self.url_badge.pack(side="left", fill="x", expand=True)
        
        self.char_count_label = ctk.CTkLabel(badge_row, text="0/500", font=ctk.CTkFont(size=11), text_color=MUTED, height=16)
        self.char_count_label.pack(side="right")

        self._section(left, "02", "Colors")
        color_row = ctk.CTkFrame(left, fg_color="transparent")
        color_row.pack(fill="x", padx=18, pady=(0, 12))
        self.qr_color_btn = self._color_card(color_row, "QR Color", self.qr_color, self._pick_qr_color)
        self.qr_color_btn.pack(fill="x")

        self._section(left, "03", "Logo")
        logo_row = ctk.CTkFrame(left, fg_color="transparent", height=32)
        logo_row.pack(fill="x", padx=18, pady=(0, 16))
        logo_row.pack_propagate(False)

        self.logo_label = ctk.CTkLabel(logo_row, text="No logo selected Max size: 5000x5000 px",
                                       font=ctk.CTkFont(size=12), text_color=MUTED, width=200, anchor="w")
        self.logo_label.pack(side="left", fill="x", expand=True)

        self.remove_logo_btn = ctk.CTkButton(
            logo_row, text="✕", width=32, height=32,
            fg_color="#1A0A0A", hover_color="#2A1010",
            text_color="#FF6B6B", border_color="#FF6B6B", border_width=1,
            command=self._remove_logo)

        ctk.CTkButton(logo_row, text="+ Add Logo", width=100, height=32,
                      fg_color="#1A3A5C", hover_color="#1E4D7A",
                      border_color=ACCENT, border_width=1, text_color="#FFFFFF",
                      font=ctk.CTkFont(size=12, weight="bold"),
                      command=self._pick_logo).pack(side="right")

        self._build_action_buttons(left)

    def _build_action_buttons(self, parent):
        bf = ctk.CTkFrame(parent, fg_color="transparent")
        bf.pack(fill="x", padx=18, pady=(0, 18))
        bf.grid_columnconfigure((0, 1), weight=1)

        self.generate_btn = ctk.CTkButton(
            bf, text="Generate QR", height=46, corner_radius=10,
            fg_color="#2979FF", hover_color="#1565C0", text_color="#FFFFFF",
            font=ctk.CTkFont(family="Courier New", size=14, weight="bold"),
            state="disabled", command=self._on_generate)
        self.generate_btn.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        self.download_btn = ctk.CTkButton(
            bf, text="⬇ Download", height=38, corner_radius=10,
            fg_color="#1B5E20", hover_color="#2E7D32",
            border_color=GREEN, border_width=1, text_color="#FFFFFF",
            font=ctk.CTkFont(size=13, weight="bold"),
            state="disabled", command=self._on_download)
        self.download_btn.grid(row=1, column=0, sticky="ew", padx=(0, 5))

        self.copy_btn = ctk.CTkButton(
            bf, text="⎘ Copy Text", height=38, corner_radius=10,
            fg_color="#4A148C", hover_color="#6A1FAD",
            border_color=PURPLE, border_width=1, text_color="#FFFFFF",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._on_copy)
        self.copy_btn.grid(row=1, column=1, sticky="ew", padx=(5, 0))

    def _build_right(self, parent):
        right = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=14, border_width=1, border_color=BORDER)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)

        hdr = ctk.CTkFrame(right, fg_color=INPUT_BG, corner_radius=10, height=44)
        hdr.pack(fill="x", padx=14, pady=(14, 0))
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="Preview",
                     font=ctk.CTkFont(family="Courier New", size=13, weight="bold"),
                     text_color="#BBBBBB").pack(side="left", padx=14, pady=10)
        self.preview_badge = ctk.CTkLabel(hdr, text="● LIVE",
                                          font=ctk.CTkFont(size=10, weight="bold"),
                                          text_color="#333333")
        self.preview_badge.pack(side="right", padx=14)

        preview_bg = ctk.CTkFrame(right, fg_color=PREVIEW_BG, corner_radius=12)
        preview_bg.pack(fill="both", expand=True, padx=14, pady=14)

        self.placeholder_label = ctk.CTkLabel(
            preview_bg,
            text="⬛\n\nYour QR code\nwill appear here",
            font=ctk.CTkFont(family="Courier New", size=13),
            text_color=MUTED, justify="center")
        self.placeholder_label.place(relx=0.5, rely=0.5, anchor="center")

        self.preview_label = ctk.CTkLabel(preview_bg, text="", image=None)
        self.preview_label.place(relx=0.5, rely=0.5, anchor="center")

        self.meta_label = ctk.CTkLabel(right, text="", font=ctk.CTkFont(size=11), text_color="#AAAAAA")
        self.meta_label.pack(pady=(0, 14))

    def _build_statusbar(self):
        self.status_bar = ctk.CTkLabel(
            self, text=f"  {APP_NAME}  —  Ready",
            font=ctk.CTkFont(family="Courier New", size=11),
            text_color="#AAAAAA", anchor="w", height=24)
        self.status_bar.pack(fill="x", padx=20, pady=(0, 8))

    def _section(self, parent, num, title):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(16, 6))
        ctk.CTkLabel(row, text=num, font=ctk.CTkFont(family="Courier New", size=10, weight="bold"),
                     text_color=ACCENT, width=24, anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=title.upper(),
                     font=ctk.CTkFont(family="Courier New", size=11, weight="bold"),
                     text_color="#999999").pack(side="left", padx=6)
        ctk.CTkFrame(row, fg_color="#333333", height=1).pack(side="left", fill="x", expand=True)

    def _color_card(self, parent, label, color, command):
        frame = ctk.CTkFrame(parent, fg_color=INPUT_BG, corner_radius=8, border_width=1, border_color=INPUT_BRD)
        ctk.CTkLabel(frame, text=label, font=ctk.CTkFont(size=11), text_color="#BBBBBB").pack(anchor="w", padx=10, pady=(8, 2))
        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=(0, 8))
        swatch = ctk.CTkFrame(inner, fg_color=color, width=24, height=24, corner_radius=5,
                              border_width=1, border_color="#666666")
        swatch.pack(side="left")
        swatch.bind("<Button-1>", lambda e: command())
        hex_lbl = ctk.CTkLabel(inner, text=color.upper(),
                               font=ctk.CTkFont(family="Courier New", size=12), text_color="#CCCCCC")
        hex_lbl.pack(side="left", padx=8)
        ctk.CTkButton(inner, text="Edit", width=44, height=24,
                      fg_color="#1A1A1A", hover_color="#252525", text_color="#CCCCCC",
                      font=ctk.CTkFont(size=11), command=command).pack(side="right")
        frame._swatch = swatch
        frame._hex_lbl = hex_lbl
        return frame

    def _clear_placeholder(self, event):
        content = self.input_box.get("0.0", "end").strip()
        if content in ("https://example.com or any text…", ""):
            self.input_box.delete("0.0", "end")

    def _on_input_change(self, event=None):
        text = self.input_box.get("0.0", "end").strip()
        char_count = len(text)
        
        if char_count > 500:
            self.input_box.delete("0.0", "end")
            self.input_box.insert("0.0", text[:500])
            self.char_count_label.configure(text="500/500", text_color="#FF6B6B")
            self.url_badge.configure(text="⚠  500 character limit reached", text_color="#FF6B6B")
            self.generate_btn.configure(state="normal")
            return
        
        self.char_count_label.configure(text=f"{char_count}/500")
        
        if char_count == 0:
            color = MUTED
            self.generate_btn.configure(state="disabled")
        elif char_count < 300:
            color = GREEN
            self.generate_btn.configure(state="normal")
        elif char_count < 400:
            color = MUTED
            self.generate_btn.configure(state="normal")
        else:
            color = "#FFA500"
            self.generate_btn.configure(state="normal")
        
        self.char_count_label.configure(text_color=color)
        
        if self._url_check_timer:
            self.after_cancel(self._url_check_timer)
        
        self._url_check_timer = self.after(300, lambda: self._check_url_type(text))
    
    def _check_url_type(self, text):
        """Check if text is URL (debounced)"""
        self._url_check_timer = None
        if not text:
            self.url_badge.configure(text="")
        elif is_url(normalize_url(text)):
            self.url_badge.configure(text="🔗 URL detected", text_color=ACCENT)
        else:
            self.url_badge.configure(text="📝 Plain text mode", text_color="#AAAAAA")

    def _on_generate(self):
        raw = self.input_box.get("0.0", "end").strip()
        ok, err = validate_input(raw)
        if not ok:
            return
        data = normalize_url(raw)
        url_flag = is_url(data)
        self.generate_btn.configure(state="disabled", text="Generating…")
        self._set_status("Generating QR code…", color=ACCENT)
        self._start_pulse()

        def _run():
            try:
                img = generate_qr_image(data, self.qr_color, "#FFFFFF", self.logo_path)
                self.qr_image = img
                self.after(0, lambda: self._update_preview(img))
                self.after(0, lambda: self._on_success(data, url_flag))
            except Exception as ex:
                self.after(0, lambda: self._on_error(str(ex)))

        threading.Thread(target=_run, daemon=True).start()

    def _on_success(self, data, url_flag):
        self._stop_pulse()
        self.generate_btn.configure(state="normal", text="⬛  Generate QR")
        self.download_btn.configure(state="normal")
        self.preview_badge.configure(text="● LIVE", text_color=GREEN)
        self._set_status(f"✓  QR generated  ({len(data)} chars)", color=GREEN)
        kind = "URL" if url_flag else "Text"
        self.meta_label.configure(text=f"{kind}  ·  {len(data)} characters")

    def _on_error(self, msg):
        self._stop_pulse()
        self.generate_btn.configure(state="normal", text="Generate QR")
        self._set_status(f"✗  Error: {msg}", color="#CC2222")
        messagebox.showerror("Generation Error", msg, parent=self)

    def _update_preview(self, img):
        self.placeholder_label.place_forget()
        tk_img = resize_for_preview(img, PREVIEW_SIZE)
        self.preview_label.configure(image=tk_img)
        self.preview_label._image_ref = tk_img

    def _on_download(self):
        if not self.qr_image:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png"), ("JPEG Image", "*.jpg"), ("All Files", "*.*")],
            initialfile="qrcode.png", title="Save QR Code", parent=self)
        if not path:
            return
        try:
            save_img = self.qr_image.convert("RGB") if path.lower().endswith(".jpg") else self.qr_image
            save_img.save(path)
            self._set_status(f"✓  Saved: {os.path.basename(path)}", color=GREEN)
        except Exception as ex:
            messagebox.showerror("Save Error", str(ex), parent=self)

    def _on_copy(self):
        text = self.input_box.get("0.0", "end").strip()
        if not text:
            self._set_status("⚠  Nothing to copy", color="#CC2222")
            return
        try:
            pyperclip.copy(text)
            self._set_status("✓  Copied to clipboard", color=PURPLE)
        except Exception:
            self._set_status("✗  Copy failed", color="#CC2222")

    def _pick_qr_color(self):
        color = colorchooser.askcolor(title="Choose QR Color", color=self.qr_color, parent=self)
        if color and color[1]:
            self.qr_color = color[1]
            self.qr_color_btn._swatch.configure(fg_color=self.qr_color)
            self.qr_color_btn._hex_lbl.configure(text=self.qr_color.upper())
            self._set_status(f"QR color → {self.qr_color}", color=MUTED)

    def _pick_logo(self):
        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"), ("All Files", "*.*")],
            title="Select Logo Image", parent=self)
        if path:
            try:
                logo_img = Image.open(path)
                width, height = logo_img.size
                
                if width > 5000 or height > 5000:
                    self._set_status("✗  Logo exceeds 5000x5000 limit", color="#CC2222")
                    messagebox.showerror("Size Error", f"Logo size ({width}x{height}) exceeds maximum limit of 5000x5000 pixels", parent=self)
                    return
                
                self.logo_path = path
                name = os.path.basename(path)
                self.logo_label.configure(text=f"✓  {width}x{height}", text_color=GREEN)
                self.remove_logo_btn.pack(side="right", padx=(0, 6))
                self._set_status(f"Logo: {name} ({width}x{height})", color=GREEN)
            except Exception as ex:
                self._set_status(f"✗  Error loading logo", color="#CC2222")
                messagebox.showerror("Load Error", f"Failed to load logo: {str(ex)}", parent=self)

    def _remove_logo(self):
        self.logo_path = None
        self.logo_label.configure(text="No logo selected Max size: 5000x5000 px", text_color=MUTED)
        self.remove_logo_btn.pack_forget()
        self._set_status("Logo removed", color=MUTED)

    def _start_pulse(self):
        self._pulse_running = True
        self._pulse_step = 0
        self._pulse()

    def _stop_pulse(self):
        self._pulse_running = False

    def _pulse(self):
        if not self._pulse_running:
            return
        colors = [ACCENT, MUTED, ACCENT, MUTED]
        self.preview_badge.configure(text="● GENERATING",
                                     text_color=colors[self._pulse_step % len(colors)])
        self._pulse_step += 1
        self.after(350, self._pulse)

    def _set_status(self, msg, color=MUTED):
        self.status_bar.configure(text=f"  {msg}", text_color=color)


if __name__ == "__main__":
    app = QRGenerator()
    app.mainloop()