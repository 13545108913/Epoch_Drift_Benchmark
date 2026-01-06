from browsergym.core.action.functions import *

import playwright.sync_api
page: playwright.sync_api.Page = None



def go_to_review_list(page_url: str, open_button_id: str):
    """Navigate to the admin reviews list page.

    Args:
        page_url: The URL of the admin reviews listing page.
        open_button_id: The element ID to click to open or focus the reviews list.

    Returns:
        None

    Examples:
        go_to_review_list("http://dockerized-magento.local/index.php/admin/catalog_product_review/", "150")
    """
    goto(page_url)
    scroll(0, 800)
    click(open_button_id)

def filter_reviews_by_status(select_id: str, status_value: str, apply_button_id: str, result_scroll: int = 2000):
    """Select a review status from a dropdown and apply the filter.

    Args:
        select_id: The ID of the status select element.
        status_value: The visible label or option value to select (e.g., "Approved").
        apply_button_id: The ID of the button that applies the filter.
        result_scroll: Vertical scroll offset to ensure results load (default 2000).

    Returns:
        None

    Examples:
        filter_reviews_by_status("608", "Approved", "474")
    """
    select_option(select_id, status_value)
    click(apply_button_id)
    scroll(0, result_scroll)

def navigate_to_admin_orders(admin_orders_url: str):
    """Open the admin orders page and ensure the page is positioned for interaction.

    Args:
        admin_orders_url: The full URL of the admin orders listing page.

    Returns:
        None

    Examples:
        navigate_to_admin_orders("http://dockerized-magento.local/index.php/admin/sales_order/")
    """
    goto(admin_orders_url)
    scroll(0, 500)
    scroll(0, 300)


def filter_orders_by_status(status_select_id: str | int, status_value: str, filter_button_id: str | int):
    """Apply a status filter on the orders listing.

    Args:
        status_select_id: The element id of the status dropdown/select.
        status_value: The visible value to select (e.g., "Canceled").
        filter_button_id: The element id of the button to apply the filter.

    Returns:
        None

    Examples:
        filter_orders_by_status("638", "Canceled", "483")
    """
    select_option(status_select_id, status_value)
    click(filter_button_id)
    scroll(0, 200)


def open_order_link(order_link_id: str | int):
    """Open an order details page from the orders listing.

    Args:
        order_link_id: The element id corresponding to the order link (e.g., most recent order link).

    Returns:
        None

    Examples:
        open_order_link("70")
    """
    click(order_link_id)
    scroll(0, 300)
    scroll(0, 100)

def search_customer_by_phone(search_field_id: str | int, phone_number: str):
    """Search for a customer using the phone number via the search field.

    Args:
        search_field_id: The ID of the phone search input element (string or int).
        phone_number: The phone number to search for (string).

    Returns:
        bool: True if the search actions were performed.

    Examples:
        search_customer_by_phone('56', '8015551212')
    """
    click(search_field_id)               # focus the search field
    fill(search_field_id, phone_number)  # enter the phone number
    keyboard_press("Enter")              # submit the search
    return True

def open_customer_profile(result_ids: list, goto_url: str | None = None):
    """Open a customer profile from search results by interacting with provided result element IDs.

    This performs scrolling and repeated clicks on the primary result element to ensure the profile page opens.

    Args:
        result_ids: A list of element IDs (strings or ints); the first ID is used as the primary result to click.
        goto_url: Optional URL to navigate to after interacting with results.

    Returns:
        str | int: The ID of the primary result element that was clicked.

    Examples:
        open_customer_profile(['163'])
        open_customer_profile(['163'], goto_url='http://example.local/admin/customer/')
    """
    primary_id = result_ids[0]
    scroll(0, 500)   # bring results into view
    click(primary_id) 
    scroll(0, 800)   # ensure any dynamic content is loaded
    click(primary_id) 
    if goto_url:
        goto(goto_url)
    return primary_id

def search_field_enter(search_field_id: str | int, query: str):
    """Enter a query into a search field and submit it.

    Args:
        search_field_id: ID of the search input element to interact with.
        query: The text to type into the search field.

    Returns:
        None

    Examples:
        search_field_enter('56', '+1 5551234567')
    """
    click(search_field_id)
    fill(search_field_id, query)
    keyboard_press("Enter")


def open_search_result(result_id: str | int, pre_scroll: int, post_scroll: int):
    """Scroll to a region, open a search result, and adjust view afterwards.

    Args:
        result_id: ID of the clickable result element.
        pre_scroll: Vertical pixels to scroll before clicking the result.
        post_scroll: Vertical pixels to scroll after clicking the result.

    Returns:
        None

    Examples:
        open_search_result('163', 500, 800)
    """
    scroll(0, pre_scroll)
    click(result_id)
    scroll(0, post_scroll)


def goto_and_search_admin(admin_url: str, admin_search_field_id: str | int, search_button_id: str | int, phone_number: str):
    """Navigate to the admin customer page, enter a phone number, and trigger the search.

    Args:
        admin_url: URL of the admin customer listing page.
        admin_search_field_id: ID of the admin page's phone/search input.
        search_button_id: ID of the admin page's search/submit button.
        phone_number: Phone number to search for.

    Returns:
        None

    Examples:
        goto_and_search_admin("http://example.local/admin/customer/", '627', '481', '+1 5551234567')
    """
    goto(admin_url)
    fill(admin_search_field_id, phone_number)
    click(search_button_id)

def open_admin_reviews(admin_link_id: str | int, reviews_url: str, focus_field_id: str | int):
    """Navigate to the admin Reviews page and focus the date field.

    Args:
        admin_link_id: ID of the admin navigation element to click (e.g., "150").
        reviews_url: URL of the admin reviews page.
        focus_field_id: ID of a field on the reviews page to focus/click (e.g., start date field).

    Returns:
        None

    Examples:
        open_admin_reviews('150', 'http://dockerized-magento.local/index.php/admin/catalog_product_review/', '602')
    """
    click(admin_link_id)
    goto(reviews_url)
    click(focus_field_id)


def filter_reviews_by_date(start_field_id: str | int, end_field_id: str | int, start_date: str, end_date: str, filter_button_id: str | int):
    """Fill a date range in the reviews filters and apply the filter.

    Args:
        start_field_id: ID of the start date input field.
        end_field_id: ID of the end date input field.
        start_date: Start date string in the required format (e.g., "05/01/2023").
        end_date: End date string in the required format (e.g., "05/31/2023").
        filter_button_id: ID of the button to apply the filter.

    Returns:
        None

    Examples:
        filter_reviews_by_date('602', '606', '05/01/2023', '05/31/2023', '477')
    """
    fill(start_field_id, start_date)
    fill(end_field_id, end_date)
    click(filter_button_id)