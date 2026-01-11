import asyncio, re
from skillweaver.agent import vars

(print,) = vars['/Users/chenboyu/Desktop/Epoch_Drift_Benchmark/Agents_new/SkillWeaver/results/wordpress_with_skills_v2_waber/wordpress/task_19/py_0_0.py']

async def monitor_keyword_and_notify(
    page,
    keyword,
    check_interval_minutes: int = 60,
    notify_via: str = "email",
    max_results: int = 10,
):
    """
    Scan the site's homepage for article headings that contain `keyword` (case-insensitive)
    and return matched results. This function performs a single scan and does NOT perform
    any internal continuous polling; schedule repeated calls externally if desired
    (for example, call this function periodically in your runner and use asyncio.sleep
    between calls).

    Preconditions / expected initial UI state:
    - The function will navigate to the site root by calling `await page.goto("/")`.
      If you need to preserve a different page state, navigate to that URL yourself
      before calling this function and remove or modify the initial navigation.
    - The function expects the homepage to contain a semantic accessibility tree with a
      region having role="main" that contains multiple elements with role="article".
      Each article is expected (ideally) to have a child with role="heading" which
      itself contains a role="link" for the article title. If that exact structure
      is not present, a fallback is used: the first role="link" inside the article.
    - The function does not attempt to dismiss overlays, cookie banners, or other
      dialogs. If such UI covers content in your environment, dismiss those before
      calling this function.

    Selector & error-handling behavior (observed & implemented):
    - Uses accessibility-tree-centric selectors (page.get_by_role) throughout rather
      than raw CSS selectors. This increases robustness on accessible sites.
    - Proactively checks existence counts using `await locator.count()` before
      calling `.nth()` or indexing into a locator. This prevents exceptions when a
      role is missing and avoids swallowing unexpected errors via broad try/except.
    - Fallback behavior: if the heading->link pattern is not found for an article,
      the function looks for the first role="link" inside the article and uses that
      as the title/href source. If no link exists, the article is skipped.
    - The function strips whitespace from inner_text() when matching titles.
    - Href values are returned as provided by the page and may be relative. If you
      require absolute URLs, resolve them against page.url or the origin.

    Parameters:
    - page: Playwright Page object (first argument).
    - keyword: string to search for in article titles (case-insensitive).
    - check_interval_minutes: suggested polling interval for callers that schedule
      repeated runs externally; this function itself performs a single scan and returns.
    - notify_via: currently supports 'email' (simulates an email by printing). Any other
      value will cause a structured dict-like print. Replace the print block with an
      actual notification implementation (SMTP, webhook, push, etc.) for production use.
    - max_results: maximum number of matched results to collect; scanning stops once
      this many results have been found.

    Returns:
    - A list of dicts: [{"title": <title>, "url": <href>}, ...]

    Usage log (runs I've performed):
    - Demonstration run (local session):
      * Call: await monitor_keyword_and_notify(page, 'Excel', check_interval_minutes=60, notify_via='email')
      * Behavior: The function navigated to '/'. It located the <main> region and iterated
        over its <article> children. It found 1 match: "You need to know what the tilde (~) does in Excel"
        with URL "/?p=6" and printed a simulated email with that result. No overlays were present
        during that run.

    Observed quirks & recommendations:
    - inner_text() may include extra whitespace; this function strips it before matching.
    - If multiple links are present in a heading, this function uses the first one. If your site
      places non-title links there, refine the locator externally or post-filter by link text.
    - Replace print-based notifications with real notification mechanisms in production.

    Important: this function does NOT run an internal continuous polling loop. To poll periodically,
    schedule repeated calls from your runner (for example, call this function and then await
    asyncio.sleep(check_interval_minutes * 60) externally).
    """
    await page.goto("/")
    results = []
    main_locator = page.get_by_role("main")
    main_count = await main_locator.count()
    if main_count == 0:
        print(
            "monitor_keyword_and_notify: no <main> region found on the page. Returning empty results."
        )
        return results
    main = main_locator.nth(0)
    articles_locator = main.get_by_role("article")
    article_count = await articles_locator.count()
    if article_count == 0:
        print(
            "monitor_keyword_and_notify: no <article> elements found inside <main>. Returning empty results."
        )
        return results
    for i in range(article_count):
        if len(results) >= max_results:
            break
        article = articles_locator.nth(i)
        title = None
        href = None
        heading_locator = article.get_by_role("heading")
        heading_count = await heading_locator.count()
        if heading_count > 0:
            heading = heading_locator.nth(0)
            link_in_heading = heading.get_by_role("link")
            if await link_in_heading.count() > 0:
                link = link_in_heading.nth(0)
                title = (await link.inner_text()).strip()
                href = await link.get_attribute("href")
        if title is None:
            link_in_article = article.get_by_role("link")
            if await link_in_article.count() > 0:
                link = link_in_article.nth(0)
                title = (await link.inner_text()).strip()
                href = await link.get_attribute("href")
        if title and keyword.lower() in title.lower():
            results.append({"title": title, "url": href})
    if results:
        if notify_via == "email":
            print(f"Subject: Keyword match for '{keyword}' on site")
            print()
            print(f"Found {len(results)} result(s) for keyword '{keyword}':")
            for r in results:
                print(f"- {r.get('title')} -> {r.get('url')}")
            print()
            print("(End of simulated email)")
        else:
            print({"notify_via": notify_via, "keyword": keyword, "results": results})
    else:
        print(f"No results found for keyword '{keyword}' on the current page.")
    return results


async def search_keyword_group_by_category(
    page, max_articles: int = 0, category_href_substring: str = "?cat="
):
    """
    Scan the site root ('/') for article entries inside the <main> region, extract each
    article's title and URL, heuristically find a nearby category anchor (an <a> whose
    href contains `category_href_substring`), and group discovered articles by the
    category name.

    Important initial UI state required before calling:
    - The page root ('/') should contain a semantic region with role="main" that
      includes one or more role="article" elements. Each article should contain a
      heading (role="heading") with a link (role="link") for the article title,
      or at minimum at least one role="link" inside the article.
    - The function begins with `await page.goto('/')` to establish a known starting
      state. If you need to start from a different URL/state, navigate there before
      calling this function and remove that initial navigation.
    - The function does NOT dismiss overlays, modals, or cookie banners. If such UI
      covers the content in your environment, dismiss those before calling.

    Behavior & mechanics:
    - Uses accessibility-tree-centric selectors (page.get_by_role and .nth()) for all
      Playwright selectors outside evaluate() to increase robustness on accessible sites.
    - For each article the function prefers the heading -> link pattern (role="heading"
      containing a role="link"). If that is missing it falls back to the first
      role="link" inside the article.
    - To determine an article's category the function executes a small DOM heuristic via
      link_locator.evaluate(...). The heuristic searches for a nearby anchor whose href
      contains `category_href_substring` (default '?cat=') by checking, in order:
        1) previous siblings of the link element,
        2) climbing parent nodes and inspecting their previous siblings,
        3) as a last resort, the first anchor anywhere in the document matching the substring.
      The heuristic returns {name: <anchor text>, href: <anchor href>} or null.
    - If no category anchor is found the article is assigned to the 'uncategorized' key.
    - The function does not attempt to convert relative hrefs to absolute; callers who
      need absolute URLs should resolve them against page.url themselves.

    Parameters:
    - page: Playwright Page object (first argument).
    - max_articles: optional integer limiting how many articles to process. 0 means no limit.
    - category_href_substring: substring to identify category anchors (default '?cat=').

    Returns:
    - A dict mapping category_name -> list of items, where each item is {"title": str, "url": str}.

    Observed quirks & recommendations (from runs):
    - inner_text() often contains extra whitespace or decorative symbols; this function trims
      title and category strings.
    - Using article-level link lookup (article.get_by_role('link')) reduces the chance of
      picking the wrong link when identical link text appears elsewhere on the page.
    - If your site does not use '?cat=' in category links, pass a different
      `category_href_substring` (for example '/category/' or '/tag/').
    - If link text is repeated across different contexts on the page and you observe
      incorrect category assignments, consider refining the heuristic (for example,
      restrict the category search to a sidebar or specific container) or change the
      method to inspect specific article metadata inside the article node.

    Usage log (runs I've performed):
    - Local dev run on site root:
      * Call: await search_keyword_group_by_category(page)
      * Behavior: navigated to '/'. Found a <main> region and multiple role="article"
        entries. Grouped results into categories such as 'Technology' and 'Business'.
      * Example returned structure (abbreviated):
        {
          'Technology': [
            {'title': 'What is Microsoft Planner and who is it for', 'url': 'http://localhost:8000/?p=8'},
            {'title': 'You need to know what the tilde (~) does in Excel', 'url': 'http://localhost:8000/?p=6'},
            ...
          ],
          'Business': [
            {'title': 'To harness crypto ingenuity, financial threat must first be neutralised', 'url': 'http://localhost:8000/?p=248'}
          ]
        }

    Notes about error handling:
    - The function proactively checks locator counts with `await locator.count()` before
      calling `.nth()` or `.evaluate()`. This avoids unbound-variable and similar runtime
      errors and prevents the need for broad try/except blocks.
    """
    await page.goto("/")
    grouped = {}
    main_locator = page.get_by_role("main")
    if await main_locator.count() == 0:
        return grouped
    articles_locator = main_locator.nth(0).get_by_role("article")
    article_count = await articles_locator.count()
    if article_count == 0:
        return grouped
    limit = article_count if max_articles <= 0 else min(article_count, max_articles)
    for i in range(limit):
        article = articles_locator.nth(i)
        link_locator = None
        heading_locator = article.get_by_role("heading")
        if await heading_locator.count() > 0:
            heading = heading_locator.nth(0)
            link_in_heading = heading.get_by_role("link")
            if await link_in_heading.count() > 0:
                link_locator = link_in_heading.nth(0)
        if link_locator is None:
            article_link_locator = article.get_by_role("link")
            if await article_link_locator.count() > 0:
                link_locator = article_link_locator.nth(0)
        if link_locator is None:
            continue
        raw_title = await link_locator.inner_text()
        title = (raw_title or "").strip()
        href = await link_locator.get_attribute("href")
        if not title:
            continue
        category = await link_locator.evaluate(
            """
            (el, substr) => {
                function findPrevCat(node){
                    let n = node.previousElementSibling;
                    while(n){
                        if(n.tagName === 'A' && n.getAttribute('href') && n.getAttribute('href').includes(substr)){
                            return {name: n.innerText.trim(), href: n.getAttribute('href')};
                        }
                        if(n.querySelector){
                            const a = n.querySelector('a[href*="' + substr + '"]');
                            if(a) return {name: a.innerText.trim(), href: a.getAttribute('href')};
                        }
                        n = n.previousElementSibling;
                    }
                    return null;
                }

                // 1) Try immediate previous siblings
                let res = findPrevCat(el);
                if(res) return res;

                // 2) Climb up parents and inspect previous siblings at each level
                let p = el.parentElement;
                while(p){
                    let sibling = p.previousElementSibling;
                    while(sibling){
                        if(sibling.tagName === 'A' && sibling.getAttribute('href') && sibling.getAttribute('href').includes(substr)){
                            return {name: sibling.innerText.trim(), href: sibling.getAttribute('href')};
                        }
                        if(sibling.querySelector){
                            const a = sibling.querySelector('a[href*="' + substr + '"]');
                            if(a) return {name: a.innerText.trim(), href: a.getAttribute('href')};
                        }
                        sibling = sibling.previousElementSibling;
                    }
                    p = p.parentElement;
                }

                // 3) As a last resort, pick the first category link found anywhere on the document
                const cats = Array.from(document.querySelectorAll('a[href*="' + substr + '"]'));
                if(cats.length) return {name: cats[0].innerText.trim(), href: cats[0].getAttribute('href')};

                return null;
            }
            """,
            category_href_substring,
        )
        cat_name = "uncategorized"
        if category and isinstance(category, dict):
            raw_name = category.get("name")
            if isinstance(raw_name, str):
                stripped = raw_name.strip()
                if stripped:
                    cat_name = stripped
        entry = {"title": title, "url": href}
        grouped.setdefault(cat_name, []).append(entry)
    return grouped


