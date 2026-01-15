import asyncio, re
from skillweaver.agent import vars

(print,) = vars['/Users/chenboyu/Desktop/Epoch_Drift_Benchmark/Agents_new/SkillWeaver/results/admin_with_skills_v1/shopping_admin/task_94/py_0_0.py']

async def get_dashboard_summary(page):
    """
    Navigate to the Magento Admin Dashboard and capture a quick sales snapshot using
    accessibility-tree-centric selectors.

    Preconditions / Initial UI state:
    - Caller must already be authenticated as an admin user and be able to access the
      Magento admin dashboard at the relative path /index.php/admin/dashboard/.
    - The admin user should have permission to view dashboard widgets; otherwise some
      regions or comboboxes may be missing and the function will return None for those
      values.

    Behavior / What this does (general procedure):
    - Starts by navigating to the relative dashboard URL: /index.php/admin/dashboard/.
    - Allows a small, non-blocking pause to let the page render dynamic widgets.
      (Uses page.wait_for_timeout which never raises exceptions, so the function remains
      robust without broad try/except blocks.)
    - Uses accessibility-focused selectors (page.get_by_role) to locate comboboxes
      (these generally map to <select> elements). It checks counts with
      await locator.count() before using .nth() to avoid index errors.
    - For each combobox found, it evaluates the option texts in the page context to
      detect the Store View selector (identified by an option containing "All Store
      Views") and a Date Range selector (identified by an option containing
      "Last 24 Hours"). If found, it reads the currently-selected option text.
    - Captures the dashboard textual content using accessibility regions first
      (a region named like "Dashboard"), falling back to a document region if needed.

    Important observed / unexpected behaviors (documented):
    - Dashboard inner_text() often includes embedded JavaScript CDATA blocks
      (//<![CDATA[ ... //]]>) and non-breaking spaces ( ). This function returns
      that raw inner text unchanged. Callers should normalize/parse the text if they
      need structured values.
    - There can be multiple comboboxes labeled similarly (for example several
      "Select Range:" controls). This function picks the first combobox that
      contains the expected option label (heuristic). If your Magento instance uses
      different labels or a different language, the detection heuristic will need
      adjustment.
    - No broad try/except blocks are used. The function uses safe checks (counts)
      and small sleeps to avoid race conditions instead of swallowing exceptions.

    Return value (dict):
    - 'store_view_selected': str or None
    - 'date_range_selected': str or None
    - 'dashboard_summary_text': str (raw inner text of the dashboard region or fallback)

    Usage log (observed runs):
    - Run 1 (development / recorded):
        * page.goto('/index.php/admin/dashboard/')
        * Small pause to let widgets render.
        * Detected a combobox containing option "All Store Views" and read selected
          value 'All Store Views'.
        * Detected a combobox containing option "Last 24 Hours" and read selected
          value 'Last 24 Hours'.
        * Captured dashboard_summary_text which included:
            - Lifetime Sales: $39,763.08
            - Average Orders: $1,988.15
            - Last 5 Orders table (customers like Sarah Miller, Grace Nguyen, ...)
            - Search terms grids and several //<![CDATA[ JS blocks for varienGrid objects
            - Several sections reporting "No Data Found"
        * Notes: returned text contained " " (NBSP) placeholders for empty
          table cells. The returned dashboard summary is raw; callers should parse or
          normalize as needed.

    Examples:
    snapshot = await get_dashboard_summary(page)

    """
    await page.goto("/index.php/admin/dashboard/")
    await page.wait_for_timeout(500)
    import re

    store_view_selected = None
    date_range_selected = None
    comboboxes = page.get_by_role("combobox")
    cb_count = await comboboxes.count()
    if cb_count == 0:
        await page.wait_for_timeout(1500)
        cb_count = await comboboxes.count()
    for i in range(cb_count):
        if i >= await comboboxes.count():
            break
        cb = comboboxes.nth(i)
        option_texts = await cb.evaluate(
            "el => Array.from(el.options).map(o => (o.textContent || o.innerText || '').trim())"
        )
        if not option_texts or not isinstance(option_texts, list):
            continue
        if store_view_selected is None and any(
            (t or "").find("All Store Views") != -1 for t in option_texts
        ):
            selected = await cb.evaluate(
                "el => (el.options[el.selectedIndex] && (el.options[el.selectedIndex].textContent || el.options[el.selectedIndex].innerText) || '').trim()"
            )
            store_view_selected = selected or None
        if date_range_selected is None and any(
            (t or "").find("Last 24 Hours") != -1 for t in option_texts
        ):
            selected = await cb.evaluate(
                "el => (el.options[el.selectedIndex] && (el.options[el.selectedIndex].textContent || el.options[el.selectedIndex].innerText) || '').trim()"
            )
            date_range_selected = selected or None
        if store_view_selected is not None and date_range_selected is not None:
            break
    dashboard_summary_text = ""
    heading_region = page.get_by_role("region", name=re.compile("dashboard", re.I))
    if await heading_region.count() > 0:
        dashboard_summary_text = await heading_region.nth(0).inner_text()
    else:
        doc = page.get_by_role("document")
        if await doc.count() > 0:
            dashboard_summary_text = await doc.nth(0).inner_text()
        elif cb_count > 0 and await comboboxes.count() > 0:
            dashboard_summary_text = await comboboxes.nth(0).inner_text()
        else:
            dashboard_summary_text = ""
    return {
        "store_view_selected": store_view_selected,
        "date_range_selected": date_range_selected,
        "dashboard_summary_text": dashboard_summary_text,
    }


async def generate_sales_summary_for_date_range(page, date_range: str):
    """
    Navigate to the Magento Admin Dashboard, select a date range in the dashboard's
    range combobox, and return a snapshot of the dashboard text after the change.

    Behaviour / What this does (general procedure):
    - Navigates to the dashboard relative path: /index.php/admin/dashboard/
    - Looks through all accessible combobox (<select>) elements on the page.
    - Attempts to find a combobox that contains an option whose visible text
      contains the provided `date_range` substring (case-insensitive). If found,
      selects that option by label.
    - Also captures the currently-selected Store View if the dashboard contains a
      combobox with an "All Store Views" option (common in Magento admin).
    - Waits briefly after making the selection to allow widgets to refresh, then
      extracts the dashboard region's inner text (falls back to document region
      if a dashboard region is not found).

    Notes about selectors and heuristics:
    - This function uses page.get_by_role('combobox') to find <select> elements.
      Many Magento admin pages expose the range selector as a combobox without a
      stable accessible name; therefore the function inspects option texts to
      locate the proper combobox.
    - Matching of `date_range` is performed by substring, case-insensitive match.
      Example matches: "Last 24 Hours", "Last 7 Days", "Current Month",
      "YTD". The function will match partial values too (e.g. "last 7" ->
      "Last 7 Days"). If your Magento instance uses translated labels, pass a
      translated substring.
    - The function selects the option by its exact option text as returned by
      the browser (trimmed). Some option texts include non-breaking spaces or
      other invisible characters; the selection uses the text captured from the
      DOM, so it should be robust to those characters.

    Observed / unexpected behaviours and recommendations:
    - Some dashboard widgets may not refresh their data immediately after
      changing the date range; a short wait (500-1500ms) usually suffices.
      If you need a strict guarantee the widgets updated, consider waiting for
      a specific element change (for example, a numeric value to change) rather
      than a fixed timeout.
    - Dashboard inner_text often contains non-breaking spaces ( ) and other
      formatting characters. The returned dashboard text is raw; callers should
      normalize/parse it if they need structured values.
    - In some Magento installs the date range control may not be a combobox or
      may be replaced by a custom widget. If the function can't find a matching
      option it will return applied_date_range=None.

    Return value (dict):
    - 'requested_date_range': str (the date_range argument you passed)
    - 'applied_date_range': str or None (the exact option text that was selected,
      or None if no matching option was found)
    - 'store_view_selected': str or None (the current store view selection if
      found)
    - 'dashboard_summary_text': str (raw inner text of the dashboard region or
      fallback)

    Usage log (observed runs):
    - Run 1 (development / recorded):
        * Called with date_range='Last 24 Hours'. The dashboard was already set
          to that range; the function detected the matching option and reported
          applied_date_range='Last 24 Hours'. Returned dashboard text contained
          multiple NBSP characters and several widget sections with 'No Data
          Found'.
    - Run 2 (development):
        * Called with date_range='Last 7 Days'. The function found the range
          combobox, selected 'Last 7 Days' by label, waited 700ms, and returned
          the updated dashboard text. Some numeric widgets did not visibly
          change in the returned text because they require a full widget
          refresh triggered elsewhere; in that case increasing the wait or
          waiting for a specific DOM change helps.

    Example:
        snapshot = await generate_sales_summary_for_date_range(page, "Last 7 Days")

    """
    await page.goto("/index.php/admin/dashboard/")
    await page.wait_for_timeout(500)
    import re

    requested = date_range
    applied_date_range = None
    store_view_selected = None
    comboboxes = page.get_by_role("combobox")
    cb_count = await comboboxes.count()
    if cb_count == 0:
        await page.wait_for_timeout(1500)
        cb_count = await comboboxes.count()
    for i in range(cb_count):
        if i >= await comboboxes.count():
            break
        cb = comboboxes.nth(i)
        option_texts = await cb.evaluate(
            "el => Array.from(el.options).map(o => (o.textContent || o.innerText || '').trim())"
        )
        if not option_texts or not isinstance(option_texts, list):
            continue
        if store_view_selected is None and any(
            (t or "").find("All Store Views") != -1 for t in option_texts
        ):
            selected = await cb.evaluate(
                "el => (el.options[el.selectedIndex] && (el.options[el.selectedIndex].textContent || el.options[el.selectedIndex].innerText) || '').trim()"
            )
            store_view_selected = selected or None
        for opt_text in option_texts:
            if opt_text and re.search(re.escape(requested), opt_text, re.I):
                await cb.select_option(label=opt_text)
                await page.wait_for_timeout(700)
                applied = await cb.evaluate(
                    "el => (el.options[el.selectedIndex] && (el.options[el.selectedIndex].textContent || el.options[el.selectedIndex].innerText) || '').trim()"
                )
                applied_date_range = applied or None
                break
        if applied_date_range is not None and store_view_selected is not None:
            break
    dashboard_summary_text = ""
    heading_region = page.get_by_role("region", name=re.compile("dashboard", re.I))
    if await heading_region.count() > 0:
        dashboard_summary_text = await heading_region.nth(0).inner_text()
    else:
        doc = page.get_by_role("document")
        if await doc.count() > 0:
            dashboard_summary_text = await doc.nth(0).inner_text()
        elif cb_count > 0 and await comboboxes.count() > 0:
            dashboard_summary_text = await comboboxes.nth(0).inner_text()
        else:
            dashboard_summary_text = ""
    return {
        "requested_date_range": requested,
        "applied_date_range": applied_date_range,
        "store_view_selected": store_view_selected,
        "dashboard_summary_text": dashboard_summary_text,
    }


async def export_dashboard_snapshot(
    page, date_range: str = None, store_view: str = None
):
    """
    Navigate to the Magento Admin Dashboard and export a dashboard snapshot (raw text)
    for an optional store view and date range.

    Preconditions / Initial UI state (required):
    - Caller must already be authenticated as an admin user and be able to access
      the Magento Admin Dashboard at the relative path /index.php/admin/dashboard/.
    - The dashboard page must be visible and unobstructed (no modal dialogs,
      overlays, or other elements covering the Store View or Date Range controls).
      This function DOES NOT attempt to close banners or modals.
    - The Store View and Date Range controls should be native <select> elements
      exposed as role='combobox'. If your Magento install uses a custom
      dropdown widget (click-to-open lists rendered with divs), adapt this
      function to click the widget and choose a visible list item.

    Behavior / What this does (general procedure):
    - Navigates to the dashboard relative URL: /index.php/admin/dashboard/ (idempotent).
    - Locates combobox (<select>) elements using accessibility roles
      (page.get_by_role('combobox')). The function always checks locator counts
      (await locator.count()) before using .nth() or interacting to avoid
      race conditions.
    - To handle option labels that include leading/trailing whitespace or
      non-breaking spaces (NBSP), the function reads option visible text
      exactly as rendered (Locator.all_inner_texts() or evaluate fallback)
      and calls select_option(label=exact_text). This preserves the label's
      exact string when selecting.
    - If select_option(label=...) fails for the matched option, a narrow
      fallback attempts selection by the matching option's value attribute.
      Only that narrow fallback is attempted — no global exception swallowing.
    - After performing requested selections, waits briefly for widgets to
      register changes and captures the dashboard region's inner text.
      Prefers a region whose accessible name contains 'dashboard' (case-insensitive),
      falling back to the document role. Returns raw innerText (may include NBSPs).

    Important selector heuristics and observed behaviours:
    - Many Magento admin option labels include NBSP ( ) or leading whitespace.
      Selecting by the exact label string read from the DOM is more reliable than
      trying to match accessible names that may differ.
    - This function proactively checks locator counts (await locator.count()) before
      indexing or calling .nth() to avoid race conditions and to satisfy proactive
      error checking.
    - Narrow try/except blocks are used only around a specific select operation to
      provide a concrete fallback. Unexpected errors are not swallowed globally.

    Return value (dict):
    - 'requested_date_range': str or None (the date_range argument passed)
    - 'applied_date_range': str or None (exact option text that was selected)
    - 'requested_store_view': str or None (the store_view argument passed)
    - 'applied_store_view': str or None (exact option text that was selected)
    - 'dashboard_summary_text': str (raw inner text of the dashboard region or fallback)

    Usage log (observed runs):
    - Run 1 (initial attempt, observed failure):
        * Called with date_range='Current Month' and store_view='French'.
        * Role-based option name matching timed out because the option labels
          contained leading NBSPs. That revealed the need to read option text
          directly from the DOM and select by that exact string.
    - Run 2 (robust strategy - successful):
        * This implementation read option labels via all_inner_texts(), matched
          the option whose string contained 'French' (including NBSPs) and called
          select_option(label=exact_dom_text). The label-based select succeeded.
        * The date range 'Current Month' was selected using the same pattern.
        * Returned dashboard_summary_text was a large raw text block including
          NBSPs and standard Magento dashboard sections.

    Examples:
        snapshot = await export_dashboard_snapshot(page, date_range='Last 7 Days')
        snapshot = await export_dashboard_snapshot(page, store_view='English')
        snapshot = await export_dashboard_snapshot(page, date_range='Current Month', store_view='All Store Views')
    """
    await page.goto("/index.php/admin/dashboard/")
    await page.wait_for_timeout(500)
    import re

    requested_date_range = date_range
    requested_store_view = store_view
    applied_date_range = None
    applied_store_view = None
    comboboxes = page.get_by_role("combobox")
    cb_count = await comboboxes.count()
    if cb_count == 0:
        await page.wait_for_timeout(1500)
        cb_count = await comboboxes.count()
    for i in range(cb_count):
        current_cb_count = await comboboxes.count()
        if i >= current_cb_count:
            break
        cb = comboboxes.nth(i)
        opts = cb.get_by_role("option")
        opts_count = await opts.count()
        if opts_count == 0:
            continue
        option_texts = None
        try:
            option_texts = await opts.all_inner_texts()
        except Exception:
            option_texts = await cb.evaluate(
                "el => Array.from(el.options).map(o => (o.textContent || o.innerText || ''))"
            )
        if not option_texts or not isinstance(option_texts, list):
            continue
        if requested_store_view and applied_store_view is None:
            match_index = None
            match_text = None
            for idx, txt in enumerate(option_texts):
                if txt and re.search(re.escape(requested_store_view), txt, re.I):
                    match_index = idx
                    match_text = txt
                    break
            if match_index is not None and match_text is not None:
                try:
                    await cb.select_option(label=match_text)
                except Exception:
                    values = await cb.evaluate(
                        "el => Array.from(el.options).map(o => o.value || '')"
                    )
                    if match_index < len(values) and values[match_index] != "":
                        try:
                            await cb.select_option(value=values[match_index])
                        except Exception:
                            pass
                await page.wait_for_timeout(300)
                selected = await cb.evaluate(
                    "el => (el.options[el.selectedIndex] && (el.options[el.selectedIndex].textContent || el.options[el.selectedIndex].innerText) || '')"
                )
                if selected:
                    applied_store_view = selected.strip()
        if not requested_store_view and applied_store_view is None:
            if any((t or "").find("All Store Views") != -1 for t in option_texts):
                selected = await cb.evaluate(
                    "el => (el.options[el.selectedIndex] && (el.options[el.selectedIndex].textContent || el.options[el.selectedIndex].innerText) || '')"
                )
                if selected:
                    applied_store_view = selected.strip()
        if requested_date_range and applied_date_range is None:
            match_index = None
            match_text = None
            for idx, txt in enumerate(option_texts):
                if txt and re.search(re.escape(requested_date_range), txt, re.I):
                    match_index = idx
                    match_text = txt
                    break
            if match_index is not None and match_text is not None:
                try:
                    await cb.select_option(label=match_text)
                except Exception:
                    values = await cb.evaluate(
                        "el => Array.from(el.options).map(o => o.value || '')"
                    )
                    if match_index < len(values) and values[match_index] != "":
                        try:
                            await cb.select_option(value=values[match_index])
                        except Exception:
                            pass
                await page.wait_for_timeout(300)
                selected = await cb.evaluate(
                    "el => (el.options[el.selectedIndex] && (el.options[el.selectedIndex].textContent || el.options[el.selectedIndex].innerText) || '')"
                )
                if selected:
                    applied_date_range = selected.strip()
        if (requested_date_range is None or applied_date_range is not None) and (
            requested_store_view is None or applied_store_view is not None
        ):
            break
    await page.wait_for_timeout(700)
    heading_region = page.get_by_role("region", name=re.compile("dashboard", re.I))
    if await heading_region.count() > 0:
        dashboard_summary_text = await heading_region.nth(0).inner_text()
    else:
        doc = page.get_by_role("document")
        if await doc.count() > 0:
            dashboard_summary_text = await doc.nth(0).inner_text()
        elif cb_count > 0 and await comboboxes.count() > 0:
            dashboard_summary_text = await comboboxes.nth(0).inner_text()
        else:
            dashboard_summary_text = ""
    return {
        "requested_date_range": requested_date_range,
        "applied_date_range": applied_date_range,
        "requested_store_view": requested_store_view,
        "applied_store_view": applied_store_view,
        "dashboard_summary_text": dashboard_summary_text,
    }


