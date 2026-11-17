// The job-hunt skill's page readers for every board but LinkedIn (linkedin.js reads that):
// Indeed, Naukri, Hirist, Cutshort, Wellfound, Internshala, foundit and Instahyre.
// Paste the whole file into javascript_tool once per page load (a full navigation clears it),
// then call one of:
//   __bdList()  the result cards: "<id or link> :: title | company | place | experience/pay | age"
//               Indeed gives "indeed:<jk>" (the job's link is https://in.indeed.com/viewjob?jk=<jk>);
//               every other board gives the job's own link, without its query string.
//   __bdJob()   the open job: the header, any recruiter or "posted by" line, and the requirement
//               lines (experience, skills, location, pay, emails).
//   __bdBlock() "" normally; otherwise the words of a captcha, login or "access denied" page:
//               stop and ask the user when it says anything.
// None of them return a URL with a query string: the tool blocks such output.
(() => {
  const clean = (s) => (s || "").split("\n").map((x) => x.trim()).filter(Boolean);
  // A job's own link on each board (Indeed's is read from its jk instead).
  const LINKS = {
    naukri: /\/job-listings-[^?#]*-\d{6,}/,
    hirist: /\/j\/[^?#]*-\d{5,}/,
    cutshort: /\/job\/[^?#]*-[A-Za-z0-9]{8}\/?$/,
    wellfound: /\/jobs\/\d{4,}-/,
    internshala: /\/job\/detail\/[^?#]*\d{9,}/,
    foundit: /\/job\/[^?#]*-\d{6,}/,
    instahyre: /^\/job-\d{4,}-/,
  };
  const board = () => {
    const h = location.host;
    if (/indeed\./.test(h)) return "indeed";
    return Object.keys(LINKS).find((k) => h.includes(k)) || "";
  };
  const NOISE = /^(new|save|saved|apply|easy apply|hiring multiple candidates|urgently hiring|responsive employer|view similar jobs|·|•|\d+ reviews?|\d(\.\d)?)$/i;
  // Climb from a link to the smallest box that holds one whole card.
  const card = (a, sel) => {
    const own = sel && a.closest(sel);
    if (own) return own;
    let c = a;
    while (c.parentElement && clean(c.innerText).length < 4) c = c.parentElement;
    return c;
  };

  window.__bdList = () => {
    const out = [];
    const seen = new Set();
    if (board() === "indeed") {
      document.querySelectorAll("a[data-jk], a[href*='jk=']").forEach((a) => {
        const jk = a.getAttribute("data-jk") || ((a.getAttribute("href") || "").match(/[?&](?:jk|vjk)=([0-9a-f]+)/) || [])[1];
        if (!jk || seen.has(jk)) return;
        seen.add(jk);
        const c = card(a, ".job_seen_beacon, li, td.resultContent");
        const t = clean(c.innerText).filter((s) => !NOISE.test(s));
        out.push(`indeed:${jk} :: ${t.slice(0, 6).join(" | ").slice(0, 220)}`);
      });
    } else if (board()) {
      const re = LINKS[board()];
      // The smallest box per board that holds one card, where it has a known one.
      const box = {
        naukri: ".srp-jobtuple-wrapper, .cust-job-tuple, article",
        internshala: ".individual_internship, .container-fluid.individual_internship",
        wellfound: "[data-test='StartupResult'], [class*='JobSearchResults'] > div",
      }[board()] || "article, li";
      document.querySelectorAll("a[href]").forEach((a) => {
        const href = a.href.split("?")[0].split("#")[0];
        if (!re.test(new URL(href).pathname) || seen.has(href)) return;
        seen.add(href);
        const c = card(a, box);
        const t = clean(c.innerText).filter((s) => !NOISE.test(s));
        out.push(`${href} :: ${t.slice(0, 7).join(" | ").slice(0, 240)}`);
      });
    } else {
      return "not a job board this reader knows";
    }
    return out.slice(0, 30).join("\n") || "no cards found: wait a few seconds and try again";
  };

  window.__bdJob = () => {
    const pick = (sels) => { for (const s of sels) { const e = document.querySelector(s); if (e && e.innerText.trim()) return e; } return null; };
    let head = "";
    let body = "";
    if (board() === "indeed") {
      const box = pick(["#jobsearch-ViewjobPaneWrapper", ".jobsearch-ViewJobLayout-jobDisplay", ".jobsearch-JobComponent", "main"]) || document.body;
      const h = pick(["[data-testid='jobsearch-JobInfoHeader-title']", "h1", "h2.jobsearch-JobInfoHeader-title"]);
      const co = pick(["[data-testid='inlineHeader-companyName']", "[data-company-name]", "[data-testid='jobsearch-CompanyInfoContainer'] a"]);
      const loc = pick(["[data-testid='inlineHeader-companyLocation']", "[data-testid='job-location']", "[data-testid='jobsearch-JobInfoHeader-companyLocation']"]);
      const meta = pick(["#salaryInfoAndJobType", "[data-testid='jobsearch-OtherJobDetailsContainer']"]);
      head = [h, co, loc, meta].filter(Boolean).map((e) => clean(e.innerText).join(" ")).join(" | ");
      body = (pick(["#jobDescriptionText"]) || box).innerText;
    } else if (board()) {
      // Every other board: the h1 and the box around it are the header; the description is the
      // section headed "Job description" / "About the job" / "About the work", else the whole page.
      const box = document.querySelector("main") || document.body;
      const h = pick(["h1"]);
      const top = h ? (h.closest("section, header, [class*='header'], [class*='Header']") || h.parentElement) : null;
      head = top ? clean(top.innerText).filter((s) => !NOISE.test(s)).slice(0, 12).join(" | ") : "";
      const jd = [...box.querySelectorAll("section, div")].find((e) =>
        /^(job description|about the job|about the work|job details|description)/i.test((e.innerText || "").trim()) &&
        (e.innerText || "").length < 20000);
      body = (jd || box).innerText;
    } else {
      return "not a job board this reader knows";
    }
    const lines = clean(body);
    const keys = lines
      .filter((s) => /experience|years|yrs|fresher|location|salary|ctc|lpa|must|required|qualification|key skills|node|typescript|postgres|mongo|express|react|python|java\b|recruiter|posted by|hiring manager|@|e-?mail/i.test(s))
      .slice(0, 16)
      .map((s) => s.slice(0, 220));
    const people = lines.filter((s) => /posted by|recruiter|hr\b|talent acquisition|contact/i.test(s)).slice(0, 3).map((s) => s.slice(0, 160));
    return `HEAD: ${head.slice(0, 400)}\nPEOPLE: ${people.join(" ; ")}\nKEY:\n${keys.join("\n")}`;
  };

  window.__bdBlock = () => {
    const t = document.body.innerText.slice(0, 3000);
    const signs = [/verify you are human/i, /are you a robot/i, /captcha/i, /access denied/i, /unusual (traffic|activity)/i,
      /security check/i, /additional verification required/i, /please (log|sign) in to (continue|view)/i, /request blocked/i];
    return signs.map((r) => (t.match(r) || [""])[0]).filter(Boolean).join(" ; ");
  };
  return "ready: " + (board() || "not a job board");
})();