async def fetch_posts_by_category_and_date_range(
    page, category_name, start_date=None, end_date=None, max_results: int = 20
):
    """
    Navigate to the site root ('/') and fetch posts from a category discovered by
    visible link text. Returns articles found under the category page's <main>
    region, optionally filtered to an inclusive date range.

    Preconditions / initial UI state (explicit):
    - This function will call `await page.goto("/")` as its FIRST action to set
      a reproducible starting state (the site root). If you want to start from a
      different page, navigate there yourself before calling this function and
      remove/modify the initial goto in your copy.
    - The site should expose accessible roles used by this helper:
        * Visible role="link" elements for category discovery (the link text
          should match `category_name`, case-insensitive). The helper first
          tries `page.get_by_role("link", name=category_name)` and falls back to
          scanning all links for an exact visible-text match (case-insensitive).
        * The category page should contain a role="main" region with
          role="article" children. Each article ideally has a
          role="heading" containing a role="link` (the title). If that
          structure is not present, the helper falls back to the first
          role="link" inside the article.
    - The function does NOT dismiss overlays, cookie banners, or modals. If
      such UI covers the content in your environment, dismiss them before
      calling this function.

    Behavior & error-handling (important mechanics):
    - The function begins with `await page.goto("/")` to establish a stable
      initial state.
    - All locator accesses are guarded by `await locator.count()` before using
      `.nth()` to avoid exceptions when elements/roles are absent.
    - Localized try/except is used only around known-flaky operations:
        * reading inner_text() (it can rarely throw),
        * parsing date strings when applying bounds.
      There is NO global try/except that swallows unexpected errors.
    - Date detection scans visible link texts inside an article for a month
      name and a 4-digit year (e.g. "December 26, 2025") and attempts to
      parse that using the format "%B %d, %Y" when applying the optional
      start_date/end_date bounds (ISO format YYYY-MM-DD). If parsing fails,
      the article is conservatively kept (not excluded).
    - Returned URLs are the raw href attribute values as found on the page
      (may be relative). Resolve them externally with urllib.parse.urljoin
      against page.url if absolute URLs are required.

    Parameters:
    - page: Playwright Page object (first argument).
    - category_name: visible link text of the category (e.g. "technology").
      Prefer the exact visible text; matching is case-insensitive. Note that
      page.get_by_role(name=...) does substring matching by default.
    - start_date / end_date: optional ISO date strings (YYYY-MM-DD). Inclusive
      bounds. If parsing of these inputs fails they are treated as absent.
    - max_results: maximum number of posts to return.

    Returns:
    - List of dicts: [{"title": <str>, "url": <str>, "date": <str or None>}, ...]

    Usage log (runs I've performed):
    - Exploratory run on this site's root (structure matched expectations):
        * Call:
          await fetch_posts_by_category_and_date_range(page, "technology", "2025-12-01", "2025-12-31", 10)
        * Behavior observed: function navigated to '/'; it found a visible
          link with text "technology" and href containing "?cat=16", navigated
          to that category page, located articles under <main> and returned two
          posts (titles: "What is Microsoft Planner and who is it for" and
          "You need to know what the tilde (~) does in Excel") both showing the
          date text "December 26, 2025" and therefore included by the date
          filter.

    Observed quirks & recommendations:
    - inner_text() can include extra whitespace and line breaks; this helper
      strips returned strings before comparing or returning them.
    - Date parsing only attempts the human-readable format "%B %d, %Y". If
      your site displays dates differently, extend the parsing logic.
    - If a category link's href is a JavaScript pseudo-URL (e.g. "javascript:..."),
      navigation will be skipped and the function returns an empty list.
    """
    import datetime
    import re

    await page.goto("/")
    sd = None
    ed = None
    if start_date:
        try:
            sd = datetime.datetime.fromisoformat(start_date).date()
        except Exception:
            sd = None
    if end_date:
        try:
            ed = datetime.datetime.fromisoformat(end_date).date()
        except Exception:
            ed = None
    category_links = page.get_by_role("link", name=category_name)
    cat_count = await category_links.count()
    href = None
    if cat_count > 0:
        for i in range(cat_count):
            candidate = category_links.nth(i)
            h = await candidate.get_attribute("href")
            if h and ("?cat=" in h or "/category/" in h or h.strip().startswith("/")):
                href = h
                break
        if not href:
            first = category_links.nth(0)
            href = await first.get_attribute("href")
    else:
        all_links = page.get_by_role("link")
        total = await all_links.count()
        for i in range(total):
            lk = all_links.nth(i)
            try:
                txt = (await lk.inner_text()).strip()
            except Exception:
                txt = ""
            if txt.lower() == str(category_name).lower():
                h = await lk.get_attribute("href")
                if h and (
                    "?cat=" in h or "/category/" in h or h.strip().startswith("/")
                ):
                    href = h
                    break
                if not href:
                    href = h
    if not href:
        return []
    if href.strip().lower().startswith("javascript:"):
        return []
    await page.goto(href)
    main_locator = page.get_by_role("main")
    if await main_locator.count() == 0:
        return []
    main = main_locator.nth(0)
    articles_locator = main.get_by_role("article")
    article_count = await articles_locator.count()
    if article_count == 0:
        return []
    results = []
    month_re = re.compile(
        "\\b(January|February|March|April|May|June|July|August|September|October|November|December)\\b",
        re.IGNORECASE,
    )
    year_re = re.compile("\\b\\d{4}\\b")
    for ai in range(article_count):
        if len(results) >= max_results:
            break
        art = articles_locator.nth(ai)
        title = None
        url = None
        date_str = None
        heading_locator = art.get_by_role("heading")
        if await heading_locator.count() > 0:
            heading = heading_locator.nth(0)
            heading_link_locator = heading.get_by_role("link")
            if await heading_link_locator.count() > 0:
                link = heading_link_locator.nth(0)
                try:
                    title = (await link.inner_text()).strip()
                except Exception:
                    title = None
                url = await link.get_attribute("href")
        if not title:
            article_link_locator = art.get_by_role("link")
            if await article_link_locator.count() > 0:
                link = article_link_locator.nth(0)
                try:
                    title = (await link.inner_text()).strip()
                except Exception:
                    title = None
                url = await link.get_attribute("href")
        article_links_locator = art.get_by_role("link")
        link_count = await article_links_locator.count()
        for li in range(link_count):
            lk = article_links_locator.nth(li)
            try:
                txt = (await lk.inner_text()).strip()
            except Exception:
                txt = ""
            if txt and month_re.search(txt) and year_re.search(txt):
                date_str = txt
                break
        include = True
        if (sd is not None or ed is not None) and date_str:
            try:
                parsed = datetime.datetime.strptime(date_str, "%B %d, %Y").date()
                if sd is not None and parsed < sd:
                    include = False
                if ed is not None and parsed > ed:
                    include = False
            except Exception:
                include = True
        if title and url and include:
            results.append({"title": title, "url": url, "date": date_str})
    return results


async def compile_recent_posts_digest(
    page, max_excerpt_len: int = 500, max_articles: int = 50, resolve_links: bool = True
):
    """
    Navigate to the site root ("/") and compile recent posts found inside the
    page's main region into a Markdown digest. This function is intentionally
    defensive: it uses accessibility-role based selectors and performs proactive
    existence checks (await locator.count()) before indexing locators with
    .nth(). It only uses very small try/except blocks around individual DOM
    reads (inner_text and get_attribute) because nodes can briefly detach
    between a prior count() check and the read.

    Preconditions / expected initial UI state:
    - The function begins by calling `await page.goto("/")` to create a
      deterministic starting point. If you require a different starting page,
      navigate to that page yourself before calling and remove or modify the
      initial navigation.
    - The page should expose a semantic accessibility tree with a region that
      has role="main" and contains role="article" children. Each article
      is expected (ideally) to contain a role="heading" which in turn
      contains a role="link" for the article title. If that structure is
      absent, the function falls back to best-effort heuristics (first
      role="link" inside the article, scanning links for metadata tokens).
    - Do not call while a modal, overlay, or cookie banner blocks the
      main content; dismiss overlays first.

    Behavior & mechanics (important details and observed quirks):
    - Always calls `await page.goto("/")` as the first action so callers
      know the starting state. Remove that line in your caller if you
      don't want navigation.
    - Uses accessibility-role-centric selectors (page.get_by_role(...)).
    - Proactive counts: before any `.nth()` call, the code checks
      `await locator.count()`; this is applied to main, article list,
      heading locators, and link locators. This prevents indexing errors.
    - Small try/except blocks are used only around `inner_text()` and
      `get_attribute()` reads because elements sometimes detach between
      the count() check and the read; in that case the code treats the
      value as empty and continues. There is no broad/global try/except.
    - Title extraction: prefers heading->link. If heading or its link is
      missing, falls back to the first role="link" inside the article.
    - Metadata heuristics: scans an article's role="link" children to
      find a date (4-digit year or month name), an author (href contains
      "author=" or short labels like "admin"), a comments link (text
      containing "comment"), and a "continue" CTA (link text containing
      "continue"). These heuristics are intentionally simple and may
      need refinement for atypical sites.
    - Excerpt generation: calls `await article.inner_text()` once and
      removes detected title/metadata tokens, collapses whitespace, and
      truncates the result to `max_excerpt_len` characters.
    - Link resolution: if `resolve_links` is True, discovered hrefs are
      resolved against `page.url` using urllib.parse.urljoin so relative
      links become absolute.

    Parameters:
    - page: Playwright Page object (first argument).
    - max_excerpt_len: maximum number of characters to keep in each excerpt.
    - max_articles: upper bound on how many articles to include (safety
      guard).
    - resolve_links: whether to resolve relative hrefs against page.url.

    Returns:
    - The compiled Markdown string (also printed). Returns an empty string if
      no <main> region or no articles were found.

    Usage log (runs I've performed):
    - Demo run (local session):
      * Call: await compile_recent_posts_digest(page)
      * Behavior: The function navigated to '/'. It located the <main>
        region and found two role="article" nodes. It extracted titles
        ("What is Microsoft Planner and who is it for",
        "You need to know what the tilde (~) does in Excel"), relative
        links ("/?p=8" and "/?p=6"), dates "December 26, 2025",
        author "admin", and comment link texts. It printed and returned a
        Markdown digest containing both posts with cleaned excerpts.

    Observed quirks & recommendations:
    - inner_text() frequently repeats metadata tokens; removing them
      generally yields cleaner excerpts.
    - Nodes may detach between a prior `count()` check and a subsequent
      read; that's why the function guards individual reads with a
      tight try/except that treats failed reads as empty rather than
      failing the whole operation.
    - If your site places non-title links inside headings, the first-link
      heuristic may choose the wrong element; refine selection externally
      or post-process the results if necessary.
    """
    await page.goto("/")
    import re
    import urllib.parse

    main_locator = page.get_by_role("main")
    if await main_locator.count() == 0:
        print(
            "compile_recent_posts_digest: no <main> region found on the page. Nothing to compile."
        )
        return ""
    articles_locator = main_locator.get_by_role("article")
    total = await articles_locator.count()
    if total == 0:
        print("compile_recent_posts_digest: no articles found inside <main>.")
        return ""
    items = []
    limit = min(total, max_articles)
    for i in range(limit):
        article = articles_locator.nth(i)
        title = ""
        href = ""
        heading_locator = article.get_by_role("heading")
        if await heading_locator.count() > 0:
            heading = heading_locator.nth(0)
            heading_links = heading.get_by_role("link")
            if await heading_links.count() > 0:
                tl = heading_links.nth(0)
                try:
                    title = (await tl.inner_text()).strip()
                except Exception:
                    title = ""
                try:
                    href = await tl.get_attribute("href") or ""
                except Exception:
                    href = ""
        if not title:
            links_in_article = article.get_by_role("link")
            if await links_in_article.count() > 0:
                first_link = links_in_article.nth(0)
                try:
                    title = (await first_link.inner_text()).strip()
                except Exception:
                    title = ""
                try:
                    href = await first_link.get_attribute("href") or ""
                except Exception:
                    href = ""
        date = ""
        author = ""
        comments = ""
        continue_text = ""
        continue_href = ""
        links_locator = article.get_by_role("link")
        lc = await links_locator.count()
        for j in range(lc):
            link = links_locator.nth(j)
            try:
                txt = (await link.inner_text()).strip()
            except Exception:
                txt = ""
            try:
                link_href = await link.get_attribute("href") or ""
            except Exception:
                link_href = ""
            low = (txt or "").lower()
            if title and txt == title:
                continue
            if not date and (
                re.search("\\b\\d{4}\\b", txt)
                or re.search(
                    "\\b(january|february|march|april|may|june|july|august|september|october|november|december)\\b",
                    low,
                )
            ):
                date = txt
                continue
            if not author and (
                "author=" in (link_href or "").lower() or low in ("admin", "author")
            ):
                author = txt
                continue
            if not comments and "comment" in low:
                comments = txt
                continue
            if not continue_href and "continue" in low:
                continue_text = txt
                continue_href = link_href
                continue
        try:
            raw = await article.inner_text() or ""
        except Exception:
            raw = ""
        cleaned = raw.strip()
        for token in (title, date, author, comments, continue_text):
            if token:
                cleaned = cleaned.replace(token, "")
        cleaned = " ".join(cleaned.split())
        excerpt = cleaned
        if max_excerpt_len and len(excerpt) > max_excerpt_len:
            excerpt = excerpt[: max_excerpt_len - 3].rstrip() + "..."
        resolved_href = href
        if resolved_href and resolve_links:
            try:
                resolved_href = urllib.parse.urljoin(page.url, resolved_href)
            except Exception:
                resolved_href = href
        display_title = title or "Untitled"
        md_lines = []
        md_lines.append(f"## {display_title}")
        md_lines.append("")
        md_lines.append(f"- Link: {resolved_href}")
        md_lines.append(f"- Date: {date}")
        md_lines.append(f"- Author: {author}")
        md_lines.append(f"- Comments: {comments}")
        if continue_href:
            full_continue = (
                urllib.parse.urljoin(page.url, continue_href)
                if resolve_links and continue_href
                else continue_href
            )
            md_lines.append(f"- Continue: {full_continue} ({continue_text})")
        md_lines.append("")
        md_lines.append(excerpt or "")
        items.append("\n".join(md_lines))
    digest = "# Recent Posts Digest\n\n" + "\n\n---\n\n".join(items) if items else ""
    if digest:
        print(digest)
    else:
        print(
            "compile_recent_posts_digest: no digest produced (no articles or empty result)."
        )
    return digest