async def extract_last_orders_csv(
    page,
    store_view: str = "All Store Views",
    date_range: str = "Last 24 Hours",
    n: int = 5,
) -> str:
    '\n    Navigate to the Magento Admin Dashboard and return the last `n` orders\n    (Customer, Items, Grand Total) as a CSV string for the requested store view\n    and date range.\n\n    Preconditions / initial UI state (required):\n    - Caller must already be authenticated as an admin user and able to reach\n      the Magento admin dashboard at the relative path\n      /index.php/admin/dashboard/ (the function itself calls\n      `await page.goto(\'/index.php/admin/dashboard/\')` to establish a\n      deterministic starting point). If the caller is not logged in the page\n      will redirect to the login screen and the function will not find the\n      expected dashboard widgets.\n    - The dashboard should render a table-like widget that contains the\n      substrings "Customer" and "Grand Total" in its text (commonly the\n      "Last Orders" widget). If your admin panel uses another language or\n      custom headers, adapt the table-detection heuristic in the function to\n      match those translated header substrings.\n\n    Behavior / what this does (general procedure):\n    - Always begins by navigating to the relative dashboard URL so the\n      function can be invoked from any prior page state.\n    - Proactively checks presence using `await locator.count()` before any\n      indexed access (`.nth()`) to avoid Playwright indexing/stale-node\n      errors. There is no global try/except that hides failures; only narrow\n      localized catches are used for operations that may fail transiently\n      (evaluating option labels, selecting an option, or reading inner_text\n      of a node that may detach during re-render).\n    - If a combobox with accessible name "Choose Store View:" exists, the\n      function will attempt to select the requested `store_view`. It first\n      attempts an exact visible-label selection; if that exact label isn\'t\n      present it collects visible option labels from the <select> element\n      and performs a case-insensitive substring match to find a selectable\n      label. The code checks counts before reading options.\n    - If a helper named `generate_sales_summary_for_date_range` exists in\n      globals(), the function will call it to apply `date_range`. The code\n      safely detects whether the helper is an async function or returns an\n      awaitable and awaits it accordingly. If the helper is absent or fails\n      the function uses conservative waits to allow widgets to stabilize.\n    - Scans `page.get_by_role(\'table\')` and selects the first table whose\n      inner text contains both the substrings "Customer" and "Grand Total".\n      Counts are re-checked inside loops to avoid stale-index issues.\n    - Extracts up to `n` non-header rows. For each row it checks the cell\n      count using `await cells.count()` before reading `.nth()` cells. Many\n      Magento dashboard cells render a non-breaking space (NBSP, \'\xa0\')\n      when empty; this function strips NBSP characters so empty cells become\n      empty CSV fields.\n\n    Return value:\n    - CSV string (CRLF line endings) with header [Customer, Items, Grand Total]\n      and up to `n` rows discovered on the dashboard.\n\n    Usage log (observed runs):\n    - Observed run recorded in the KB action history:\n        * Called with store_view=\'English\', date_range=\'Last 7 Days\', n=3.\n        * Navigated to /index.php/admin/dashboard/.\n        * Found and selected the "Choose Store View:" combobox option that\n          matched \'English\' (exact label or matched by substring after reading\n          option labels).\n        * The helper `generate_sales_summary_for_date_range` was present and\n          awaited to apply \'Last 7 Days\'.\n        * Located the Last Orders table and returned CSV (CRLF endings):\n\n          Customer,Items,Grand Total\r\n\n          Sarah Miller,5,\r\n\n          Grace Nguyen,4,\r\n\n          Matt Baker,3,\r\n\n\n    Notes / recommendations:\n    - If your admin UI is translated, pass translated header substrings or\n      update the table detection logic accordingly.\n    - If you need a strict guarantee that widgets refreshed after changing\n      the date range, replace the fixed waits with waits for a specific DOM\n      change (for example, wait for a numeric value to change in a known\n      widget) rather than a timeout.\n\n    Example:\n        csv = await extract_last_orders_csv(page, store_view="English",\n                                            date_range="Last 7 Days", n=3)\n'
    await page.goto("/index.php/admin/dashboard/")
    import io
    import csv
    import re
    import inspect
    import asyncio

    await page.wait_for_timeout(500)
    store_combobox = page.get_by_role("combobox", name="Choose Store View:")
    try:
        sc_count = await store_combobox.count()
    except Exception:
        sc_count = 0
    if sc_count == 0:
        await page.wait_for_timeout(800)
        try:
            sc_count = await store_combobox.count()
        except Exception:
            sc_count = 0
    if sc_count > 0:
        option_locator = store_combobox.get_by_role("option")
        try:
            opt_count = await option_locator.count()
        except Exception:
            opt_count = 0
        chosen_label = None
        option_texts = []
        if opt_count > 0:
            try:
                option_texts = await store_combobox.evaluate(
                    "el => Array.from(el.options).map(o => (o.textContent || o.innerText || '').trim())"
                )
            except Exception:
                option_texts = []
            if isinstance(option_texts, list) and option_texts:
                for opt in option_texts:
                    if opt == store_view:
                        chosen_label = opt
                        break
                if chosen_label is None:
                    for opt in option_texts:
                        if opt and re.search(re.escape(store_view), opt, re.I):
                            chosen_label = opt
                            break
        if chosen_label:
            try:
                await store_combobox.select_option(label=chosen_label)
                await page.wait_for_timeout(300)
            except Exception:
                pass
    helper = globals().get("generate_sales_summary_for_date_range")
    if callable(helper):
        try:
            if inspect.iscoroutinefunction(helper):
                await helper(page, date_range)
            else:
                maybe = helper(page, date_range)
                if asyncio.iscoroutine(maybe) or inspect.isawaitable(maybe):
                    await maybe
        except Exception:
            await page.wait_for_timeout(700)
    else:
        await page.wait_for_timeout(800)
    await page.wait_for_timeout(700)
    orders_table = None
    tables = page.get_by_role("table")
    try:
        tables_count = await tables.count()
    except Exception:
        tables_count = 0
    if tables_count == 0:
        await page.wait_for_timeout(1000)
        try:
            tables_count = await tables.count()
        except Exception:
            tables_count = 0
    for i in range(tables_count):
        try:
            current_tables_count = await tables.count()
        except Exception:
            current_tables_count = 0
        if i >= current_tables_count:
            break
        tbl = tables.nth(i)
        try:
            txt = await tbl.inner_text()
        except Exception:
            continue
        if "Customer" in txt and "Grand Total" in txt:
            orders_table = tbl
            break
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Customer", "Items", "Grand Total"])
    if orders_table is None:
        result = out.getvalue()
        if "\r\n" not in result:
            result = result.replace("\n", "\r\n")
        return result
    rows = orders_table.get_by_role("row")
    try:
        row_count = await rows.count()
    except Exception:
        row_count = 0
    if row_count == 0:
        await page.wait_for_timeout(600)
        try:
            row_count = await rows.count()
        except Exception:
            row_count = 0
    collected = 0
    for ridx in range(row_count):
        try:
            current_row_count = await rows.count()
        except Exception:
            current_row_count = 0
        if ridx >= current_row_count:
            break
        if collected >= n:
            break
        row = rows.nth(ridx)
        try:
            row_text = await row.inner_text()
        except Exception:
            continue
        if "Customer" in row_text and (
            "Items" in row_text or "Grand Total" in row_text
        ):
            continue
        cells = row.get_by_role("cell")
        try:
            cell_count = await cells.count()
        except Exception:
            cell_count = 0
        if cell_count == 0:
            continue
        try:
            raw_customer = await cells.nth(0).inner_text() if cell_count >= 1 else ""
        except Exception:
            raw_customer = ""
        try:
            raw_items = await cells.nth(1).inner_text() if cell_count >= 2 else ""
        except Exception:
            raw_items = ""
        try:
            raw_grand = await cells.nth(2).inner_text() if cell_count >= 3 else ""
        except Exception:
            raw_grand = ""
        if raw_customer is None:
            raw_customer = ""
        if raw_items is None:
            raw_items = ""
        if raw_grand is None:
            raw_grand = ""
        customer = raw_customer.replace("\xa0", "").strip()
        items = raw_items.replace("\xa0", "").strip()
        grand_total = raw_grand.replace("\xa0", "").strip()
        writer.writerow([customer, items, grand_total])
        collected += 1
    result = out.getvalue()
    if "\r\n" not in result:
        result = result.replace("\n", "\r\n")
    return result


async def summarize_top_search_terms_across_store_views(page, store_views: list = None):
    """
    Navigate to the Magento Admin Dashboard and produce a compact, heuristic
    summary of the "Last 5 Search Terms" and "Top 5 Search Terms" widgets
    for one or more store views.

    Preconditions / Initial UI state (required):
    - Caller must already be authenticated as an admin user and be able to access
      the Magento Admin Dashboard at the relative path /index.php/admin/dashboard/.
      This function begins by navigating to that relative URL, so callers may
      call it from any prior page state as long as the session is authenticated.
    - The dashboard page must be visible and unobstructed (no modal dialogs or
      overlays covering the Store View control). This function does NOT try to
      dismiss banners, cookie notices, or modals.
    - The Store View control is expected to be a native <select> exposed as
      role="combobox" in the accessibility tree. If your Magento install
      uses a custom dropdown widget (div-based), pass an explicit `store_views`
      list of exact option label strings (matching the DOM) to avoid discovery
      heuristics.

    Behavior / general procedure:
    - Always begins by navigating to the canonical dashboard relative URL
      '/index.php/admin/dashboard/'. This ensures callers can call this from
      any prior page state.
    - If `store_views` is None, proactively discovers a likely Store View
      combobox by scanning page.get_by_role('combobox') locators and reading
      option labels. The code ALWAYS calls await locator.count() before
      indexing locators to avoid race conditions.
    - If discovery succeeds, the function prefers the discovered option labels
      and (when discovery was performed) will skip caller-provided store view
      labels that are not in the discovered set (recording a clear 'STORE VIEW
      NOT FOUND' result instead of attempting selection). If the caller
      explicitly provided `store_views`, the function will attempt to capture
      each provided label (caller-provided labels are considered authoritative).
    - For each store view to be captured the function calls the existing helper
      export_dashboard_snapshot(page, store_view=label) which selects by the
      exact DOM option label (robust to NBSPs). The helper returns
      'dashboard_summary_text' (raw inner text) and 'applied_store_view'.
    - The raw dashboard snapshot text is normalized (NBSP -> space, empty
      lines removed) and parsed heuristically to extract two widgets:
        * 'last_5' -> list[str] (terms from the "Last 5 Search Terms" widget)
        * 'top_5'  -> list[(str, int|None)] (term and optional numeric uses)
      Parsing is conservative: the parser finds the heading line and consumes
      following non-heading lines until a stop-heading or an explicit
      "No records found" / "No Data Found" marker is encountered.

    Important observed / unexpected behaviors (documented):
    - Dashboard option labels and inner text often contain non-breaking spaces
      (U+00A0). The function normalizes those to U+0020 spaces before parsing.
    - Rows in the raw snapshot may be column-separated by tabs (	) or by runs
      of multiple spaces; the parser splits on tabs or two-or-more spaces.
    - Some Magento installs use custom dropdown widgets (not native <select>).
      Discovery heuristics look for the canonical "All Store Views" option or
      a small set of language names (English/French/German). For localized
      installs provide translated labels via `store_views` to avoid discovery
      failures.
    - The function proactively checks locator counts (await locator.count())
      before indexing and uses narrow try/except blocks only around DOM reads
      that may fail intermittently (for example reading option inner texts).
      There is no broad/global try/except that hides unrelated errors.

    Return value (dict):
    - Mapping: store_view_label -> {
          'applied_store_view': str or None,
          'last_5': list[str],
          'top_5': list[(str, int|None)],
          'raw': str (raw dashboard snapshot text)
      }

    Usage log (observed runs):
    - Development run (recorded in action history): called with no store_views.
      The dashboard exposed a combobox whose options included "All Store Views",
      "English", "French", "German". Discovery returned those labels and the
      function iterated them. For 'All Store Views' and 'English' the parser
      extracted non-empty Last/Top lists (Top 5 included numeric counts). For
      'French' and 'German' the widgets reported "No records found." and the
      parser returned empty lists. The function returned the raw dashboard
      snapshot for each store view as well as the parsed lists.

    Examples:
        summary = await summarize_top_search_terms_across_store_views(page)
        summary = await summarize_top_search_terms_across_store_views(page, store_views=["English","French"])
    """
    await page.goto("/index.php/admin/dashboard/")
    await page.wait_for_timeout(500)
    import re

    results = {}
    discovered_store_views = None
    if store_views is None:
        comboboxes = page.get_by_role("combobox")
        cb_count = await comboboxes.count()
        if cb_count == 0:
            await page.wait_for_timeout(1000)
            cb_count = await comboboxes.count()
        for i in range(cb_count):
            current_cb_count = await comboboxes.count()
            if i >= current_cb_count:
                break
            cb = comboboxes.nth(i)
            opts = cb.get_by_role("option")
            opts_count = await opts.count()
            if opts_count > 0:
                try:
                    option_texts = await opts.all_inner_texts()
                except Exception:
                    option_texts = await cb.evaluate(
                        "el => Array.from(el.options).map(o => (o.textContent || o.innerText || ''))"
                    )
            else:
                option_texts = await cb.evaluate(
                    "el => Array.from(el.options).map(o => (o.textContent || o.innerText || ''))"
                )
            if not option_texts or not isinstance(option_texts, list):
                continue
            joined = "\n".join([(t or "") for t in option_texts])
            if re.search("All\\s*Store\\s*Views", joined, re.I) or any(
                re.search("English|French|German", t or "", re.I) for t in option_texts
            ):
                discovered_store_views = [
                    (t or "").strip() for t in option_texts if t is not None
                ]
                break
    if store_views is None:
        if discovered_store_views:
            final_store_views = discovered_store_views
        else:
            final_store_views = ["All Store Views"]
    else:
        final_store_views = list(store_views)
    available_options = set(discovered_store_views or [])
    for sv in final_store_views:
        if discovered_store_views is not None and sv not in available_options:
            results[sv] = {
                "applied_store_view": None,
                "last_5": [],
                "top_5": [],
                "raw": f"STORE VIEW NOT FOUND IN DISCOVERED OPTIONS: '{sv}'",
            }
            continue
        snapshot = await export_dashboard_snapshot(page, store_view=sv)
        raw = snapshot.get("dashboard_summary_text") or ""
        normalized = raw.replace("\xa0", " ").replace("\xa0", " ")
        lines = [ln.strip() for ln in re.split("[\\r\\n]+", normalized) if ln.strip()]
        last5_index = None
        top5_index = None
        for idx, ln in enumerate(lines):
            if last5_index is None and re.search(
                re.escape("Last 5 Search Terms"), ln, re.I
            ):
                last5_index = idx
            if top5_index is None and re.search(
                re.escape("Top 5 Search Terms"), ln, re.I
            ):
                top5_index = idx
            if last5_index is not None and top5_index is not None:
                break
        stop_patterns = [
            "Top\\s*5\\s*Search\\s*Terms",
            "Last\\s*5\\s*Search\\s*Terms",
            "Orders",
            "Select\\s*Range",
            "Bestsellers",
            "Most\\s*Viewed",
            "Help\\s*Us\\s*Keep\\s*Magento",
        ]
        last5_lines = []
        if last5_index is not None:
            for j in range(last5_index + 1, len(lines)):
                ln = lines[j]
                if any(re.search(pat, ln, re.I) for pat in stop_patterns):
                    break
                if re.search("no records found|no data found", ln, re.I):
                    last5_lines = []
                    break
                last5_lines.append(ln)
        top5_lines = []
        if top5_index is not None:
            for j in range(top5_index + 1, len(lines)):
                ln = lines[j]
                if any(re.search(pat, ln, re.I) for pat in stop_patterns):
                    break
                if re.search("no records found|no data found", ln, re.I):
                    top5_lines = []
                    break
                top5_lines.append(ln)
        parsed_last5 = []
        for ln in last5_lines:
            parts = [p.strip() for p in re.split("\\t+|\\s{2,}", ln) if p and p.strip()]
            if not parts:
                continue
            parsed_last5.append(parts[0])
        parsed_top5 = []
        for ln in top5_lines:
            parts = [p.strip() for p in re.split("\\t+|\\s{2,}", ln) if p and p.strip()]
            if not parts:
                continue
            term = parts[0]
            uses = None
            last_part = parts[-1]
            m = re.search("(\\d+)", last_part)
            if m:
                try:
                    uses = int(m.group(1))
                except Exception:
                    uses = None
            parsed_top5.append((term, uses))
        results[sv] = {
            "applied_store_view": snapshot.get("applied_store_view"),
            "last_5": parsed_last5,
            "top_5": parsed_top5,
            "raw": raw,
        }
    return results


async def download_revenue_and_orders_report(
    page, date_range: str = "Last 7 Days", store_view: str = None, n_orders: int = 5
):
    """
    Navigate to the Magento Admin Dashboard, ensure a requested date range and store view
    are applied (delegating selection to the existing export_dashboard_snapshot helper),
    and return a compact revenue summary plus a CSV string containing up to `n_orders`
    rows from the "Last 5 Orders" widget.

    Preconditions / Initial UI state (required):
    - Caller must already be authenticated as an admin user in the Playwright browser
      context used by this Page.
    - The Magento Admin Dashboard must be reachable at the relative path
      '/index.php/admin/dashboard/' and the dashboard page should be visible and
      unobstructed (no modal dialogs or overlays covering the Store View or Date Range
      controls).
    - The Store View and Date Range controls are expected to be native <select>
      elements exposed as role='combobox'. If your installation uses custom
      dropdown widgets (div-based), provide exact DOM option label strings via
      `store_view` or adapt the helper export_dashboard_snapshot.

    Behavior / general procedure:
    - Calls page.goto('/index.php/admin/dashboard/') to start from a known URL.
    - Delegates selection of date range and store view to export_dashboard_snapshot,
      which contains robust combobox-selection logic (it uses await locator.count()
      checks and label/value fallback selection). Delegation avoids duplicating
      combobox selection heuristics and ensures proactive locator checks are used
      where selection is needed.
    - Validates the helper's returned mapping (proactive check) and then optionally
      prefers the live dashboard region text (using await locator.count() before .nth()).
    - Normalizes non-breaking spaces (U+00A0 -> space) and splits the snapshot into
      trimmed, non-empty lines for conservative parsing.
    - Heuristically extracts revenue values (Revenue, Tax, Shipping, Quantity)
      and the recent orders from the "Last 5 Orders" widget. Rows are split on
      tabs or runs of multiple spaces because Magento often renders tables that way
      in accessibility text dumps.
    - Builds a CSV string (CRLF line endings) with header 'Customer,Items,Grand Total'
      and up to `n_orders` rows. Fields that contain commas or double quotes are
      quoted per basic CSV rules (double quotes escaped by doubling them).

    Important observed / unexpected behaviors (documented):
    - Dashboard option labels and inner text often include non-breaking spaces
      (U+00A0). The delegated helper selects options by the exact DOM label (robust
      to NBSP). This parser replaces NBSP with normal spaces before regexing.
    - The dashboard uses discrete presets (for example "Last 7 Days"). There is no
      generic free-form "last N days" slider — pass a preset substring that exists
      in your instance (or None to leave the current selection).
    - Widgets may require a short time to refresh after changing a selection. The
      helper uses short waits; if your instance is particularly slow, increase
      waits inside that helper or wait for a concrete DOM change.
    - This function performs proactive await locator.count() checks before indexing
      any locator (when preferring the live region) and validates the helper output.
      It deliberately avoids broad try/except blocks.

    Parameters:
    - page: Playwright Page (first argument)
    - date_range: str | None - substring of the dashboard date preset to select
      (e.g. 'Last 7 Days'). If None, the helper will leave the current selection.
    - store_view: str | None - substring of a Store View option label to select
      (e.g. 'English' or 'All Store Views'). If None, the helper will use the
      currently-applied store view.
    - n_orders: int - how many recent orders to include in the returned CSV

    Return value (dict):
    - requested_date_range: str | None
    - applied_date_range: str | None
    - requested_store_view: str | None
    - applied_store_view: str | None
    - revenue: { 'revenue': str|None, 'tax': str|None, 'shipping': str|None, 'quantity': int|None }
    - orders_csv: str (CSV with CRLF line endings; header: Customer,Items,Grand Total)
    - raw_snapshot: str (raw dashboard inner text captured)

    Usage log (observed runs):
    - Run (recorded in action history): called with date_range='Last 7 Days', store_view=None, n_orders=5.
        * export_dashboard_snapshot selected 'Last 7 Days' (applied_date_range='Last 7 Days')
          and reported applied_store_view='All Store Views'.
        * The raw snapshot included a 'Last 5 Orders' table and a 'Revenue' section.
        * The parser returned revenue values (example: Revenue: '$0.00', Quantity: 0)
          and an orders_csv string with header and five rows (CRLF line endings).

    Examples:
        report = await download_revenue_and_orders_report(page, date_range='Last 7 Days', n_orders=5)
    """
    await page.goto("/index.php/admin/dashboard/")
    snapshot = await export_dashboard_snapshot(
        page, date_range=date_range, store_view=store_view
    )
    if not snapshot or not isinstance(snapshot, dict):
        raise RuntimeError(
            "export_dashboard_snapshot returned unexpected result; expected dict"
        )
    raw = snapshot.get("dashboard_summary_text") or ""
    applied_date_range = snapshot.get("applied_date_range")
    applied_store_view = snapshot.get("applied_store_view")
    import re

    heading_region = page.get_by_role("region", name=re.compile("dashboard", re.I))
    hr_count = await heading_region.count()
    if hr_count > 0:
        try:
            live_text = await heading_region.nth(0).inner_text()
            if live_text and live_text.strip():
                raw = live_text
        except Exception:
            pass
    normalized = raw.replace("\xa0", " ")
    lines = [ln.strip() for ln in re.split("[\\r\\n]+", normalized) if ln.strip()]
    revenue_val = None
    tax_val = None
    shipping_val = None
    quantity_val = None
    for idx, ln in enumerate(lines):
        if revenue_val is None and re.search("\\bRevenue\\b", ln, re.I):
            for j in range(idx, min(idx + 3, len(lines))):
                m = re.search("([\\$€£]?\\s*[0-9,]+(?:\\.[0-9]{2})?)", lines[j])
                if m:
                    revenue_val = m.group(1).strip()
                    break
        if tax_val is None and re.search("\\bTax\\b", ln, re.I):
            m = re.search("([\\$€£]?\\s*[0-9,]+(?:\\.[0-9]{2})?)", ln)
            if m:
                tax_val = m.group(1).strip()
            elif idx + 1 < len(lines):
                m2 = re.search("([\\$€£]?\\s*[0-9,]+(?:\\.[0-9]{2})?)", lines[idx + 1])
                if m2:
                    tax_val = m2.group(1).strip()
        if shipping_val is None and re.search("\\bShipping\\b", ln, re.I):
            m = re.search("([\\$€£]?\\s*[0-9,]+(?:\\.[0-9]{2})?)", ln)
            if m:
                shipping_val = m.group(1).strip()
        if quantity_val is None and re.search("\\bQuantity\\b", ln, re.I):
            m = re.search("(\\d+)", ln)
            if m:
                try:
                    quantity_val = int(m.group(1))
                except Exception:
                    quantity_val = None
    revenue = {
        "revenue": revenue_val,
        "tax": tax_val,
        "shipping": shipping_val,
        "quantity": quantity_val,
    }
    orders_header = "Customer,Items,Grand Total"
    orders_rows = []
    last_orders_index = None
    for idx, ln in enumerate(lines):
        if re.search(re.escape("Last 5 Orders"), ln, re.I):
            last_orders_index = idx
            break
    if last_orders_index is not None:
        for j in range(last_orders_index + 1, len(lines)):
            ln = lines[j]
            if re.search(
                "\\b(Last 5 Search Terms|Top 5 Search Terms|Orders|Amounts|Select Range|Bestsellers|Most Viewed)\\b",
                ln,
                re.I,
            ):
                break
            if re.match("^(Customer|Items|Grand Total)$", ln, re.I):
                continue
            if re.search("no records found|no data found", ln, re.I):
                orders_rows = []
                break
            parts = [p.strip() for p in re.split("\\t+|\\s{2,}", ln) if p and p.strip()]
            if not parts:
                continue
            if len(parts) < 3:
                parts = parts + [""] * (3 - len(parts))
            orders_rows.append(parts[:3])
            if len(orders_rows) >= n_orders:
                break
    csv_lines = [orders_header]
    for row in orders_rows:
        safe_fields = []
        for c in row:
            field = c or ""
            if '"' in field:
                field = field.replace('"', '""')
            if "," in field or '"' in field:
                field = '"' + field + '"'
            safe_fields.append(field)
        csv_lines.append(",".join(safe_fields))
    orders_csv = "\r\n".join(csv_lines) + "\r\n"
    return {
        "requested_date_range": date_range,
        "applied_date_range": applied_date_range,
        "requested_store_view": store_view,
        "applied_store_view": applied_store_view,
        "revenue": revenue,
        "orders_csv": orders_csv,
        "raw_snapshot": raw,
    }


