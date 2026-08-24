"""Job Hunter — Desktop App (CustomTkinter).
Run: python job_search_app.py
"""
import threading
import webbrowser

import customtkinter as ctk
import tkinter.filedialog as fd
import tkinter.messagebox as mb

import icons
import scrapers
import matcher
import cv_parser
import database
import stats as stats_mod          # see note below*
from apply_helper import apply_to_job

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ---- Design tokens ----------------------------------------------------------
# Validated against ui-ux-pro-max's "Developer Tool" / "Financial Dashboard"
# dark palettes: BG/SURFACE/BORDER/TEXT_DIM/DANGER match those presets almost
# exactly. CARD is a slightly warmer, separate tone from SURFACE so nested
# cards read as a distinct depth layer from the toolbar/chrome around them.
BG = "#0f172a"
SURFACE = "#1e293b"
CARD = "#1b2336"
SURFACE_ALT = "#25314a"
BORDER = "#334155"
TEXT = "#e2e8f0"
TEXT_DIM = "#94a3b8"
ACCENT = "#2563eb"
ACCENT_HOVER = "#1d4ed8"
SUCCESS = "#22c55e"
WARNING = "#eab308"
DANGER = "#ef4444"
NEUTRAL = "#64748b"

STATUS_COLORS = {"Applied": NEUTRAL, "Follow-up sent": ACCENT,
                  "Interview": SUCCESS, "Offer": "#16a34a",
                  "Rejected": DANGER, "Ghosted": TEXT_DIM}

FONT_TITLE = ("Segoe UI", 20, "bold")
FONT_SUBTITLE = ("Segoe UI", 12)
FONT_CARD_TITLE = ("Segoe UI", 14, "bold")
FONT_BODY = ("Segoe UI", 12)
FONT_SMALL = ("Segoe UI", 11)
FONT_STAT = ("Segoe UI", 26, "bold")


class JobHunterApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Job Hunter")
        self.geometry("1160x760")
        self.configure(fg_color=BG)
        self.profile = None
        self._icon_cache = {}

        self._build_header()

        tabs = ctk.CTkTabview(self, fg_color=BG, segmented_button_fg_color=SURFACE,
                              segmented_button_selected_color=ACCENT,
                              segmented_button_selected_hover_color=ACCENT_HOVER,
                              segmented_button_unselected_color=SURFACE,
                              text_color=TEXT)
        tabs.pack(fill="both", expand=True, padx=16, pady=(4, 16))
        self.tabview = tabs
        self.tab_search = tabs.add("Search")
        self.tab_tracker = tabs.add("Tracker")
        self.tab_favorites = tabs.add("Favorites")
        self.tab_stats = tabs.add("Stats")

        self._build_search_tab()
        self._build_tracker_tab()
        self._build_favorites_tab()
        self._build_stats_tab()

    # ================= HEADER =================
    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=BG)
        header.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(header, text="Job Hunter", font=FONT_TITLE,
                     text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(header, text="Search, match, and track jobs across every site in one place.",
                     font=FONT_SUBTITLE, text_color=TEXT_DIM).pack(anchor="w")

    # ================= ICON HELPER =================
    def site_icon(self, site: str, size=(20, 20)):
        """Lazily builds a CTkImage for a site logo. Main-thread only."""
        key = (site, size)
        if key in self._icon_cache:
            return self._icon_cache[key]
        pil_img = icons.get_pil_image(site)
        img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size) if pil_img else None
        self._icon_cache[key] = img
        return img

    # ================= SEARCH TAB =================
    def _build_search_tab(self):
        tab = self.tab_search

        toolbar = ctk.CTkFrame(tab, fg_color=SURFACE, corner_radius=12,
                               border_width=1, border_color=BORDER)
        toolbar.pack(fill="x", pady=(8, 10))

        row1 = ctk.CTkFrame(toolbar, fg_color="transparent")
        row1.pack(fill="x", padx=16, pady=(14, 8))

        self.query_entry = ctk.CTkEntry(row1, placeholder_text="Job title or keyword...",
                                        width=300, height=36, corner_radius=8)
        self.query_entry.pack(side="left", padx=(0, 10))
        self.query_entry.bind("<Return>", lambda e: self.start_search())

        self.site_menu = ctk.CTkOptionMenu(
            row1, values=["All sites"] + list(scrapers.SITES.keys()),
            width=160, height=36, corner_radius=8,
            fg_color=ACCENT, button_color=ACCENT, button_hover_color=ACCENT_HOVER)
        self.site_menu.pack(side="left", padx=6)
        self.site_menu.set("All sites")

        self.remote_var = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(row1, text="Remote only", variable=self.remote_var,
                      progress_color=ACCENT, text_color=TEXT).pack(side="left", padx=14)

        ctk.CTkButton(row1, text="Search", width=110, height=36, corner_radius=8,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self.start_search).pack(side="left", padx=(14, 0))

        row2 = ctk.CTkFrame(toolbar, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=(0, 14))

        self.cv_label = ctk.CTkLabel(row2, text="No CV loaded", font=FONT_SMALL,
                                     text_color=TEXT_DIM)
        self.cv_label.pack(side="left", padx=(0, 10))
        ctk.CTkButton(row2, text="Upload CV", width=110, height=28, corner_radius=6,
                      fg_color=SURFACE_ALT, hover_color=BORDER, text_color=TEXT,
                      command=self.upload_cv).pack(side="left", padx=4)

        ctk.CTkLabel(row2, text="Min match:", font=FONT_SMALL,
                     text_color=TEXT_DIM).pack(side="left", padx=(20, 6))
        self.thresh_slider = ctk.CTkSlider(row2, from_=30, to=95, width=160,
                                           number_of_steps=13, progress_color=ACCENT,
                                           button_color=ACCENT, button_hover_color=ACCENT_HOVER)
        self.thresh_slider.set(50)
        self.thresh_slider.pack(side="left")
        self.thresh_lbl = ctk.CTkLabel(row2, text="50%", width=40, font=FONT_SMALL,
                                       text_color=TEXT)
        self.thresh_lbl.pack(side="left", padx=(6, 0))
        self.thresh_slider.configure(command=lambda v: self.thresh_lbl.configure(text=f"{int(v)}%"))

        self.status_lbl = ctk.CTkLabel(tab, text="", font=FONT_SMALL, text_color=TEXT_DIM)
        self.status_lbl.pack(anchor="w", pady=(0, 6))

        self.results_frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.results_frame.pack(fill="both", expand=True)

    def upload_cv(self):
        path = fd.askopenfilename(filetypes=[("CV files", "*.pdf *.docx *.doc")])
        if not path:
            return
        try:
            self.profile = cv_parser.CVProfile(path)
        except Exception as e:
            mb.showerror("CV Error", str(e))
            return
        self.cv_label.configure(text=self.profile.summary(), text_color=SUCCESS)

    def start_search(self):
        query = self.query_entry.get().strip() or "Accounting"
        if self.site_menu.get() == "All sites":
            sites = list(scrapers.SITES.keys())
        else:
            sites = [self.site_menu.get()]
        if self.remote_var.get():
            remote_sites = [s for s in sites if s in
                            ("Remotive", "RemoteOK", "WeWorkRemotely")]
            sites = remote_sites or ["Remotive", "RemoteOK"]

        self.status_lbl.configure(text=f"Searching '{query}' on "
                                       f"{len(sites)} site(s)...")
        threading.Thread(target=self._search_worker,
                         args=(query, sites), daemon=True).start()

    def _search_worker(self, query, sites):
        jobs = scrapers.fetch_all(sites, query)
        if self.profile:
            jobs = matcher.rank_jobs(jobs, self.profile)
            thresh = int(self.thresh_slider.get())
            jobs = [j for j in jobs if j["score"] >= thresh] or \
                   sorted(jobs, key=lambda x: x["score"], reverse=True)[:10]
        # pre-warm the icon cache off the UI thread (network only, no Tk objects)
        for site in {j["site"] for j in jobs}:
            icons.get_pil_image(site)
        self.after(0, self.show_results, jobs)

    def show_results(self, jobs):
        for w in self.results_frame.winfo_children():
            w.destroy()
        if not jobs:
            self.status_lbl.configure(text="No jobs found")
            return
        for j in jobs:
            self.add_result_card(j)
        extra = ""
        if self.profile and jobs and "score" in jobs[0]:
            extra = f" · best match {jobs[0]['score']}%"
        self.status_lbl.configure(text=f"{len(jobs)} jobs found{extra}")

    def add_result_card(self, job):
        score = job.get("score")
        accent = matcher.color_for(score) if score is not None else ACCENT

        # NOTE: this card lives inside a CTkScrollableFrame. pack(side="right")
        # content there gets silently clipped (its logical width doesn't match
        # the visible viewport) — so everything here flows left-to-right/
        # top-to-bottom instead of anchoring anything to the right edge.
        card = ctk.CTkFrame(self.results_frame, fg_color=CARD, corner_radius=12,
                            border_width=1, border_color=BORDER)
        card.pack(fill="x", pady=6, padx=2)

        # height=1 overrides CTkFrame's default height (200, scaled by DPI) —
        # without it, fill="y" stretches the whole row to match that default
        # instead of shrinking the bar to the row's actual content height.
        ctk.CTkFrame(card, fg_color=accent, corner_radius=0,
                     width=4, height=1).pack(side="left", fill="y")

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(side="left", fill="both", expand=True, padx=14, pady=12)

        header_row = ctk.CTkFrame(body, fg_color="transparent")
        header_row.pack(fill="x", anchor="w")

        icon = self.site_icon(job["site"])
        if icon:
            ctk.CTkLabel(header_row, image=icon, text="").pack(side="left", padx=(0, 8))

        ctk.CTkLabel(header_row, text=job["title"], font=FONT_CARD_TITLE,
                     text_color=TEXT, anchor="w").pack(side="left")

        if score is not None:
            badge = ctk.CTkLabel(header_row, text=f"{score}% match", font=("Segoe UI", 11, "bold"),
                                 text_color="#0f172a", fg_color=accent, corner_radius=10,
                                 width=90, height=22)
            badge.pack(side="left", padx=(10, 0))

        ctk.CTkLabel(body, text=f"{job['company']}  ·  {job['location']}  ·  {job['site']}",
                     font=FONT_BODY, text_color=TEXT_DIM, anchor="w").pack(anchor="w", pady=(4, 0))

        matched = job.get("matched_skills")
        if matched:
            chips = ctk.CTkFrame(body, fg_color="transparent")
            chips.pack(anchor="w", pady=(8, 0))
            for skill in matched[:6]:
                ctk.CTkLabel(chips, text=skill, font=FONT_SMALL, text_color=SUCCESS,
                            fg_color=SURFACE_ALT, corner_radius=8,
                            padx=8, pady=2).pack(side="left", padx=(0, 6))

        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.pack(anchor="w", pady=(10, 0))
        ctk.CTkButton(actions, text="Apply", width=90, height=30, corner_radius=6,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=lambda j=job: self.quick_apply(j)).pack(side="left", padx=(0, 6))
        ctk.CTkButton(actions, text="Open", width=90, height=30, corner_radius=6,
                      fg_color=SURFACE_ALT, hover_color=BORDER, text_color=TEXT,
                      command=lambda u=job["link"]: webbrowser.open(u)).pack(side="left", padx=(0, 6))
        fav_btn = ctk.CTkButton(actions, text="Save", width=90, height=30, corner_radius=6,
                                fg_color=SURFACE_ALT, hover_color=BORDER, text_color=TEXT)
        fav_btn.configure(command=lambda j=job, btn=fav_btn: self.toggle_fav(j, btn))
        fav_btn.pack(side="left")

    def quick_apply(self, job):
        letter = apply_to_job(self.profile, job) if self.profile else None
        database.add_application(job)
        msg = f"Logged: {job['title']} @ {job['company']}"
        if letter:
            msg += "\nCover letter copied to clipboard!"
        mb.showinfo("Applied", msg)
        self.refresh_tracker()

    def toggle_fav(self, job, btn):
        now_fav = database.toggle_favorite(job)
        btn.configure(text="Saved" if now_fav else "Save",
                     fg_color=SUCCESS if now_fav else SURFACE_ALT,
                     text_color="#0f172a" if now_fav else TEXT)

    # ================= TRACKER TAB =================
    def _build_tracker_tab(self):
        bar = ctk.CTkFrame(self.tab_tracker, fg_color="transparent")
        bar.pack(fill="x", pady=10)
        ctk.CTkButton(bar, text="Refresh", width=100, height=32, corner_radius=6,
                      fg_color=SURFACE_ALT, hover_color=BORDER, text_color=TEXT,
                      command=self.refresh_tracker).pack(side="left", padx=(0, 8))
        ctk.CTkButton(bar, text="Export CSV", width=110, height=32, corner_radius=6,
                      fg_color=SURFACE_ALT, hover_color=BORDER, text_color=TEXT,
                      command=self.export_csv).pack(side="left")
        self.followup_badge = ctk.CTkLabel(bar, text="", font=("Segoe UI", 11, "bold"),
                                           text_color="#0f172a", corner_radius=10,
                                           fg_color=WARNING, padx=10, height=24)
        self.followup_badge.pack(side="left", padx=(12, 0))

        self.tracker_frame = ctk.CTkScrollableFrame(self.tab_tracker, fg_color="transparent")
        self.tracker_frame.pack(fill="both", expand=True)
        self.refresh_tracker()

    def refresh_tracker(self):
        if not hasattr(self, "tracker_frame"):
            return
        due = database.due_followups()
        if due:
            self.followup_badge.configure(
                text=f"{len(due)} follow-up{'s' if len(due) > 1 else ''} due")
            self.followup_badge.pack(side="left", padx=(12, 0))
        else:
            self.followup_badge.pack_forget()
        for w in self.tracker_frame.winfo_children():
            w.destroy()
        apps = database.all_applications()
        if not apps:
            ctk.CTkLabel(self.tracker_frame, text="No applications yet — hit Apply!",
                        font=FONT_BODY, text_color=TEXT_DIM).pack(pady=24)
            return
        for aid, title, comp, site, status, applied, followup, link, notes in apps:
            color = STATUS_COLORS.get(status, NEUTRAL)
            row = ctk.CTkFrame(self.tracker_frame, fg_color=CARD, corner_radius=10,
                               border_width=1, border_color=BORDER)
            row.pack(fill="x", pady=4, padx=2)
            ctk.CTkFrame(row, fg_color=color, width=4, height=1).pack(side="left", fill="y")

            icon = self.site_icon(site)
            if icon:
                ctk.CTkLabel(row, image=icon, text="").pack(side="left", padx=(10, 0), pady=10)

            ctk.CTkLabel(row, width=100, corner_radius=6, text_color="#0f172a",
                         fg_color=color, text=status, font=("Segoe UI", 11, "bold")
                         ).pack(side="left", padx=10, pady=10)
            ctk.CTkLabel(row, anchor="w", justify="left", font=FONT_BODY, text_color=TEXT,
                         text=f"{title} @ {comp}  ·  {site}\n"
                              f"Applied {str(applied)[:10]}   Follow-up {str(followup)[:10]}"
                         ).pack(side="left", padx=10)
            # side="left", not "right": this row lives in a CTkScrollableFrame,
            # where right-packed content is silently clipped (see Observation 4).
            menu = ctk.CTkOptionMenu(row, values=database.STATUSES, width=150, height=28,
                                     corner_radius=6, fg_color=ACCENT, button_color=ACCENT,
                                     button_hover_color=ACCENT_HOVER,
                                     command=lambda s, l=link:
                                     (database.update_status(l, s),
                                      self.refresh_tracker()))
            menu.set(status)
            menu.pack(side="left", padx=10, pady=10)

    def export_csv(self):
        import csv
        path = fd.asksaveasfilename(defaultextension=".csv",
                                    initialfile="applications.csv")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Title", "Company", "Site", "Status",
                        "Applied", "Follow-up", "Link"])
            w.writerows([a[1:8] for a in database.all_applications()])
        mb.showinfo("Export", "Exported successfully.")

    # ================= FAVORITES TAB =================
    def _build_favorites_tab(self):
        bar = ctk.CTkFrame(self.tab_favorites, fg_color="transparent")
        bar.pack(fill="x", pady=10)
        ctk.CTkButton(bar, text="Refresh", width=100, height=32, corner_radius=6,
                      fg_color=SURFACE_ALT, hover_color=BORDER, text_color=TEXT,
                      command=self.refresh_favorites).pack(side="left")

        self.favorites_frame = ctk.CTkScrollableFrame(self.tab_favorites, fg_color="transparent")
        self.favorites_frame.pack(fill="both", expand=True)
        self.refresh_favorites()

    def refresh_favorites(self):
        if not hasattr(self, "favorites_frame"):
            return
        for w in self.favorites_frame.winfo_children():
            w.destroy()
        favorites = database.all_favorites()
        if not favorites:
            ctk.CTkLabel(self.favorites_frame, text="No saved jobs yet — hit Save on a result!",
                        font=FONT_BODY, text_color=TEXT_DIM).pack(pady=24)
            return
        for job in favorites:
            self.add_favorite_card(job)

    def add_favorite_card(self, job):
        # Same left-to-right/top-to-bottom flow as add_result_card, for the
        # same CTkScrollableFrame reason (see Observation 4 in this project's
        # skill-observations log): never anchor content to the right edge here.
        card = ctk.CTkFrame(self.favorites_frame, fg_color=CARD, corner_radius=12,
                            border_width=1, border_color=BORDER)
        card.pack(fill="x", pady=6, padx=2)

        ctk.CTkFrame(card, fg_color=ACCENT, corner_radius=0,
                     width=4, height=1).pack(side="left", fill="y")

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(side="left", fill="both", expand=True, padx=14, pady=12)

        header_row = ctk.CTkFrame(body, fg_color="transparent")
        header_row.pack(fill="x", anchor="w")

        icon = self.site_icon(job["site"])
        if icon:
            ctk.CTkLabel(header_row, image=icon, text="").pack(side="left", padx=(0, 8))
        ctk.CTkLabel(header_row, text=job["title"], font=FONT_CARD_TITLE,
                     text_color=TEXT, anchor="w").pack(side="left")

        ctk.CTkLabel(body, text=f"{job['company']}  ·  {job['location']}  ·  {job['site']}",
                     font=FONT_BODY, text_color=TEXT_DIM, anchor="w").pack(anchor="w", pady=(4, 0))

        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.pack(anchor="w", pady=(10, 0))
        ctk.CTkButton(actions, text="Apply", width=90, height=30, corner_radius=6,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=lambda j=job: self.quick_apply(j)).pack(side="left", padx=(0, 6))
        ctk.CTkButton(actions, text="Open", width=90, height=30, corner_radius=6,
                      fg_color=SURFACE_ALT, hover_color=BORDER, text_color=TEXT,
                      command=lambda u=job["link"]: webbrowser.open(u)).pack(side="left", padx=(0, 6))
        ctk.CTkButton(actions, text="Remove", width=90, height=30, corner_radius=6,
                      fg_color=SURFACE_ALT, hover_color=DANGER, text_color=TEXT,
                      command=lambda j=job: self.remove_favorite(j)).pack(side="left")

    def remove_favorite(self, job):
        database.toggle_favorite(job)
        self.refresh_favorites()

    # ================= STATS TAB =================
    def _build_stats_tab(self):
        bar = ctk.CTkFrame(self.tab_stats, fg_color="transparent")
        bar.pack(fill="x", pady=10)
        ctk.CTkButton(bar, text="Refresh", width=100, height=32, corner_radius=6,
                      fg_color=SURFACE_ALT, hover_color=BORDER, text_color=TEXT,
                      command=self.refresh_stats).pack(side="left")
        self.stats_frame = ctk.CTkScrollableFrame(self.tab_stats, fg_color="transparent")
        self.stats_frame.pack(fill="both", expand=True)
        self.refresh_stats()

    def refresh_stats(self):
        for w in self.stats_frame.winfo_children():
            w.destroy()
        s = stats_mod.get_stats()
        if s.get("total", 0) == 0:
            ctk.CTkLabel(self.stats_frame, text="Apply to some jobs first!",
                        font=FONT_BODY, text_color=TEXT_DIM).pack(pady=40)
            return
        row = ctk.CTkFrame(self.stats_frame, fg_color="transparent")
        row.pack(fill="x", pady=(0, 16))
        for label, val in [("Total", s["total"]),
                           ("Response %", f"{s['response_rate']}%"),
                           ("Interviews %", f"{s['interview_rate']}%")]:
            card = ctk.CTkFrame(row, fg_color=SURFACE, corner_radius=12,
                               border_width=1, border_color=BORDER)
            card.pack(side="left", expand=True, fill="x", padx=6)
            ctk.CTkLabel(card, text=str(val), font=FONT_STAT, text_color=TEXT).pack(pady=(16, 0))
            ctk.CTkLabel(card, text=label, font=FONT_SMALL, text_color=TEXT_DIM).pack(pady=(0, 16))

        ctk.CTkLabel(self.stats_frame, text="Status Breakdown", font=("Segoe UI", 15, "bold"),
                     text_color=TEXT).pack(anchor="w", pady=(4, 8))
        max_v = max(s["statuses"].values())
        for st, count in s["statuses"].items():
            line = ctk.CTkFrame(self.stats_frame, fg_color=SURFACE, corner_radius=8,
                                border_width=1, border_color=BORDER)
            line.pack(fill="x", pady=3)
            ctk.CTkLabel(line, text=st, width=130, font=FONT_BODY, text_color=TEXT,
                        anchor="w").pack(side="left", padx=(12, 0), pady=8)
            ctk.CTkLabel(line, text="", height=14, corner_radius=6,
                         width=max(10, int(count / max_v * 380)),
                         fg_color=STATUS_COLORS.get(st, NEUTRAL)).pack(side="left", padx=8, pady=8)
            ctk.CTkLabel(line, text=str(count), width=30, font=FONT_BODY,
                        text_color=TEXT_DIM).pack(side="left", padx=(0, 12), pady=8)


if __name__ == "__main__":
    JobHunterApp().mainloop()
