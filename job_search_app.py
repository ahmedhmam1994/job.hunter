"""Job Hunter — Desktop App (CustomTkinter).
Run: python job_search_app.py
"""
import threading
import customtkinter as ctk
import tkinter.filedialog as fd
import tkinter.messagebox as mb

import scrapers
import matcher
import cv_parser
import database
import stats as stats_mod          # see note below*
from apply_helper import apply_to_job

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class JobHunterApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Job Hunter")
        self.geometry("1100x720")
        self.profile = None

        tabs = ctk.CTkTabview(self)
        tabs.pack(fill="both", expand=True, padx=12, pady=12)
        self.tab_search = tabs.add("Search")
        self.tab_tracker = tabs.add("Tracker")
        self.tab_stats = tabs.add("Stats")

        self._build_search_tab()
        self._build_tracker_tab()
        self._build_stats_tab()

    # ================= SEARCH TAB =================
    def _build_search_tab(self):
        tab = self.tab_search

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", pady=(8, 4))

        self.query_entry = ctk.CTkEntry(top, placeholder_text=
                                        "Job title or keyword...", width=280)
        self.query_entry.pack(side="left", padx=(0, 8))
        self.query_entry.bind("<Return>", lambda e: self.start_search())

        self.site_menu = ctk.CTkOptionMenu(
            top, values=["All sites"] + list(scrapers.SITES.keys()), width=150)
        self.site_menu.pack(side="left", padx=8)
        self.site_menu.set("All sites")

        self.remote_var = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(top, text="Remote only",
                      variable=self.remote_var).pack(side="left", padx=8)

        ctk.CTkButton(top, text="Search",
                      command=self.start_search).pack(side="left", padx=8)

        bar2 = ctk.CTkFrame(tab, fg_color="transparent")
        bar2.pack(fill="x", pady=2)
        self.cv_label = ctk.CTkLabel(bar2, text="No CV loaded")
        self.cv_label.pack(side="left", padx=4)
        ctk.CTkButton(bar2, text="Upload CV", width=110,
                      command=self.upload_cv).pack(side="left", padx=4)
        self.thresh_slider = ctk.CTkSlider(bar2, from_=30, to=95, width=160,
                                           number_of_steps=13)
        self.thresh_slider.set(50)
        ctk.CTkLabel(bar2, text="Min match:").pack(side="left", padx=(14, 4))
        self.thresh_lbl = ctk.CTkLabel(bar2, text="50%", width=40)
        self.thresh_lbl.pack(side="left")
        self.thresh_slider.configure(command=lambda v: self.thresh_lbl.configure(text=f"{int(v)}%"))

        self.results_frame = ctk.CTkScrollableFrame(tab)
        self.results_frame.pack(fill="both", expand=True, pady=6)

    def upload_cv(self):
        path = fd.askopenfilename(filetypes=[("CV files", "*.pdf *.docx *.doc")])
        if not path:
            return
        try:
            self.profile = cv_parser.CVProfile(path)
        except Exception as e:
            mb.showerror("CV Error", str(e))
            return
        self.cv_label.configure(text=f"{self.profile.summary()}")

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
            extra = f" - best match {jobs[0]['score']}%"
        self.status_lbl.configure(text=f"{len(jobs)} jobs{extra}")

    def add_result_card(self, job):
        card = ctk.CTkFrame(self.results_frame)
        card.pack(fill="x", pady=5)

        left = ctk.CTkFrame(card, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=10, pady=8)

        title_txt = f"{job['title']}"
        if "score" in job:
            title_txt += f"   [{job['score']}% match]"
        ctk.CTkLabel(left, justify="left", anchor="w", font=("Arial", 14, "bold"),
                     text=title_txt).pack(anchor="w")
        ctk.CTkLabel(left, justify="left", anchor="w",
                     text=f"{job['company']}   {job['location']}   [{job['site']}]"
                     ).pack(anchor="w")
        matched = job.get("matched_skills")
        if matched:
            ctk.CTkLabel(left, anchor="w", text_color="#22c55e",
                         text="Matched: " + ", ".join(matched[:8])).pack(anchor="w")

        right = ctk.CTkFrame(card, fg_color="transparent")
        right.pack(side="right", padx=10, pady=8)
        ctk.CTkButton(right, text="Apply", width=80, fg_color="#2563eb",
                      command=lambda j=job: self.quick_apply(j)).pack(pady=2)
        ctk.CTkButton(right, text="Open", width=80, fg_color="#334155",
                      command=lambda u=job["link"]: __import__("webbrowser").open(u)).pack(pady=2)
        fav_btn = ctk.CTkButton(right, text="Save", width=80, fg_color="#334155",
                                command=lambda j=job, b=None: None)
        fav_btn.configure(command=lambda j=job, btn=fav_btn: self.toggle_fav(j, btn))
        fav_btn.pack(pady=2)

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
        btn.configure(text="Saved" if now_fav else "Save")

    # ================= TRACKER TAB =================
    def _build_tracker_tab(self):
        bar = ctk.CTkFrame(self.tab_tracker, fg_color="transparent")
        bar.pack(fill="x", pady=6)
        ctk.CTkButton(bar, text="Refresh",
                      command=self.refresh_tracker).pack(side="left", padx=8)
        ctk.CTkButton(bar, text="Export CSV",
                      command=self.export_csv).pack(side="left")
        self.status_lbl = ctk.CTkLabel(bar, text="")
        self.status_lbl.pack(side="left", padx=14)

        self.tracker_frame = ctk.CTkScrollableFrame(self.tab_tracker)
        self.tracker_frame.pack(fill="both", expand=True)
        self.refresh_tracker()

    def refresh_tracker(self):
        if not hasattr(self, "tracker_frame"):
            return
        for w in self.tracker_frame.winfo_children():
            w.destroy()
        apps = database.all_applications()
        if not apps:
            ctk.CTkLabel(self.tracker_frame,
                         text="No applications yet — hit Apply!").pack(pady=24)
            return
        colors = {"Applied": "#64748b", "Follow-up sent": "#2563eb",
                  "Interview": "#22c55e", "Offer": "#16a34a",
                  "Rejected": "#ef4444", "Ghosted": "#94a3b8"}
        for aid, title, comp, site, status, applied, followup, link, notes in apps:
            row = ctk.CTkFrame(self.tracker_frame)
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, width=90, corner_radius=6, text_color="#fff",
                         fg_color=colors.get(status, "#333"), text=status
                         ).pack(side="left", padx=6, pady=6)
            ctk.CTkLabel(row, anchor="w", justify="left",
                         text=f"{title} @ {comp} [{site}]\n"
                              f"Applied {str(applied)[:10]}   Follow-up {str(followup)[:10]}"
                         ).pack(side="left", padx=10)
            menu = ctk.CTkOptionMenu(row, values=database.STATUSES, width=140,
                                     command=lambda s, l=link:
                                     (database.update_status(l, s),
                                      self.refresh_tracker()))
            menu.set(status)
            menu.pack(side="right", padx=8)

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
            w.writerows([a[1:8][::-1][::-1] for a in database.all_applications()])
        self.status_lbl.configure(text=f"Exported")

    # ================= STATS TAB =================
    def _build_stats_tab(self):
        bar = ctk.CTkFrame(self.tab_stats, fg_color="transparent")
        bar.pack(fill="x", pady=6)
        ctk.CTkButton(bar, text="Refresh",
                      command=self.refresh_stats).pack(side="left", padx=8)
        self.stats_frame = ctk.CTkScrollableFrame(self.tab_stats)
        self.stats_frame.pack(fill="both", expand=True)
        self.refresh_stats()

    def refresh_stats(self):
        for w in self.stats_frame.winfo_children():
            w.destroy()
        s = stats_mod.get_stats()
        if s.get("total", 0) == 0:
            ctk.CTkLabel(self.stats_frame,
                         text="Apply to some jobs first!").pack(pady=40)
            return
        row = ctk.CTkFrame(self.stats_frame, fg_color="transparent")
        row.pack(fill="x", pady=10)
        for label, val in [("Total", s["total"]),
                           ("Response %", f"{s['response_rate']}%"),
                           ("Interviews %", f"{s['interview_rate']}%")]:
            card = ctk.CTkFrame(row)
            card.pack(side="left", expand=True, fill="x", padx=4)
            ctk.CTkLabel(card, text=str(val),
                         font=("Arial", 26, "bold")).pack(pady=(10, 0))
            ctk.CTkLabel(card, text=label,
                         text_color="#94a3b8").pack(pady=(0, 10))

        colors = {"Applied": "#64748b", "Follow-up sent": "#2563eb",
                  "Interview": "#22c55e", "Offer": "#16a34a",
                  "Rejected": "#ef4444", "Ghosted": "#94a3b8"}
        ctk.CTkLabel(self.stats_frame, text="Status Breakdown",
                     font=("Arial", 16, "bold")).pack(pady=(14, 4))
        max_v = max(s["statuses"].values())
        for st, count in s["statuses"].items():
            line = ctk.CTkFrame(self.stats_frame)
            line.pack(fill="x", padx=20, pady=2)
            ctk.CTkLabel(line, text=st, width=120).pack(side="left")
            ctk.CTkLabel(line, text="", height=18, corner_radius=4,
                         width=max(10, int(count / max_v * 400)),
                         fg_color=colors.get(st)).pack(side="left", padx=8, pady=2)
            ctk.CTkLabel(line, text=str(count), width=30).pack(side="left")


if __name__ == "__main__":
    JobHunterApp().mainloop()