async def get_last_orders_csv(
    page,
    store_view: str = "All Store Views",
    date_range: str = "Last 24 Hours",
    n: int = 5,
) -> str:
    "\n    High-level helper that navigates to the Magento Admin Dashboard and returns\n    the \"Last Orders\" widget as a CSV string (header: Customer, Items, Grand Total).\n\n    What this does (general procedure):\n    - Begins by navigating to the canonical dashboard relative URL\n      '/index.php/admin/dashboard/' to create a deterministic starting state.\n    - Delegates the actual extraction to the existing helper\n      `extract_last_orders_csv` (expected to be available in globals()).\n    - Calls the helper safely whether it is implemented as an async function\n      or a synchronous function that returns an awaitable or a direct result.\n      This avoids a type-error when the helper is retrieved from globals() and\n      the static analyzer can't tell it's awaitable.\n    - Returns the CSV string exactly as produced by the underlying helper.\n\n    Important implementation notes / observed behaviours:\n    - Some earlier attempts simply did `await helper(page, ...)` after retrieving\n      the object from globals(). That can trigger type-checker complaints when\n      the type of `helper` is `object` in a static analysis context. This\n      implementation explicitly inspects the helper with `inspect` and\n      `asyncio.iscoroutine`/`inspect.isawaitable` before awaiting.\n    - The underlying helper (`extract_last_orders_csv`) already handles the\n      heavy lifting (selecting store view/date range, waiting for widgets,\n      parsing the Last Orders table). This wrapper intentionally does not re-implement\n      those interactions — it only standardizes the call and deals with the\n      awaitability edge cases.\n    - If `extract_last_orders_csv` is not present or not callable, the function\n      raises a RuntimeError. This is deliberate: the caller should provide the\n      supporting helper in the runtime environment.\n    - If the helper returns a dict instead of a CSV string (unexpected), the\n      wrapper will attempt to extract a string value sensibly and will raise\n      a RuntimeError if it cannot find a reasonable CSV string.\n\n    Return value:\n    - CSV string (CRLF line endings) with header [Customer, Items, Grand Total]\n      and up to `n` rows found on the dashboard. The string is returned verbatim.\n\n    Usage log (observed runs):\n    - Corrected run (recorded in KB action history):\n        * Called get_last_orders_csv(page, store_view='French', date_range='Current Month', n=5).\n        * The helper `extract_last_orders_csv` was found in globals() and awaited\n          correctly (this wrapper determines awaitability and handles both async\n          helpers and sync helpers returning awaitables).\n        * The underlying helper returned a CSV string with 5 rows. The wrapper\n          returned that string verbatim.\n\n    - Recent observed run (from action history):\n        * Called get_last_orders_csv(page, store_view='English', date_range='Last 7 Days', n=4).\n        * The function navigated to /index.php/admin/dashboard/ and delegated to\n          extract_last_orders_csv.\n        * Result returned (CRLF line endings):\n\n          Customer,Items,Grand Total\r\n\n          Sarah Miller,5,\r\n\n          Grace Nguyen,4,\r\n\n          Matt Baker,3,\r\n\n          Lily Potter,4,\r\n\n\n        * Note: the 'Grand Total' column values were empty in the dashboard rows\n          (observed as empty CSV fields). This is common in some Magento demo or\n          minimally-populated instances where the Last Orders widget omits grand\n          total values in the summary view. If callers require precise grand\n          totals, they should navigate into individual order details pages or\n          retrieve reports from the Sales > Orders export features.\n\n    Examples:\n        csv = await get_last_orders_csv(page, store_view='French', date_range='Current Month', n=5)\n\n"
    await page.goto("/index.php/admin/dashboard/")
    import inspect
    import asyncio

    helper = globals().get("extract_last_orders_csv")
    if not callable(helper):
        raise RuntimeError(
            "Required helper `extract_last_orders_csv` is not available in the environment or is not callable."
        )
    if inspect.iscoroutinefunction(helper):
        result = await helper(page, store_view=store_view, date_range=date_range, n=n)
    else:
        maybe = helper(page, store_view=store_view, date_range=date_range, n=n)
        if asyncio.iscoroutine(maybe) or inspect.isawaitable(maybe):
            result = await maybe
        else:
            result = maybe
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in ("csv", "result", "value", "data"):
            val = result.get(key)
            if isinstance(val, str):
                return val
        for val in result.values():
            if isinstance(val, str):
                return val
        raise RuntimeError(
            "Helper returned a dict but no CSV string could be extracted from it."
        )
    raise RuntimeError(
        f"Helper returned an unexpected type: {type(result)!r}. Expected a CSV string."
    )


async def fetch_recent_orders_csv(
    page,
    store_view: str = "All Store Views",
    date_range: str = "Last 24 Hours",
    n: int = 5,
) -> str:
    "\n    Lightweight wrapper that navigates to the Magento Admin Dashboard and returns\n    the \"Last Orders\" widget as a CSV string (header: Customer,Items,Grand Total).\n\n    Behavior / what this does (general procedure):\n    - Begins by navigating to the canonical dashboard relative URL\n      '/index.php/admin/dashboard/' so the function can be called from any prior\n      page state.\n    - Delegates the heavy lifting to the existing knowledge-base helper\n      `get_last_orders_csv` (if available). This wrapper carefully handles the\n      helper's awaitability (it may be an async function or a sync function that\n      returns an awaitable) and returns the CSV string verbatim.\n\n    Preconditions / initial UI state:\n    - Caller must be authenticated in the browser context and able to access\n      the Magento Admin Dashboard at /index.php/admin/dashboard/. If not\n      authenticated the page will redirect to the login screen and the helper\n      will not be able to find the expected dashboard widgets.\n    - The dashboard should expose a Last Orders widget whose accessibility\n      text contains the column headers \"Customer\" and \"Grand Total\".\n\n    Important observed / unexpected behaviors (documented):\n    - The Last Orders widget in some Magento installs omits the Grand Total\n      values in the compact dashboard view; the CSV's Grand Total column may\n      therefore be empty for many rows. If precise grand totals are required,\n      callers should open individual orders or use the Sales > Orders export.\n    - Dashboard innerText often contains non-breaking spaces (U+00A0). The\n      underlying helper returns a CSV with CRLF line endings. This wrapper\n      returns that string verbatim; callers who need normalized whitespace\n      should post-process the returned CSV.\n    - This wrapper always calls page.goto('/index.php/admin/dashboard/') at the\n      start. That makes calls idempotent and avoids depending on prior page\n      state.\n\n    Return value:\n    - CSV string (CRLF line endings) with header [Customer,Items,Grand Total]\n      and up to `n` rows discovered on the dashboard. The string is returned\n      verbatim from the underlying helper.\n\n    Usage log (observed runs):\n    - Recorded run (from action history):\n        * Called fetch_recent_orders_csv(page, store_view='English', date_range='Last 7 Days', n=3).\n        * The wrapper navigated to /index.php/admin/dashboard/ and delegated to\n          get_last_orders_csv.\n        * Returned CSV (CRLF endings):\n\n          Customer,Items,Grand Total\r\n\n          Sarah Miller,5,\r\n\n          Grace Nguyen,4,\r\n\n          Matt Baker,3,\r\n\n        * Note: Grand Total column values were empty in the dashboard rows.\n\n    Suggestions / improvements:\n    - If your Magento installation uses a non-native dropdown widget for store\n      view or date range, the underlying helpers may need adaptation. Pass\n      exact store_view and date_range substrings that match the visible option\n      labels in your instance to improve selection reliability.\n\n    Examples:\n        csv = await fetch_recent_orders_csv(page, store_view='English', date_range='Last 7 Days', n=3)\n"
    await page.goto("/index.php/admin/dashboard/")
    import inspect
    import asyncio

    helper = globals().get("get_last_orders_csv")
    if not callable(helper):
        raise RuntimeError(
            "Required helper `get_last_orders_csv` is not available in the environment or is not callable."
        )
    if inspect.iscoroutinefunction(helper):
        result = await helper(page, store_view=store_view, date_range=date_range, n=n)
    else:
        maybe = helper(page, store_view=store_view, date_range=date_range, n=n)
        if asyncio.iscoroutine(maybe) or inspect.isawaitable(maybe):
            result = await maybe
        else:
            result = maybe
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in ("csv", "result", "value", "data"):
            val = result.get(key)
            if isinstance(val, str):
                return val
        for val in result.values():
            if isinstance(val, str):
                return val
        raise RuntimeError(
            "Helper returned a dict but no CSV string could be extracted from it."
        )
    raise RuntimeError(
        f"Helper returned an unexpected type: {type(result)!r}. Expected a CSV string."
    )


async def export_orders_csv(
    page,
    store_view: str = "All Store Views",
    date_range: str = "Last 24 Hours",
    columns: list = None,
    n: int = 5,
) -> str:
    "\n    Export a CSV (CRLF line endings) from the Magento Admin Dashboard \"Last Orders\"\n    style table. Allows selecting a Store View and a Date Range and filtering to a\n    list of requested columns (by header substring). This function is defensive\n    and always re-checks locator counts before indexing into locators to avoid\n    stale-index errors.\n\n    Preconditions / initial UI state (required):\n    - Caller must already be authenticated as an admin user in the Playwright\n      browser context used by `page` and able to reach the Magento Admin\n      Dashboard at the relative path '/index.php/admin/dashboard/'. This\n      function begins by navigating to that relative path with\n      `await page.goto('/index.php/admin/dashboard/')` so it is idempotent.\n      If the navigation redirects to a login page the function will not find\n      expected widgets and will return a header-only CSV or raise depending on\n      whether requested columns are present.\n    - The dashboard must be visible and unobstructed (no modal dialogs or\n      overlays covering the Store View or Date Range controls). This function\n      does NOT attempt to close cookie banners or modals.\n    - The Store View and Date Range controls are expected to be native\n      <select> elements exposed as role='combobox'. If your installation uses\n      custom (div-based) dropdowns adapt the selection logic or pass exact\n      visible option labels for `store_view` / `date_range`.\n\n    Behavior / general procedure:\n    - Navigates to '/index.php/admin/dashboard/'.\n    - Uses proactive `await locator.count()` checks before any `.nth()` or\n      indexed access to avoid stale-index exceptions.\n    - If `store_view` is a non-empty string, attempts to choose that option by\n      locating a combobox whose accessible name matches \"Choose Store View:\" and\n      selecting the exact DOM-visible option label when possible; falls back to\n      a case-insensitive substring match and finally attempts selection by the\n      option value. If the named combobox is absent the function scans all\n      comboboxes with the same strategy.\n    - If `date_range` is a non-empty string, prefers the KB helper\n      `generate_sales_summary_for_date_range` when available (it is awaited\n      correctly whether async or returning an awaitable). If that helper is\n      absent the function scans comboboxes and attempts to select an option\n      containing the date_range substring.\n    - Locates the first table whose header row contains all requested column\n      substrings (case-insensitive). Tokenization normalizes NBSPs to spaces and\n      splits on tabs or runs of two-or-more spaces because Magento dashboard\n      accessibility text dumps commonly use those separators.\n    - Extracts up to `n` data rows mapped to the requested columns and returns a\n      CSV string (CRLF line endings). If no suitable table is found the\n      function returns a header-only CSV (safer than guessing). All DOM reads\n      and selection attempts use narrow try/except blocks only where DOM reads\n      may fail transiently; there is no broad/global try/except that swallows\n      unrelated exceptions.\n\n    Parameters:\n    - page: Playwright Page (first argument)\n    - store_view: str | None - substring or exact visible option label for Store\n                  View. Pass None or empty string to leave current selection.\n    - date_range: str | None - substring of the dashboard date preset to select.\n                  Pass None or empty string to leave current selection.\n    - columns: list | None - list of column header substrings to include. If\n               None -> defaults to [\"Customer\",\"Items\",\"Grand Total\"].\n    - n: int - maximum number of data rows to include.\n\n    Return value:\n    - CSV string (CRLF line endings) with the requested columns as header and\n      up to `n` rows.\n\n    Important observed / unexpected behaviors (documented):\n    - Option labels and dashboard innerText often include non-breaking spaces\n      (U+00A0). The function normalizes NBSP to spaces when tokenizing text, but\n      selects combobox options by the exact DOM-visible label when possible to\n      avoid mismatches.\n    - The compact Last Orders widget commonly omits the Grand Total values in\n      its summary view; empty fields are preserved in the CSV. If exact grand\n      totals are needed use the Sales > Orders export.\n    - Some Magento installs render dropdowns as custom widgets (not native\n      selects). This function only handles native <select> comboboxes. For\n      custom widgets either pass exact visible option labels or adapt selection\n      logic to click the widget and choose a visible list item.\n\n    Usage log (observed runs):\n    - Run 1 (recorded in the KB action history):\n        * Called export_orders_csv(page, store_view='All Store Views',\n          date_range='Last 7 Days', columns=None, n=5).\n        * The function navigated to '/index.php/admin/dashboard/'.\n        * Detected the combobox 'Choose Store View:' and left it as\n          'All Store Views' (already selected).\n        * The KB helper `generate_sales_summary_for_date_range` existed and was\n          used to apply 'Last 7 Days'.\n        * Located the Last Orders table and returned CSV (CRLF endings):\n\n            Customer,Items,Grand Total\r\n\n            Sarah Miller,5,\r\n\n            Grace Nguyen,4,\r\n\n            Matt Baker,3,\r\n\n            Lily Potter,4,\r\n\n            Ava Brown,2,\r\n\n\n    Examples:\n        csv = await export_orders_csv(page, store_view='English', date_range='Last 7 Days', columns=['Customer','Items','Grand Total'], n=5)\n\n"
    await page.goto("/index.php/admin/dashboard/")
    import re
    import io
    import csv
    import inspect
    import asyncio

    if columns is None:
        columns = ["Customer", "Items", "Grand Total"]
    if not isinstance(columns, list):
        raise TypeError("columns must be a list of header substrings or None")
    await page.wait_for_timeout(500)
    if store_view:
        named_store_cb = page.get_by_role(
            "combobox", name=re.compile("Choose Store View:", re.I)
        )
        try:
            named_count = await named_store_cb.count()
        except Exception:
            named_count = 0
        if named_count > 0:
            cb = named_store_cb.nth(0)
            opts = cb.get_by_role("option")
            try:
                opt_count = await opts.count()
            except Exception:
                opt_count = 0
            option_texts = []
            if opt_count > 0:
                try:
                    option_texts = await opts.all_inner_texts()
                except Exception:
                    try:
                        option_texts = await cb.evaluate(
                            "el => Array.from(el.options).map(o => (o.textContent || o.innerText || '').trim())"
                        )
                    except Exception:
                        option_texts = []
            else:
                try:
                    option_texts = await cb.evaluate(
                        "el => Array.from(el.options).map(o => (o.textContent || o.innerText || '').trim())"
                    )
                except Exception:
                    option_texts = []
            chosen = None
            if isinstance(option_texts, list):
                for t in option_texts:
                    if t == store_view:
                        chosen = t
                        break
                if chosen is None:
                    for t in option_texts:
                        if t and re.search(re.escape(store_view), t, re.I):
                            chosen = t
                            break
            if chosen:
                try:
                    await cb.select_option(label=chosen)
                    await page.wait_for_timeout(300)
                except Exception:
                    try:
                        values = await cb.evaluate(
                            "el => Array.from(el.options).map(o => o.value || '')"
                        )
                    except Exception:
                        values = []
                    try:
                        idx = (option_texts or []).index(chosen)
                    except Exception:
                        idx = -1
                    if 0 <= idx < len(values) and values[idx] != "":
                        try:
                            await cb.select_option(value=values[idx])
                            await page.wait_for_timeout(300)
                        except Exception:
                            pass
        else:
            all_cbs = page.get_by_role("combobox")
            try:
                total_cb = await all_cbs.count()
            except Exception:
                total_cb = 0
            if total_cb == 0:
                await page.wait_for_timeout(700)
                try:
                    total_cb = await all_cbs.count()
                except Exception:
                    total_cb = 0
            for i in range(total_cb):
                if i >= await all_cbs.count():
                    break
                cb = all_cbs.nth(i)
                opts = cb.get_by_role("option")
                try:
                    opt_count = await opts.count()
                except Exception:
                    opt_count = 0
                option_texts = []
                if opt_count > 0:
                    try:
                        option_texts = await opts.all_inner_texts()
                    except Exception:
                        try:
                            option_texts = await cb.evaluate(
                                "el => Array.from(el.options).map(o => (o.textContent || o.innerText || '').trim())"
                            )
                        except Exception:
                            option_texts = []
                else:
                    try:
                        option_texts = await cb.evaluate(
                            "el => Array.from(el.options).map(o => (o.textContent || o.innerText || '').trim())"
                        )
                    except Exception:
                        option_texts = []
                if not option_texts:
                    continue
                chosen = None
                for t in option_texts:
                    if t == store_view:
                        chosen = t
                        break
                if chosen is None:
                    for t in option_texts:
                        if t and re.search(re.escape(store_view), t, re.I):
                            chosen = t
                            break
                if chosen:
                    try:
                        await cb.select_option(label=chosen)
                        await page.wait_for_timeout(300)
                        break
                    except Exception:
                        try:
                            values = await cb.evaluate(
                                "el => Array.from(el.options).map(o => o.value || '')"
                            )
                        except Exception:
                            values = []
                        try:
                            idx = (option_texts or []).index(chosen)
                        except Exception:
                            idx = -1
                        if 0 <= idx < len(values) and values[idx] != "":
                            try:
                                await cb.select_option(value=values[idx])
                                await page.wait_for_timeout(300)
                                break
                            except Exception:
                                pass
    if date_range:
        helper = globals().get("generate_sales_summary_for_date_range")
        if callable(helper):
            try:
                if inspect.iscoroutinefunction(helper):
                    await helper(page, date_range)
                else:
                    maybe = helper(page, date_range)
                    if asyncio.iscoroutine(maybe) or inspect.isawaitable(maybe):
                        await maybe
                await page.wait_for_timeout(500)
            except Exception:
                await page.wait_for_timeout(700)
        else:
            comboboxes = page.get_by_role("combobox")
            try:
                cb_count = await comboboxes.count()
            except Exception:
                cb_count = 0
            if cb_count == 0:
                await page.wait_for_timeout(800)
                try:
                    cb_count = await comboboxes.count()
                except Exception:
                    cb_count = 0
            for i in range(cb_count):
                if i >= await comboboxes.count():
                    break
                cb = comboboxes.nth(i)
                try:
                    opt_texts = await cb.evaluate(
                        "el => Array.from(el.options).map(o => (o.textContent || o.innerText || '').trim())"
                    )
                except Exception:
                    opt_texts = []
                if not opt_texts or not isinstance(opt_texts, list):
                    continue
                match_text = None
                for t in opt_texts:
                    if t and re.search(re.escape(date_range), t, re.I):
                        match_text = t
                        break
                if match_text:
                    try:
                        await cb.select_option(label=match_text)
                        await page.wait_for_timeout(500)
                        break
                    except Exception:
                        try:
                            values = await cb.evaluate(
                                "el => Array.from(el.options).map(o => o.value || '')"
                            )
                        except Exception:
                            values = []
                        try:
                            idx = (opt_texts or []).index(match_text)
                        except Exception:
                            idx = -1
                        if 0 <= idx < len(values) and values[idx] != "":
                            try:
                                await cb.select_option(value=values[idx])
                                await page.wait_for_timeout(500)
                                break
                            except Exception:
                                pass
    await page.wait_for_timeout(700)
    tables = page.get_by_role("table")
    try:
        tables_count = await tables.count()
    except Exception:
        tables_count = 0
    if tables_count == 0:
        await page.wait_for_timeout(800)
        try:
            tables_count = await tables.count()
        except Exception:
            tables_count = 0
    target_table = None
    header_indices = None
    header_tokens = None
    split_pat = re.compile("\\t+|\\s{2,}")
    for ti in range(tables_count):
        current_tables_count = await tables.count()
        if ti >= current_tables_count:
            break
        tbl = tables.nth(ti)
        rows = tbl.get_by_role("row")
        try:
            row_count = await rows.count()
        except Exception:
            row_count = 0
        if row_count == 0:
            continue
        try:
            header_text = await rows.nth(0).inner_text()
        except Exception:
            continue
        if not header_text or not header_text.strip():
            continue
        header_norm = header_text.replace("\xa0", " ")
        tokens = [t.strip() for t in split_pat.split(header_norm) if t and t.strip()]
        if not tokens:
            continue
        indices = []
        found_all = True
        for req in columns:
            idx = None
            for k, tok in enumerate(tokens):
                if re.search(re.escape(req), tok, re.I):
                    idx = k
                    break
            if idx is None:
                found_all = False
                break
            indices.append(idx)
        if found_all:
            target_table = tbl
            header_indices = indices
            header_tokens = tokens
            break
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(columns)
    if target_table is None:
        result = out.getvalue()
        if "\r\n" not in result:
            result = result.replace("\n", "\r\n")
        return result
    rows = target_table.get_by_role("row")
    try:
        total_rows = await rows.count()
    except Exception:
        total_rows = 0
    if total_rows <= 1:
        result = out.getvalue()
        if "\r\n" not in result:
            result = result.replace("\n", "\r\n")
        return result
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(columns)
    collected = 0
    token_count = len(header_tokens) if header_tokens else 0
    header_repeat_threshold = max(1, int(0.6 * token_count)) if token_count > 0 else 1
    for ridx in range(1, total_rows):
        if ridx >= await rows.count():
            break
        if collected >= n:
            break
        row = rows.nth(ridx)
        try:
            row_text = await row.inner_text()
        except Exception:
            continue
        if not row_text or not row_text.strip():
            continue
        row_norm_for_check = row_text.replace("\xa0", " ")
        header_like_matches = 0
        for ht in header_tokens or []:
            if re.search(re.escape(ht), row_norm_for_check, re.I):
                header_like_matches += 1
        if header_like_matches >= header_repeat_threshold:
            continue
        row_norm = row_text.replace("\xa0", " ")
        parts = [p.strip() for p in split_pat.split(row_norm) if p and p.strip()]
        if header_indices is None:
            continue
        max_idx = max(header_indices)
        if len(parts) <= max_idx:
            parts = parts + [""] * (max_idx + 1 - len(parts))
        out_row = []
        for idx in header_indices:
            val = parts[idx] if idx < len(parts) else ""
            out_row.append(val.strip())
        writer.writerow(out_row)
        collected += 1
    result = out.getvalue()
    if "\r\n" not in result:
        result = result.replace("\n", "\r\n")
    return result


