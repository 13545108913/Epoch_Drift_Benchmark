
import asyncio

from browser import BrowserUse

browser = BrowserUse()

browser_axtree_wrapper = "<webpage accessibility tree>\n{axtree}\n</webpage accessibility tree>"
browser_state_wrapper = "<webpage interactive elements>\n{state}\n</webpage interactive elements>"
tool_result_prompt = "Performed browser action: {tool_result}\nThe updated browser page status is as follows:\n" + browser_axtree_wrapper + "\n" + browser_state_wrapper + "\n"

async def _get_browser_observation(wait_seconds: int=1):
    await asyncio.sleep(wait_seconds)
    axtree = await browser.get_axtree()
    state = await browser.get_browser_state()
    return axtree, state

async def browser_extract_content_by_vision(query: str):
    """
    Following the instructions, use the Visual Language model to extract the specified content from the browser page screenshot.
    Note:
        The VL model is subject to error. You should primarily use the `accessibility tree` and `interactive elements` returned by each browser tool to understand the browser state.
        This visual tool is intended only as a last resort.

    Args:
        query: Query to the VL model to get the browser page content.
    """
    await browser.get_browser_state()
    result = await browser.extract_content_by_vision(query)
    axtree, state = await _get_browser_observation()
    yield {
        "data": tool_result_prompt.format(axtree=axtree, state=state, tool_result=str(result)),
        "instruction": ""
    }

async def browser_go_to_url( url: str, new_tab: bool = False):
    """
    Use the browser to navigate to the specified URL, and support opening it in a new tab.

    Args:
        url: The URL of the target website.
        new_tab: Whether to open in a new tab (default False).
    """
    result = await browser.go_to_url(url, new_tab=new_tab)
    axtree, state = await _get_browser_observation()

    yield {
        "data": tool_result_prompt.format(axtree=axtree, state=state, tool_result=str(result)),
        "instruction": ""
    }

async def browser_click(index: int):
    """
    In the current page of the browser, click the interactive element according to the element index

    Args:
        index: The index number of the target element.
    """
    result = await browser.click_element_by_index(index)
    axtree, state = await _get_browser_observation(2)

    yield {
        "data": tool_result_prompt.format(axtree=axtree, state=state, tool_result=str(result)),
        "instruction": ""
    }

async def browser_wait_and_get_update(seconds: int = 3):
    """
    Wait for a set amount of time, then retrieve the latest browser accessibility tree and interactive elements.
    Note: You can set a very short wait time (1 second) to immediately retrieve the current browser accessibility tree and interactive elements.

    In addition, after running this tool, a local archive of the latest browser accessibility tree and interactive elements will be saved locally in the directory `workspace/latest_browser_status.txt`.
    You can use it for analysis if necessary.
    The file content format is:
    `Browser action result: ... \n<webpage accessibility tree>\n ... \n</webpage accessibility tree>\n<webpage interactive elements>\n ... \n</webpage interactive elements>`

    Args:
        seconds: The number of seconds to wait, the default is 3 seconds.
    """
    result = await browser.wait(seconds)
    axtree, state = await _get_browser_observation()
    browser_status_text = tool_result_prompt.format(axtree=axtree, state=state, tool_result=str(result))
    with open("workspace/latest_browser_status.txt", "w") as f:
        f.write(browser_status_text)

    yield {
        "data": browser_status_text,
        "instruction": ""
    }

async def browser_input_text(index: int, text: str):
    """
    Enter text into the specified element in the current browser tab.

    Args:
        index: The index number of the target element.
        text: The text to be entered.
    """
    result = await browser.input_text(index, text)
    axtree, state = await _get_browser_observation()

    yield {
        "data": tool_result_prompt.format(axtree=axtree, state=state, tool_result=str(result)),
        "instruction": ""
    }

async def browser_send_keys(keys: str):
    """
    Sends a keyboard shortcut/keystroke to the currently displayed browser tab.

    Args:
        keys: The key to sent, such as "Enter", "Control+A", etc.
    """
    result = await browser.send_keys(keys)
    axtree, state = await _get_browser_observation()

    yield {
        "data": tool_result_prompt.format(axtree=axtree, state=state, tool_result=str(result)),
        "instruction": ""
    }

async def browser_go_back():
    """
    Trigger "back" of the current browser tab.
    """
    result = await browser.go_back()
    axtree, state = await _get_browser_observation()

    yield {
        "data": tool_result_prompt.format(axtree=axtree, state=state, tool_result=str(result)),
        "instruction": ""
    }

async def browser_scroll(down: bool=True, num_pages: float=0.5, index: int=None):
    """
    Scroll the page by specified number of pages.
    Optional index parameter to scroll within a specific element or its scroll container (works well for dropdowns and custom UI components).

    Args:
        down: True to scroll down, False to scroll up
        num_pages: Number of pages to scroll (0.5 = half page, 1.0 = one page, etc.)
        index: Optional element index to find scroll container for
    """
    result = await browser.scroll(down, num_pages, index)
    axtree, state = await _get_browser_observation()

    yield {
        "data": tool_result_prompt.format(axtree=axtree, state=state, tool_result=str(result)),
        "instruction": ""
    }

async def browser_list_tabs():
    """
    Get a list of all currently open tabs in the browser.
    """
    result = await browser.list_tabs()
    axtree, state = await _get_browser_observation()

    yield {
        "data": tool_result_prompt.format(axtree=axtree, state=state, tool_result=str(result)),
        "instruction": ""
    }

async def browser_switch_tab(tab_index: int):
    """
    Switch to the tab of the specified index in the browser

    Args:
        tab_index: The index number of the target tab.
    """
    result = await browser.switch_tab(tab_index)
    axtree, state = await _get_browser_observation()

    yield {
        "data": tool_result_prompt.format(axtree=axtree, state=state, tool_result=str(result)),
        "instruction": ""
    }

async def browser_close_tab(tab_index: int):
    """
    Close the tab with the specified index in the browser.

    Args:
        tab_index: The index number of the target tab.
    """
    result = await browser.close_tab(tab_index)
    axtree, state = await _get_browser_observation()

    yield {
        "data": tool_result_prompt.format(axtree=axtree, state=state, tool_result=str(result)),
        "instruction": ""
    }