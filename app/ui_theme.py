"""Shared, standard-library-only visual tokens for the Tkinter applications."""

from __future__ import annotations

import tkinter.font as tkfont
from tkinter import ttk


COLORS = {
    "page": "#edf3ed",
    "surface": "#ffffff",
    "surface_alt": "#f5f8f4",
    "text": "#183b2e",
    "muted": "#52665a",
    "green": "#176b4b",
    "green_dark": "#104d37",
    "green_soft": "#dcebe0",
    "red": "#a63232",
    "red_soft": "#f8e7e4",
    "border": "#c8d5c9",
    "grid": "#d4dfd3",
    "food": "#c93632",
}


def system_font(root: object, size: int = 10, weight: str = "normal") -> tuple[str, int, str]:
    """Return a font based on Tk's active system default, with no named font dependency."""

    family = tkfont.nametofont("TkDefaultFont", root=root).actual("family")
    return family, size, weight


def apply_theme(root: object) -> ttk.Style:
    """Apply shared page, card, status, and button styles while keeping ttk controls."""

    root.configure(background=COLORS["page"])
    style = ttk.Style(root)
    style.configure("TFrame", background=COLORS["page"])
    style.configure("Card.TFrame", background=COLORS["surface"], borderwidth=1, relief="solid")
    style.configure("TLabel", foreground=COLORS["text"], font=system_font(root))
    style.configure("Title.TLabel", foreground=COLORS["green_dark"], font=system_font(root, 20, "bold"))
    style.configure(
        "Subtitle.TLabel",
        background=COLORS["page"],
        foreground=COLORS["muted"],
        font=system_font(root, 10),
    )
    style.configure(
        "CardHeading.TLabel",
        background=COLORS["surface"],
        foreground=COLORS["green_dark"],
        font=system_font(root, 12, "bold"),
    )
    style.configure("Card.TLabel", background=COLORS["surface"], foreground=COLORS["text"])
    style.configure("Question.TLabel", background=COLORS["surface"], foreground=COLORS["text"], font=system_font(root, 16, "bold"))
    style.configure("Muted.TLabel", background=COLORS["surface"], foreground=COLORS["muted"])
    style.configure("Success.TLabel", background=COLORS["surface"], foreground=COLORS["green_dark"], font=system_font(root, 11, "bold"))
    style.configure("Error.TLabel", background=COLORS["surface"], foreground=COLORS["red"], font=system_font(root, 11, "bold"))
    style.configure("Status.TLabel", foreground=COLORS["green_dark"], font=system_font(root, 10, "bold"))
    style.configure("StatusError.TLabel", foreground=COLORS["red"], font=system_font(root, 10, "bold"))
    style.configure("StatusSuccess.TLabel", foreground=COLORS["green_dark"], font=system_font(root, 10, "bold"))
    style.configure("Score.TLabel", foreground=COLORS["green_dark"], font=system_font(root, 14, "bold"))
    style.configure("TButton", padding=(10, 7), font=system_font(root, 10))
    style.configure("Primary.TButton", padding=(13, 8), font=system_font(root, 10, "bold"))
    style.configure("TEntry", padding=(6, 5), fieldbackground=COLORS["surface"])
    return style
