from browsergym.core.action.functions import *

import playwright.sync_api
page: playwright.sync_api.Page = None


def navigate_to_all_reviews():
    """Navigate to the All Reviews page from the admin dashboard.
    
    Examples:
        navigate_to_all_reviews()
    """
    hover('113')  # Hover over Catalog menu
    hover('139')  # Hover over Reviews and Ratings
    click('143')  # Click on Reviews and Ratings submenu
    click('150')  # Click on All Reviews

def filter_reviews_by_term(filter_field_id: str, search_term: str, search_button_id: str):
    """Filter reviews by searching for a specific term in the review text.
    
    Args:
        filter_field_id: The ID of the review filter input field
        search_term: The term to search for in reviews
        search_button_id: The ID of the search/filter button
        
    Examples:
        filter_reviews_by_term('621', 'satisfied', '474')
        filter_reviews_by_term('621', 'excellent', '474')
    """
    fill(filter_field_id, search_term)  # Enter search term in review filter
    click(search_button_id)  # Click search button to apply filter

def navigate_to_manage_products():
    """Navigate from homepage to the Manage Products page in the Catalog menu.
    
    Examples:
        navigate_to_manage_products()
    """
    click('113')  # Click on Catalog menu
    click('117')  # Click on Manage Products option

def filter_products_by_quantity(qty_from_id: str, qty_to_id: str, quantity: str, search_button_id: str):
    """Filter products by a specific quantity range.
    
    Args:
        qty_from_id: The ID of the "From" quantity field
        qty_to_id: The ID of the "To" quantity field
        quantity: The quantity value to filter by
        search_button_id: The ID of the search button
        
    Examples:
        filter_products_by_quantity('656', '659', '3', '485')
        filter_products_by_quantity('656', '659', '5', '485')
    """
    fill(qty_from_id, quantity)  # Fill "From" quantity field
    fill(qty_to_id, quantity)  # Fill "To" quantity field
    click(search_button_id)  # Click Search button
    noop(2000)  # Wait for results to load

def navigate_to_reviews():
    """Navigate from homepage to the All Reviews page.
    
    Examples:
        navigate_to_reviews()
    """
    hover('113')  # Hover over Catalog menu
    hover('139')  # Hover over Reviews and Ratings
    click('143')  # Click Reviews and Ratings
    click('150')  # Click All Reviews

def search_reviews_by_term(search_field_id: str, search_button_id: str, term: str):
    """Search for reviews containing a specific term.
    
    Args:
        search_field_id: The ID of the review search/filter field
        search_button_id: The ID of the search button
        term: The search term to filter reviews by
        
    Examples:
        search_reviews_by_term('621', '474', 'disappointed')
        search_reviews_by_term('621', '474', 'excellent')
    """
    fill(search_field_id, term)  # Fill the search field with the term
    click(search_button_id)  # Click the Search button

def navigate_to_orders():
    """Navigate to the Orders page from the admin panel.
    
    Examples:
        navigate_to_orders()
    """
    hover('66')  # Hover over Sales menu
    click('70')  # Click Orders option

def filter_orders_by_status(status_filter_id: str, status: str):
    """Filter orders by a specific status.
    
    Args:
        status_filter_id: The ID of the status filter dropdown
        status: The order status to filter by (e.g., 'Pending', 'Complete')
        
    Examples:
        filter_orders_by_status('638', 'Pending')
        filter_orders_by_status('638', 'Complete')
    """
    click(status_filter_id)  # Click status filter dropdown
    select_option(status_filter_id, status)  # Select the desired status
    click('483')  # Click Search button to apply filter
    noop(3000)  # Wait for results to load

def filter_reviews_by_date_range(from_date_id: str, to_date_id: str, search_button_id: str, start_date: str, end_date: str):
    """Filter reviews by a specific date range.
    
    Args:
        from_date_id: The ID of the "From" date field
        to_date_id: The ID of the "To" date field
        search_button_id: The ID of the search button
        start_date: Start date in MM/DD/YYYY format
        end_date: End date in MM/DD/YYYY format
        
    Returns:
        None
        
    Examples:
        filter_reviews_by_date_range('599', '603', '474', '05/01/2023', '05/31/2023')
        filter_reviews_by_date_range('599', '603', '474', '01/01/2024', '01/31/2024')
    """
    click(from_date_id)
    fill(from_date_id, start_date)
    click(to_date_id)
    fill(to_date_id, end_date)
    click(search_button_id)

def set_product_stock_status(inventory_id: str, dropdown_id: str, status: str):
    """Set the stock status of a product in inventory management.
    
    Args:
        inventory_id: The ID of the Inventory navigation link
        dropdown_id: The ID of the Stock Availability dropdown
        status: The stock status to set (e.g., 'Out of Stock', 'In Stock')
        
    Examples:
        set_product_stock_status('508', '1646', 'Out of Stock')
        set_product_stock_status('508', '1646', 'In Stock')
    """
    click(inventory_id)  # Navigate to Inventory
    click(dropdown_id)  # Open Stock Availability dropdown
    select_option(dropdown_id, status)  # Select the desired stock status

def navigate_to_cms_pages(content_id: str, cms_menu_id: str):
    """Navigate to the CMS Pages management section.
    
    Args:
        content_id: The ID of the Content menu item
        cms_menu_id: The ID of the CMS submenu item
        
    Examples:
        navigate_to_cms_pages('198', '202')
    """
    click(content_id)  # Click Content menu
    click(cms_menu_id)  # Click CMS to open Pages section

def update_page_title(title_field_id: str, new_title: str, save_button_id: str):
    """Update the page title and save the changes.
    
    Args:
        title_field_id: The ID of the page title input field
        new_title: The new title text to set
        save_button_id: The ID of the save button
        
    Examples:
        update_page_title('529', 'New Title', '500')
    """
    click(title_field_id)  # Click on the page title field
    keyboard_press('ControlOrMeta+a')  # Select all existing text
    fill(title_field_id, new_title)  # Fill in the new title
    click(save_button_id)  # Click save button

def set_stock_availability(inventory_id: str, availability_dropdown_id: str, status: str):
    """Set the stock availability status for a product.
    
    Args:
        inventory_id: The ID of the Inventory section/link
        availability_dropdown_id: The ID of the Stock Availability dropdown
        status: The desired stock status (e.g., 'Out of Stock', 'In Stock')
        
    Returns:
        None
        
    Examples:
        set_stock_availability('508', '1646', 'Out of Stock')
        set_stock_availability('508', '1646', 'In Stock')
    """
    click(inventory_id)  # Click on Inventory section
    click(availability_dropdown_id)  # Click Stock Availability dropdown
    select_option(availability_dropdown_id, status)  # Select the desired stock status