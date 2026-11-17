// The network skill's page readers for LinkedIn and X (2026 layouts). They only read: every click
// (Connect, Send, Follow) is done with find + a ref, so it is the same click a person makes.
// Paste the whole file into javascript_tool once per page load (a navigation clears it), then call:
//   __nwPeople()   LinkedIn people search: "profile :: name | headline | place | button"
//   __nwPosts()    LinkedIn post search: "author profile :: name | headline || first 200 chars of the post"
//   __nwProfile()  a LinkedIn profile: name, headline, place, degree, buttons, about, recent roles
//   __nwXUsers()   X people search or a follow list: "x.com/handle :: name | bio | Follow/Following"
//   __nwXPosts()   X posts on the page: "post link :: @handle | time | text"
//   __nwLimit()    any LinkedIn/X limit or warning on screen ("" when none): stop the run if it says something
// None of them return the page URL: the tool blocks output that holds query strings.
(() => {
  const main = () => document.querySelector("main") || document.body;
  const clean = (s) => (s || "").split("\n").map((x) => x.trim()).filter(Boolean);
  const NOISE = /^(·|•|Message|Connect|Follow|Pending|Following|More|Save|Status is (online|offline|reachable))$|mutual connection|followers$|Provides services|See open roles|Visit my website|^\d(st|nd|rd)\+?$|degree connection/i;
  const BUTTON = /^(Connect|Follow|Message|Pending|Following)$/;
  const root = (href) => href.split("?")[0].replace(/\/+$/, "") + "/";

  window.__nwPeople = () => {
    const rows = [];
    const seen = new Set();
    main().querySelectorAll('a[href*="/in/"]').forEach((a) => {
      const href = root(a.href);
      if (seen.has(href) || /\/in\/[^/]+\/.+/.test(href)) return;
      let c = a;
      while (c.parentElement && clean(c.innerText).length < 4) c = c.parentElement;
      const all = clean(c.innerText);
      const button = [...c.querySelectorAll("button, a")].map((b) => (b.innerText || "").trim()).find((t) => BUTTON.test(t)) || "-";
      const t = all.filter((s) => !NOISE.test(s));
      if (t.length < 2 || t.length > 14) return;
      seen.add(href);
      rows.push(`${href} :: ${t.slice(0, 4).join(" | ")} | ${button}`);
    });
    return rows.slice(0, 12).join("\n") || "no people found: wait a few seconds and try again";
  };

  window.__nwPosts = () => {
    const out = [];
    let posts = [...main().querySelectorAll('[data-urn*="activity"], [data-id*="activity"], div.feed-shared-update-v2')];
    if (!posts.length) {
      // 2026 layout: each result is a block that starts with a hidden "Feed post" heading.
      posts = [...main().querySelectorAll("h2, span, div")].filter((e) => e.childElementCount === 0 && e.textContent.trim() === "Feed post")
        .map((h) => { let c = h.parentElement; while (c && c !== main() && !c.querySelector('a[href*="/in/"]')) c = c.parentElement; return c; })
        .filter(Boolean);
    }
    posts.forEach((p) => {
      const a = p.querySelector('a[href*="/in/"]');
      if (!a) return;
      const lines = clean(p.innerText).filter((s) => !NOISE.test(s));
      const body = lines.slice(3).join(" ").replace(/\s+/g, " ");
      out.push(`${root(a.href)} :: ${lines.slice(0, 2).join(" | ")} || ${body.slice(0, 200)}`);
    });
    return [...new Set(out)].slice(0, 10).join("\n") || "no posts found: wait a few seconds and try again";
  };

  window.__nwProfile = () => {
    const m = main();
    const top = clean(m.querySelector("section")?.innerText || m.innerText).slice(0, 12);
    const buttons = [...m.querySelectorAll("section button")].slice(0, 10).map((b) => (b.innerText || b.getAttribute("aria-label") || "").trim()).filter(Boolean);
    const section = (title) => {
      const s = [...m.querySelectorAll("section")].find((x) => clean(x.innerText)[0] === title);
      return s ? clean(s.innerText).slice(1, 14).join(" | ").slice(0, 600) : "";
    };
    const degree = (m.innerText.match(/\b(1st|2nd|3rd\+?)\b/) || [""])[0];
    return [
      `TOP: ${top.join(" | ")}`,
      `DEGREE: ${degree}`,
      `BUTTONS: ${[...new Set(buttons)].join(" | ")}`,
      `ABOUT: ${section("About")}`,
      `EXPERIENCE: ${section("Experience")}`,
      `ACTIVITY: ${section("Activity")}`,
    ].join("\n");
  };

  window.__nwXUsers = () => {
    const cells = document.querySelectorAll('[data-testid="UserCell"], [data-testid="cellInnerDiv"]');
    const rows = [];
    const seen = new Set();
    cells.forEach((c) => {
      const a = [...c.querySelectorAll('a[href^="/"]')].find((x) => /^\/[A-Za-z0-9_]{1,15}$/.test(x.getAttribute("href")));
      if (!a) return;
      const handle = a.getAttribute("href").slice(1);
      if (seen.has(handle)) return;
      const btn = c.querySelector('[data-testid$="-follow"], [data-testid$="-unfollow"]');
      if (!btn) return;
      seen.add(handle);
      const state = /unfollow/.test(btn.getAttribute("data-testid")) ? "Following" : "Follow";
      const t = clean(c.innerText).filter((s) => !/^(Follow|Following|Follows you|Click to Follow)$/.test(s) && !s.startsWith("@"));
      rows.push(`https://x.com/${handle} :: ${t[0] || ""} | ${t.slice(1).join(" ").slice(0, 160)} | ${state}`);
    });
    return rows.slice(0, 15).join("\n") || "no accounts found: wait a few seconds or scroll";
  };

  window.__nwXPosts = () => {
    const out = [];
    document.querySelectorAll('article[data-testid="tweet"]').forEach((t) => {
      const link = t.querySelector('a[href*="/status/"] time')?.parentElement;
      const handle = [...t.querySelectorAll('a[href^="/"]')].map((a) => a.getAttribute("href")).find((h) => /^\/[A-Za-z0-9_]{1,15}$/.test(h)) || "";
      const text = (t.querySelector('[data-testid="tweetText"]')?.innerText || "").replace(/\s+/g, " ");
      if (!link) return;
      out.push(`https://x.com${link.getAttribute("href").split("?")[0]} :: @${handle.slice(1)} | ${t.querySelector("time")?.getAttribute("datetime") || ""} | ${text.slice(0, 220)}`);
    });
    return out.slice(0, 12).join("\n") || "no posts found: wait a few seconds or scroll";
  };

  window.__nwLimit = () => {
    const t = document.body.innerText;
    const signs = [
      /weekly invitation limit/i, /reached the (weekly|monthly) limit/i, /used all (of )?your personali[sz]ed invitations/i,
      /out of personali[sz]ed invitations/i, /unusual activity/i, /verify (that )?you('| a)re (a )?human/i,
      /security verification/i, /account (has been )?(restricted|limited|locked)/i, /rate limit/i,
      /You are unable to follow more/i, /temporarily (restricted|limited)/i, /How do you know/i, /enter (their|the) email/i,
    ];
    const hit = signs.map((r) => (t.match(r) || [""])[0]).filter(Boolean);
    return hit.join(" ; ");
  };
  return "ready";
})();
