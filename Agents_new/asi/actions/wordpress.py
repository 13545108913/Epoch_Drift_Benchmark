from browsergym.core.action.functions import *

import playwright.sync_api
page: playwright.sync_api.Page = None


def search_keyword(search_icon_id: str, search_bar_id: str, search_button_id: str, keyword: str):
    """Search for a keyword using the site search bar.
    
    Args:
        search_icon_id: The ID of the search icon to open the search bar
        search_bar_id: The ID of the search input field
        search_button_id: The ID of the search button
        keyword: The keyword to search for
        
    Returns:
        None
        
    Examples:
        search_keyword('61', '67', '68', 'Tracing')
        search_keyword('25', '30', '32', 'Machine Learning')
    """
    click(search_icon_id)  # Click the search icon to open the search bar
    fill(search_bar_id, keyword)  # Fill the search bar with the keyword
    click(search_button_id)  # Click the Search button to execute the search

def scroll_to_bottom_post():
    """Scroll down the homepage to locate the bottom-most post.
    
    Returns:
        None. The page will be scrolled to show the bottom post.
        
    Examples:
        scroll_to_bottom_post()
    """
    scroll(0, 500)  # Initial scroll to start viewing lower posts
    scroll(0, 800)  # Continue scrolling toward bottom
    scroll(0, 800)  # Further scroll to reach bottom area
    scroll(0, 800)  # Final scroll to ensure bottom post is visible

def search_article(search_icon_id: str, search_bar_id: str, search_button_id: str, search_query: str):
    """Search for an article using the search functionality.
    
    Args:
        search_icon_id: The ID of the search icon to open search
        search_bar_id: The ID of the search input field
        search_button_id: The ID of the search submit button
        search_query: The search query string to find the article
        
    Examples:
        search_article('61', '67', '68', 'Jimmy Kimmel Trump alternative Christmas message UK')
        search_article('45', '50', '52', 'climate change report 2024')
    """
    click(search_icon_id)  # Open the search functionality
    fill(search_bar_id, search_query)  # Fill the search bar with the query
    click(search_button_id)  # Execute the search

def open_and_search(search_icon_id: str | int, search_input_id: str | int, search_button_id: str | int, query: str):
    """Open the search bar by clicking the search icon, fill in the search query, and submit the search.

    Args:
        search_icon_id: The ID of the search icon element to click to open the search bar.
        search_input_id: The ID of the search input field to type the query into.
        search_button_id: The ID of the search submit button to execute the search.
        query: The search query string to enter into the search input field.

    Returns:
        None. Navigates the page to the search results for the given query.

    Examples:
        open_and_search('61', '67', '68', 'Treating your agents like microservices')
        open_and_search('42', '55', '56', 'Introduction to machine learning')
    """
    click(search_icon_id)          # Click the search icon to open the search bar
    fill(search_input_id, query)   # Fill the search input with the query
    click(search_button_id)        # Click the search button to execute the search

def open_and_search(search_icon_id: str | int, search_input_id: str | int, search_button_id: str | int, query: str):
    """Open the search bar by clicking the search icon, fill in the search query, and submit the search.

    Args:
        search_icon_id: The ID of the search icon element to click to open the search bar.
        search_input_id: The ID of the search input field to type the query into.
        search_button_id: The ID of the search submit button to execute the search.
        query: The search query string to enter into the search input field.

    Returns:
        None. Navigates the page to the search results for the given query.

    Examples:
        open_and_search('61', '67', '68', 'Treating your agents like microservices')
        open_and_search('42', '55', '56', 'Introduction to machine learning')
    """
    click(search_icon_id)          # Click the search icon to open the search bar
    fill(search_input_id, query)   # Fill the search input with the query
    click(search_button_id)        # Click the search button to execute the search

def search_for_post(search_icon_id: str, search_input_id: str, search_button_id: str, post_title: str):
    """Search for a blog post by title.
    
    Args:
        search_icon_id: The ID of the search icon to click
        search_input_id: The ID of the search input field
        search_button_id: The ID of the search button
        post_title: The title of the post to search for
        
    Examples:
        search_for_post('61', '67', '68', 'JavaScript SpeechSynthesis API')
    """
    click(search_icon_id)
    fill(search_input_id, post_title)
    click(search_button_id)

def submit_comment(comment_field_id: str, name_field_id: str, email_field_id: str, submit_button_id: str, comment_text: str):
    """Fill and submit a blog comment form.
    
    Args:
        comment_field_id: The ID of the comment text field
        name_field_id: The ID of the name field
        email_field_id: The ID of the email field
        submit_button_id: The ID of the submit button
        comment_text: The comment text to post
        
    Examples:
        submit_comment('177', '181', '185', '193', 'Thanks, this solved my problem.')
    """
    fill(comment_field_id, comment_text)
    fill(name_field_id, 'John Doe')
    fill(email_field_id, 'johndoe@example.com')
    click(submit_button_id)

def search_for_term(search_icon_id: str, search_bar_id: str, search_button_id: str, search_term: str):
    """Search for a term using the search functionality.
    
    Args:
        search_icon_id: The ID of the search icon to activate search
        search_bar_id: The ID of the search input field
        search_button_id: The ID of the search button
        search_term: The term to search for
        
    Returns:
        None
        
    Examples:
        search_for_term('61', '67', '68', 'volunteer')
        search_for_term('61', '67', '68', 'technology')
    """
    click(search_icon_id)  # Click the search icon
    fill(search_bar_id, search_term)  # Fill the search bar with the search term
    click(search_button_id)  # Click the search button to execute search

def search_article(search_icon_id: str, search_input_id: str, search_button_id: str, article_title: str):
    """Search for an article by title using the search functionality.
    
    Args:
        search_icon_id: The ID of the search icon to open the search bar
        search_input_id: The ID of the search input field
        search_button_id: The ID of the search button
        article_title: The title of the article to search for
        
    Examples:
        search_article('61', '67', '68', 'Disrupting yourself in the age of AI')
    """
    click(search_icon_id)  # Open the search bar
    fill(search_input_id, article_title)  # Fill in the article title
    click(search_button_id)  # Execute the search

def scroll_through_article(num_scrolls: int, scroll_distance: int = 500):
    """Scroll through an article to view all content.
    
    Args:
        num_scrolls: Number of times to scroll down
        scroll_distance: Distance to scroll each time (default 500)
        
    Examples:
        scroll_through_article(4, 500)
    """
    for _ in range(num_scrolls):
        scroll(0, scroll_distance)