"""
Crypto Check - a desktop crypto price checker built with CustomTkinter.

Type a coin's name ("Bitcoin") or ticker symbol ("BTC") and press Enter.
Prices come from the free CoinGecko API.
"""

import math
import queue
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path

import customtkinter as ctk
from PIL import Image

from . import __version__
from .crypto_api import CryptoAPIError, get_logo, get_market_data, search_coins

# --------------------------------------------------------------------------- #
# Look & feel
# --------------------------------------------------------------------------- #
# Colors are (light mode, dark mode) pairs, which CustomTkinter switches automatically.
BG = ("#eef0f5", "#11131a")
CARD = ("#ffffff", "#1b1e29")
TILE = ("#f4f5f9", "#242836")
MUTED = ("#6b7280", "#8b93a7")
TEXT = ("#111827", "#f3f4f6")
GREEN = ("#16a34a", "#22c55e")
RED = ("#dc2626", "#ef4444")
ACCENT = ("#3b82f6", "#3b82f6")
ACCENT_HOVER = ("#2563eb", "#2563eb")

CURRENCIES = {
    "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CAD": "C$",
    "AUD": "A$", "CHF": "CHF ", "INR": "₹", "BTC": "₿", "ETH": "Ξ",
}
POPULAR = ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA"]
ASSETS = Path(__file__).parent / "assets"
AUTO_REFRESH_MS = 60_000


# --------------------------------------------------------------------------- #
# Number formatting helpers
# --------------------------------------------------------------------------- #
def format_price(value, symbol):
    if value is None:
        return "—"
    if value == 0:
        return f"{symbol}0.00"
    if abs(value) >= 1:
        return f"{symbol}{value:,.2f}"
    # Tiny prices (e.g. SHIB) need more decimals: keep ~4 significant digits.
    decimals = min(12, -math.floor(math.log10(abs(value))) + 3)
    return f"{symbol}{value:.{decimals}f}"


def format_compact(value, prefix="", suffix=""):
    if value is None:
        return "—"
    for limit, unit in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(value) >= limit:
            return f"{prefix}{value / limit:,.2f}{unit}{suffix}"
    return f"{prefix}{value:,.2f}{suffix}"


def format_percent(value):
    if value is None:
        return "—"
    arrow = "▲" if value >= 0 else "▼"
    return f"{arrow} {abs(value):.2f}%"


def change_color(value):
    return GREEN if (value or 0) >= 0 else RED