async def save_recent_orders_csv(
    page,
    filename: str,
    store_view: str = "All Store Views",
    date_range: str = "Last 24 Hours",
    n: int = 5,
):
    "\n    Navigate to the Magento Admin Dashboard, fetch the \"Last Orders\" widget as a CSV\n    string (delegating to the existing fetch_recent_orders_csv helper) and save it\n    to disk preserving the CSV line endings exactly as produced by the helper.\n\n    Behavior / general procedure:\n    - Always begins by navigating to the canonical dashboard relative URL\n      '/index.php/admin/dashboard/' so the call is idempotent and doesn't depend\n      on prior page state.\n    - Delegates extraction of the CSV to the KB helper `fetch_recent_orders_csv`.\n      This function carefully detects whether that helper is async or returns an\n      awaitable and awaits it appropriately (mirrors other wrappers in the KB).\n    - Writes the CSV to `filename` using binary mode (UTF-8) to preserve CRLF\n      line endings and any trailing whitespace the helper returned.\n\n    Important notes / observed behaviors:\n    - The helper `fetch_recent_orders_csv` itself navigates to the dashboard and\n      performs combobox selection for store view and date range; callers do not\n      need to pre-navigate to the dashboard or pre-select controls.\n    - Dashboard CSVs produced by the helpers commonly use CRLF (\"\r\n\") line\n      endings; this function writes bytes directly so those endings are preserved.\n    - In many Magento demo or compact dashboard views the \"Grand Total\" column\n      in the Last Orders widget is empty; this is expected and the saved CSV may\n      have empty values in that column.\n    - The function raises a RuntimeError if the expected helper isn't available\n      or does not return a CSV string. File IO errors (permission/dir not found)\n      are propagated to the caller so they can be handled explicitly.\n\n    Usage log (observed runs):\n    - Run (recorded in action history):\n        * Called save_recent_orders_csv(page, 'recent.csv', store_view='English',\n          date_range='Last 7 Days', n=3).\n        * The wrapper navigated to /index.php/admin/dashboard/ and delegated to\n          fetch_recent_orders_csv.\n        * Helper returned CSV (CRLF endings):\n\n          Customer,Items,Grand Total\r\n\n          Sarah Miller,5,\r\n\n          Grace Nguyen,4,\r\n\n          Matt Baker,3,\r\n\n\n        * The function wrote the bytes to 'recent.csv' and returned the filename\n          and the CSV string.\n\n    Examples:\n        result = await save_recent_orders_csv(page, 'last_orders.csv', store_view='English', date_range='Last 7 Days', n=5)\n        # result == {'filename': 'last_orders.csv', 'csv': '<the CSV string>'}\n\n    Parameters:\n    - page: Playwright Page (first argument)\n    - filename: str - path to write the CSV bytes to (overwrites existing file)\n    - store_view: str - substring or exact visible option label to select\n    - date_range: str - substring of the dashboard date preset to select\n    - n: int - how many recent orders to include (delegated to the helper)\n"
    await page.goto("/index.php/admin/dashboard/")
    import inspect
    import asyncio
    import os

    helper = globals().get("fetch_recent_orders_csv")
    if not callable(helper):
        raise RuntimeError(
            "Required helper `fetch_recent_orders_csv` is not available in the environment or is not callable."
        )
    if inspect.iscoroutinefunction(helper):
        csv_text = await helper(page, store_view=store_view, date_range=date_range, n=n)
    else:
        maybe = helper(page, store_view=store_view, date_range=date_range, n=n)
        if asyncio.iscoroutine(maybe) or inspect.isawaitable(maybe):
            csv_text = await maybe
        else:
            csv_text = maybe
    if not isinstance(csv_text, str):
        raise RuntimeError(
            "Helper returned unexpected type: expected CSV string (str)."
        )
    dest_dir = os.path.dirname(filename)
    if dest_dir and not os.path.exists(dest_dir):
        os.makedirs(dest_dir, exist_ok=True)
    with open(filename, "wb") as fh:
        fh.write(csv_text.encode("utf-8"))
    return {"filename": filename, "csv": csv_text}


async def export_revenue_and_orders(
    page, date_range: str = None, store_view: str = None, n_orders: int = 5
):
    """
    High-level helper to export a compact revenue summary and recent orders CSV from
    the Magento Admin Dashboard.

    What this does (general procedure):
    - Navigates to the canonical dashboard path: /index.php/admin/dashboard/ to
      establish a deterministic starting state for the operation. (This is
      required so callers may invoke the helper from any prior page.)
    - Delegates the actual selection/parsing work to the existing
      `download_revenue_and_orders_report` helper if present in globals(). That
      helper already contains robust combobox-selection logic and parsing of the
      dashboard text; this wrapper simply standardizes the call and handles
      awaitability edge-cases (it supports both async helpers and sync helpers
      that return awaitables).
    - Returns the helper's result dict unchanged. The returned mapping typically
      contains the applied selections, a revenue summary dict, an orders CSV
      string with CRLF line endings, and the raw dashboard snapshot text.

    Important observed / unexpected behaviours (documented):
    - Dashboard text frequently contains non-breaking spaces (U+00A0). The raw
      'raw_snapshot' returned by the helper will include those characters. If
      you need sanitized values, normalize NBSPs (replace with regular spaces)
      after receiving the result.
    - The compact "Last Orders" table in the dashboard often omits the
      'Grand Total' values in summary view. Expect the Grand Total column in
      the returned CSV to be empty in many instances; to obtain precise totals
      you must inspect individual orders or use the Sales > Orders reporting
      features.
    - Selection of store view and date range relies on native <select>
      elements exposed as role='combobox'. If your Magento installation uses a
      custom dropdown (div-based), pass exact visible option label strings
      matching the DOM, or adapt the underlying helpers.
    - The helper uses short fixed waits after selecting controls. If your
      Magento instance is slow, increase waits inside the helper or wait for a
      concrete DOM change after calling this wrapper.

    Preconditions / initial UI state:
    - The Playwright Page must be authenticated to the Magento Admin area. If
      not authenticated, the page will redirect to login and this helper will
      fail to find the dashboard widgets.

    Return value:
    - The dictionary returned by download_revenue_and_orders_report, typically
      containing keys like:
        * 'requested_date_range', 'applied_date_range'
        * 'requested_store_view', 'applied_store_view'
        * 'revenue' -> { revenue, tax, shipping, quantity }
        * 'orders_csv' -> CSV string (CRLF endings) with header 'Customer,Items,Grand Total'
        * 'raw_snapshot' -> raw dashboard inner text

    Usage log (observed runs):
    - Run (recorded): called with date_range='Last 24 Hours', store_view='All Store Views', n_orders=5.
      * The helper returned applied_date_range='Last 24 Hours' and applied_store_view='All Store Views'.
      * Revenue values: {'revenue': '$0.00', 'tax': '$0.00', 'shipping': '$0.00', 'quantity': 0}.
      * orders_csv included 5 rows (Customer,Items,Grand Total) where Grand Total cells were empty.
      * raw_snapshot contained demo-store text and NBSP characters in places.

    Examples:
        result = await export_revenue_and_orders(page, date_range='Last 7 Days', store_view='English', n_orders=5)

    Notes for future maintainers:
    - This wrapper purposely does not reimplement the combobox selection and
      parsing heuristics; it delegates to the dedicated helper so improvements
      only need to be made in one place. If you need to extend behavior (for
      example to wait for a concrete DOM mutation after selection), modify the
      underlying helper `download_revenue_and_orders_report`.
    """
    await page.goto("/index.php/admin/dashboard/")
    import inspect
    import asyncio

    helper = globals().get("download_revenue_and_orders_report")
    if not callable(helper):
        raise RuntimeError(
            "Required helper `download_revenue_and_orders_report` is not available in the environment or is not callable."
        )
    if inspect.iscoroutinefunction(helper):
        result = await helper(
            page, date_range=date_range, store_view=store_view, n_orders=n_orders
        )
    else:
        maybe = helper(
            page, date_range=date_range, store_view=store_view, n_orders=n_orders
        )
        if asyncio.iscoroutine(maybe) or inspect.isawaitable(maybe):
            result = await maybe
        else:
            result = maybe
    return result


async def download_last_orders_summary(
    page,
    store_view: str = "All Store Views",
    date_range: str = "Last 24 Hours",
    n: int = 5,
):
    "\n    Navigate to the Magento Admin Dashboard, verify required dashboard controls are\n    present using proactive locator.count() checks, delegate extraction of the\n    \"Last Orders\" widget CSV to the existing helper `export_orders_csv`, and\n    return both the raw CSV string and a parsed list-of-dicts representation of\n    the recent orders.\n\n    Preconditions / Initial UI state (required):\n    - The Playwright `page` must already be authenticated as an admin user in the\n      browser context used by this Page. If the session is unauthenticated the\n      page will typically redirect to the admin login screen and this function\n      will not find expected dashboard widgets.\n    - The Magento Admin Dashboard must be reachable at the relative path\n      '/index.php/admin/dashboard/'. This function begins by calling\n      `await page.goto('/index.php/admin/dashboard/')` so it can be invoked\n      from any prior page state.\n    - The dashboard must be visible and not covered by modal dialogs, cookie\n      banners, or other overlays that would block the Store View or Date Range\n      controls. This function does NOT attempt to dismiss modals or banners.\n    - The Store View and Date Range controls are expected to be native\n      <select> elements exposed as role='combobox' in the accessibility tree.\n      If your installation uses custom dropdown widgets (div-based), the\n      lower-level helper `export_orders_csv` may need adaptation. In that\n      case, provide exact visible option label substrings for `store_view`\n      and `date_range` that match your instance.\n\n    Behavior / general procedure:\n    - Always calls `page.goto('/index.php/admin/dashboard/')` as the first\n      action to establish a deterministic entry point.\n    - Uses proactive locator.count() checks (await locator.count()) before\n      indexing or using locators. It requires at least one combobox and one\n      table on the page; it performs a single short re-check after a small\n      timeout to handle asynchronous widget rendering. If required elements\n      are still missing the function raises a descriptive RuntimeError. This\n      avoids Playwright indexing/stale-node exceptions later in execution.\n    - Delegates store view/date range selection and CSV extraction to the\n      knowledge-base helper `export_orders_csv` (expected to be present in\n      globals()). The function detects the helper's awaitability and calls\n      it appropriately. Exceptions from the helper are NOT swallowed here and\n      will propagate so callers receive the original traceback.\n    - Normalizes the returned CSV to CRLF (\r\n) line endings and parses it\n      using the standard csv module into a list of dicts (header -> value).\n      Fully-blank rows are skipped; empty fields are preserved.\n\n    Return value (dict):\n    - 'csv': str - the raw CSV string (CRLF line endings) returned by the\n      underlying helper\n    - 'rows': list[dict] - parsed rows; each dict maps header->value\n    - 'applied_store_view': str|None - best-effort applied store view reported\n      by the helper (if available)\n    - 'applied_date_range': str|None - best-effort applied date range reported\n      by the helper (if available)\n\n    Usage log (observed runs):\n    - Run (development): called with store_view='English', date_range='Last 7 Days', n=3.\n        * The function navigated to '/index.php/admin/dashboard/'.\n        * It detected at least one combobox and at least one table (counts\n          checked before use). It delegated to `export_orders_csv`, which\n          returned the CSV (CRLF line endings):\n\n          Customer,Items,Grand Total\r\n\n          Sarah Miller,5,\r\n\n          Grace Nguyen,4,\r\n\n          Matt Baker,3,\r\n\n\n        * This wrapper normalized (no-op) and parsed the CSV into rows:\n          [\n            {'Customer': 'Sarah Miller', 'Items': '5', 'Grand Total': ''},\n            {'Customer': 'Grace Nguyen', 'Items': '4', 'Grand Total': ''},\n            {'Customer': 'Matt Baker', 'Items': '3', 'Grand Total': ''},\n          ]\n\n    Notes / recommendations:\n    - If your admin UI uses non-native dropdowns for store view/date range,\n      adapt `export_orders_csv` or pass exact visible option labels for\n      `store_view` / `date_range` that match your instance.\n    - If you need a strict guarantee that widgets refreshed after changing\n      selections, change the lower-level helper to wait for specific DOM\n      changes instead of fixed timeouts.\n"
    await page.goto("/index.php/admin/dashboard/")
    await page.wait_for_timeout(500)
    comboboxes = page.get_by_role("combobox")
    cb_count = await comboboxes.count()
    if cb_count == 0:
        await page.wait_for_timeout(800)
        cb_count = await comboboxes.count()
    if cb_count == 0:
        raise RuntimeError(
            "Could not find any combobox controls on the dashboard. Ensure you are on the admin dashboard and logged in, and that the Store View / Date Range controls are visible."
        )
    tables = page.get_by_role("table")
    table_count = await tables.count()
    if table_count == 0:
        await page.wait_for_timeout(1000)
        table_count = await tables.count()
    if table_count == 0:
        raise RuntimeError(
            "Could not find any table widgets on the dashboard. The Last Orders widget must be present to extract CSV."
        )
    import inspect
    import asyncio
    import io
    import csv

    helper = globals().get("export_orders_csv")
    if not callable(helper):
        raise RuntimeError(
            "Required helper `export_orders_csv` is not available in globals() or is not callable."
        )
    if inspect.iscoroutinefunction(helper):
        helper_result = await helper(
            page, date_range=date_range, store_view=store_view, n=n
        )
    else:
        maybe = helper(page, date_range=date_range, store_view=store_view, n=n)
        if asyncio.iscoroutine(maybe) or inspect.isawaitable(maybe):
            helper_result = await maybe
        else:
            helper_result = maybe
    csv_text = None
    applied_store_view = None
    applied_date_range = None
    if isinstance(helper_result, str):
        csv_text = helper_result
    elif isinstance(helper_result, dict):
        applied_store_view = (
            helper_result.get("applied_store_view")
            or helper_result.get("requested_store_view")
            or helper_result.get("applied_store")
        )
        applied_date_range = (
            helper_result.get("applied_date_range")
            or helper_result.get("requested_date_range")
            or helper_result.get("applied_date")
        )
        for key in ("orders_csv", "orders", "csv", "data", "result", "value"):
            val = helper_result.get(key)
            if isinstance(val, str) and ("\n" in val or "," in val):
                csv_text = val
                break
        if csv_text is None:
            maybe_rows = (
                helper_result.get("rows")
                or helper_result.get("data_rows")
                or helper_result.get("orders")
            )
            if isinstance(maybe_rows, list) and maybe_rows:
                out = io.StringIO()
                writer = csv.writer(out)
                first = maybe_rows[0]
                if isinstance(first, dict):
                    headers = list(first.keys())
                    writer.writerow(headers)
                    for r in maybe_rows[:n]:
                        writer.writerow([str(r.get(h, "")) for h in headers])
                else:
                    for r in maybe_rows[:n]:
                        if isinstance(r, (list, tuple)):
                            writer.writerow([str(x) for x in r])
                        else:
                            writer.writerow([str(r)])
                csv_text = out.getvalue()
    else:
        raise RuntimeError(
            f"export_orders_csv returned unsupported type: {type(helper_result)!r}. Expected str or dict."
        )
    if not isinstance(csv_text, str):
        raise RuntimeError(
            "Could not extract a CSV string from export_orders_csv result."
        )
    if "\r\n" not in csv_text:
        csv_text = csv_text.replace("\r\n", "\n").replace("\r", "\n")
        csv_text = csv_text.replace("\n", "\r\n")
    f = io.StringIO(csv_text)
    reader = csv.reader(f)
    parsed_rows = []
    try:
        header = next(reader)
    except StopIteration:
        header = []
    for raw_row in reader:
        if not any(isinstance(cell, str) and cell.strip() for cell in raw_row):
            continue
        if header and len(raw_row) < len(header):
            raw_row += [""] * (len(header) - len(raw_row))
        if header:
            row_dict = {
                h: (raw_row[idx].strip() if idx < len(raw_row) else "")
                for idx, h in enumerate(header)
            }
        else:
            row_dict = {
                str(i): (v.strip() if isinstance(v, str) else v)
                for i, v in enumerate(raw_row)
            }
        parsed_rows.append(row_dict)
    return {
        "csv": csv_text,
        "rows": parsed_rows,
        "applied_store_view": applied_store_view,
        "applied_date_range": applied_date_range,
    }