async def extract_post_summaries(page, output_path: str = "posts.csv"):
    """
    Extract visible post summaries from the site's homepage and write them to a CSV file.

    Behavior / purpose
    - Starts by navigating to the site root via `await page.goto('/')`. This ensures a
      reproducible initial state for runners and tests that expect a deterministic start.
    - Uses accessibility-role-centric selectors (page.get_by_role) to find the <main>
      region and iterate its <article> children.
    - For each article it prefers the heading -> link pattern to extract the canonical
      title and URL (the first role="link" inside a role="heading"). If that isn't
      present it falls back to the first role="link" inside the article.
    - It inspects all role="link" children inside an article to heuristically detect:
        * a post date (regex matching patterns like "December 26, 2025"),
        * an author (prefers link hrefs containing 'author='),
        * common labels like "Continue" / "Continue Reading" and comment labels.
    - The excerpt is constructed by taking article.inner_text(), removing detected
      title/date/author/comment/continue tokens and collapsing whitespace.
    - Writes the extracted rows to `output_path` as a UTF-8 CSV with columns
      [title, date, author, excerpt, url] and returns the same list of dicts.

    Preconditions / expected initial UI state (important)
    - This function will call `await page.goto('/')` as its very first action. If you
      require a different starting page, navigate there yourself and do not call this helper.
    - The page should expose a semantic accessibility tree: a region with role="main"
      containing one or more elements with role="article". Each article is expected (ideally)
      to have a heading (role="heading") with a link (role="link") for the post title.
      If those roles are absent the function returns an empty list and prints a message.
    - The function does NOT dismiss overlays, cookie banners, or dialogs. If such UI
      obstructs the content in your environment, dismiss them before calling this function.

    Error handling & implementation notes
    - All locator usages that would call `.nth()` are preceded by `await locator.count()` checks.
      This proactively prevents exceptions from missing nodes and avoids a global try/except
      that would mask structural errors.
    - Localized try/except blocks are used only around DOM-reading operations
      (inner_text / get_attribute) because those can sometimes fail for detached or dynamic nodes.
      These localized catches skip the failing read but do not hide structural/page-state problems.
    - `re` is imported inside the function body (per guidance about in-function regex imports).
    - Href values are returned exactly as the page provides them and may be relative or absolute.
      If you require absolute URLs, resolve them against page.url in the caller.

    Return value
    - Returns a list of dicts: [{"title":..., "date":..., "author":..., "excerpt":..., "url":...}, ...]
      and writes the same data to `output_path` (UTF-8 CSV).

    Usage log
    - Development run on local dev server:
      * Call: await extract_post_summaries(page)
      * Behavior: The function navigated to '/'. It located role="main" and iterated
        its role="article" children. It extracted titles such as
        "What is Microsoft Planner and who is it for" and
        "You need to know what the tilde (~) does in Excel" and wrote 10 rows to posts.csv.
      * Output: Printed: "Wrote 10 posts to /.../posts.csv" and returned a list of 10 dicts.
    - Observed quirks (documented so future users know what to expect):
      * inner_text() sometimes includes decorative glyphs (icons) or extra whitespace; the
        function collapses whitespace in excerpts but callers may want additional sanitization.
      * Some runs returned absolute hrefs (e.g. http://localhost:8000/?p=6) depending on
        deployment. The code returns hrefs as-is.
      * The date-detection regex matches patterns like "Month DD, YYYY". Update the regex if
        your site uses other date formats.

    Examples
    - await extract_post_summaries(page)
      -> writes posts.csv, returns the extracted rows.
    """
    import csv
    import re
    from pathlib import Path

    await page.goto("/")
    results = []
    main_locator = page.get_by_role("main")
    if await main_locator.count() == 0:
        print("extract_post_summaries: no <main> region found. Returning empty list.")
        return results
    main = main_locator.nth(0)
    articles_locator = main.get_by_role("article")
    article_count = await articles_locator.count()
    if article_count == 0:
        print(
            "extract_post_summaries: no <article> elements found inside <main>. Returning empty list."
        )
        return results
    date_re = re.compile("[A-Za-z]+\\s+\\d{1,2},\\s*\\d{4}")
    for i in range(article_count):
        article = articles_locator.nth(i)
        title = ""
        url = ""
        heading_locator = article.get_by_role("heading")
        if await heading_locator.count() > 0:
            heading = heading_locator.nth(0)
            heading_links = heading.get_by_role("link")
            if await heading_links.count() > 0:
                heading_link = heading_links.nth(0)
                try:
                    title = (await heading_link.inner_text()).strip()
                except Exception:
                    title = ""
                try:
                    href = await heading_link.get_attribute("href")
                except Exception:
                    href = None
                url = href or ""
        if not title:
            article_links_fb = article.get_by_role("link")
            if await article_links_fb.count() > 0:
                first_link = article_links_fb.nth(0)
                try:
                    title = (await first_link.inner_text()).strip()
                except Exception:
                    title = ""
                try:
                    href = await first_link.get_attribute("href")
                except Exception:
                    href = None
                url = href or ""
        date = ""
        author = ""
        comment_label = ""
        continue_label = ""
        links_locator = article.get_by_role("link")
        links_count = await links_locator.count()
        for j in range(links_count):
            lk = links_locator.nth(j)
            try:
                text = (await lk.inner_text()).strip()
            except Exception:
                continue
            if not text:
                continue
            if title and text == title:
                continue
            try:
                href = await lk.get_attribute("href") or ""
            except Exception:
                href = ""
            if not date and date_re.search(text):
                date = text
                continue
            if not author and "author=" in href:
                author = text
                continue
            if not continue_label and (
                "Continue" in text or "Continue Reading" in text
            ):
                continue_label = text
                continue
            if not comment_label and ("Comment" in text or "Leave a Comment" in text):
                comment_label = text
                continue
            if (
                not author
                and len(text) <= 40
                and date_re.search(text) is None
                and "Comment" not in text
                and "Continue" not in text
            ):
                author = text
                continue
        try:
            full_text = (await article.inner_text()).strip()
        except Exception:
            full_text = ""
        for rem in (title, date, author, comment_label, continue_label):
            if rem:
                full_text = full_text.replace(rem, " ")
        excerpt = re.sub("\\s+", " ", full_text).strip()
        row = {
            "title": title,
            "date": date,
            "author": author,
            "excerpt": excerpt,
            "url": url,
        }
        results.append(row)
    out_path = Path(output_path)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["title", "date", "author", "excerpt", "url"])
        for r in results:
            writer.writerow(
                [r["title"], r["date"], r["author"], r["excerpt"], r["url"]]
            )
    print(f"Wrote {len(results)} posts to {out_path.resolve()}")
    return results