def blend(hex_a, hex_b, amount):
    """Mix two #rrggbb colors. amount=0 -> a, amount=1 -> b. (Tk has no transparency.)"""
    a = [int(hex_a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(hex_b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * amount):02x}" for x, y in zip(a, b))


# --------------------------------------------------------------------------- #
# Widgets
# --------------------------------------------------------------------------- #
class Sparkline(ctk.CTkCanvas):
    """A 7-day price chart drawn on a plain canvas, with a hover tooltip."""

    PAD_X, PAD_Y = 12, 26

    def __init__(self, master, **kwargs):
        super().__init__(master, highlightthickness=0, borderwidth=0, **kwargs)
        self.prices = []
        self.currency_symbol = "$"
        self.bind("<Configure>", lambda _e: self.redraw())
        self.bind("<Motion>", self._on_hover)
        self.bind("<Leave>", lambda _e: self.delete("hover"))

    @staticmethod
    def _pick(color_pair):
        return color_pair[1] if ctk.get_appearance_mode() == "Dark" else color_pair[0]

    def set_data(self, prices, currency_symbol):
        self.prices = prices or []
        self.currency_symbol = currency_symbol
        self.redraw()

    def _point(self, i, price, low, high):
        w, h = self.winfo_width(), self.winfo_height()
        x = self.PAD_X + i / (len(self.prices) - 1) * (w - 2 * self.PAD_X)
        span = (high - low) or 1
        y = self.PAD_Y + (1 - (price - low) / span) * (h - 2 * self.PAD_Y)
        return x, y

    def redraw(self):
        self.delete("all")
        bg = self._pick(CARD)
        self.configure(bg=bg)
        if len(self.prices) < 2:
            self.create_text(
                self.winfo_width() / 2, self.winfo_height() / 2,
                text="No chart data", fill=self._pick(MUTED), font=("", 12),
            )
            return

        low, high = min(self.prices), max(self.prices)
        line = self._pick(GREEN if self.prices[-1] >= self.prices[0] else RED)
        points = [self._point(i, p, low, high) for i, p in enumerate(self.prices)]

        # Soft filled area under the line.
        bottom = self.winfo_height() - self.PAD_Y + 6  # leave room for the "Low" label
        area = [(points[0][0], bottom), *points, (points[-1][0], bottom)]
        self.create_polygon(area, fill=blend(line, bg, 0.82), outline="")
        self.create_line(points, fill=line, width=2, smooth=True)

        # High / low labels.
        muted = self._pick(MUTED)
        self.create_text(self.PAD_X, 2, anchor="nw", fill=muted, font=("", 10),
                         text=f"High {format_price(high, self.currency_symbol)}")
        self.create_text(self.PAD_X, self.winfo_height() - 2, anchor="sw", fill=muted, font=("", 10),
                         text=f"Low {format_price(low, self.currency_symbol)}")

    def _on_hover(self, event):
        self.delete("hover")
        if len(self.prices) < 2:
            return
        usable = self.winfo_width() - 2 * self.PAD_X
        i = round((event.x - self.PAD_X) / usable * (len(self.prices) - 1))
        i = max(0, min(len(self.prices) - 1, i))
        low, high = min(self.prices), max(self.prices)
        x, y = self._point(i, self.prices[i], low, high)

        text_color = self._pick(TEXT)
        self.create_line(x, self.PAD_Y / 2, x, self.winfo_height() - self.PAD_Y / 2,
                         fill=self._pick(MUTED), dash=(2, 3), tags="hover")
        self.create_oval(x - 4, y - 4, x + 4, y + 4, fill=text_color, outline="", tags="hover")

        hours_ago = len(self.prices) - 1 - i
        when = "now" if hours_ago == 0 else f"{hours_ago}h ago"
        label = f"{format_price(self.prices[i], self.currency_symbol)}  ·  {when}"
        anchor = "ne" if x > self.winfo_width() / 2 else "nw"
        offset = -8 if anchor == "ne" else 8
        self.create_text(x + offset, 2, anchor=anchor, text=label, fill=text_color,
                         font=("", 11, "bold"), tags="hover")


class StatTile(ctk.CTkFrame):
    def __init__(self, master, title):
        super().__init__(master, fg_color=TILE, corner_radius=12)
        ctk.CTkLabel(self, text=title.upper(), text_color=MUTED,
                     font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=14, pady=(10, 0))
        self.value = ctk.CTkLabel(self, text="—", text_color=TEXT, font=ctk.CTkFont(size=16, weight="bold"))
        self.value.pack(anchor="w", padx=14, pady=(0, 10))

    def set(self, text):
        self.value.configure(text=text)


# --------------------------------------------------------------------------- #
# Main window
# --------------------------------------------------------------------------- #
class CryptoApp(ctk.CTk):
    def __init__(self):
        # className sets the window class Linux docks use to match the window to its .desktop entry.
        super().__init__(fg_color=BG, className="CryptoCheck")
        self.title("Crypto Check")
        self.geometry("760x820")
        self.minsize(640, 760)
        self._set_icon()

        self.current_coin = None      # last market data dict we displayed
        self.alternatives = []        # other coins matching the last search
        self.logo_cache = {}          # image url -> PIL image
        self.logo_image = None        # keep a reference so Tk doesn't drop it
        self.auto_refresh_job = None

        # Background work posts results here; the Tk main loop picks them up.
        self.results = queue.Queue()
        self.request_id = 0

        self._build_header()
        self._build_search()
        self._build_card()
        self._build_footer()

        self.after(100, self._poll_results)
        self.search_entry.focus()
        self.check_price(coin_id="bitcoin")

    def _set_icon(self):
        if sys.platform == "win32":
            # CustomTkinter sets its own icon on Windows shortly after start-up, so apply ours after it.
            self.after(250, lambda: self.iconbitmap(str(ASSETS / "icon.ico")))
        else:
            self.icon_photo = tk.PhotoImage(file=str(ASSETS / "icon.png"))
            self.iconphoto(True, self.icon_photo)

    # ---------- layout ---------- #
    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=28, pady=(24, 8))

        app_logo = Image.open(ASSETS / "icon.png")
        self.header_logo = ctk.CTkImage(light_image=app_logo, dark_image=app_logo, size=(54, 54))
        ctk.CTkLabel(header, image=self.header_logo, text="").pack(side="left", padx=(0, 12))

        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.pack(side="left")
        ctk.CTkLabel(titles, text="Crypto Check", text_color=TEXT,
                     font=ctk.CTkFont(size=28, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(titles, text="Live prices for any coin, by name or symbol",
                     text_color=MUTED, font=ctk.CTkFont(size=13)).pack(anchor="w")

        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.pack(side="right")
        self.currency_var = ctk.StringVar(value="USD")
        ctk.CTkOptionMenu(
            controls, values=list(CURRENCIES), variable=self.currency_var, width=90,
            command=lambda _v: self.refresh(), fg_color=ACCENT, button_color=ACCENT_HOVER,
        ).pack(side="left", padx=(0, 12))

        self.dark_switch = ctk.CTkSwitch(controls, text="Dark", command=self._toggle_theme,
                                         progress_color=ACCENT, text_color=TEXT)
        self.dark_switch.select()
        self.dark_switch.pack(side="left")

    def _build_search(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=28, pady=(12, 0))

        self.search_entry = ctk.CTkEntry(
            bar, height=46, corner_radius=12, font=ctk.CTkFont(size=15),
            placeholder_text="Search a coin — e.g. Bitcoin, ETH, dogecoin, PEPE",
        )
        self.search_entry.pack(side="left", fill="x", expand=True)
        self.search_entry.bind("<Return>", lambda _e: self._on_search())

        self.search_button = ctk.CTkButton(
            bar, text="Check", width=110, height=46, corner_radius=12,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self._on_search,
        )
        self.search_button.pack(side="left", padx=(10, 0))

        chips = ctk.CTkFrame(self, fg_color="transparent")
        chips.pack(fill="x", padx=28, pady=(10, 0))
        ctk.CTkLabel(chips, text="Popular:", text_color=MUTED).pack(side="left", padx=(2, 8))
        for symbol in POPULAR:
            self._chip(chips, symbol, lambda s=symbol: self._quick_pick(s)).pack(side="left", padx=3)

        # "Did you mean" row, only shown when a search has other matches.
        self.alt_row = ctk.CTkFrame(self, fg_color="transparent")
        self.alt_inner = ctk.CTkFrame(self.alt_row, fg_color="transparent")
        self.alt_inner.pack(fill="x")

    def _chip(self, master, text, command):
        return ctk.CTkButton(
            master, text=text, command=command, height=28, width=10, corner_radius=14,
            fg_color=TILE, hover_color=("#e2e5ee", "#2f3446"), text_color=TEXT,
            font=ctk.CTkFont(size=12, weight="bold"),
        )

    def _build_card(self):
        self.card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=18)
        self.card.pack(fill="both", expand=True, padx=28, pady=16)

        # Top: logo, name, price.
        top = ctk.CTkFrame(self.card, fg_color="transparent")
        top.pack(fill="x", padx=22, pady=(22, 6))

        self.logo_label = ctk.CTkLabel(top, text="", width=56, height=56)
        self.logo_label.pack(side="left", padx=(0, 14))

        name_box = ctk.CTkFrame(top, fg_color="transparent")
        name_box.pack(side="left")
        self.name_label = ctk.CTkLabel(name_box, text="Loading…", text_color=TEXT,
                                       font=ctk.CTkFont(size=22, weight="bold"))
        self.name_label.pack(anchor="w")
        self.symbol_label = ctk.CTkLabel(name_box, text="", text_color=MUTED,
                                         font=ctk.CTkFont(size=13, weight="bold"))
        self.symbol_label.pack(anchor="w")

        price_box = ctk.CTkFrame(top, fg_color="transparent")
        price_box.pack(side="right")
        self.price_label = ctk.CTkLabel(price_box, text="—", text_color=TEXT,
                                        font=ctk.CTkFont(size=32, weight="bold"))
        self.price_label.pack(anchor="e")
        self.change_label = ctk.CTkLabel(price_box, text="", corner_radius=8, text_color="#ffffff",
                                         fg_color=GREEN, font=ctk.CTkFont(size=13, weight="bold"))
        self.change_label.pack(anchor="e", pady=(2, 0))

        # 1h / 24h / 7d changes.
        periods = ctk.CTkFrame(self.card, fg_color="transparent")
        periods.pack(fill="x", padx=22, pady=(8, 0))
        self.period_labels = {}
        for key, title in (("1h", "1H"), ("24h", "24H"), ("7d", "7D")):
            ctk.CTkLabel(periods, text=title, text_color=MUTED,
                         font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 6))
            label = ctk.CTkLabel(periods, text="—", font=ctk.CTkFont(size=13, weight="bold"))
            label.pack(side="left", padx=(0, 22))
            self.period_labels[key] = label

        # Chart.
        ctk.CTkLabel(self.card, text="LAST 7 DAYS", text_color=MUTED,
                     font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=22, pady=(16, 2))
        self.chart = Sparkline(self.card, height=170)
        self.chart.pack(fill="x", padx=12)

        # Stats grid.
        grid = ctk.CTkFrame(self.card, fg_color="transparent")
        grid.pack(fill="x", padx=22, pady=(14, 22))
        for col in range(3):
            grid.grid_columnconfigure(col, weight=1, uniform="stats")
        titles = ["Market cap", "24h volume", "Circulating supply", "24h high", "24h low", "All-time high"]
        self.stats = {}
        for i, title in enumerate(titles):
            tile = StatTile(grid, title)
            tile.grid(row=i // 3, column=i % 3, sticky="nsew", padx=5, pady=5)
            self.stats[title] = tile

    def _build_footer(self):
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=28, pady=(0, 18))

        self.status_label = ctk.CTkLabel(footer, text="", text_color=MUTED, font=ctk.CTkFont(size=12))
        self.status_label.pack(side="left")

        ctk.CTkLabel(footer, text=f"v{__version__}  ·  Data: CoinGecko", text_color=MUTED,
                     font=ctk.CTkFont(size=12)).pack(side="right")
        ctk.CTkButton(footer, text="⟳ Refresh", width=90, height=28, corner_radius=8,
                      fg_color=TILE, hover_color=("#e2e5ee", "#2f3446"), text_color=TEXT,
                      command=self.refresh).pack(side="right", padx=12)
        self.auto_switch = ctk.CTkSwitch(footer, text="Auto-refresh (60s)", command=self._toggle_auto_refresh,
                                         progress_color=ACCENT, text_color=MUTED, font=ctk.CTkFont(size=12))
        self.auto_switch.pack(side="right")

    # ---------- user actions ---------- #
    def _on_search(self):
        query = self.search_entry.get().strip()
        if query:
            self.check_price(query)

    def _quick_pick(self, symbol):
        self.search_entry.delete(0, "end")
        self.search_entry.insert(0, symbol)
        self.check_price(symbol)

    def _pick_alternative(self, coin):
        # Swap: the coin we were showing becomes one of the "did you mean" options.
        if self.current_coin:
            shown = {k: self.current_coin[k] for k in ("id", "name", "symbol")}
            self.alternatives = [shown] + [c for c in self.alternatives if c["id"] != coin["id"]]
        self.check_price(coin_id=coin["id"])

    def refresh(self):
        if self.current_coin:
            self.check_price(coin_id=self.current_coin["id"], quiet=True)

    def _toggle_theme(self):
        ctk.set_appearance_mode("dark" if self.dark_switch.get() else "light")
        self.after(50, self.chart.redraw)  # the canvas doesn't recolor on its own

    def _toggle_auto_refresh(self):
        if self.auto_refresh_job:
            self.after_cancel(self.auto_refresh_job)
            self.auto_refresh_job = None
        if self.auto_switch.get():
            self._auto_refresh_tick()

    def _auto_refresh_tick(self):
        self.refresh()
        self.auto_refresh_job = self.after(AUTO_REFRESH_MS, self._auto_refresh_tick)

    # ---------- fetching (runs off the UI thread) ---------- #
    def check_price(self, query=None, coin_id=None, quiet=False):
        """Look up a coin by search text, or directly by CoinGecko id."""
        currency = self.currency_var.get().lower()
        self.request_id += 1
        request_id = self.request_id

        if not quiet:
            self.search_button.configure(text="Checking…", state="disabled")
        self._set_status("Fetching latest prices…")

        def work():
            try:
                alternatives = None
                coin = coin_id
                if coin is None:
                    matches = search_coins(query)
                    coin = matches[0]["id"]
                    alternatives = matches[1:5]
                market = get_market_data(coin, currency)
                url = market.get("image")
                if url and url not in self.logo_cache:
                    self.logo_cache[url] = get_logo(url, size=56)
                self.results.put((request_id, self._show_result, (market, alternatives)))
            except CryptoAPIError as e:
                self.results.put((request_id, self._show_error, str(e)))
            except Exception as e:  # never let a worker crash silently
                self.results.put((request_id, self._show_error, f"Unexpected error: {e}"))

        threading.Thread(target=work, daemon=True).start()

    def _poll_results(self):
        try:
            while True:
                request_id, callback, payload = self.results.get_nowait()
                if request_id == self.request_id:  # ignore results from older, superseded requests
                    callback(payload)
        except queue.Empty:
            pass
        self.after(100, self._poll_results)

    # ---------- rendering ---------- #
    def _show_result(self, payload):
        market, alternatives = payload
        self.current_coin = market
        if alternatives is not None:
            self.alternatives = alternatives
        self.search_button.configure(text="Check", state="normal")

        sym = CURRENCIES[self.currency_var.get()]
        ticker = market["symbol"].upper()

        logo = self.logo_cache.get(market.get("image"))
        if logo:
            self.logo_image = ctk.CTkImage(light_image=logo, dark_image=logo, size=(56, 56))
            self.logo_label.configure(image=self.logo_image)
        rank = market.get("market_cap_rank")
        self.name_label.configure(text=market["name"])
        self.symbol_label.configure(text=f"{ticker}" + (f"   ·   Rank #{rank}" if rank else ""))

        self.price_label.configure(text=format_price(market.get("current_price"), sym))
        change_24h = market.get("price_change_percentage_24h")
        self.change_label.configure(text=f"  {format_percent(change_24h)}  24h  ", fg_color=change_color(change_24h))

        for key, label in self.period_labels.items():
            value = market.get(f"price_change_percentage_{key}_in_currency")
            label.configure(text=format_percent(value), text_color=change_color(value))

        self.chart.set_data((market.get("sparkline_in_7d") or {}).get("price"), sym)

        self.stats["Market cap"].set(format_compact(market.get("market_cap"), sym))
        self.stats["24h volume"].set(format_compact(market.get("total_volume"), sym))
        self.stats["Circulating supply"].set(format_compact(market.get("circulating_supply"), suffix=f" {ticker}"))
        self.stats["24h high"].set(format_price(market.get("high_24h"), sym))
        self.stats["24h low"].set(format_price(market.get("low_24h"), sym))
        self.stats["All-time high"].set(format_price(market.get("ath"), sym))

        self._render_alternatives()
        self._set_status(f"Updated {datetime.now():%I:%M:%S %p}")

    def _render_alternatives(self):
        for child in self.alt_inner.winfo_children():
            child.destroy()
        if not self.alternatives:
            self.alt_row.pack_forget()
            return
        ctk.CTkLabel(self.alt_inner, text="Not it? Try:", text_color=MUTED).pack(side="left", padx=(2, 8))
        for coin in self.alternatives:
            name = coin["name"] if len(coin["name"]) <= 16 else coin["name"][:15] + "…"
            text = f"{name} ({coin['symbol'].upper()})"
            self._chip(self.alt_inner, text, lambda c=coin: self._pick_alternative(c)).pack(side="left", padx=3)
        self.alt_row.pack(fill="x", padx=28, pady=(8, 0), before=self.card)

    def _show_error(self, message):
        self.search_button.configure(text="Check", state="normal")
        self._set_status(message, error=True)

    def _set_status(self, text, error=False):
        self.status_label.configure(text=text, text_color=RED if error else MUTED)


def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    CryptoApp().mainloop()


if __name__ == "__main__":
    main()