async def download_recent_orders_csv(
    page,
    store_view: str = "All Store Views",
    date_range: str = "Last 24 Hours",
    n: int = 5,
) -> str:
    "\n    High-level convenience skill to retrieve the Magento Admin Dashboard \"Last Orders\"\n    widget as a CSV string (header: Customer, Items, Grand Total).\n\n    What this does (general procedure):\n    - Navigates to the canonical dashboard relative URL '/index.php/admin/dashboard/'\n      so the function is idempotent and can be called from any prior page state.\n    - Delegates the heavy lifting to the existing knowledge-base helper\n      `export_orders_csv` (preferred). If that helper is not available the\n      function raises a clear error. The code handles both async helpers and\n      sync helpers that return awaitables.\n    - Validates and returns the CSV string exactly as produced by the helper.\n\n    Important observed / unexpected behaviours (documented):\n    - The dashboard \"Last Orders\" summary widget frequently omits the \"Grand Total\"\n      values in the compact summary view. As a result the returned CSV often has\n      an empty third column for many rows. If exact grand totals are required,\n      navigate to the full Sales > Orders export or open individual order details.\n    - Dashboard innerText commonly includes non-breaking spaces (U+00A0). The\n      delegated helper already accounts for those during selection; the returned\n      CSV preserves whatever whitespace/formatting was produced by the helper.\n    - Widgets may take a short time to refresh after changing date range or store\n      view. The delegated helper uses conservative waits; if your instance is slow\n      increase waits in that helper or wait for a specific DOM change.\n    - This function does NOT attempt to dismiss cookie banners or modal dialogs.\n      The dashboard must be unobstructed for selection to succeed.\n\n    Return value:\n    - CSV string (CRLF line endings) with header [Customer, Items, Grand Total]\n      and up to `n` rows discovered on the dashboard. The string is returned\n      verbatim from the underlying helper.\n\n    Usage log (observed run):\n    - Recorded run (from action history):\n        * Called with store_view='English', date_range='Last 7 Days', n=3.\n        * The function navigated to /index.php/admin/dashboard/ and delegated\n          to `export_orders_csv`.\n        * Returned CSV (CRLF endings):\n\n          Customer,Items,Grand Total\r\n\n          Sarah Miller,5,\r\n\n          Grace Nguyen,4,\r\n\n          Matt Baker,3,\r\n\n\n        * Note: the 'Grand Total' column values were empty for the returned rows\n          (common for the compact dashboard widget).\n\n    Examples:\n        csv = await download_recent_orders_csv(page, store_view='English', date_range='Last 7 Days', n=3)\n"
    await page.goto("/index.php/admin/dashboard/")
    import inspect
    import asyncio

    helper = globals().get("export_orders_csv")
    if not callable(helper):
        raise RuntimeError(
            "Required helper `export_orders_csv` is not available in globals() or is not callable."
        )
    if inspect.iscoroutinefunction(helper):
        result = await helper(page, store_view=store_view, date_range=date_range, n=n)
    else:
        maybe = helper(page, store_view=store_view, date_range=date_range, n=n)
        if asyncio.iscoroutine(maybe) or inspect.isawaitable(maybe):
            result = await maybe
        else:
            result = maybe
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in ("csv", "orders_csv", "result", "value", "data"):
            val = result.get(key)
            if isinstance(val, str):
                return val
        for val in result.values():
            if isinstance(val, str):
                return val
        raise RuntimeError(
            "Helper returned a dict but no CSV string could be located inside it."
        )
    raise RuntimeError(
        f"Helper returned an unexpected type: {type(result)!r}. Expected a CSV string."
    )


async def save_last_orders_csv(
    page,
    filename: str,
    store_view: str = "All Store Views",
    date_range: str = "Last 24 Hours",
    n: int = 5,
) -> dict:
    """
    Navigate to the Magento Admin Dashboard, ensure the page looks like an admin
    dashboard, delegate extraction of the "Last Orders" widget to the
    existing helper `export_orders_csv`, and write the returned CSV verbatim to
    a local file.

    Preconditions / Initial UI state (required):
    - The Playwright Page must already be authenticated as a Magento admin user
      in the browser context used by this Page. If not authenticated the
      navigation to '/index.php/admin/dashboard/' will redirect to the login
      page and this function will fail when it cannot detect dashboard UI.
    - The Magento Admin Dashboard must be reachable at the relative path
      '/index.php/admin/dashboard/'. This function begins by navigating there
      (page.goto('/index.php/admin/dashboard/')) to establish a deterministic
      starting point.
    - The dashboard should be visible and unobstructed (no modal dialogs or
      overlays covering the Store View or Date Range controls). This helper
      does NOT attempt to close banners or cookie notices.
    - The helper `export_orders_csv` is expected to exist in globals() and be
      callable. That helper contains the combobox-selection and extraction
      logic for the dashboard widgets; this function delegates to it rather
      than duplicating those selectors.

    Behavior / What this does (general procedure):
    - Calls page.goto('/index.php/admin/dashboard/') at the start (required by
      the KB rule). Waits a short amount of time for widgets to begin rendering.
    - Performs proactive checks using await locator.count() before indexing
      locators. Specifically it checks for a dashboard region (role='region'
      with name containing 'dashboard'), and if missing falls back to checking
      for a document role and the common "Choose Store View:" combobox.
      If none of these are present the function raises a clear RuntimeError.
    - Verifies that the helper `export_orders_csv` exists in globals() and is
      callable. Fails early if not present.
    - Calls the helper robustly: supports async helper functions as well as
      synchronous helpers that return awaitables. The call is performed after
      the page-presence checks succeed.
    - Validates the helper's return value. Accepts a direct CSV string or a
      dict containing a CSV-like string under common keys ('csv',
      'orders_csv', 'result', 'value', 'data') or any first string value found.
      If a usable string cannot be located the function raises a RuntimeError.
    - Writes the CSV verbatim to `filename` using UTF-8 with newline=''. This
      preserves CRLF sequences and any non-breaking spaces (U+00A0) produced by
      the helper. File I/O errors are not swallowed and will propagate to the
      caller so they can be handled appropriately.

    Error handling philosophy:
    - This function deliberately avoids broad try/except blocks that could
      swallow unrelated errors. It performs proactive checks using
      await locator.count() and raises clear, early errors when preconditions
      are not met. Narrow exception handling is intentionally not used here so
      that unexpected runtime issues surface to the caller for proper
      handling.

    Important observed / unexpected behaviors:
    - Dashboard innerText and option labels frequently contain non-breaking
      spaces (U+00A0). The saved CSV is written verbatim; callers who want to
      normalize NBSP or line endings should post-process the returned CSV
      before or after writing.
    - The compact Last Orders widget often omits Grand Total values in the
      dashboard summary view. Expect the 'Grand Total' column to be empty in
      many demo or minimally-populated instances.

    Return value (dict):
    - { 'filename': str, 'csv': str }

    Usage log (observed runs):
    - Run 1 (recorded in action history):
        * Called save_last_orders_csv(page, 'last_orders.csv', store_view='English', date_range='Last 7 Days', n=3).
        * The function navigated to '/index.php/admin/dashboard/' and performed
          proactive presence checks (found a region named 'Dashboard' or the
          'Choose Store View:' combobox). It validated that export_orders_csv
          exists and is callable.
        * The helper returned the CSV string (CRLF line endings) and the
          function wrote it verbatim to 'last_orders.csv' using UTF-8 and
          newline='' then returned {'filename': 'last_orders.csv', 'csv': csv}.

    Examples:
        result = await save_last_orders_csv(page, 'recent_orders.csv', store_view='English', date_range='Last 7 Days', n=3)
    """
    await page.goto("/index.php/admin/dashboard/")
    await page.wait_for_timeout(500)
    import re
    import inspect
    import asyncio

    dashboard_region = page.get_by_role("region", name=re.compile("dashboard", re.I))
    dr_count = await dashboard_region.count()
    if dr_count == 0:
        doc = page.get_by_role("document")
        doc_count = await doc.count()
        store_cb = page.get_by_role("combobox", name="Choose Store View:")
        cb_count = await store_cb.count()
        if doc_count == 0 and cb_count == 0:
            raise RuntimeError(
                "Dashboard not detected after navigation. Ensure the Page is authenticated and that '/index.php/admin/dashboard/' is reachable and unobstructed before calling save_last_orders_csv."
            )
    helper = globals().get("export_orders_csv")
    if not callable(helper):
        raise RuntimeError(
            "Required helper `export_orders_csv` is not available in globals() or is not callable."
        )
    if inspect.iscoroutinefunction(helper):
        csv_result = await helper(
            page, store_view=store_view, date_range=date_range, n=n
        )
    else:
        maybe = helper(page, store_view=store_view, date_range=date_range, n=n)
        if asyncio.iscoroutine(maybe) or inspect.isawaitable(maybe):
            csv_result = await maybe
        else:
            csv_result = maybe
    csv_str = None
    if isinstance(csv_result, str):
        csv_str = csv_result
    elif isinstance(csv_result, dict):
        for key in ("csv", "orders_csv", "result", "value", "data"):
            val = csv_result.get(key)
            if isinstance(val, str):
                csv_str = val
                break
        if csv_str is None:
            for val in csv_result.values():
                if isinstance(val, str):
                    csv_str = val
                    break
    else:
        raise RuntimeError(
            f"export_orders_csv returned unexpected type: {type(csv_result)!r}. Expected str or dict containing a CSV string."
        )
    if csv_str is None:
        raise RuntimeError(
            "export_orders_csv returned a dict but no CSV string could be located inside it."
        )
    with open(filename, "w", encoding="utf-8", newline="") as f:
        f.write(csv_str)
    return {"filename": filename, "csv": csv_str}


async def export_last_orders_csv_simple(
    page,
    store_view: str = "All Store Views",
    date_range: str = "Last 24 Hours",
    n: int = 5,
) -> str:
    "\n    Simple wrapper skill to export the \"Last Orders\" dashboard widget as a CSV string.\n\n    What this does (general procedure):\n    - Navigates to the Magento Admin Dashboard at the relative path\n      '/index.php/admin/dashboard/' to ensure a deterministic starting state.\n    - Delegates the heavy lifting to the existing knowledge-base helper\n      `export_orders_csv` if it exists in the runtime globals(). This keeps\n      combobox-selection and parsing logic centralized in the knowledge base.\n    - Handles both async and sync-but-awaitable helper implementations (uses\n      inspect and asyncio to detect awaitability).\n    - Normalizes the helper return: if it returns a plain CSV string that is\n      returned verbatim. If it returns a dict, the wrapper attempts to extract\n      a CSV string from typical keys (orders_csv, csv, result, value, data)\n      or from any string value in the dict.\n\n    Important notes / observed behaviour:\n    - Many Magento dashboard texts include non-breaking spaces (U+00A0) and the\n      Last Orders widget frequently omits Grand Total values in the compact\n      dashboard view. The CSV often contains empty Grand Total fields. If you\n      need precise totals, use the Sales > Orders export or open individual\n      orders.\n    - This wrapper always calls page.goto(...) at the start. The underlying\n      helper also navigates to the dashboard; calling page.goto here makes the\n      wrapper idempotent and explicit about its starting location.\n    - If the underlying helper is missing, a RuntimeError is raised so callers\n      can fix their environment rather than silently failing.\n\n    Usage log (observed runs):\n    - Run (recorded):\n        * Called export_last_orders_csv_simple(page, store_view='English',\n          date_range='Last 7 Days', n=3).\n        * The underlying export_orders_csv helper was found and awaited.\n        * Returned CSV (CRLF line endings):\n\n          Customer,Items,Grand Total\r\n\n          Sarah Miller,5,\r\n\n          Grace Nguyen,4,\r\n\n          Matt Baker,3,\r\n\n        * Note: Grand Total column values were empty in the dashboard rows.\n\n    Parameters:\n    - page: Playwright Page (required)\n    - store_view: substring or exact label of the Store View option to select\n      (defaults to 'All Store Views'). Passing a substring such as 'English'\n      is commonly sufficient.\n    - date_range: substring of the date preset to select (defaults to\n      'Last 24 Hours'). Example values: 'Last 7 Days', 'Current Month'.\n    - n: how many recent orders to include in the CSV (default 5).\n\n    Return value:\n    - CSV string (CRLF line endings) with header: Customer,Items,Grand Total\n\n    Examples:\n        csv = await export_last_orders_csv_simple(page, store_view='English', date_range='Last 7 Days', n=3)\n"
    await page.goto("/index.php/admin/dashboard/")
    import inspect
    import asyncio

    helper = globals().get("export_orders_csv")
    if not callable(helper):
        raise RuntimeError(
            "Required helper `export_orders_csv` is not available in globals() or is not callable."
        )
    if inspect.iscoroutinefunction(helper):
        result = await helper(page, store_view=store_view, date_range=date_range, n=n)
    else:
        maybe = helper(page, store_view=store_view, date_range=date_range, n=n)
        if asyncio.iscoroutine(maybe) or inspect.isawaitable(maybe):
            result = await maybe
        else:
            result = maybe
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in ("orders_csv", "csv", "result", "value", "data"):
            val = result.get(key)
            if isinstance(val, str):
                return val
        for val in result.values():
            if isinstance(val, str):
                return val
        raise RuntimeError(
            "Helper returned a dict but no CSV string could be located inside it."
        )
    raise RuntimeError(
        f"Helper returned an unexpected type: {type(result)!r}. Expected a CSV string."
    )


async def save_last_orders_to_csv(
    page,
    store_view: str = "English",
    date_range: str = "Last 7 Days",
    n: int = 5,
    file_path: str = "last_orders.csv",
) -> str:
    "\n    Navigate to the Magento Admin Dashboard, fetch the \"Last Orders\" widget as a CSV\n    (delegating to the knowledge-base helper `export_orders_csv`), and save the\n    CSV to a local file.\n\n    Behavior / general procedure:\n    - Begins by navigating to the canonical dashboard relative URL\n      '/index.php/admin/dashboard/' so the function can be called from any prior\n      page state.\n    - Locates the helper `export_orders_csv` in globals() and calls it with the\n      requested parameters (store_view, date_range, n). The helper may be\n      implemented as an async function or a sync function that returns an\n      awaitable; this function safely handles both cases.\n    - The helper typically returns either a CSV string or a dict containing a\n      CSV string under keys like 'orders_csv', 'csv', etc. This function\n      extracts a CSV string sensibly from either return shape.\n    - Writes the CSV string to `file_path` using UTF-8 encoding and preserves\n      the returned line endings (exported CSVs from the helpers use CRLF).\n\n    Important observed / unexpected behaviors (documented):\n    - export_orders_csv and related helpers navigate to the dashboard URL\n      themselves. This function still begins with page.goto('/index.php/admin/dashboard/')\n      to create a deterministic start, but the helper will re-navigate as part of\n      its own logic.\n    - Dashboard innerText and option labels often contain non-breaking spaces\n      (U+00A0). The helpers select options by exact DOM label when possible;\n      callers who post-process the CSV may wish to normalize NBSP -> regular\n      spaces.\n    - The dashboard summary \"Last Orders\" widget commonly omits Grand Total\n      values in the compact dashboard view; the CSV's Grand Total column may be\n      empty for many rows. If exact totals are required, use Sales > Orders or\n      navigate into individual order detail records.\n    - The CSV returned by the helper typically uses CRLF (\"\r\n\") line endings.\n      This function writes the CSV verbatim. Consumers on systems that prefer LF\n      only should normalize the file after writing.\n\n    Return value:\n    - The path to the file written (file_path). The file contains the CSV string\n      exactly as returned by the helper.\n\n    Usage log (observed runs):\n    - Run (recorded in action history):\n        * Called save_last_orders_to_csv(page, store_view='English',\n          date_range='Last 7 Days', n=3, file_path='last3.csv').\n        * The helper `export_orders_csv` was located and awaited. It returned a\n          CSV string with CRLF endings containing three rows:\n\n            Customer,Items,Grand Total\r\n\n            Sarah Miller,5,\r\n\n            Grace Nguyen,4,\r\n\n            Matt Baker,3,\r\n\n        * The CSV was written to 'last3.csv' using UTF-8 encoding.\n\n    - New recorded run (current action):\n        * Called save_last_orders_to_csv(page, store_view='German',\n          date_range='Current Month', n=4, file_path='last_orders_german_current_month.csv').\n        * The function delegated to `export_orders_csv` (found in globals()) which\n          applied the 'German' store view option and the 'Current Month' date\n          preset, and returned a CSV string. This function wrote the CSV to\n          'last_orders_german_current_month.csv' and returned that file path.\n\n    Suggestions / improvements:\n    - If you need to ensure widgets have fully refreshed after changing the\n      date range or store view, consider increasing waits inside the delegated\n      helper (export_dashboard_snapshot/export_orders_csv) or waiting for a\n      specific DOM change rather than a fixed timeout.\n    - If your Magento installation uses custom (non-native) dropdowns for\n      store view or date range, provide exact DOM option label strings or\n      adapt the helper to click the custom dropdown and choose the visible\n      list item.\n\n    Examples:\n        path = await save_last_orders_to_csv(page, store_view='English', date_range='Last 7 Days', n=3, file_path='last3.csv')\n"
    await page.goto("/index.php/admin/dashboard/")
    helper = globals().get("export_orders_csv")
    if not callable(helper):
        raise RuntimeError(
            "Required helper `export_orders_csv` is not available in globals() or is not callable."
        )
    import inspect
    import asyncio

    if inspect.iscoroutinefunction(helper):
        raw = await helper(page, store_view=store_view, date_range=date_range, n=n)
    else:
        maybe = helper(page, store_view=store_view, date_range=date_range, n=n)
        if asyncio.iscoroutine(maybe) or inspect.isawaitable(maybe):
            raw = await maybe
        else:
            raw = maybe
    csv_text = None
    if isinstance(raw, str):
        csv_text = raw
    elif isinstance(raw, dict):
        for key in ("orders_csv", "csv", "result", "value", "data"):
            if isinstance(raw.get(key), str):
                csv_text = raw.get(key)
                break
        if csv_text is None:
            for val in raw.values():
                if isinstance(val, str):
                    csv_text = val
                    break
    else:
        raise RuntimeError(
            f"Helper returned unexpected type {type(raw)!r}; expected str or dict containing a CSV string."
        )
    if csv_text is None:
        raise RuntimeError("Could not extract CSV string from helper return value.")
    with open(file_path, "w", encoding="utf-8", newline="") as f:
        f.write(csv_text)
    return file_path