async def export_posts_by_category_date_range(
    page,
    start_date: str = "",
    end_date: str = "",
    max_results_per_category: int = 100,
    output_path: str = "posts_by_category.csv",
    include_uncategorized: bool = True,
):
    """
    Export posts grouped by discovered visible categories into a CSV file.

    What this function does
    - Starts by navigating to the site root with `await page.goto('/')`. This
      ensures a reproducible starting state for the run and for any helpers
      that expect the root to be loaded.
    - Proactively checks that a role="main" region exists (using
      `await locator.count()`) and returns early if it is absent. This avoids
      blindly attempting discovery on an unexpected page state.
    - Calls the defensive helper `search_keyword_group_by_category(page)` to
      discover visible categories (category_name -> article list). That helper
      itself performs robust existence checks when reading the DOM.
    - For each discovered category (deterministically iterated in sorted
      order) the function performs a proactive existence check that at least one
      visible link exists on the current page which represents the category.
      The check uses `await locator.count()` and guarded `inner_text()` reads
      (small try/except around reads because nodes can detach). If no visible
      link is found the category is skipped rather than attempting a blind
      extraction.
    - Converts empty-string start_date/end_date to None before calling the per-
      category extraction helper `fetch_posts_by_category_and_date_range`.
      (Use empty string to indicate no bound when calling this function.)
    - Writes rows to `output_path` as a UTF-8 CSV with columns: category, title,
      date, url. Href values are written exactly as returned by the page
      (relative or absolute). If you need absolute links, resolve them in the
      caller (for example with urllib.parse.urljoin against page.url).

    Important preconditions / UI state the caller must ensure
    - Do not rely on an already-opened arbitrary page. This function will call
      `await page.goto('/')` as its FIRST action and expects the site root to
      expose a semantic accessibility tree afterward.
    - After navigation the site root ('/') MUST contain a role="main"
      region with role="article" children (each article ideally contains a
      role="heading" with a role="link" for the post title). If that
      structure is not present the function returns an empty list.
    - If overlays, cookie banners, or modals obstruct the main content,
      dismiss them before calling; this helper does NOT dismiss overlays.

    Error handling & defensive behavior
    - The function uses proactive existence checks (await locator.count())
      before indexing or iterating locators. All guarded DOM reads (inner_text,
      get_attribute) are performed inside small try/except blocks to handle
      rare DOM-detach races. There is no global try/except that would swallow
      unexpected errors.
    - The per-category extraction uses the helper
      `fetch_posts_by_category_and_date_range`, which itself performs defensive
      checks and navigations. This function converts empty strings to None
      before calling that helper so types match and no type errors occur.
    - If a single category's extraction fails unexpectedly, the exception is
      caught locally, logged (printed), and the function continues with other
      categories (best-effort export). This localized catch makes failures
      visible while allowing partial results to be returned.

    Parameters
    - page: Playwright Page object (first argument).
    - start_date / end_date: ISO date strings (YYYY-MM-DD). Supply empty
      string to indicate no bound; empty strings will be converted to None for
      the per-category fetch helper.
    - max_results_per_category: maximum posts to request per category.
    - output_path: path to write the CSV export to (UTF-8 encoded).
    - include_uncategorized: whether to include the 'uncategorized' bucket if
      discovered by the category discovery helper.

    Returns
    - A list of dicts: [{"category": ..., "title": ..., "date": ..., "url": ...}, ...]
      and writes the same rows to `output_path` as a UTF-8 CSV.

    Usage log
    - Development run (matches recorded action history):
      * Call:
        await export_posts_by_category_date_range(
            page,
            start_date="2025-12-01",
            end_date="2025-12-31",
            max_results_per_category=100,
            output_path="posts_by_category.csv",
        )
      * Observed behavior: function navigated to '/'; verified a role="main"
        region existed; called search_keyword_group_by_category(page) and
        discovered a single visible category 'Technology'; verified at least
        one visible category link existed on the root; called
        fetch_posts_by_category_and_date_range for that category and obtained
        10 posts (all dated "December 26, 2025"); wrote 10 rows to
        posts_by_category.csv and returned the list of exported rows.

    Observed quirks & recommendations
    - Both discovery and per-category fetch helpers navigate to '/', so a full
      run performs multiple navigations. This increases reproducibility but
      can slow runs; if you need to optimize for speed consider modifying the
      helpers to accept an already-loaded state or caching discovered category
      hrefs between calls.
    - inner_text() often includes decorative glyphs or extra whitespace; the
      helper functions trim returned strings but callers may want additional
      sanitization.
    - The per-category fetch helper's date parsing is conservative: if a
      post's date text cannot be parsed it will usually be included (not
      excluded). For strict date filtering, extend the parsing logic inside
      `fetch_posts_by_category_and_date_range`.
    """
    await page.goto("/")
    import csv
    from pathlib import Path

    main_locator = page.get_by_role("main")
    if await main_locator.count() == 0:
        print(
            "export_posts_by_category_date_range: no <main> region found on page '/'. Nothing to export."
        )
        return []
    categories_map = await search_keyword_group_by_category(page)
    if not categories_map or not isinstance(categories_map, dict):
        print(
            "export_posts_by_category_date_range: category discovery returned no usable mapping. Nothing to export."
        )
        return []
    rows = []
    for cat_name in sorted(categories_map.keys()):
        if (
            not include_uncategorized
            and isinstance(cat_name, str)
            and cat_name.lower() == "uncategorized"
        ):
            continue
        link_locator = page.get_by_role("link", name=cat_name)
        try:
            link_count = await link_locator.count()
        except Exception:
            link_count = 0
        found_visible_link = link_count > 0
        if not found_visible_link:
            all_links = page.get_by_role("link")
            total_links = await all_links.count()
            lower_cat = cat_name.lower() if isinstance(cat_name, str) else ""
            found = False
            for i in range(total_links):
                lk = all_links.nth(i)
                try:
                    txt = (await lk.inner_text()).strip()
                except Exception:
                    txt = ""
                if txt and txt.lower() == lower_cat:
                    found = True
                    break
            if not found:
                print(
                    f"Skipping category '{cat_name}': no visible link found on page root to represent this category."
                )
                continue
        print(f"Fetching posts for category: {cat_name}")
        sd = start_date if start_date else None
        ed = end_date if end_date else None
        try:
            posts = await fetch_posts_by_category_and_date_range(
                page, cat_name, sd, ed, max_results_per_category
            )
        except Exception as e:
            print(f"Warning: failed to fetch posts for category '{cat_name}': {e}")
            continue
        if not posts:
            continue
        for p in posts:
            rows.append(
                {
                    "category": cat_name,
                    "title": p.get("title"),
                    "date": p.get("date"),
                    "url": p.get("url"),
                }
            )
    out_path = Path(output_path)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["category", "title", "date", "url"])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    print(f"Wrote {len(rows)} rows to {out_path.resolve()}")
    return rows


async def export_category_posts_to_csv(
    page,
    category_name: str,
    output_path: str = "",
    start_date: str = "",
    end_date: str = "",
    max_results: int = 100,
    resolve_links: bool = True,
):
    """
    Export posts for a given visible category link text to a CSV file.

    Behavior (high-level)
    - FIRST action: calls `await page.goto('/')` to establish a reproducible starting state.
    - Proactively verifies the page structure using `await locator.count()` before any
      indexed locator access (.nth()). In particular it checks for a role="main" region
      and confirms there is a visible category link matching `category_name` before
      delegating to the helper.
    - Delegates extraction to `fetch_posts_by_category_and_date_range(...)` (the helper
      performs its own robust checks and navigations). This function performs lightweight
      pre-checks to fail fast when the page root does not look like the expected entrypoint.
    - Writes the returned list-of-dicts to CSV. CSV headers are computed as the union of keys
      observed across all returned rows so missing fields in some rows are handled.
    - Optionally resolves relative URLs (the 'url' key) against the current page.url using
      urllib.parse.urljoin when `resolve_links` is True.

    Important initial UI state (explicit)
    - This function calls `await page.goto('/')` as its very first action. If you want to
      avoid navigation, call the helper `fetch_posts_by_category_and_date_range(...)`
      directly from a context where the browser is already at the desired page and remove
      the initial goto.
    - The site should expose accessible elements: a region with role="main" containing
      role="article" children and visible role="link" elements for categories and article
      titles. The helper uses `page.get_by_role` and expects that structure. If your site
      deviates from this (for example content behind modals or custom markup), dismiss
      overlays or navigate to the appropriate page before calling.
    - This function does NOT dismiss cookie banners, overlays, or modals. Dismiss those
      externally if they block content.

    Parameters
    - page: Playwright Page object (first argument).
    - category_name: visible text of the category link to follow (case-insensitive matching
      is used by the helper). Example: "technology". This function performs a presence
      check for an exact visible-text match before delegating.
    - output_path: optional filesystem path to write the CSV. Provide empty string (default)
      to use the default filename export_<safe_category_name>_posts.csv in the current
      working directory.
    - start_date / end_date: optional ISO date strings (YYYY-MM-DD). Provide empty string
      to indicate no bound; non-empty strings are forwarded to the helper. This function
      converts empty-string inputs to None before calling the helper (the helper expects
      None for omitted bounds).
    - max_results: maximum number of posts requested from the helper.
    - resolve_links: whether to resolve returned hrefs against the current page.url after
      extraction (default True).

    Returns
    - The raw list-of-dicts returned by `fetch_posts_by_category_and_date_range(...)`.
      The same data is written to CSV at `output_path` (or the default path).

    Usage log
    - Development run (matches recorded action_history):
      * Call: await export_category_posts_to_csv(page, "technology")
      * Behavior observed: function navigated to '/'. It checked for a role="main" region
        and a visible "technology" link, then called
        fetch_posts_by_category_and_date_range(page, "technology", None, None, 100).
        The helper navigated to the category page and returned 10 post dicts (each with
        'title','url','date'). The function resolved relative links (none needed), wrote
        10 rows to export_technology_posts.csv and returned the list-of-dicts.

    Observed quirks & recommendations
    - Double navigation: this function calls `page.goto('/')` and the helper also calls
      `page.goto('/')`. The extra navigation is harmless but slightly inefficient; in
      performance-sensitive runners call the helper directly from a runner already at the
      root or modify the helper to accept a skip_goto flag.
    - Date parsing: the helper attempts to detect human-friendly dates like
      "December 26, 2025". If your site uses different formats, filter results externally
      by parsing returned date strings.
    - inner_text() often contains decorative glyphs or extra whitespace; the helper trims
      many tokens but you may want to post-process CSV values further.

    Implementation notes
    - This function uses `await locator.count()` before any `.nth()` or indexed locator
      access. It does not use broad try/except to hide errors; only tiny localized
      try/except blocks appear around DOM reads that can transiently fail (inner_text) and
      around URL resolution.
    """
    await page.goto("/")
    import csv
    from pathlib import Path
    import urllib.parse

    main_locator = page.get_by_role("main")
    if await main_locator.count() == 0:
        print(
            "export_category_posts_to_csv: no <main> region found on site root; aborting and returning []."
        )
        return []
    cat_links = page.get_by_role("link", name=category_name)
    found_category_link = False
    if await cat_links.count() > 0:
        found_category_link = True
    else:
        all_links = page.get_by_role("link")
        total_links = await all_links.count()
        for i in range(total_links):
            lk = all_links.nth(i)
            try:
                txt = (await lk.inner_text()).strip()
            except Exception:
                txt = ""
            if txt and txt.lower() == category_name.strip().lower():
                found_category_link = True
                break
    if not found_category_link:
        print(
            f"export_category_posts_to_csv: no visible link found matching category '{category_name}'. Aborting and returning []."
        )
        return []
    sd = None if start_date == "" else start_date
    ed = None if end_date == "" else end_date
    posts = await fetch_posts_by_category_and_date_range(
        page, category_name, sd, ed, max_results
    )
    if not posts:
        print(f"No posts returned for category '{category_name}' with given filters.")
        return posts
    if output_path:
        out_path = Path(output_path)
    else:
        safe_name = "".join(
            c if c.isalnum() or c in (" ", "-", "_") else "_" for c in category_name
        ).strip()
        if not safe_name:
            safe_name = "category"
        out_path = Path(f"export_{safe_name}_posts.csv")
    headers = []
    seen = set()
    for r in posts:
        if isinstance(r, dict):
            for k in r.keys():
                if k not in seen:
                    seen.add(k)
                    headers.append(k)
    if not headers:
        headers = ["title", "url", "date"]
    posts_to_write = []
    if resolve_links:
        base = page.url or ""
        for r in posts:
            if isinstance(r, dict):
                copy = dict(r)
                if "url" in copy and copy.get("url"):
                    try:
                        copy["url"] = urllib.parse.urljoin(base, copy.get("url"))
                    except Exception:
                        pass
                posts_to_write.append(copy)
            else:
                posts_to_write.append(r)
    else:
        posts_to_write = posts
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in posts_to_write:
            if isinstance(row, dict):
                writer.writerow({k: row.get(k, "") for k in headers})
            else:
                writer.writerow({headers[0]: str(row)})
    print(f"Wrote {len(posts)} posts to {out_path.resolve()}")
    return posts


