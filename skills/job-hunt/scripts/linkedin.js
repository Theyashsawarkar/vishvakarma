// The job-hunt skill's page readers for LinkedIn (2026 layout, /jobs/search-results/).
// Paste the whole file into javascript_tool once per page load (a full navigation clears it),
// then call one of:
//   __jhList()    the result cards on the left: "title @ company - location", one per line
//   __jhJob()     the open job: header, hiring team (names and their profile links only),
//                 and the requirement lines (experience, skills, location, pay, emails)
//   __jhPeople()  a people search: "profile :: name | headline | place | current role"
// None of them return the page URL: the tool blocks output that holds query strings. Read the job id
// from the tab's URL in tabs_context_mcp instead (currentJobId=<id>).
(() => {
  const main = () => document.querySelector("main") || document.body;
  const clean = (s) => s.split("\n").map((x) => x.trim()).filter(Boolean);
  const split = () => {
    const t = main().innerText;
    const i = t.indexOf("Get job alerts for this search");
    return i < 0 ? [t, ""] : [t.slice(0, i), t.slice(i)];
  };
  const NOISE = /^(·|Easy Apply|Viewed|Be an early applicant|Actively reviewing applicants|Promoted|Save|Message|Connect|Follow)$/;

  window.__jhList = () => {
    const L = clean(split()[0]).filter((s) => !NOISE.test(s) && !/ago$/.test(s));
    const out = [];
    for (let i = 0; i < L.length - 2; i++) {
      // A card repeats its title: "Title (Verified job)" or "Title", then "Title", then the company.
      if (L[i + 1] === L[i].replace(" (Verified job)", "")) {
        out.push(`${L[i + 1]} @ ${L[i + 2]} - ${L[i + 3] || ""}`);
        i += 3;
      }
    }
    return out.join("\n") || "no cards found: wait a few seconds and try again";
  };

  window.__jhJob = () => {
    const d = split()[1];
    if (!d) return "no job open";
    const lines = clean(d).slice(1);
    const head = lines.slice(0, 9).join(" | ");
    const team = d.includes("Meet the hiring team")
      ? clean(d.split("Meet the hiring team")[1].split("About the job")[0]).join(" | ")
      : "";
    // Only links inside the small hiring-team box: the page has other people widgets.
    const box = [...main().querySelectorAll("*")].find(
      (e) => e.children.length && /Meet the hiring team/.test(e.innerText || "") && (e.innerText || "").length < 600,
    );
    const profiles = box ? [...new Set([...box.querySelectorAll('a[href*="/in/"]')].map((a) => a.href.split("?")[0]))] : [];
    const about = d.split("About the job")[1] || "";
    const keys = clean(about)
      .filter((s) => /experience|years|yrs|location|salary|ctc|lpa|must|required|qualification|node|typescript|postgres|mongo|express|react|@|e-?mail/i.test(s))
      .slice(0, 14)
      .map((s) => s.slice(0, 220));
    return `HEAD: ${head}\nTEAM: ${team}\nPROFILES: ${profiles.join(" ")}\nKEY:\n${keys.join("\n")}`;
  };

  window.__jhPeople = () => {
    const rows = [];
    const seen = new Set();
    main().querySelectorAll('a[href*="/in/"]').forEach((a) => {
      const href = a.href.split("?")[0];
      // Skip sub-pages such as /in/<name>/opportunities/...: only profile roots.
      if (seen.has(href) || /\/in\/[^/]+\/.+/.test(href)) return;
      let c = a;
      // Climb to the smallest box that holds one person's card.
      while (c.parentElement && (c.innerText || "").split("\n").length < 4) c = c.parentElement;
      const t = clean(c.innerText || "").filter((s) => !NOISE.test(s) && !/mutual connection|followers|See open roles|Visit my website/.test(s));
      if (t.length < 2 || t.length > 12) return;
      seen.add(href);
      rows.push(`${href} :: ${t.slice(0, 5).join(" | ")}`);
    });
    return rows.slice(0, 12).join("\n") || "no people found";
  };
  return "ready";
})();