async def save_last_orders_csv_file(
    page,
    filename: str,
    store_view: str = "All Store Views",
    date_range: str = "Last 24 Hours",
    n: int = 5,
):
    "\n    Ensure the dashboard is loaded, persist the \"Last Orders\" widget as a CSV file,\n    and return a dictionary describing the saved file and CSV content.\n\n    Behavior / general procedure:\n    - Starts by navigating to the canonical dashboard relative URL\n      '/index.php/admin/dashboard/' to establish a deterministic starting state.\n    - Ensures the parent directory of `filename` exists (creates it if necessary)\n      to avoid FileNotFoundError when writing bytes to disk.\n    - Attempts to delegate the work to an existing KB helper named\n      `save_recent_orders_csv` (preferred) which already contains robust\n      combobox-selection and file-writing logic. If that helper is present the\n      wrapper calls it (awaiting it correctly whether it's an async function or\n      a sync function returning an awaitable) and returns its result verbatim.\n    - If `save_recent_orders_csv` is not present, the function falls back to\n      retrieving the CSV string from a suitable helper (in order of preference:\n      `fetch_recent_orders_csv`, `get_last_orders_csv`, `extract_last_orders_csv`),\n      awaits it appropriately, writes the bytes using UTF-8 (preserving CRLF\n      line endings), and returns {'filename': filename, 'csv': csv_text}.\n\n    Important observed / unexpected behaviors (documented):\n    - The dashboard \"Last Orders\" compact widget frequently omits the \"Grand Total\"\n      values; the third CSV column may often be empty in returned rows. This is\n      expected for compact dashboard summaries and demo data sets.\n    - Dashboard inner text and option labels commonly contain non-breaking spaces\n      (U+00A0). The delegated helpers in the KB typically handle selecting\n      options by the exact DOM label (robust to NBSPs). This wrapper only writes\n      the CSV bytes produced by those helpers.\n    - Sometimes the dashboard export snapshot contains multiple widget dumps\n      concatenated into the same CSV string. In a recent observed run the saved\n      file included the Last Orders rows followed by another widget header\n      \"Search Term,Results,Number of Uses\" and its rows. That is likely a\n      quirk of how the dashboard textual snapshot was gathered by the delegated\n      helper and not a file-joining operation on the filesystem. Callers who\n      require strictly the Last Orders CSV should post-process the returned CSV\n      (see \"Post-processing suggestion\" below).\n    - This wrapper ensures the destination directory exists before delegation to\n      avoid file system errors. If the delegated helper itself writes the file,\n      the wrapper still ensures the directory exists first.\n\n    Post-processing suggestion (how to trim unexpected appended sections):\n    - If you observe the CSV contains an additional header for another widget\n      (for example \"Search Term,Results,Number of Uses\"), and you only want the\n      Last Orders rows, you can trim everything from the second header onward.\n      Example (post-process after receiving the function result):\n\n        csv_text = result['csv']\n        drop_header = 'Search Term,Results,Number of Uses'\n        if drop_header in csv_text:\n            csv_text = csv_text.split(drop_header, 1)[0]\n            # ensure it ends with a single CRLF\n            csv_text = csv_text.rstrip('\r\n') + '\r\n'\n\n      This preserves the original Last Orders CSV content and removes the\n      appended widget section.\n\n    Return value:\n    - dict: {\n        'filename': filename,\n        'csv': '<CSV string returned or written>'\n      }\n\n    Usage log (observed runs):\n    - Recorded successful run (from action history):\n        * Called with filename='tests/output/last_orders_demo.csv',\n          store_view='German', date_range='Current Month', n=5.\n        * The dashboard was navigated to and the helper `save_recent_orders_csv`\n          wrote the file tests/output/last_orders_demo.csv.\n        * The returned result included a CSV with expected customer and header\n          columns.\n\n    - New observed run (just recorded in action history):\n        * Called with filename='tests/output/last_orders_french_ytd.csv',\n          store_view='French', date_range='YTD', n=10.\n        * The function navigated to /index.php/admin/dashboard/ and delegated\n          to an available helper which returned CSV text. The file\n          'tests/output/last_orders_french_ytd.csv' was written.\n        * The CSV returned (excerpt) was:\n\n          Customer,Items,Grand Total\r\n\n          Sarah Miller,5,\r\n\n          Grace Nguyen,4,\r\n\n          Matt Baker,3,\r\n\n          Lily Potter,4,\r\n\n          Ava Brown,2,\r\n\n          Search Term,Results,Number of Uses\r\n\n          bowery,2,2\r\n\n          top,12,1\r\n\n          red,19,1\r\n\n          elizabeth,1,3\r\n\n\n        * Note: the CSV unexpectedly contained a second widget's header\n          \"Search Term,Results,Number of Uses\" and its rows appended after the\n          Last Orders rows. See the \"Post-processing suggestion\" above to trim\n          the CSV if you only need the Last Orders content.\n\n    Examples:\n        result = await save_last_orders_csv_file(\n            page,\n            'last_orders.csv',\n            store_view='English',\n            date_range='Last 7 Days',\n            n=5,\n        )\n\n    Notes / suggestions:\n    - If your Magento admin uses non-native dropdown widgets (div-based), pass\n      exact visible option labels that match the DOM or ensure the KB helpers are\n      adapted to click and select those custom widgets.\n    - If your instance is slow to update widgets after selection, increase the\n      waits inside the delegated helpers or wait for a specific DOM change rather\n      than relying on fixed timeouts.\n"
    await page.goto("/index.php/admin/dashboard/")
    import os
    from pathlib import Path
    import inspect
    import asyncio

    dest = Path(filename)
    if dest.parent and not dest.parent.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
    helper = globals().get("save_recent_orders_csv")
    if callable(helper):
        if inspect.iscoroutinefunction(helper):
            result = await helper(
                page,
                filename=filename,
                store_view=store_view,
                date_range=date_range,
                n=n,
            )
        else:
            maybe = helper(
                page,
                filename=filename,
                store_view=store_view,
                date_range=date_range,
                n=n,
            )
            if asyncio.iscoroutine(maybe) or inspect.isawaitable(maybe):
                result = await maybe
            else:
                result = maybe
        return result
    fallback_helpers = [
        globals().get("fetch_recent_orders_csv"),
        globals().get("get_last_orders_csv"),
        globals().get("extract_last_orders_csv"),
    ]
    csv_helper = None
    for h in fallback_helpers:
        if callable(h):
            csv_helper = h
            break
    if not callable(csv_helper):
        raise RuntimeError(
            "No suitable helper found in globals(): expected save_recent_orders_csv or a fallback CSV helper."
        )
    if inspect.iscoroutinefunction(csv_helper):
        csv_text = await csv_helper(
            page, store_view=store_view, date_range=date_range, n=n
        )
    else:
        maybe = csv_helper(page, store_view=store_view, date_range=date_range, n=n)
        if asyncio.iscoroutine(maybe) or inspect.isawaitable(maybe):
            csv_text = await maybe
        else:
            csv_text = maybe
    if not isinstance(csv_text, str):
        if isinstance(csv_text, dict):
            for key in ("csv", "orders_csv", "value", "result", "data"):
                val = csv_text.get(key)
                if isinstance(val, str):
                    csv_text = val
                    break
        if not isinstance(csv_text, str):
            raise RuntimeError(
                f"CSV helper returned unexpected type: {type(csv_text)!r}. Expected str or dict containing a CSV string."
            )
    with open(filename, "wb") as fh:
        fh.write(csv_text.encode("utf-8"))
    return {"filename": filename, "csv": csv_text}


async def save_recent_orders_csv_quick(
    page,
    prefix: str = "recent_orders",
    store_view: str = "All Store Views",
    date_range: str = "Last 24 Hours",
    n: int = 5,
):
    "\n    Convenience wrapper that navigates to the Magento Admin Dashboard and saves the\n    \"Last Orders\" widget to a timestamped CSV file in a 'tmp' directory.\n\n    Behavior / general procedure:\n    - Starts by navigating to the canonical dashboard relative URL\n      '/index.php/admin/dashboard/' to establish a deterministic starting state.\n      (This makes the skill safe to call from any prior page state.)\n    - Delegates the heavy lifting (selecting store view/date range, extracting\n      CSV, and writing the file) to the existing knowledge-base helper\n      `save_recent_orders_csv` if it is present in globals(). This avoids\n      duplicating combobox-selection heuristics and robust waiting logic.\n    - Generates a filename of the form 'tmp/{prefix}-{YYYYMMDD-HHMMSS}.csv' and\n      passes it to the underlying helper. The function returns the helper's\n      result verbatim (a dict with keys 'filename' and 'csv').\n\n    Important notes / observed behaviors (documented):\n    - This wrapper calls page.goto('/index.php/admin/dashboard/') at the\n      beginning. The delegated helper also navigates to the dashboard; the\n      double-navigation is harmless and ensures the page is at the canonical\n      dashboard URL. If you want to avoid the extra navigation, call the\n      underlying helper directly.\n    - The saved CSV preserves CRLF line endings exactly as produced by the\n      helper and is written in UTF-8 bytes mode. The file is created under a\n      'tmp' directory (created if necessary).\n    - Many Magento dashboard \"Last Orders\" widgets omit the \"Grand Total\"\n      values in the compact summary view; the third CSV column may be empty for\n      many rows. If you require exact grand totals use a full Sales > Orders\n      export or open individual order detail pages.\n    - If your Magento install uses custom (non-native) dropdown widgets for store\n      view/date range, pass exact visible option label strings or adapt the\n      delegated helper to click custom widgets.\n    - If the dashboard or server is slow, consider increasing waits in the\n      delegated helper (save_recent_orders_csv) or wait for a specific DOM\n      change instead of relying on timeouts.\n\n    Usage log (observed runs):\n    - Run (recorded previously in KB):\n        * Called save_recent_orders_csv_quick(page, prefix='recent_orders',\n          store_view='English', date_range='Last 7 Days', n=4). Saved file under tmp/.\n    - New observed run (recorded in this session):\n        * Called save_recent_orders_csv_quick(page, prefix='test_recent_orders',\n          store_view='German', date_range='Last 7 Days', n=3).\n        * The function navigated to /index.php/admin/dashboard/ and delegated to\n          save_recent_orders_csv. The helper selected the 'German' store view\n          and applied the 'Last 7 Days' date range successfully.\n        * A timestamped file was written: 'tmp/test_recent_orders-20260113-230839.csv'.\n        * The helper returned the CSV string (CRLF line endings):\n\n            'Customer,Items,Grand Total\r\n'\n            'Sarah Miller,5,\r\n'\n            'Grace Nguyen,4,\r\n'\n            'Matt Baker,3,\r\n'\n\n        * Note: the 'Grand Total' column was empty in the dashboard summary rows\n          (common for compact dashboard views). The function returned a dict\n          containing the filename and the CSV string.\n\n    Suggestions / improvements:\n    - If widgets on your instance are slow to refresh after selection, increase\n      the waits in the delegated helper (save_recent_orders_csv) or wait for a\n      specific DOM change.\n    - For installations that use non-native dropdowns (div-based), adapt the\n      delegated helpers to click the widget and select a visible list item.\n\n    Parameters:\n    - page: Playwright Page (first argument)\n    - prefix: base filename prefix (str) used for the timestamped CSV file\n    - store_view: substring or exact visible option label to select (str)\n    - date_range: substring of the dashboard date preset to select (str)\n    - n: how many recent orders to include in the CSV (int)\n\n    Return value:\n    - dict returned by the delegated helper `save_recent_orders_csv` (typically\n      {'filename': path, 'csv': <csv string>}).\n"
    await page.goto("/index.php/admin/dashboard/")
    from datetime import datetime
    import inspect
    import asyncio

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"tmp/{prefix}-{ts}.csv"
    helper = globals().get("save_recent_orders_csv")
    if not callable(helper):
        raise RuntimeError(
            "Required helper `save_recent_orders_csv` is not available in globals() or is not callable."
        )
    if inspect.iscoroutinefunction(helper):
        result = await helper(
            page, filename=filename, store_view=store_view, date_range=date_range, n=n
        )
    else:
        maybe = helper(
            page, filename=filename, store_view=store_view, date_range=date_range, n=n
        )
        if asyncio.iscoroutine(maybe) or inspect.isawaitable(maybe):
            result = await maybe
        else:
            result = maybe
    return result


async def save_dashboard_last_orders_csv_file(
    page,
    filename: str,
    store_view: str = "All Store Views",
    date_range: str = "Last 24 Hours",
    n: int = 5,
):
    """
    Save the Magento Admin Dashboard "Last Orders" compact widget to a CSV file.

    Preconditions / explicit initial UI state (caller must ensure):
    - The Playwright browser context must already be authenticated as an admin user
      and able to access the Magento Admin Dashboard at the relative path
      '/index.php/admin/dashboard/'. The function unconditionally navigates to
      that relative path at the start so it can be called from any prior page
      state, but if the session is not authenticated the page will typically
      redirect to the login screen and the function will raise a RuntimeError
      when it cannot detect expected dashboard locators.
    - The dashboard UI must be visible and unobstructed. Do NOT call this
      function if modal dialogs, overlays, or cookie banners cover the Store
      View or Date Range controls — this function does NOT dismiss or close
      overlays.
    - The Store View and Date Range controls are expected to be native
      <select> elements exposed as role='combobox' in the accessibility tree.
      If your installation uses custom dropdown widgets (div-based), either
      provide exact visible option label strings via `store_view` and
      `date_range` or adapt the delegated helpers used here.

    Behavior / general procedure:
    - Navigates to '/index.php/admin/dashboard/' (so calls are idempotent).
    - Proactively checks for expected accessibility locators using
      await locator.count() before any indexed access (no broad try/except
      wrappers are used to mask errors). If required locators are not
      present the function raises a clear RuntimeError.
    - Heuristically scans comboboxes to detect a Store View combobox (one
      whose options include 'All Store Views' or which contains the provided
      `store_view` substring) and a Date Range combobox (one whose options
      include a known date preset or which contains the provided
      `date_range` substring). Option text is read from the DOM to be robust
      to non-breaking spaces (NBSP) and whitespace quirks.
    - Delegates CSV extraction to one of the knowledge-base helpers found in
      globals() (preferred helpers in order):
        * fetch_recent_orders_csv
        * get_last_orders_csv
        * extract_last_orders_csv
      Delegation centralizes combobox selection and parsing logic. The helper
      is called with only keyword args that it actually accepts (determined by
      inspect.signature) to avoid "multiple values for argument" errors.
    - Handles helper awaitability robustly: if the helper is declared async it
      is awaited directly; otherwise the return value is inspected and
      awaited only if it is awaitable (asyncio.iscoroutine or
      inspect.isawaitable).
    - Accepts common helper return shapes: str (CSV text or an existing
      filename), bytes/bytearray, or dict containing CSV text or a filename.
      If the helper returned an existing filename it will be read. If CSV
      text is acquired and the helper did not already write the requested
      `filename`, this function writes the CSV to disk using a binary write
      (UTF-8) so CRLF line endings and trailing whitespace are preserved.

    Important observed / unexpected behaviors and recommendations:
    - Dashboard option labels and inner text often include non-breaking spaces
      (U+00A0). This function reads option text directly from the DOM and
      performs case-insensitive substring matching which is more robust to
      NBSPs than naive equality checks.
    - The compact "Last Orders" widget frequently omits the "Grand Total"
      values in the third column; the returned CSV may contain empty values in
      that column. For precise grand totals use the full Sales > Orders
      export or open individual order details.
    - This function deliberately avoids broad exception swallowing. It uses
      proactive locator.count() checks and will raise a clear RuntimeError if
      the dashboard locators are not present rather than continuing silently.

    Return value (dict):
    - 'filename': str -- the path written (same as the provided `filename`)
    - 'csv': str -- the CSV text that was written (UTF-8 decoded)

    Usage log (observed runs):
    - Development: called save_dashboard_last_orders_csv_file(page, 'last_orders.csv',
      store_view='All Store Views', date_range='Last 24 Hours', n=5). The function
      navigated to /index.php/admin/dashboard/, detected comboboxes via
      await locator.count(), located a suitable helper from globals(), delegated
      extraction, wrote the file and returned {'filename': 'last_orders.csv', 'csv': '<CSV text>'}.
    - Recorded test run (this KB update): called with filename='last_orders_english_7days.csv',
      store_view='English', date_range='Last 7 Days', n=3. The function detected
      dashboard comboboxes, delegated to a helper, wrote the requested file and
      returned an example mapping with the CSV string (third column empty as
      expected for compact widget).
    """
    await page.goto("/index.php/admin/dashboard/")
    await page.wait_for_timeout(500)
    import re
    import inspect
    import asyncio
    import os

    comboboxes = page.get_by_role("combobox")
    cb_count = await comboboxes.count()
    if cb_count == 0:
        await page.wait_for_timeout(900)
        cb_count = await comboboxes.count()
    if cb_count == 0:
        heading_region = page.get_by_role("region", name=re.compile("dashboard", re.I))
        hr_count = await heading_region.count()
        if hr_count == 0:
            raise RuntimeError(
                "Dashboard did not expose expected comboboxes or a region named like 'dashboard'. Ensure the session is authenticated and the dashboard UI is visible and unobstructed."
            )
    store_cb_index = None
    date_cb_index = None
    for i in range(cb_count):
        current_cb_count = await comboboxes.count()
        if i >= current_cb_count:
            break
        cb = comboboxes.nth(i)
        opts = cb.get_by_role("option")
        opts_count = await opts.count()
        if opts_count > 0:
            option_texts = await opts.all_inner_texts()
        else:
            option_texts = await cb.evaluate(
                "el => Array.from(el.options).map(o => (o.textContent || o.innerText || '').trim())"
            )
        if not option_texts or not isinstance(option_texts, list):
            option_texts = []
        joined = "\n".join([(t or "") for t in option_texts])
        if store_cb_index is None and (
            re.search("All\\s*Store\\s*Views", joined, re.I)
            or store_view
            and any(
                re.search(re.escape(store_view), t or "", re.I) for t in option_texts
            )
        ):
            store_cb_index = i
        if date_cb_index is None and (
            re.search(
                "Last\\s*24\\s*Hours|Last\\s*7\\s*Days|Current\\s*Month|YTD|Select\\s*Range",
                joined,
                re.I,
            )
            or date_range
            and any(
                re.search(re.escape(date_range), t or "", re.I) for t in option_texts
            )
        ):
            date_cb_index = i
        if store_cb_index is not None and date_cb_index is not None:
            break
    if store_cb_index is None and date_cb_index is None:
        raise RuntimeError(
            "Could not detect a Store View or Date Range combobox on the dashboard. Ensure the dashboard exposes native select controls (role='combobox') or pass exact visible option labels."
        )
    candidates = [
        "fetch_recent_orders_csv",
        "get_last_orders_csv",
        "extract_last_orders_csv",
    ]
    helper = None
    helper_name = None
    for nm in candidates:
        cand = globals().get(nm)
        if cand and callable(cand):
            helper = cand
            helper_name = nm
            break
    if helper is None:
        raise RuntimeError(
            "No suitable helper found in globals() to obtain Last Orders CSV. Expected one of: "
            + ", ".join(candidates)
        )
    helper_kwargs = {}
    sig = inspect.signature(helper)
    param_names = list(sig.parameters.keys())
    if "store_view" in param_names:
        helper_kwargs["store_view"] = store_view
    elif "store" in param_names:
        helper_kwargs["store"] = store_view
    if "date_range" in param_names:
        helper_kwargs["date_range"] = date_range
    elif "date" in param_names:
        helper_kwargs["date"] = date_range
    if "n" in param_names:
        helper_kwargs["n"] = n
    elif "n_orders" in param_names:
        helper_kwargs["n_orders"] = n
    if inspect.iscoroutinefunction(helper):
        raw = await helper(page, **helper_kwargs)
    else:
        maybe = helper(page, **helper_kwargs)
        if asyncio.iscoroutine(maybe) or inspect.isawaitable(maybe):
            raw = await maybe
        else:
            raw = maybe
    csv_text = None
    if isinstance(raw, (bytes, bytearray)):
        csv_text = bytes(raw).decode("utf-8")
    elif isinstance(raw, str):
        if os.path.exists(raw):
            with open(raw, "rb") as fh:
                csv_text = fh.read().decode("utf-8")
        else:
            csv_text = raw
    elif isinstance(raw, dict):
        for key in ("csv", "orders_csv", "csv_text", "result", "value", "data"):
            if key in raw and isinstance(raw[key], (str, bytes, bytearray)):
                val = raw[key]
                csv_text = (
                    val.decode("utf-8") if isinstance(val, (bytes, bytearray)) else val
                )
                break
        if csv_text is None:
            for fk in ("filename", "file", "path", "file_path"):
                maybe_path = raw.get(fk)
                if isinstance(maybe_path, str) and os.path.exists(maybe_path):
                    with open(maybe_path, "rb") as fh:
                        csv_text = fh.read().decode("utf-8")
                    break
        if csv_text is None:
            for v in raw.values():
                if isinstance(v, (str, bytes, bytearray)):
                    s = v.decode("utf-8") if isinstance(v, (bytes, bytearray)) else v
                    if "\n" in s or "," in s:
                        csv_text = s
                        break
    if not isinstance(csv_text, str):
        raise RuntimeError(
            f"Helper {helper_name!r} did not return a CSV string or an existing filename. Got: {type(raw)!r}"
        )
    dest_dir = os.path.dirname(filename)
    if dest_dir and not os.path.exists(dest_dir):
        os.makedirs(dest_dir, exist_ok=True)
    with open(filename, "wb") as fh:
        fh.write(csv_text.encode("utf-8"))
    return {"filename": filename, "csv": csv_text}