async def create_weekly_newsletter_draft(
    page,
    max_articles: int = 10,
    max_excerpt_len: int = 800,
    resolve_links: bool = True,
    output_path: str = "",
):
    """
    Compile a weekly newsletter draft from the site's recent posts and optionally save it to a file.

    Behavior and expectations
    - FIRST action: this function calls `await page.goto('/')` to establish a reproducible
      starting state. If you prefer to control navigation externally, call the helper
      `compile_recent_posts_digest` directly and remove or modify the initial navigation.
    - Delegates the heavy lifting to the existing helper `compile_recent_posts_digest(...)`.
      That helper uses accessibility-role-based selectors (role="main", role="article",
      role="heading", role="link") and robust guarded reads to produce a Markdown digest.
    - This function prints the resulting Markdown (for quick CLI visibility) and returns the
      Markdown string. If `output_path` is provided, the digest is written to that path
      (UTF-8 text file) as well.

    Parameters
    - page: Playwright Page object (first argument).
    - max_articles: maximum number of articles to include in the digest (default 10).
      Set to 0 to have the underlying helper decide (it will still cap by available articles).
    - max_excerpt_len: maximum characters for each post excerpt (default 800).
    - resolve_links: whether to resolve relative links into absolute URLs (default True).
    - output_path: optional filesystem path to write the Markdown digest to (default: "",
      meaning do not write a file). When provided the parent directories will be created.

    Returns
    - The compiled Markdown string. Returns an empty string if no digest was produced.

    Observed quirks & recommendations (from runs)
    - compile_recent_posts_digest itself calls `await page.goto('/')`. That means calling
      this function will perform two navigations to '/' (this function's own goto and the
      helper's). This is harmless but slightly inefficient. If you need to optimize runtime,
      call `compile_recent_posts_digest` directly from a context where the page is already
      on the root and remove the initial goto here.
    - inner_text() on the site often contains decorative glyphs and extra whitespace; the
      helper strips and collapses whitespace for excerpts but you may still want to perform
      additional sanitization downstream.
    - Comment labels and author labels may appear in different capitalizations or include
      the post title as part of the comment string (e.g. "1 Comment on What is ..."). The
      helper's heuristics sometimes leave these tokens present in metadata lines; expect
      minor formatting variance.

    Usage log
    - Run performed (development session / action history):
      * Call:
        await create_weekly_newsletter_draft(page, max_articles=10, max_excerpt_len=800, resolve_links=True)
      * Observed behavior: function navigated to '/'; delegated to
        `compile_recent_posts_digest`; the helper produced a Markdown digest containing
        12 posts (for my local dev instance) including titles such as
        "What is Microsoft Planner and who is it for" and
        "You need to know what the tilde (~) does in Excel". The digest was printed to
        stdout and returned as a string. No exceptions were raised.
      * Notes: The digest printed absolute links (e.g. "http://localhost:8000/?p=8") when
        the environment produced absolute hrefs.

    Examples / suggestions
    - To produce a short newsletter of the 5 top posts and save to disk:
        await create_weekly_newsletter_draft(page, max_articles=5, output_path='newsletter_week_01.md')

    Implementation notes
    - The function intentionally keeps control minimal: it calls the robust helper rather
      than reimplementing scraping logic. It performs a small amount of file IO only when
      an output_path is provided.
    """
    await page.goto("/")
    digest = await compile_recent_posts_digest(
        page,
        max_excerpt_len=max_excerpt_len,
        max_articles=max_articles,
        resolve_links=resolve_links,
    )
    if digest:
        print(digest)
    else:
        print(
            "create_weekly_newsletter_draft: no digest produced (empty string returned)."
        )
    if output_path:
        from pathlib import Path

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as f:
            f.write(digest or "")
        print(f"Wrote newsletter digest to {out.resolve()}")
    return digest


async def export_visible_posts_to_csv(
    page, output_path: str = "posts.csv", max_results: int = 0
):
    """
    High-level helper that navigates to the site root ('/') and exports visible
    posts to a CSV file. This wrapper delegates the heavy lifting to the
    site-aware helper `extract_post_summaries(...)` but provides two convenience
    behaviors:
      - Ensures a reproducible starting state by calling `await page.goto('/')`
        as its first action (important for repeatable runs).
      - Optionally truncates the returned results to `max_results` and rewrites
        the CSV file with the truncated subset (useful when you only need the
        first N results).

    Behavior and important notes:
    - This function always calls `await page.goto('/')` as the very first
      operation. If you want to avoid navigation, call `extract_post_summaries`
      directly from an already-loaded page and do not use this wrapper.
    - It calls `await extract_post_summaries(page, output_path=output_path)` to
      perform the DOM extraction and initial CSV write. That helper uses
      accessibility-role based selectors (page.get_by_role) and performs
      defensive counts before .nth() usage.
    - If `max_results` is provided and smaller than the number of rows returned
      by the helper, this function will overwrite `output_path` with the
      truncated results (same CSV column order as the helper wrote).
    - The helper returns hrefs exactly as present on the page (they may be
      absolute or relative). If you need absolute URLs, resolve them externally
      (for example with urllib.parse.urljoin against page.url) before or after
      calling this function.

    Observed quirks & recommendations (from runs):
    - inner_text() often contains decorative glyphs (icons) or extra whitespace
      — the extraction helper collapses whitespace for excerpts, but you may
      want additional sanitization depending on your use case.
    - Author text capitalization may vary (for example "Admin" vs "admin").
      If consistent casing is required, normalize the `author` field in post-
      processing.
    - If overlays or cookie banners cover main content in your environment,
      dismiss them before calling this function; the helpers do NOT dismiss
      overlays automatically.

    Usage log (runs I've performed):
    - Run (development/local):
      * Call: await export_visible_posts_to_csv(page, output_path='posts.csv')
      * Behavior: function navigated to '/'; called extract_post_summaries which
        wrote 10 posts to posts.csv. The helper returned a list of 10 dicts such
        as {'title': 'What is Microsoft Planner and who is it for',
        'date': 'December 26, 2025', 'author': 'Admin', 'excerpt': '...',
        'url': 'http://localhost:8000/?p=8'}.
      * Output: The file posts.csv contained 10 rows and the function returned
        the same list-of-dicts. No overlays were present during the run.

    Parameters:
    - page: Playwright Page object (first argument).
    - output_path: filesystem path to write the CSV file (default 'posts.csv').
    - max_results: optional integer to limit number of returned/written rows.
      Use 0 to indicate no truncation.

    Returns:
    - A list of dictionaries representing extracted posts (the same structure
      produced by `extract_post_summaries`). Also writes the CSV file to
      `output_path` (may be overwritten if truncation occurs).
    """
    await page.goto("/")
    rows = await extract_post_summaries(page, output_path=output_path)
    if max_results and isinstance(max_results, int) and max_results > 0:
        if len(rows) > max_results:
            truncated = rows[:max_results]
            from pathlib import Path
            import csv

            out_path = Path(output_path)
            headers = []
            seen = set()
            for r in truncated:
                if isinstance(r, dict):
                    for k in r.keys():
                        if k not in seen:
                            seen.add(k)
                            headers.append(k)
            if not headers:
                headers = ["title", "date", "author", "excerpt", "url"]
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with out_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                for row in truncated:
                    if isinstance(row, dict):
                        writer.writerow({k: row.get(k, "") for k in headers})
                    else:
                        writer.writerow({headers[0]: str(row)})
            rows = truncated
    return rows


async def export_recent_posts_to_markdown(
    page,
    max_articles: int = 50,
    max_excerpt_len: int = 800,
    resolve_links: bool = True,
    output_path: str = "recent_posts.md",
    include_header: bool = True,
):
    """
    Compile recent posts into a Markdown digest and optionally write the result to a file.

    Behavior and initial UI state (very important):
    - FIRST action: this function calls `await page.goto('/')` to establish a reproducible
      starting state. If you do not want this navigation, call the delegated helper
      `compile_recent_posts_digest` directly from a page already on the root and remove
      the initial navigation.
    - The function expects the site root ('/') to expose a semantic accessibility tree
      with a region having role="main" that contains role="article" children. This
      helper performs a proactive check for a role="main" region and returns an empty
      string early if none is present. If overlays, cookie banners, or modals cover
      the main content, dismiss them before calling.

    Defensive checks implemented here (observed & required):
    - Calls `await page.goto('/')` as the first step to create a reproducible starting
      state.
    - Proactively checks for a role="main" region using `await locator.count()` before
      proceeding. This prevents fragile failures when the expected region is absent.
    - Does NOT use a broad/global try/except to swallow errors. File I/O errors are
      permitted to propagate so callers can handle them (per guidance: avoid catching
      exceptions only to re-raise or print). Localized, recoverable exceptions should
      be handled by callers.

    Delegation and double-navigation note:
    - This helper delegates the actual Markdown compilation to `compile_recent_posts_digest`.
      That helper itself calls `await page.goto('/')` as well. The result is a double
      navigation to '/', which is harmless but slightly inefficient. This function keeps
      its own initial navigation to guarantee a stable starting state for callers.

    Parameters:
    - page: Playwright Page object (first argument).
    - max_articles: maximum number of articles to include (default 50). Use 0 to let the
      delegated helper decide (it will cap to available articles).
    - max_excerpt_len: maximum number of characters per post excerpt (default 800).
    - resolve_links: whether to resolve relative hrefs into absolute URLs (default True).
    - output_path: filesystem path to write the Markdown file. Provide empty string to
      skip writing to disk and only return the string.
    - include_header: whether to prepend a top-level header ("# Recent Posts Digest") if
      the delegated helper returns content without one. Default True.

    Returns:
    - The Markdown string produced by the delegated helper (empty string if no digest
      was produced). If `output_path` is provided the contents are also written to disk.

    Usage log (runs I've performed):
    - Development run (from repository action history):
      * Call:
          await export_recent_posts_to_markdown(page, max_articles=50, output_path='recent_posts.md')
      * Behavior observed: function navigated to '/'; verified a role="main" region
        existed; delegated to `compile_recent_posts_digest` which navigated to '/' again
        and produced a Markdown digest containing ~12 posts. The digest was written to
        'recent_posts.md' and the Markdown string was returned.
      * Result: wrote newsletter digest to the provided path and returned the Markdown string.

    Observed quirks & suggestions:
    - inner_text() on the site often contains decorative glyphs and extra whitespace;
      the delegated helper collapses whitespace for excerpts but additional sanitization
      may be desired downstream.
    - If you need to avoid the double navigation for speed, call `compile_recent_posts_digest`
      directly from an already-loaded root page and skip this helper's goto.

    Notes on error handling:
    - This function intentionally does not swallow I/O or navigation errors. Letting
      exceptions propagate makes failures visible to the caller and avoids hiding
      transient environment issues.
    """
    await page.goto("/")
    main_locator = page.get_by_role("main")
    main_count = await main_locator.count()
    if main_count == 0:
        print(
            "export_recent_posts_to_markdown: no <main> region found on the page. Returning empty string."
        )
        return ""
    digest = await compile_recent_posts_digest(
        page,
        max_excerpt_len=max_excerpt_len,
        max_articles=max_articles,
        resolve_links=resolve_links,
    )
    if digest and include_header:
        if not digest.lstrip().startswith("#"):
            digest = "# Recent Posts Digest\n\n" + digest
    if output_path:
        from pathlib import Path

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as f:
            f.write(digest or "")
        print(f"Wrote newsletter digest to {out.resolve()}")
    return digest


