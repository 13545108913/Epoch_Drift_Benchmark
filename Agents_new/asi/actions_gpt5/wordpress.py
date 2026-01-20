from browsergym.core.action.functions import *

import playwright.sync_api
page: playwright.sync_api.Page = None


def search_and_open_article(search_field_id: str | int, search_button_id: str | int, title: str, article_link_id: str | int):
    """Search for an article by title and open the specified result link.

    Args:
        search_field_id: ID of the search input element (str or int).
        search_button_id: ID of the search button element (str or int).
        title: The article title to search for.
        article_link_id: The link ID to click to open the desired article.

    Returns:
        None

    Examples:
        search_and_open_article('370', '371', 'Some Article Title', '85')
    """
    fill(search_field_id, title)    # enter the article title into the search field
    click(search_button_id)         # submit the search
    click(article_link_id)          # open the article from the search results

def report_image_relevance_from_metadata(keyword: str, image_alt_text: str, image_url: str):
    """Check whether provided image metadata is related to a keyword and report the result to the user.

    The message sent to the user is constructed inside the function from the keyword and the metadata.

    Args:
        keyword: The keyword to check for (e.g., 'iPad Mini').
        image_alt_text: The alt text of the image (obtained from the article).
        image_url: The image URL (obtained from the article).

    Returns:
        None

    Examples:
        report_image_relevance_from_metadata('iPad Mini', 'Hand holding an iPad Mini.', 'https://example.com/img.jpg')
    """
    kw = keyword.lower()
    alt_lower = (image_alt_text or "").lower()
    url_lower = (image_url or "").lower()

    related = (kw in alt_lower) or (kw in url_lower)

    if related:
        message = f"Yes — the article contains an image related to {keyword}. Alt text: '{image_alt_text}' Image URL: {image_url}"
    else:
        message = f"No — the article does not contain an image related to {keyword}."
    send_msg_to_user(message)

def find_and_open_post(search_box_id: str | int, post_title: str, result_id: str | int, wait_ms: int = 500):
    """Search for a post by title and open the search result.

    Args:
        search_box_id: ID of the search or title input element.
        post_title: The exact title to search for.
        result_id: ID of the clickable search result element to open.
        wait_ms: Milliseconds to wait after clicking the search result.

    Returns:
        None

    Examples:
        find_and_open_post('370', 'How to get rid of unwanted Christmas presents - without being found out', '371', 1000)
    """
    fill(search_box_id, post_title)  # enter the post title into search/input
    click(result_id)                  # click the result that corresponds to the post
    noop(wait_ms)                     # wait for the page/result to load


def post_comment(comment_field_id: str | int, comment_text: str,
                 name_field_id: str | int, name: str,
                 email_field_id: str | int, email: str,
                 submit_button_id: str | int):
    """Fill the comment form and submit it.

    Args:
        comment_field_id: ID of the comment text area/input.
        comment_text: The comment content to post.
        name_field_id: ID of the name input field.
        name: The name to use for the comment.
        email_field_id: ID of the email input field.
        email: The email to use for the comment.
        submit_button_id: ID of the submit/post button.

    Returns:
        None

    Examples:
        post_comment('240', 'Interesting perspective.', '244', 'ChatGPT User', '248', 'chatgpt@example.com', '256')
    """
    fill(comment_field_id, comment_text)  # enter the comment text
    fill(name_field_id, name)             # enter the commenter's name
    fill(email_field_id, email)           # enter the commenter's email
    click(submit_button_id)               # submit the comment form