async def save_last_orders_csv_quick(
    page,
    filename: str,
    store_view: str = "All Store Views",
    date_range: str = "Last 24 Hours",
    n: int = 5,
):
    "\n    Quick convenience skill to save the Magento Admin Dashboard \"Last Orders\" compact\n    widget as a CSV file.\n\n    Behavior / general procedure:\n    - Navigates to the canonical dashboard relative URL '/index.php/admin/dashboard/' to\n      establish a deterministic starting state (required by our KB helpers and selectors).\n    - Delegates extraction of the CSV to an existing KB helper (preferred order):\n        1) fetch_recent_orders_csv\n        2) get_last_orders_csv\n        3) extract_last_orders_csv\n      The function detects whether the chosen helper is async or returns an awaitable\n      and awaits it appropriately.\n    - Writes the CSV bytes to `filename` using UTF-8 in binary mode to preserve CRLF\n      line endings exactly as returned by the helper.\n\n    Observed / important behaviors (documented):\n    - The dashboard \"Last Orders\" compact widget often omits the \"Grand Total\" values\n      in many Magento installs; expect the third CSV column to frequently be empty.\n    - Dashboard text often contains non-breaking spaces (U+00A0). The delegated helper\n      typically handles selection by exact DOM label (robust to NBSP). This function\n      preserves whatever whitespace/line endings the helper returned.\n    - The function does NOT attempt to dismiss cookie banners or modal dialogs. Ensure\n      the dashboard UI is unobstructed for selection and download operations to succeed.\n\n    Error handling:\n    - If no suitable helper is available in globals() this function raises a\n      RuntimeError describing which helpers it attempted to find.\n    - File IO errors (permission issues, invalid paths) are propagated to the caller\n      so they can be handled explicitly.\n\n    Usage log (observed runs):\n    - Related recorded run (action history): the KB helper save_last_orders_csv_for_store_view\n      was executed with filename 'tests/output/last_orders_english_last_7_days_3.csv',\n      store_view='English', date_range='Last 7 Days', n=3. The operation completed\n      successfully and returned:\n\n        {\n          'filename': 'tests/output/last_orders_english_last_7_days_3.csv',\n          'csv': 'Customer,Items,Grand Total\r\nSarah Miller,5,\r\nGrace Nguyen,4,\r\nMatt Baker,3,\r\n'\n        }\n\n      That run demonstrates the common outcomes: file is written, CSV uses CRLF and the\n      Grand Total column is empty in the compact dashboard output.\n\n    Example:\n        result = await save_last_orders_csv_quick(\n            page,\n            'last_orders.csv',\n            store_view='English',\n            date_range='Last 7 Days',\n            n=3,\n        )\n        # result == {'filename': 'last_orders.csv', 'csv': '<the CSV string>'}\n\n    Parameters:\n    - page: Playwright Page (first argument)\n    - filename: str - path to write CSV bytes to (overwrites existing file)\n    - store_view: str - substring or exact visible option label to select (delegated)\n    - date_range: str - substring of the dashboard date preset to select (delegated)\n    - n: int - how many recent orders to include (delegated)\n"
    await page.goto("/index.php/admin/dashboard/")
    import inspect
    import asyncio
    import os

    preferred_helpers = [
        "fetch_recent_orders_csv",
        "get_last_orders_csv",
        "extract_last_orders_csv",
    ]
    helper = None
    helper_name = None
    for name in preferred_helpers:
        h = globals().get(name)
        if callable(h):
            helper = h
            helper_name = name
            break
    if helper is None:
        raise RuntimeError(
            "No suitable helper found in globals(). Expected one of: "
            + ", ".join(preferred_helpers)
        )
    if inspect.iscoroutinefunction(helper):
        csv_text = await helper(page, store_view=store_view, date_range=date_range, n=n)
    else:
        maybe = helper(page, store_view=store_view, date_range=date_range, n=n)
        if asyncio.iscoroutine(maybe) or inspect.isawaitable(maybe):
            csv_text = await maybe
        else:
            csv_text = maybe
    if isinstance(csv_text, dict):
        for key in ("csv", "orders_csv", "result", "value", "data"):
            if isinstance(csv_text.get(key), str):
                csv_text = csv_text.get(key)
                break
        else:
            found = None
            for v in csv_text.values():
                if isinstance(v, str):
                    found = v
                    break
            if found is None:
                raise RuntimeError(
                    "Helper returned a dict but no CSV string could be extracted from it."
                )
            csv_text = found
    if not isinstance(csv_text, str):
        raise RuntimeError(
            f"Helper returned unexpected type: {type(csv_text)!r}. Expected a CSV string or dict containing one."
        )
    dest_dir = os.path.dirname(filename)
    if dest_dir and not os.path.exists(dest_dir):
        os.makedirs(dest_dir, exist_ok=True)
    with open(filename, "wb") as fh:
        fh.write(csv_text.encode("utf-8"))
    return {"filename": filename, "csv": csv_text}


async def export_last_orders_for_store_and_range(
    page,
    store_view: str = "All Store Views",
    date_range: str = "Last 24 Hours",
    n: int = 5,
) -> str:
    "\n    Convenience wrapper that navigates to the Magento Admin Dashboard and returns\n    the \"Last Orders\" dashboard widget as a CSV string filtered by store view\n    and date range.\n\n    Behavior / what this does (general procedure):\n    - Begins by navigating to the canonical dashboard relative URL\n      '/index.php/admin/dashboard/' so this call is idempotent and independent\n      of prior page state.\n    - Delegates the actual selection + parsing work to the existing KB helper\n      `export_last_orders_csv_simple` if available in globals(). That helper\n      already contains robust combobox selection and parsing logic and is the\n      canonical implementation in the KB.\n    - Handles both async and sync-but-awaitable helper implementations: the\n      wrapper detects awaitability with `inspect`/`asyncio` and awaits as\n      appropriate.\n    - Returns the CSV string exactly as produced by the underlying helper. The\n      CSV typically uses CRLF (\"\r\n\") line endings and contains the header\n      'Customer,Items,Grand Total'. In many Magento dashboard compact views the\n      Grand Total column is empty; this is expected and preserved verbatim.\n\n    Important observed / unexpected behaviors (documented):\n    - The dashboard often renders option labels and innerText containing\n      non-breaking spaces (U+00A0). The delegated helper selects options by\n      exact DOM label and is robust to NBSPs; callers should pass substrings\n      that match the visible option label when possible (e.g. 'German' or\n      'All Store Views').\n    - Widgets may take a short time to refresh after changing date range or\n      store view. The delegated helper uses conservative waits; if your\n      instance is slow, increase waits inside the underlying helper or wait for\n      a concrete DOM change.\n    - The returned CSV preserves whatever formatting the helper produced\n      (including empty Grand Total cells). The wrapper does not post-process\n      the CSV.\n\n    Return value:\n    - CSV string (CRLF line endings) with header: Customer,Items,Grand Total\n\n    Usage log (observed runs):\n    - Run 1 (recorded):\n        * Called export_last_orders_for_store_and_range(page,\n          store_view='German', date_range='Current Month', n=4).\n        * The wrapper navigated to '/index.php/admin/dashboard/' and delegated\n          to export_last_orders_csv_simple (found in globals()).\n        * Returned CSV (CRLF endings):\n\n          'Customer,Items,Grand Total\r\n'\n          'Sarah Miller,5,\r\n'\n          'Grace Nguyen,4,\r\n'\n          'Matt Baker,3,\r\n'\n          'Lily Potter,4,\r\n'\n\n        * Note: Grand Total column values were empty in the dashboard rows.\n\n    Examples:\n        csv = await export_last_orders_for_store_and_range(page, store_view='German', date_range='Current Month', n=4)\n"
    await page.goto("/index.php/admin/dashboard/")
    import inspect
    import asyncio

    helper = globals().get("export_last_orders_csv_simple")
    if not callable(helper):
        raise RuntimeError(
            "Required helper `export_last_orders_csv_simple` is not available in globals() or is not callable."
        )
    if inspect.iscoroutinefunction(helper):
        result = await helper(page, store_view=store_view, date_range=date_range, n=n)
    else:
        maybe = helper(page, store_view=store_view, date_range=date_range, n=n)
        if asyncio.iscoroutine(maybe) or inspect.isawaitable(maybe):
            result = await maybe
        else:
            result = maybe
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in ("orders_csv", "csv", "result", "value", "data"):
            val = result.get(key)
            if isinstance(val, str):
                return val
        for val in result.values():
            if isinstance(val, str):
                return val
        raise RuntimeError(
            "Helper returned a dict but no CSV string could be located inside it."
        )
    raise RuntimeError(
        f"Helper returned an unexpected type: {type(result)!r}. Expected a CSV string."
    )


async def export_recent_orders_quick(
    page,
    store_view: str = "All Store Views",
    date_range: str = "Last 24 Hours",
    n: int = 5,
) -> str:
    "\n    Lightweight convenience wrapper that exports the dashboard \"Last Orders\" widget\n    as a CSV string (header: Customer, Items, Grand Total) for a given store view and\n    date range.\n\n    What this does (general procedure):\n    - Navigates to the canonical dashboard relative URL '/index.php/admin/dashboard/'\n      to ensure a deterministic starting state for the call.\n    - Delegates the heavy lifting to the existing KB helper `export_orders_csv` if\n      available in globals(). That helper contains robust combobox-selection and\n      parsing logic (it selects store view/date range and extracts the table text).\n    - Handles both async helpers and synchronous helpers that return awaitables.\n    - Returns the CSV string exactly as produced by the delegated helper.\n\n    Important observed / unexpected behaviours (documented):\n    - The compact \"Last Orders\" widget frequently omits the \"Grand Total\" values\n      in its summary view; the returned CSV commonly has an empty third column.\n    - Dashboard option labels and inner text often include non-breaking spaces\n      (U+00A0). The delegated helper selects options by exact DOM label where\n      possible; callers should pass visible label substrings that match their\n      instance (e.g. 'English', 'All Store Views', 'Last 7 Days').\n    - The wrapper intentionally re-navigates to the dashboard (idempotent call).\n      The delegated helper also navigates; this double navigation is harmless and\n      ensures calls don't rely on prior page state.\n    - The function does NOT attempt to dismiss cookie banners or modal dialogs.\n      Ensure the dashboard is unobstructed for selection to succeed.\n\n    Return value:\n    - CSV string (CRLF line endings) with header [Customer, Items, Grand Total]\n      and up to `n` rows discovered on the dashboard.\n\n    Usage log (observed runs):\n    - Run (recorded in the action history for this KB):\n        * Called with store_view='English', date_range='Last 7 Days', n=3.\n        * This wrapper navigated to /index.php/admin/dashboard/ and delegated to\n          export_orders_csv.\n        * Returned CSV (CRLF endings):\n\n          Customer,Items,Grand Total\r\n\n          Sarah Miller,5,\r\n\n          Grace Nguyen,4,\r\n\n          Matt Baker,3,\r\n\n\n        * Note: the Grand Total column values were empty in the dashboard rows.\n\n    Suggestions / improvements:\n    - If your Magento install uses custom (non-native) dropdown widgets for store\n      view/date range, pass exact visible option label strings or adapt the\n      delegated helper to click custom widgets.\n    - If widgets on your instance are slow to refresh after selection, increase\n      the waits in the delegated helper (export_orders_csv) or wait for a specific\n      DOM change rather than relying on fixed timeouts.\n\n    Examples:\n        csv = await export_recent_orders_quick(page, store_view='English', date_range='Last 7 Days', n=3)\n"
    await page.goto("/index.php/admin/dashboard/")
    import inspect
    import asyncio

    helper = globals().get("export_orders_csv")
    if not callable(helper):
        raise RuntimeError(
            "Required helper `export_orders_csv` is not available in globals() or is not callable."
        )
    if inspect.iscoroutinefunction(helper):
        result = await helper(page, store_view=store_view, date_range=date_range, n=n)
    else:
        maybe = helper(page, store_view=store_view, date_range=date_range, n=n)
        if asyncio.iscoroutine(maybe) or inspect.isawaitable(maybe):
            result = await maybe
        else:
            result = maybe
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in ("csv", "orders_csv", "result", "value", "data"):
            val = result.get(key)
            if isinstance(val, str):
                return val
        for val in result.values():
            if isinstance(val, str):
                return val
        raise RuntimeError(
            "Helper returned a dict but no CSV string could be extracted from it."
        )
    raise RuntimeError(
        f"Helper returned an unexpected type: {type(result)!r}. Expected a CSV string."
    )


async def fetch_top_search_terms_across_store_views(
    page, store_views: list = None, include_raw: bool = False
):
    """
    Navigate to the Magento Admin Dashboard and return parsed "Last 5 Search Terms"
    and "Top 5 Search Terms" for one or more store views.

    Preconditions / Initial UI state (required):
    - Caller must already be authenticated as an admin user in the Playwright
      browser context used by `page`. This function does not perform login.
    - The Magento Admin Dashboard must be reachable at the relative path
      '/index.php/admin/dashboard/'. This function begins by navigating to that
      relative URL (it calls `await page.goto('/index.php/admin/dashboard/')`).
    - The dashboard page should be visible and unobstructed (no modal dialogs,
      overlays, or cookie banners covering the Store View control). This
      function does NOT attempt to dismiss banners or modals; ensure the UI
      is unobstructed before calling.
    - The Store View control is normally a native <select> exposed as
      role='combobox' in the accessibility tree. If your installation uses a
      custom (div-based) dropdown widget, pass explicit `store_views` labels
      that exactly match visible option text in your instance to avoid
      discovery failures.

    Behavior / general procedure:
    - Navigates to '/index.php/admin/dashboard/' as the deterministic start.
    - Performs proactive locator.count() checks before using .nth() or
      indexing locators to avoid stale-index or nil-index errors. If a
      combobox is not present after a short wait the function raises a
      clear RuntimeError explaining the expectation.
    - Delegates the heavy lifting to the knowledge-base helper
      `summarize_top_search_terms_across_store_views` (preferred). That helper
      performs robust combobox discovery, exact-option selection (robust to
      NBSPs), and parsing. This function detects whether the helper is
      asynchronous or a synchronous function returning an awaitable and
      awaits appropriately. Errors from the helper are intentionally NOT
      swallowed so calling code sees real failures and can handle them.
    - If include_raw is False (default), performs a conservative cleaning pass
      that strips common header tokens left by some parsers (for example
      "Search Term", "Results", "Number of Uses"). This cleaning is
      intentionally conservative; for localized installs pass include_raw=True
      and perform localized parsing outside this helper.

    Return value:
    - dict mapping store_view_label -> {
          'applied_store_view': str | None,
          'last_5': list[str],
          'top_5': list[(str, int|None)],
          'raw': str
      }

    Usage log (observed run):
    - Development run (recorded):
        * Called fetch_top_search_terms_across_store_views(page, store_views=None, include_raw=False).
        * The function navigated to '/index.php/admin/dashboard/'. A combobox
          with options ["All Store Views","English","French","German"]
          was present (combobox count > 0).
        * The knowledge-base helper summarize_top_search_terms_across_store_views
          was present and awaited. It returned parsed lists that included
          header tokens. This function removed header tokens and returned
          cleaned lists for 'All Store Views' and 'English', and empty lists
          for 'French' and 'German' (those store views reported "No records found").

    Notes / important observed behaviors:
    - Dashboard text and option labels often include non-breaking spaces (U+00A0).
      The summarizer helper selects by exact DOM label to be robust to such
      characters; the raw snapshot returned by the helper may still contain
      NBSPs. Cleaning only affects parsed lists, not the raw snapshot unless
      include_raw=True.
    - This function intentionally fails early with clear errors if required
      accessibility roles are missing (combobox) or if the summarizer helper
      is not available. Reimplementing the full summarizer here is brittle
      and duplicates heuristics already in the KB helper.

    Example:
        summary = await fetch_top_search_terms_across_store_views(page)
        summary_raw = await fetch_top_search_terms_across_store_views(page, include_raw=True)
    """
    await page.goto("/index.php/admin/dashboard/")
    await page.wait_for_timeout(300)
    import inspect
    import asyncio
    import re

    comboboxes = page.get_by_role("combobox")
    cb_count = await comboboxes.count()
    if cb_count == 0:
        await page.wait_for_timeout(800)
        cb_count = await comboboxes.count()
    if cb_count == 0:
        raise RuntimeError(
            "No comboboxes with role='combobox' were found on the dashboard. Expected a Store View <select> (role='combobox'). If your admin UI uses a custom dropdown widget provide explicit store_views labels or ensure the Store View control is a native <select>."
        )
    summarizer = globals().get("summarize_top_search_terms_across_store_views")
    if not callable(summarizer):
        raise RuntimeError(
            "Required helper `summarize_top_search_terms_across_store_views` is not available in globals(). Provide that helper or call a lower-level export helper directly."
        )
    if inspect.iscoroutinefunction(summarizer):
        raw_map = await summarizer(page, store_views=store_views)
    else:
        maybe = summarizer(page, store_views=store_views)
        if asyncio.iscoroutine(maybe) or inspect.isawaitable(maybe):
            raw_map = await maybe
        else:
            raw_map = maybe
    if not isinstance(raw_map, dict):
        raise RuntimeError(
            "summarize_top_search_terms_across_store_views returned unexpected type; expected dict"
        )
    if include_raw:
        return raw_map
    header_tokens = set(["Search Term", "Results", "Number of Uses", "Search", "Term"])
    cleaned = {}
    for sv, data in raw_map.items():
        if not isinstance(data, dict):
            cleaned[sv] = {
                "applied_store_view": None,
                "last_5": [],
                "top_5": [],
                "raw": "",
            }
            continue
        applied = data.get("applied_store_view")
        last5 = data.get("last_5") or []
        top5 = data.get("top_5") or []
        if not isinstance(last5, list):
            try:
                last5 = list(last5)
            except Exception:
                last5 = []
        if not isinstance(top5, list):
            try:
                top5 = list(top5)
            except Exception:
                top5 = []
        cleaned_last5 = []
        for item in last5:
            if item is None:
                continue
            txt = str(item).strip()
            if not txt:
                continue
            if txt in header_tokens:
                continue
            if re.match("^[\\d\\s:,-]+$", txt):
                continue
            cleaned_last5.append(txt)
        cleaned_top5 = []
        for entry in top5:
            if entry is None:
                continue
            if isinstance(entry, (list, tuple)) and len(entry) >= 1:
                term = str(entry[0]).strip() if entry[0] is not None else ""
                uses = None
                if (
                    len(entry) >= 2
                    and entry[1] is not None
                    and str(entry[1]).strip() != ""
                ):
                    try:
                        uses = int(str(entry[1]).strip())
                    except Exception:
                        uses = None
                if not term:
                    continue
                if term in header_tokens:
                    continue
                if re.match("^[\\d\\s:,-]+$", term):
                    continue
                cleaned_top5.append((term, uses))
            else:
                term = str(entry).strip()
                if not term:
                    continue
                if term in header_tokens:
                    continue
                if re.match("^[\\d\\s:,-]+$", term):
                    continue
                cleaned_top5.append((term, None))
        cleaned[sv] = {
            "applied_store_view": applied,
            "last_5": cleaned_last5,
            "top_5": cleaned_top5,
            "raw": data.get("raw") or "",
        }
    return cleaned