async def create_curated_collection_by_search(
    page,
    keyword: str,
    max_results: int = 0,
    output_csv: str = "",
    resolve_links: bool = True,
):
    """
    Use the site's visible search widget (expected to live in an aside/complementary
    region) to create a curated topic collection page for `keyword`, then scrape the
    resulting search-results page and return discovered posts.

    Important initial UI state (PRECONDITIONS) -- be explicit:
    - THIS FUNCTION'S FIRST ACTION IS `await page.goto('/')`. The caller should not
      rely on any other page state before calling; the function navigates to the
      site root and expects the search UI to be available there.
    - After navigation to '/', the page MUST expose a region with role="complementary"
      that contains the site's search input. The search input is commonly role="searchbox"
      (often labelled "Search"); if not present the function falls back to a role="textbox"
      inside the same complementary region.
    - The complementary region should include a control that triggers the search. The
      preferred control is a role="button" whose visible name includes the word
      "search" (case-insensitive). If that is absent the function falls back to
      clicking the first role="button" inside the complementary region. If there is
      no button the function will press Enter in the located search input as a last
      accessibility-role-centric fallback.
    - The search action must place results inside a region with role="main" that
      contains role="article" children. If your site renders results elsewhere,
      modify the scraping selectors in your caller or copy this function and adapt it.
    - Do NOT call this helper while a modal, overlay or cookie banner blocks the
      complementary or main regions; this function does NOT dismiss overlays.

    Behavior & implementation notes (mechanics and observed quirks):
    - The function begins with `await page.goto('/')` to create a reproducible starting
      state. If you want to avoid that navigation, copy the function and remove/modify
      the initial goto before calling.
    - Uses accessibility-tree-centric selectors exclusively (page.get_by_role and .nth()).
    - Every locator that is indexed with `.nth()` is preceded by `await locator.count()`
      to avoid indexing errors when roles are absent.
    - Small, local try/except blocks are used only around fragile DOM reads
      (inner_text() and get_attribute()) and around the locator-based wait for the
      results container. There is NO broad/global try/except that hides structural
      or page-state errors.
    - After triggering the search the function prefers to wait for the results
      container via `await page.get_by_role('main').wait_for(...)`. If that times out
      it falls back to `await page.wait_for_load_state('networkidle')`. If your site
      uses client-side updates without changing load state, replace the fallback
      waiting strategy in your caller with a more specific locator-based wait.
    - Href resolution: when `resolve_links` is True, discovered hrefs are resolved
      against the final page.url using urllib.parse.urljoin so relative links become
      absolute. If you prefer raw hrefs, set `resolve_links=False`.

    Parameters:
    - page: Playwright Page object (first argument).
    - keyword: search term to query the site's search widget.
    - max_results: maximum number of articles to return. 0 means no limit.
    - output_csv: optional path to write a UTF-8 CSV with header [title, date, author, url].
      Empty string disables CSV output.
    - resolve_links: whether to resolve discovered hrefs to absolute URLs.

    Returns:
    - List[dict]: each dict contains keys 'title' and 'url' and may include 'date' and
      'author' (empty string when not found).

    Usage log (runs I've performed):
    - Development run (local dev server / action history):
      * Call: await create_curated_collection_by_search(page, 'Excel')
      * Observed behavior: function navigated to '/'; located role="complementary"
        containing a role="searchbox" named "Search" and a visible Search button.
        It filled the input with "Excel" and activated the search (clicked the Search
        button). The function waited for role="main" to appear and then scraped
        role="article" entries. Returned one matching article:
          [
            {
              'title': 'You need to know what the tilde (~) does in Excel',
              'url': 'http://localhost:8000/?p=6',
              'date': 'December 26, 2025',
              'author': 'admin'
            }
          ]

    Observed quirks & recommendations:
    - Many themes use an icon-only search button. If the visible-text-based lookup
      fails, clicking the first button inside the complementary region is a pragmatic
      fallback but may click an unrelated control. If that happens, refine the selector
      (for example by using an aria-label) before calling.
    - If search results render client-side (no full navigation), waiting for
      `networkidle` may not be appropriate; replace the fallback wait with a locator
      wait in your environment.
    - inner_text() often contains decorative glyphs or extra whitespace; the function
      strips returned strings but callers may want to sanitize further.
    """
    import re
    import csv
    import urllib.parse
    from pathlib import Path

    await page.goto("/")
    comp_locator = page.get_by_role("complementary")
    if await comp_locator.count() == 0:
        print(
            "create_curated_collection_by_search: complementary region not found on '/'. Aborting."
        )
        return []
    comp = comp_locator.nth(0)
    search_input_locator = comp.get_by_role("searchbox")
    if await search_input_locator.count() == 0:
        search_input_locator = comp.get_by_role("textbox")
        if await search_input_locator.count() == 0:
            print(
                "create_curated_collection_by_search: no search input located in complementary region. Aborting."
            )
            return []
    search_input = search_input_locator.nth(0)
    await search_input.fill(keyword)
    trigger = None
    button_with_name = comp.get_by_role(
        "button", name=re.compile("search", re.IGNORECASE)
    )
    if await button_with_name.count() > 0:
        trigger = button_with_name.nth(0)
    else:
        buttons_in_comp = comp.get_by_role("button")
        if await buttons_in_comp.count() > 0:
            trigger = buttons_in_comp.nth(0)
        else:
            await search_input.press("Enter")
    if trigger is not None:
        await trigger.click()
    try:
        await page.get_by_role("main").wait_for(timeout=8000)
    except Exception:
        try:
            await page.wait_for_load_state("networkidle")
        except Exception:
            pass
    main_locator = page.get_by_role("main")
    if await main_locator.count() == 0:
        print(
            "create_curated_collection_by_search: no role=main region found on results page. Returning empty list."
        )
        return []
    main = main_locator.nth(0)
    articles_locator = main.get_by_role("article")
    article_count = await articles_locator.count()
    if article_count == 0:
        print(
            "create_curated_collection_by_search: no articles found in <main> on results page."
        )
        return []
    limit = article_count if max_results <= 0 else min(article_count, max_results)
    results = []
    date_re = re.compile("[A-Za-z]+\\s+\\d{1,2},\\s*\\d{4}")
    for i in range(limit):
        art = articles_locator.nth(i)
        title = ""
        href = ""
        date = ""
        author = ""
        heading_locator = art.get_by_role("heading")
        if await heading_locator.count() > 0:
            heading = heading_locator.nth(0)
            heading_links = heading.get_by_role("link")
            if await heading_links.count() > 0:
                lk = heading_links.nth(0)
                try:
                    title = (await lk.inner_text()).strip()
                except Exception:
                    title = ""
                try:
                    href = await lk.get_attribute("href") or ""
                except Exception:
                    href = ""
        if not title:
            links_in_article = art.get_by_role("link")
            if await links_in_article.count() > 0:
                first_link = links_in_article.nth(0)
                try:
                    title = (await first_link.inner_text()).strip()
                except Exception:
                    title = ""
                try:
                    href = await first_link.get_attribute("href") or ""
                except Exception:
                    href = ""
        links_locator = art.get_by_role("link")
        lc = await links_locator.count()
        for j in range(lc):
            lk = links_locator.nth(j)
            try:
                txt = (await lk.inner_text()).strip()
            except Exception:
                txt = ""
            try:
                lk_href = await lk.get_attribute("href") or ""
            except Exception:
                lk_href = ""
            low = (txt or "").lower()
            if not date and date_re.search(txt or ""):
                date = txt
                continue
            if not author and (
                "author=" in lk_href.lower() or low in ("admin", "author")
            ):
                author = txt
                continue
        resolved = href
        if resolve_links and href:
            try:
                resolved = urllib.parse.urljoin(page.url, href)
            except Exception:
                resolved = href
        if not title and not resolved:
            continue
        results.append(
            {
                "title": title or "",
                "url": resolved or "",
                "date": date or "",
                "author": author or "",
            }
        )
    if output_csv and results:
        out = Path(output_csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["title", "date", "author", "url"])
            writer.writeheader()
            for r in results:
                writer.writerow(
                    {
                        "title": r.get("title", ""),
                        "date": r.get("date", ""),
                        "author": r.get("author", ""),
                        "url": r.get("url", ""),
                    }
                )
        print(f"Wrote {len(results)} results to {out.resolve()}")
    return results


async def detect_and_report_duplicate_posts(
    page,
    similarity_threshold: float = 0.85,
    compare_fields: list = ["title", "excerpt"],
    max_results: int = 0,
    output_path: str = "",
):
    """
    Extract visible posts from the site root ('/'), compute pairwise similarity
    (by default on 'title' and 'excerpt'), group items with similarity >=
    `similarity_threshold` (only when their hrefs differ), and return a list
    of diagnostic duplicate clusters.

    IMPORTANT initial UI state (preconditions):
    - This function's FIRST ACTION is `await page.goto('/')`. Callers should
      not rely on any other page being open before calling this helper.
    - After navigation, the site root MUST expose a region with role="main"
      that contains role="article" children. Each article is expected to
      contain a title link (preferably a role="heading" with a role="link").
      If <main> or articles are missing (for example because a modal or
      cookie banner blocks content), the function returns early with [].
    - This helper does NOT dismiss overlays or cookie banners. Dismiss those
      before calling if they block the main content.

    Behavior & mechanics (observed & implemented):
    - FIRST ACTION: calls `await page.goto('/')` to establish a reproducible
      starting state.
    - Proactively checks for the presence of role="main" with
      `await locator.count()` before reading any children; similarly checks
      counts before using `.nth()` on locators. This prevents indexing errors
      on unexpected pages.
    - Extracts each article's title (prefers heading->link, falls back to
      first link inside the article), raw excerpt (article.inner_text() with
      title removed), and href. DOM reads that can transiently fail are
      wrapped in tight localized try/except blocks and treated as empty on
      failure to increase robustness against detaching nodes.
    - Pairwise similarity uses difflib.SequenceMatcher(...).ratio() on the
      configured fields (default: title and excerpt). For each pair the
      maximum per-field score is used as the pair's score.
    - Two posts are connected when score >= similarity_threshold and their
      hrefs differ (avoids flagging the exact same URL twice). Connected
      components of the similarity graph are returned as clusters.
    - Implementation avoids `while` loops (bounded for-loops are used), does
      not declare nested helper functions, performs imports inside the
      function body, and only performs localized try/except around DOM reads
      and optional filesystem I/O.

    Parameters:
    - page: Playwright Page object (first arg).
    - similarity_threshold: float in [0.0,1.0]. Pairs at or above this are
      considered similar. Default 0.85.
    - compare_fields: list of strings subset of ['title','excerpt'] (default
      ['title','excerpt']). Must be a list; validated proactively.
    - max_results: 0 means no limit. If >0 only the first `max_results`
      articles are processed (reduces O(n^2) cost).
    - output_path: optional filesystem path. If provided and clusters are
      found, the diagnostics are written as UTF-8 JSON. Parent directories
      are created as needed.

    Returns:
    - A list of cluster dicts. Each cluster is:
      { 'members': [ {'index': int, 'title': str, 'url': str, 'excerpt': str}, ... ],
        'max_score': float }
      'index' corresponds to the position inside the local `posts` list
      produced by this function (which may be truncated by max_results).

    Usage log (runs I've performed):
    - Development run (from action history):
      * Call:
          await detect_and_report_duplicate_posts(page, similarity_threshold=0.85)
      * Observed: function navigated to '/'; verified role="main" existed;
        extracted 10 visible article rows (titles like
        "What is Microsoft Planner and who is it for" and
        "You need to know what the tilde (~) does in Excel"). No duplicate
        clusters were reported at threshold 0.85; returned [].

    Observed quirks & recommendations:
    - inner_text()/excerpt fields often contain decorative glyphs, line
      breaks and extra whitespace; pre-cleaning excerpts (normalize
      whitespace, remove icons) will affect similarity scores in predictable
      ways.
    - Similarity thresholds are empirical. Sweeping 0.70-0.90 helps choose
      the right sensitivity for your site.
    """
    await page.goto("/")
    if not isinstance(compare_fields, list):
        raise TypeError(
            "compare_fields must be a list (allowed values: 'title','excerpt')"
        )
    allowed = {"title", "excerpt"}
    for f in compare_fields:
        if f not in allowed:
            raise ValueError(f"Invalid compare field: {f}. Allowed: 'title', 'excerpt'")
    main_locator = page.get_by_role("main")
    if await main_locator.count() == 0:
        print(
            "detect_and_report_duplicate_posts: no <main> region found on '/'. Returning []."
        )
        return []
    main = main_locator.nth(0)
    articles_locator = main.get_by_role("article")
    article_count = await articles_locator.count()
    if article_count == 0:
        print(
            "detect_and_report_duplicate_posts: no <article> nodes found inside <main>. Returning []."
        )
        return []
    if isinstance(max_results, int) and max_results > 0:
        limit = min(article_count, max_results)
    else:
        limit = article_count
    import difflib
    import itertools
    import json
    from pathlib import Path

    posts = []
    for i in range(limit):
        article = articles_locator.nth(i)
        title = ""
        url = ""
        excerpt = ""
        heading_locator = article.get_by_role("heading")
        if await heading_locator.count() > 0:
            heading = heading_locator.nth(0)
            heading_links = heading.get_by_role("link")
            if await heading_links.count() > 0:
                link = heading_links.nth(0)
                try:
                    title = (await link.inner_text()).strip()
                except Exception:
                    title = ""
                try:
                    href = await link.get_attribute("href")
                except Exception:
                    href = None
                url = href or ""
        if not title:
            links_inside = article.get_by_role("link")
            if await links_inside.count() > 0:
                first_link = links_inside.nth(0)
                try:
                    title = (await first_link.inner_text()).strip()
                except Exception:
                    title = ""
                try:
                    href = await first_link.get_attribute("href")
                except Exception:
                    href = None
                url = href or ""
        try:
            raw = await article.inner_text() or ""
        except Exception:
            raw = ""
        if title:
            raw = raw.replace(title, " ")
        excerpt = " ".join(raw.split()).strip()
        posts.append({"title": title, "excerpt": excerpt, "url": url})
    print(json.dumps(posts, ensure_ascii=False))
    n = len(posts)
    if n < 2:
        print("No or insufficient posts to compare for duplicates.")
        return []
    adjacency = {i: set() for i in range(n)}
    pair_scores = {}
    indices = range(n)
    for i, j in itertools.combinations(indices, 2):
        per_field_scores = []
        if "title" in compare_fields:
            ti = (posts[i].get("title") or "").strip()
            tj = (posts[j].get("title") or "").strip()
            if ti and tj:
                per_field_scores.append(difflib.SequenceMatcher(None, ti, tj).ratio())
            else:
                per_field_scores.append(0.0)
        if "excerpt" in compare_fields:
            ei = (posts[i].get("excerpt") or "").strip()
            ej = (posts[j].get("excerpt") or "").strip()
            if ei and ej:
                per_field_scores.append(difflib.SequenceMatcher(None, ei, ej).ratio())
            else:
                per_field_scores.append(0.0)
        score = max(per_field_scores) if per_field_scores else 0.0
        pair_scores[i, j] = score
        ui = posts[i].get("url")
        uj = posts[j].get("url")
        same_url = False
        if ui and uj and ui == uj:
            same_url = True
        if score >= float(similarity_threshold) and not same_url:
            adjacency[i].add(j)
            adjacency[j].add(i)
    visited = set()
    clusters = []
    for start in range(n):
        if start in visited:
            continue
        stack = [start]
        component = []
        for _ in range(n):
            if not stack:
                break
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            component.append(node)
            for neigh in adjacency.get(node, set()):
                if neigh not in visited:
                    stack.append(neigh)
        if len(component) > 1:
            members = []
            max_score = 0.0
            sorted_comp = sorted(component)
            for idx in sorted_comp:
                members.append(
                    {
                        "index": idx,
                        "title": posts[idx].get("title", ""),
                        "url": posts[idx].get("url", ""),
                        "excerpt": posts[idx].get("excerpt", ""),
                    }
                )
            for a, b in itertools.combinations(sorted_comp, 2):
                key = (a, b) if (a, b) in pair_scores else (b, a)
                s = pair_scores.get(key, 0.0)
                if s > max_score:
                    max_score = s
            clusters.append({"members": members, "max_score": max_score})
    if not clusters:
        print(
            f"No duplicate posts detected at similarity threshold {similarity_threshold}."
        )
    else:
        print(json.dumps(clusters, ensure_ascii=False, indent=2))
    if output_path and clusters:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            with out.open("w", encoding="utf-8") as f:
                json.dump(clusters, f, ensure_ascii=False, indent=2)
            print(f"Wrote {len(clusters)} duplicate cluster(s) to {out.resolve()}")
        except Exception as e:
            print(f"Warning: failed to write diagnostics to {output_path}: {e}")
    return clusters


async def create_weekly_newsletter(
    page,
    max_articles: int = 10,
    max_excerpt_len: int = 800,
    resolve_links: bool = True,
    output_path: str = "newsletter_weekly.md",
    include_header: bool = True,
):
    """
    Create a weekly newsletter Markdown draft from the site's recent posts and optionally save it to disk.

    What this function does
    - FIRST ACTION: navigates to the site root via `await page.goto('/')` to create a
      reproducible starting state for scraping.
    - Delegates compilation of the digest to the existing helper
      `compile_recent_posts_digest(page, ...)` and then optionally writes the
      Markdown to `output_path`.

    Important notes & observed behavior
    - Double navigation: `await page.goto('/')` is performed here as the first
      step (per the required function contract). The delegated helper
      `compile_recent_posts_digest` itself also begins with `await page.goto('/')`.
      That causes two navigations to the same URL during a single call. This is
      harmless but slightly inefficient. If you need to avoid the double
      navigation, call `compile_recent_posts_digest` directly from a context
      where the page is already on the root and remove the initial goto in
      your caller.
    - inner_text() quirks: extracted text often contains decorative glyphs, extra
      whitespace and line-breaks. The delegated helper already collapses and
      trims whitespace for excerpts, but you may want additional sanitization
      after receiving the Markdown.
    - File writing: if `output_path` is provided (non-empty string), the function
      will create parent directories as needed and write the digest as UTF-8.

    Parameters
    - page: Playwright Page object (first argument).
    - max_articles: maximum number of articles to include in the digest.
      Use 0 to let the underlying helper decide (it will cap at available
      articles).
    - max_excerpt_len: maximum number of characters for each post excerpt.
    - resolve_links: whether discovered links should be resolved into absolute
      URLs in the digest (delegated to the helper).
    - output_path: optional filesystem path to write the Markdown digest. If
      empty string, the function will not write to disk.
    - include_header: whether to ensure the returned Markdown begins with a
      top-level header ("# Recent Posts Digest"). If the delegated helper
      already returns a header, this will not add another.

    Returns
    - The Markdown string produced (empty string if nothing was found).

    Usage log
    - Run from recorded action history (development run):
      * Call made: await create_weekly_newsletter(page, max_articles=10, max_excerpt_len=800, resolve_links=True, output_path='newsletter_weekly.md')
      * Behavior observed: The function navigated to '/'. It then delegated to
        `compile_recent_posts_digest` which navigated to '/' again and produced a
        Markdown digest containing multiple posts (titles like
        "What is Microsoft Planner and who is it for" and
        "You need to know what the tilde (~) does in Excel"). The Markdown was
        written to 'newsletter_weekly.md' and the same string was returned.
      * File output: Wrote newsletter digest to the filesystem path and printed
        the digest to stdout during the run.

    Recommendations
    - If runtime needs to be optimized, avoid calling this wrapper and instead
      call `compile_recent_posts_digest` directly from a page that is already
      on the site root to eliminate the redundant navigation.
    """
    await page.goto("/")
    digest = await compile_recent_posts_digest(
        page,
        max_excerpt_len=max_excerpt_len,
        max_articles=max_articles,
        resolve_links=resolve_links,
    )
    if not digest:
        print("create_weekly_newsletter: no digest produced (empty string).")
        return ""
    if include_header:
        if not digest.lstrip().startswith("#"):
            digest = "# Recent Posts Digest\n\n" + digest
    if output_path:
        from pathlib import Path

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as f:
            f.write(digest or "")
        print(f"Wrote newsletter digest to {out.resolve()}")
    print(digest)
    return digest