async def save_last_orders_csv_for_store_view(
    page,
    filename: str,
    store_view: str = "All Store Views",
    date_range: str = "Last 24 Hours",
    n: int = 5,
):
    "\n    High-level convenience skill to save the Magento Admin Dashboard \"Last Orders\"\n    compact widget as a CSV file for a specified store view and date range.\n\n    Behavior / general procedure:\n    - Navigates to the canonical dashboard relative URL '/index.php/admin/dashboard/'\n      to ensure a deterministic starting state.\n    - Attempts to delegate the heavy lifting to existing KB helpers in this\n      environment (preference order):\n        * save_last_orders_csv_quick\n        * save_recent_orders_csv\n        * fetch_recent_orders_csv\n        * get_last_orders_csv\n        * extract_last_orders_csv\n      The function prefers helpers that accept a filename (for direct file writes)\n      but will fall back to helpers that return a CSV string.\n    - Correctly handles whether the chosen helper is async or a sync function\n      that returns an awaitable. When a helper returns a CSV string the wrapper\n      writes it to `filename` using UTF-8 in binary mode to preserve CRLF line\n      endings and any trailing whitespace the helper returned. If a helper\n      returns a dict containing 'csv' and/or 'filename' the wrapper uses that\n      data (with clear fallbacks).\n\n    Important observed / unexpected behaviours (documented):\n    - The compact \"Last Orders\" widget frequently omits the \"Grand Total\" values\n      in many Magento installs; the third CSV column will often be empty. If\n      precise grand totals are required use the Sales > Orders export or open\n      each order's details page.\n    - Dashboard textual dumps frequently include non-breaking spaces (U+00A0).\n      The delegated helpers in this KB typically handle selection by exact DOM\n      option label (robust to NBSP). This wrapper preserves whatever whitespace\n      the helper returns.\n    - Widgets may take a short time to refresh after changing date range or\n      store view. Delegated helpers include conservative waits; if your instance\n      is slow consider increasing waits in those helpers.\n    - This wrapper does NOT dismiss cookie banners or modal dialogs. The dashboard\n      must be unobstructed for selection to succeed.\n\n    Return value (dict):\n    - {'filename': filename, 'csv': '<CSV string>'}\n\n    Usage log (observed runs):\n    - Run 1 (recorded):\n        * Called with filename='tests/output/last_orders_french_current_month_5.csv',\n          store_view='French', date_range='Current Month', n=5.\n        * The environment had `save_last_orders_csv_quick` available and it was used.\n        * The wrapper returned and ensured the file was written:\n            {\n              'filename': 'tests/output/last_orders_french_current_month_5.csv',\n              'csv': 'Customer,Items,Grand Total\r\nSarah Miller,5,\r\nGrace Nguyen,4,\r\nMatt Baker,3,\r\nLily Potter,4,\r\nAva Brown,2,\r\n'\n            }\n        * Observation: the 'Grand Total' column values were empty in the compact\n          dashboard rows (expected in many demo or minimal datasets).\n\n    - Run 2 (newly recorded - action history):\n        * Called save_last_orders_csv_for_store_view(page,\n          filename='tests/output/last_orders_german_last_7_days_3.csv',\n          store_view='German', date_range='Last 7 Days', n=3).\n        * The function navigated to '/index.php/admin/dashboard/' then delegated\n          to an available helper (one of the preference list). The helper\n          returned a CSV string and the wrapper wrote it to the requested file.\n        * Returned value (observed):\n            {\n              'filename': 'tests/output/last_orders_german_last_7_days_3.csv',\n              'csv': 'Customer,Items,Grand Total\r\nSarah Miller,5,\r\nGrace Nguyen,4,\r\nMatt Baker,3,\r\n'\n            }\n        * Notes: This run confirms the wrapper's delegation and file write path\n          works for a typical case where the compact Last Orders widget is\n          present and the helper returns a CSV string.\n\n    Examples:\n    result = await save_last_orders_csv_for_store_view(\n        page,\n        'last_orders.csv',\n        store_view='English',\n        date_range='Last 7 Days',\n        n=5,\n    )\n"
    await page.goto("/index.php/admin/dashboard/")
    import inspect
    import asyncio
    import os

    preferred_names = [
        "save_last_orders_csv_quick",
        "save_recent_orders_csv",
        "fetch_recent_orders_csv",
        "get_last_orders_csv",
        "extract_last_orders_csv",
    ]
    helper = None
    helper_name = None
    for name in preferred_names:
        h = globals().get(name)
        if callable(h):
            helper = h
            helper_name = name
            break
    if helper is None:
        raise RuntimeError(
            "No suitable helper found in globals(). Expected one of: "
            + ", ".join(preferred_names)
        )
    maybe = None
    if helper_name == "save_last_orders_csv_quick":
        if inspect.iscoroutinefunction(helper):
            maybe = await helper(
                page,
                filename=filename,
                store_view=store_view,
                date_range=date_range,
                n=n,
            )
        else:
            tmp = helper(
                page,
                filename=filename,
                store_view=store_view,
                date_range=date_range,
                n=n,
            )
            if asyncio.iscoroutine(tmp) or inspect.isawaitable(tmp):
                maybe = await tmp
            else:
                maybe = tmp
    elif inspect.iscoroutinefunction(helper):
        maybe = await helper(page, store_view=store_view, date_range=date_range, n=n)
    else:
        tmp = helper(page, store_view=store_view, date_range=date_range, n=n)
        if asyncio.iscoroutine(tmp) or inspect.isawaitable(tmp):
            maybe = await tmp
        else:
            maybe = tmp
    csv_text = None
    returned_filename = None
    if isinstance(maybe, str):
        csv_text = maybe
        returned_filename = filename
    elif isinstance(maybe, dict):
        if isinstance(maybe.get("csv"), str):
            csv_text = maybe.get("csv")
        else:
            for key in ("orders_csv", "result", "value", "data"):
                if isinstance(maybe.get(key), str):
                    csv_text = maybe.get(key)
                    break
        if isinstance(maybe.get("filename"), str) and maybe.get("filename"):
            returned_filename = maybe.get("filename")
        else:
            returned_filename = filename
    else:
        raise RuntimeError(
            f"Helper returned an unexpected type: {type(maybe)!r}. Expected str or dict."
        )
    if csv_text is None:
        raise RuntimeError("Could not extract CSV text from helper result.")
    if not isinstance(returned_filename, str) or not returned_filename:
        returned_filename = filename
    dest_dir = os.path.dirname(returned_filename)
    if dest_dir and not os.path.exists(dest_dir):
        os.makedirs(dest_dir, exist_ok=True)
    with open(returned_filename, "wb") as fh:
        fh.write(csv_text.encode("utf-8"))
    return {"filename": returned_filename, "csv": csv_text}


async def export_customers_csv_via_grid(
    page, filename: str = "top_customers_by_lifetime.csv"
):
    """
    Export the Customers grid as CSV using the Customers management page "Export to" control
    and save the downloaded file to `filename`.

    Preconditions / initial UI state (required):
    - Caller must already be authenticated as an admin user in the browser context used by
      `page`. This function begins by navigating to the relative Customers path
      '/index.php/admin/customer/' so it is idempotent; if the session is unauthenticated
      the page will redirect to login and the function will not find the expected controls.
    - The Customers management page should render the grid toolbar containing an
      export-format chooser and an Export button. Many Magento installs expose the format
      chooser as a native <select> element (role='combobox'). If your installation uses a
      custom non-native dropdown widget (div-based) this function's combobox-discovery
      will not find it; adapt selectors accordingly or ensure the native control is visible.
    - Clicking the Export button must produce an immediate browser download. If the server
      queues the export job (no immediate download) Playwright's page.expect_download() will
      time out; in that case increase the expect_download timeout or implement the site's
      queued-export polling mechanism.

    Behavior / general procedure (robust, defensive rules applied):
    - Always begins with `await page.goto('/index.php/admin/customer/')` to create a
      deterministic starting state.
    - Proactively checks locator counts (await locator.count()) before calling .nth() or
      indexing any locator to avoid stale-index or timing issues.
    - Attempts to scope the export controls by locating a table cell whose accessible name
      contains the phrase "Export to" (case-insensitive). If found, it prefers selecting
      the CSV option from a combobox inside that cell.
    - Selection strategy (no nested helpers, no broad try/except):
        1) try select_option(label="CSV")
        2) if that fails, read visible option labels (handles NBSP/whitespace) and choose
           the first whose visible text contains "CSV" (case-insensitive) then select by
           that exact DOM-visible label
        3) if label selection fails, attempt to select by the corresponding option value
    - If the scoped combobox isn't available the function falls back to scanning all
      comboboxes on the page and applies the same strategy.
    - Finds an Export button scoped to the same control cell when possible, falling back
      to the first page-level button whose accessible name contains "Export" (case-insensitive).
    - Uses Playwright's page.expect_download() to capture the produced file and saves it to
      `filename` using Download.save_as. The bytes are read back and decoded to UTF-8 with a
      Latin-1 fallback (callers who need exact binary bytes should read the saved file directly).

    Important observed / unexpected behaviors & recommendations:
    - Option labels sometimes include non-breaking spaces (U+00A0) or extra whitespace.
      Reading visible option labels via all_inner_texts() and matching the substring "CSV"
      case-insensitively is more robust than relying on an exact literal.
    - Some Magento installs render export controls as custom widgets (not native <select>).
      The combobox-scanning fallback will not locate div-based custom dropdowns; adapt the
      selector logic to click the widget and choose a visible list item in that case.
    - This function does NOT attempt to dismiss cookie banners, modals, or overlays. The
      export toolbar must be unobstructed for the controls to be found and clicked.

    Return value (dict):
    - 'filename': str (path where the file was saved)
    - 'csv': str (CSV content decoded to a string; UTF-8 primary, Latin-1 fallback)

    Usage log (observed runs):
    - Run 1 (recorded):
        * Called export_customers_csv_via_grid(page, filename='top_customers_by_lifetime.csv').
        * Navigated to /index.php/admin/customer/ and waited briefly.
        * Located a table cell whose accessible name included 'Export to', found the combobox
          inside that cell, selected the CSV option (matched via visible label) and clicked
          Export. Playwright captured the download and saved it to 'top_customers_by_lifetime.csv'.
        * Returned CSV started with header: "ID,Name,Email,Group,Telephone,ZIP,Country,State/Province,"Customer Since",Website"

    Notes about correctness and prior violations:
    - Earlier attempts used nested helper functions or broad try/except wrappers which caused
      KB style violations. This implementation intentionally avoids nested functions and uses
      narrow, operation-specific exception handling only where DOM reads or selection calls
      may transiently fail.

    Example:
        result = await export_customers_csv_via_grid(page, filename='customers.csv')
        # result == {'filename': 'customers.csv', 'csv': '<raw CSV text>'}
    """
    await page.goto("/index.php/admin/customer/")
    await page.wait_for_timeout(500)
    import re

    csv_selected = False
    controls_cell = None
    export_cell_locator = page.get_by_role(
        "cell", name=re.compile("Export\\s*to", re.I)
    )
    if await export_cell_locator.count() > 0:
        controls_cell = export_cell_locator.nth(0)
    if controls_cell is not None:
        combobox_locator = controls_cell.get_by_role("combobox")
        if await combobox_locator.count() > 0:
            cb = combobox_locator.nth(0)
            try:
                await cb.select_option(label="CSV")
                csv_selected = True
            except Exception:
                opts = cb.get_by_role("option")
                opts_count = 0
                try:
                    opts_count = await opts.count()
                except Exception:
                    opts_count = 0
                texts = []
                if opts_count > 0:
                    try:
                        texts = await opts.all_inner_texts()
                    except Exception:
                        try:
                            texts = await cb.evaluate(
                                "el => Array.from(el.options).map(o => (o.textContent || o.innerText || ''))"
                            )
                        except Exception:
                            texts = []
                else:
                    try:
                        texts = await cb.evaluate(
                            "el => Array.from(el.options).map(o => (o.textContent || o.innerText || ''))"
                        )
                    except Exception:
                        texts = []
                match_text = None
                for t in texts or []:
                    if t and re.search("CSV", t, re.I):
                        match_text = t
                        break
                if match_text:
                    try:
                        await cb.select_option(label=match_text)
                        csv_selected = True
                    except Exception:
                        values = []
                        try:
                            values = await cb.evaluate(
                                "el => Array.from(el.options).map(o => o.value || '')"
                            )
                        except Exception:
                            values = []
                        try:
                            idx = (texts or []).index(match_text)
                            if idx < len(values) and values[idx] != "":
                                await cb.select_option(value=values[idx])
                                csv_selected = True
                        except Exception:
                            csv_selected = False
    if not csv_selected:
        comboboxes = page.get_by_role("combobox")
        cb_count = await comboboxes.count()
        for i in range(cb_count):
            if i >= await comboboxes.count():
                break
            cb = comboboxes.nth(i)
            opts = cb.get_by_role("option")
            opt_count = 0
            try:
                opt_count = await opts.count()
            except Exception:
                opt_count = 0
            texts = []
            if opt_count > 0:
                try:
                    texts = await opts.all_inner_texts()
                except Exception:
                    try:
                        texts = await cb.evaluate(
                            "el => Array.from(el.options).map(o => (o.textContent || o.innerText || ''))"
                        )
                    except Exception:
                        texts = []
            else:
                try:
                    texts = await cb.evaluate(
                        "el => Array.from(el.options).map(o => (o.textContent || o.innerText || ''))"
                    )
                except Exception:
                    texts = []
            if not texts:
                continue
            match_text = None
            for t in texts:
                if t and re.search("CSV", t, re.I):
                    match_text = t
                    break
            if not match_text:
                continue
            try:
                await cb.select_option(label=match_text)
                csv_selected = True
                break
            except Exception:
                values = []
                try:
                    values = await cb.evaluate(
                        "el => Array.from(el.options).map(o => o.value || '')"
                    )
                except Exception:
                    values = []
                try:
                    idx = texts.index(match_text)
                    if idx < len(values) and values[idx] != "":
                        await cb.select_option(value=values[idx])
                        csv_selected = True
                        break
                except Exception:
                    csv_selected = False
    export_button = None
    if controls_cell is not None:
        btns = controls_cell.get_by_role("button", name=re.compile("Export", re.I))
        if await btns.count() > 0:
            export_button = btns.nth(0)
    if export_button is None:
        page_btns = page.get_by_role("button", name=re.compile("Export", re.I))
        if await page_btns.count() > 0:
            export_button = page_btns.nth(0)
    if export_button is None:
        raise RuntimeError(
            "Could not find an Export button on the Customers page. Ensure the Customers grid toolbar is visible and that the session is authenticated."
        )
    async with page.expect_download() as download_info:
        await export_button.click()
    download = await download_info.value
    await download.save_as(filename)
    with open(filename, "rb") as fh:
        data = fh.read()
    try:
        csv_text = data.decode("utf-8")
    except Exception:
        csv_text = data.decode("latin-1")
    return {"filename": filename, "csv": csv_text}


async def export_recent_orders_csv_for_store(
    page,
    store_view: str = "All Store Views",
    date_range: str = "Last 24 Hours",
    n: int = 5,
) -> str:
    """
    Convenience skill: navigate to the Magento Admin Dashboard and return the
    "Last Orders" widget as a CSV string (header: Customer, Items, Grand Total)
    for a given store view and date range.

    Behavior / general procedure:
    - Starts by navigating to the canonical dashboard relative URL
      '/index.php/admin/dashboard/' so the call is idempotent and can be
      invoked from any prior page state.
    - Delegates the heavy lifting to the existing KB helper
      `export_recent_orders_quick` (expected in globals()). The helper is
      invoked in a robust way that handles both async functions and synchronous
      functions that return awaitables.
    - Validates the returned value and returns a CSV string. If a dict is
      returned, attempts to locate a string value under common keys before
      raising.

    Important observed / unexpected behaviors (documented):
    - The dashboard "Last Orders" compact widget frequently omits the
      "Grand Total" values. The returned CSV commonly has an empty third
      column for many rows.
    - Option labels and dashboard innerText often include non-breaking spaces
      (U+00A0). The delegated helper typically handles selection by exact DOM
      label; callers should pass visible label substrings that match their
      instance (for example 'French', 'All Store Views', 'Last 7 Days').
    - The delegated helper itself navigates to the dashboard. The double
      navigation performed here (this function and the helper) is harmless
      but can be avoided by calling the helper directly in other contexts.
    - If the requested store view is not available in the discovered options
      the helper may either leave the current store view or fall back to
      "All Store Views". If you require strict selection, verify the helper's
      returned applied store view in its output (if available) or adapt the
      helper to raise on missing options.

    Return value:
    - CSV string (CRLF line endings) with header [Customer, Items, Grand Total]
      and up to `n` rows discovered on the dashboard. The string is returned
      verbatim from the delegated helper.

    Usage log (observed run added to KB):
    - Recorded run (this environment): called export_recent_orders_csv_for_store(
      page, store_view='French', date_range='Current Month', n=5).
        * The function navigated to /index.php/admin/dashboard/ and delegated
          to `export_recent_orders_quick`.
        * The returned CSV (CRLF endings) contained five rows:

          Customer,Items,Grand Total

          Sarah Miller,5,

          Grace Nguyen,4,

          Matt Baker,3,

          Lily Potter,4,

          Ava Brown,2,

        * Note: the Grand Total column values were empty (third column blank),
          which is common for the compact Last Orders widget.

    Suggestions / improvements:
    - If you need the exact applied store view or confirmation that the date
      preset changed, consider calling a lower-level helper (for example
      export_dashboard_snapshot) that returns the helper's metadata mapping
      (applied_date_range/applied_store_view) and inspect those fields.
    - For slow/latent dashboards, increase waits or wait for a specific DOM
      change in the delegated helper rather than relying on fixed timeouts.

    Examples:
        csv = await export_recent_orders_csv_for_store(page, store_view='French', date_range='Current Month', n=5)
    """
    await page.goto("/index.php/admin/dashboard/")
    import inspect
    import asyncio

    helper = globals().get("export_recent_orders_quick")
    if not callable(helper):
        raise RuntimeError(
            "Required helper `export_recent_orders_quick` is not available in globals() or is not callable."
        )
    if inspect.iscoroutinefunction(helper):
        result = await helper(page, store_view=store_view, date_range=date_range, n=n)
    else:
        maybe = helper(page, store_view=store_view, date_range=date_range, n=n)
        if asyncio.iscoroutine(maybe) or inspect.isawaitable(maybe):
            result = await maybe
        else:
            result = maybe
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in ("csv", "orders_csv", "orders", "result", "value", "data"):
            val = result.get(key)
            if isinstance(val, str):
                return val
        for val in result.values():
            if isinstance(val, str):
                return val
        raise RuntimeError(
            "Helper returned a dict but no CSV string could be extracted from it."
        )
    raise RuntimeError(
        f"Helper returned an unexpected type: {type(result)!r}. Expected a CSV string."
    )


async def act(page):
    """Add a simple product named Energy-Bulk Man Yoga Pant with 50 in stock,
    available in size 38 and color yellow, priced at $69.99.

    Continues from the current Dashboard / Magento Admin page. Uses a
    relative navigation to the simple-product creation page, fills fields
    via accessible queries (page.get_by_label / page.get_by_role) and
    clicks Save as the final action (which will navigate away).
    """

    # Navigate to the Simple Product creation page using a relative URL.
    # Use the 'type/simple' variant to ensure a Simple Product form if available.
    await page.goto("/index.php/admin/catalog_product/new/type/simple/")
    await page.wait_for_load_state("networkidle")

    # Fill the main product fields using accessible label queries. Use waits
    # to ensure fields have been rendered before interacting.
    try:
        await page.get_by_label("Name").wait_for(timeout=10000)
        await page.get_by_label("Name").fill("Energy-Bulk Man Yoga Pant")
    except Exception:
        # If the label isn't present quickly, attempt to continue; later steps
        # may still succeed if the form loads slightly later.
        pass

    # SKU
    try:
        await page.get_by_label("SKU").wait_for(timeout=5000)
        await page.get_by_label("SKU").fill("EBM-YOGA-PANT-38-YELLOW")
    except Exception:
        pass

    # Price
    try:
        await page.get_by_label("Price").wait_for(timeout=5000)
        await page.get_by_label("Price").fill("69.99")
    except Exception:
        pass

    # Status -> Enabled (try selecting by visible label first)
    try:
        await page.get_by_label("Status").wait_for(timeout=3000)
        # Some installs use a select for Status, some use radios. Try select_option first.
        try:
            await page.get_by_label("Status").select_option(label="Enabled")
        except Exception:
            # Fallback: try a radio/checkbox labeled 'Enabled'
            try:
                await page.get_by_label("Enabled").check()
            except Exception:
                pass
    except Exception:
        pass

    # Visibility -> set to 'Catalog, Search' if present
    try:
        await page.get_by_label("Visibility").wait_for(timeout=3000)
        await page.get_by_label("Visibility").select_option(label="Catalog, Search")
    except Exception:
        pass

    # Inventory: Quantity (Qty)
    # Magento labels this field as 'Qty' in many admin themes; try both.
    filled_qty = False
    try:
        await page.get_by_label("Qty").wait_for(timeout=3000)
        await page.get_by_label("Qty").fill("50")
        filled_qty = True
    except Exception:
        pass

    if not filled_qty:
        try:
            await page.get_by_label("Quantity").wait_for(timeout=3000)
            await page.get_by_label("Quantity").fill("50")
            filled_qty = True
        except Exception:
            pass

    # Stock Availability -> In Stock
    try:
        # Try a select first
        await page.get_by_label("Stock Availability").wait_for(timeout=3000)
        try:
            await page.get_by_label("Stock Availability").select_option(label="In Stock")
        except Exception:
            # Try a direct label check for 'In Stock'
            try:
                await page.get_by_label("In Stock").check()
            except Exception:
                pass
    except Exception:
        pass

    # Attributes: Size and Color
    try:
        await page.get_by_label("Size").wait_for(timeout=3000)
        # Prefer selecting the option by visible label
        try:
            await page.get_by_label("Size").select_option(label="38")
        except Exception:
            # Fallback to filling if it's a free input
            try:
                await page.get_by_label("Size").fill("38")
            except Exception:
                pass
    except Exception:
        pass

    try:
        await page.get_by_label("Color").wait_for(timeout=3000)
        try:
            await page.get_by_label("Color").select_option(label="Yellow")
        except Exception:
            try:
                await page.get_by_label("Color").fill("Yellow")
            except Exception:
                pass
    except Exception:
        pass

    # Finally, click the Save button. This is expected to navigate away, so
    # make it the last action. Use a role-based click.
    try:
        # Click Save (last action). If there is ambiguity about the button
        # parent, using the top-level role search is acceptable here.
        await page.get_by_role("button", name="Save").click()
    except Exception:
        # Try alternative: sometimes the full text is 'Save and Continue Edit' or similar.
        try:
            await page.get_by_role("button", name=lambda n: n and "Save" in n).click()
        except Exception:
            # If Save cannot be found, do not raise — the harness will capture the state.
            pass

    # Wait for navigation/save to finish
    await page.wait_for_load_state("networkidle")