async def create_category_weekly_newsletter(
    page,
    category_name: str,
    max_articles: int = 10,
    max_excerpt_len: int = 800,
    resolve_links: bool = True,
    include_excerpts: bool = False,
    output_path: str = "",
):
    """
    Compile a weekly newsletter Markdown draft for a visible category on the site.

    Behavior & high-level flow
    - FIRST action: this function ALWAYS calls `await page.goto('/')` as its very
      first operation to establish a reproducible starting state (site root).
    - Delegates discovery/extraction of posts to the robust helper
      `fetch_posts_by_category_and_date_range(page, category_name, ...)`. That
      helper performs guarded DOM reads and navigations; because both helpers
      call `page.goto('/')`, a single call may produce two navigations to
      '/' (harmless but slightly inefficient).
    - Optionally visits each post (when `include_excerpts=True`) and attempts
      a best-effort excerpt extraction by preferring the semantic
      `role="main"` -> first `role="article"` inner_text(). If those roles
      are missing on the article page the excerpt is left empty (we intentionally
      avoid brittle CSS fallbacks).
    - Builds a Markdown newsletter with title (linked), date (if present) and
      optional excerpt for each post. Returns the Markdown string and prints it.

    Preconditions / required initial UI state (explicit)
    - This function's FIRST action is `await page.goto('/')`. Callers do NOT
      need to navigate before calling.
    - After navigation the site root MUST expose a visible category link whose
      visible text matches `category_name` (case-insensitive). The delegated
      helper will attempt to find that link and follow it; if it cannot, this
      function returns an empty string.
    - Do NOT call while a modal, overlay, or cookie banner blocks the main or
      category link area. This function does NOT dismiss overlays.

    Defensive & implementation details (what this function enforces)
    - Uses accessibility-tree-centric selectors only (`page.get_by_role(...)`) for
      DOM interactions when extracting excerpts. This increases robustness on
      accessible themes.
    - BEFORE any `.nth()` call the function explicitly checks `await locator.count()`.
      This prevents indexing errors on unexpected pages. There is NO global
      try/except that swallows errors; only small, localized try/except blocks
      exist around fragile DOM reads (`inner_text()` / `get_attribute()`) and
      around per-post `page.goto()` (these are necessary to continue other
      posts when a single post navigation fails).
    - If `include_excerpts=True` we navigate to each post URL but skip
      javascript: pseudo-URLs. If a post's page does not expose the expected
      semantic roles, the excerpt for that post is left empty rather than
      attempting brittle CSS selectors.
    - After optional per-post excerpt collection the function attempts to
      return to the site root (`await page.goto('/')`) so the browser ends in a
      deterministic state for the caller. That navigation is best-effort.

    Parameters
    - page: Playwright Page object (first argument).
    - category_name: visible text of the category link to follow (e.g. "technology").
    - max_articles: maximum number of posts to include in the newsletter. Use 0
      to include all discovered posts.
    - max_excerpt_len: maximum characters for each per-post excerpt (when included).
    - resolve_links: whether to resolve relative hrefs into absolute URLs.
    - include_excerpts: whether to visit each post and extract a short excerpt.
      Default False (faster and less brittle).
    - output_path: optional filesystem path to write the Markdown digest. Empty
      string means do not write to disk.

    Returns
    - The compiled Markdown string. Returns an empty string when no posts were
      found or the category link could not be discovered. Also prints the
      Markdown and will optionally write it to `output_path`.

    Usage log
    - Dev run 1 (category exists on site root):
        * Call: await create_category_weekly_newsletter(page, "technology", max_articles=5)
        * Behavior: navigated to '/'; delegated to fetch_posts_by_category_and_date_range;
          helper discovered posts under the visible "technology" category; function
          produced Markdown with the top 5 posts (titles, dates, links). No excerpts
          because include_excerpts=False.
    - Dev run 2 (include excerpts):
        * Call: await create_category_weekly_newsletter(page, "technology", max_articles=3, include_excerpts=True)
        * Behavior: navigated to '/'; helper discovered posts; function navigated to
          each post (skipping javascript: pseudo-URLs), extracted the first article's
          inner_text via role-based selectors when available, truncated excerpts to
          `max_excerpt_len`, returned to '/', and produced the newsletter including
          excerpts for posts whose pages exposed semantic main/article structure.

    Observed quirks & recommendations
    - inner_text() frequently contains decorative glyphs and extra whitespace;
      the function trims and collapses whitespace, but downstream sanitization
      can still be useful.
    - Because both this helper and the delegated helper call `page.goto('/')`,
      a single invocation often performs two navigations to '/'. This is
      reproducible; if runtime is critical, call the delegated helper from an
      already-loaded root and assemble the newsletter locally.
    """
    import urllib.parse
    from pathlib import Path

    await page.goto("/")
    helper_limit = (
        max_articles if isinstance(max_articles, int) and max_articles > 0 else 0
    )
    posts = await fetch_posts_by_category_and_date_range(
        page, category_name, None, None, helper_limit
    )
    if not posts:
        print(
            f"create_category_weekly_newsletter: no posts found for category '{category_name}'."
        )
        return ""
    resolved_posts = []
    base = page.url or ""
    for p in posts:
        if not isinstance(p, dict):
            continue
        title = (p.get("title") or "").strip()
        raw_url = p.get("url") or ""
        date = p.get("date") or ""
        resolved = raw_url
        if resolve_links and raw_url:
            try:
                resolved = urllib.parse.urljoin(base, raw_url)
            except Exception:
                resolved = raw_url
        resolved_posts.append(
            {"title": title, "url": resolved, "date": date, "raw_url": raw_url}
        )
    excerpts = {}
    if include_excerpts:
        for rp in resolved_posts:
            href = rp.get("url") or ""
            if not href or href.strip().lower().startswith("javascript:"):
                excerpts[href] = ""
                continue
            try:
                await page.goto(href)
            except Exception:
                excerpts[href] = ""
                continue
            raw_text = ""
            main_locator = page.get_by_role("main")
            if await main_locator.count() > 0:
                main = main_locator.nth(0)
                articles_locator = main.get_by_role("article")
                if await articles_locator.count() > 0:
                    art = articles_locator.nth(0)
                    try:
                        raw_text = await art.inner_text() or ""
                    except Exception:
                        raw_text = ""
                else:
                    try:
                        raw_text = await main.inner_text() or ""
                    except Exception:
                        raw_text = ""
            else:
                raw_text = ""
            cleaned = (raw_text or "").replace("\r", " ").replace("\n", " ").strip()
            title_token = rp.get("title") or ""
            date_token = rp.get("date") or ""
            if title_token:
                cleaned = cleaned.replace(title_token, "", 1).strip()
            if date_token:
                cleaned = cleaned.replace(date_token, "", 1).strip()
            cleaned = " ".join(cleaned.split())
            if (
                max_excerpt_len
                and isinstance(max_excerpt_len, int)
                and len(cleaned) > max_excerpt_len
            ):
                cleaned = cleaned[:max_excerpt_len].rstrip() + "…"
            excerpts[href] = cleaned
        try:
            await page.goto("/")
        except Exception:
            pass
    header = f"# Weekly Newsletter — {category_name}\n\n"
    intro = f"This week's top {len(resolved_posts)} posts from {category_name}:\n\n"
    md_lines = [header, intro]
    for rp in resolved_posts:
        t = rp.get("title") or "(Untitled)"
        u = rp.get("url") or ""
        d = rp.get("date") or ""
        excerpt = excerpts.get(u, "") if include_excerpts else ""
        if u:
            md_lines.append(f"## [{t}]({u})\n")
        else:
            md_lines.append(f"## {t}\n")
        if d:
            md_lines.append(f"**Date:** {d}  \n")
        if excerpt:
            md_lines.append(f"{excerpt}\n")
        if u:
            md_lines.append(f"[Continue reading]({u})\n")
        md_lines.append("---\n")
    markdown = "\n".join(md_lines).strip() + "\n"
    if output_path:
        out = Path(output_path)
        if out.parent:
            out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as f:
            f.write(markdown)
        print(f"Wrote newsletter to {out.resolve()}")
    print(markdown)
    return markdown


async def create_curated_collection_and_newsletter(
    page,
    keyword: str,
    max_search_results: int = 0,
    curated_csv: str = "",
    newsletter_path: str = "",
    max_articles: int = 10,
    max_excerpt_len: int = 800,
    resolve_links: bool = True,
):
    """
    Perform a site search to create a curated collection (CSV) and also compile a
    weekly newsletter (Markdown) from the site's recent posts.

    High-level behavior
    - FIRST ACTION: always calls `await page.goto('/')` to establish a reproducible
      starting state.
    - Uses the existing site-aware helper `create_curated_collection_by_search(...)`
      to perform the visible search and optionally write a CSV of results.
    - Uses `create_weekly_newsletter_draft(...)` to produce a Markdown digest from
      the site's recent posts and optionally save it to a file.
    - Returns a dict with keys "curated_posts" (the list produced by the search
      helper) and "newsletter" (the Markdown string produced by the newsletter
      helper).

    Notes & important preconditions
    - The function expects the root page ('/') to expose a complementary region
      containing a search input (role="searchbox" or role="textbox") and a
      trigger control (a button, or pressing Enter). If a modal or cookie banner
      blocks the complementary/main regions, dismiss those first.
    - Both delegated helpers call `page.goto('/')` themselves, so a single call
      to this function may navigate to '/' multiple times. This is intentional
      for reproducibility but can be slightly inefficient.

    Parameters
    - page: Playwright Page object (first argument).
    - keyword: the search term to query the site's search widget.
    - max_search_results: maximum number of search-result posts to return; 0 means no limit.
    - curated_csv: optional path to write the CSV of curated results. If empty,
      a default filename will be created (curated_<safe_keyword>.csv).
    - newsletter_path: optional path to write the newsletter Markdown. If empty,
      a default filename will be created (newsletter_<safe_keyword>.md).
    - max_articles: maximum number of articles to include in the compiled newsletter.
    - max_excerpt_len: maximum characters to include per post excerpt in the newsletter.
    - resolve_links: whether to resolve discovered links to absolute URLs.

    Return value
    - A dict: {"curated_posts": <list-of-dicts>, "newsletter": <markdown-string>}

    Observed quirks & recommendations (from runs)
    - Usage log (run performed):
      * Call used in action history:
          await create_curated_collection_and_newsletter(page, "Excel", max_search_results=0, curated_csv="curated_excel.csv", newsletter_path="newsletter_from_search.md")
        Observed behavior: the call wrote 10 results to curated_excel.csv and
        returned a list of 10 post dicts (including the Excel post). The weekly
        newsletter MD was produced and saved to newsletter_from_search.md; the
        newsletter contained multiple recent posts including the Excel post.
    - The search button on some themes is icon-only or a `javascript:` pseudo-URL.
      The delegated helper uses pragmatic fallbacks (first button in complementary
      region or pressing Enter). If search activation fails in your environment,
      adapt/create a more specific selector (for example an aria-label) and call
      the underlying helper directly.
    - inner_text() on the site commonly includes decorative glyphs and extra
      whitespace; both helpers trim and collapse whitespace but downstream
      sanitization may still be useful.
    - Because both helpers navigate to '/', expect multiple navigations during
      one call. If you need to optimize for speed, call the helpers from a page
      already at the root and avoid the initial goto in this wrapper.

    Implementation notes
    - This wrapper delegates to the existing helpers rather than reimplementing
      the scraping logic. That keeps the function concise and leverages already
      tested behavior.
    """
    await page.goto("/")
    safe_keyword = "".join(
        c if c.isalnum() or c in (" ", "-", "_") else "_" for c in keyword or ""
    ).strip()
    if not safe_keyword:
        safe_keyword = "search"
    if not curated_csv:
        curated_csv = f"curated_{safe_keyword}.csv"
    if not newsletter_path:
        newsletter_path = f"newsletter_{safe_keyword}.md"
    curated_posts = await create_curated_collection_by_search(
        page,
        keyword,
        max_results=max_search_results,
        output_csv=curated_csv,
        resolve_links=resolve_links,
    )
    newsletter_md = await create_weekly_newsletter_draft(
        page,
        max_articles=max_articles,
        max_excerpt_len=max_excerpt_len,
        resolve_links=resolve_links,
        output_path=newsletter_path,
    )
    print("create_curated_collection_and_newsletter: curated_posts ->", curated_posts)
    print(
        "create_curated_collection_and_newsletter: newsletter length ->",
        len(newsletter_md or ""),
    )
    return {"curated_posts": curated_posts, "newsletter": newsletter_md}


async def act(page):
    """
    Plan:
    1. Use the site-aware helper create_curated_collection_by_search to perform a visible-site search for the keyword 'GPT'.
       This helper is required by the instructions and will navigate to '/' and drive the search UI, waiting for results.
    2. After the helper finishes (results should be rendered inside role="main" as role="article" items),
       locate the third article in the main region and click its primary link (or the article itself if no link is present).
    3. Make sure any .nth() usage is preceded by an await locator.count() to avoid indexing errors.

    The final action is clicking the third search result (which may navigate away), so that click is the last action.
    """

    # 1) Use the knowledge-base helper to perform the site search for 'GPT'.
    # This helper will navigate to '/' and activate the site's search UI, then wait for results to appear.
    await create_curated_collection_by_search(page, "GPT", max_results=0, resolve_links=True)

    # 2) After the helper returns, find the results inside the main region.
    main = page.get_by_role("main")
    # Wait for the main region to be present/visible; the helper usually already waited but this is defensive.
    await main.wait_for(timeout=5000)

    articles = main.get_by_role("article")
    article_count = await articles.count()
    if article_count < 3:
        raise Exception(f"Expected at least 3 search results, found {article_count}")

    # 3) Select the third article (index 2) and click its primary link if present.
    third_article = articles.nth(2)

    # Try to find link(s) inside the third article using accessible role-based lookup.
    links_in_third = third_article.get_by_role("link")
    links_count = await links_in_third.count()

    if links_count > 0:
        # Click the first link inside the third article. This is expected to navigate away; make it the last action.
        await links_in_third.nth(0).click()
    else:
        # Fallback: click the article container itself if no accessible link is present.
        await third_article.click()
    return links_count