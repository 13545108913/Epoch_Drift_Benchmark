from browsergym.core.action.functions import *

import playwright.sync_api
page: playwright.sync_api.Page = None



def browse_issues_pagination():
    """Browse through issues pages to find recent issues.
    
    Args:
        None
        
    Returns:
        None
        
    Examples:
        browse_issues_pagination()
    """
    scroll(0, 500)  # Scroll down to view more issues
    next_page_element = page.get_by_role("link", name="Next")
    next_page_element.click()  # Click Next to view next page of issues

def search_repository(search_box_id: str, search_term: str):
    """Search for repositories using the search box.
    
    Args:
        search_box_id: The ID of the search box element
        search_term: The search term to look for repositories
        
    Returns:
        None
        
    Examples:
        search_repository('142', 'GAN python')
        search_repository('142', 'machine learning')
    """
    click(search_box_id)
    fill(search_box_id, search_term)
    keyboard_press("Enter")

def navigate_to_commits_page(activity_id: str, repo_id: str, commits_id: str):
    """Navigate from homepage to commits page.
    
    Args:
        activity_id: The ID of the "Activity" link
        repo_id: The ID of the "Repository" link
        commits_id: The ID of the "Commits" link
        
    Returns:
        None
        
    Examples:
        navigate_to_commits_page('248', '255', '267')
    """
    click(activity_id)  # Click Activity link
    click(repo_id)  # Click Repository link
    click(commits_id)  # Click Commits link

def search_commits(search_box_id: str, author: str, start_date: str, end_date: str):
    """Search for commits by author and date range.
    
    Args:
        search_box_id: The ID of the search box
        author: The author name to filter by
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        None
        
    Examples:
        search_commits('155', 'Kilian', '2023-01-01', '2024-01-01')
    """
    click(search_box_id)  # Click search box
    fill(search_box_id, f"author:{author} after:{start_date} before:{end_date}")  # Fill search query
    keyboard_press("Enter")  # Execute search

def filter_commits_by_author_and_date(search_box_id: str, author: str, start_date: str, end_date: str):
    """Filter commits by author and date range using the search box.
    
    Args:
        search_box_id: The ID of the search box element
        author: The author name to filter by
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        None
        
    Examples:
        filter_commits_by_author_and_date('499', 'Philip', '2023-01-01', '2023-01-31')
        filter_commits_by_author_and_date('499', 'John', '2023-03-01', '2023-03-15')
    """
    click(search_box_id)
    fill(search_box_id, f"author:{author} after:{start_date} before:{end_date}")
    keyboard_press("Enter")

def navigate_to_profile_settings(profile_dropdown_id: str, settings_option_id: str):
    """Navigate from homepage to profile settings page.
    
    Args:
        profile_dropdown_id: The ID of the profile dropdown/avatar
        settings_option_id: The ID of the Settings option in the dropdown
        
    Returns:
        None
        
    Examples:
        navigate_to_profile_settings('186', '202')
    """
    click(profile_dropdown_id)
    click(settings_option_id)

def update_website_url(website_field_id: str, url: str, save_button_id: str):
    """Update the website URL in profile settings.
    
    Args:
        website_field_id: The ID of the website URL field
        url: The new URL to set
        save_button_id: The ID of the save/update button
        
    Returns:
        None
        
    Examples:
        update_website_url('481', 'https://example.com', '512')
    """
    click(website_field_id)
    fill(website_field_id, url)
    click(save_button_id)

def navigate_to_repository_issues(repo_link_id: str, issues_link_id: str):
    """Navigate to the issues page of a repository.
    
    Args:
        repo_link_id: The ID of the repository link
        issues_link_id: The ID of the issues link
        
    Returns:
        None
        
    Examples:
        navigate_to_repository_issues('440', '283')
    """
    click(repo_link_id)  # Click repository link
    click(issues_link_id)  # Click issues link

def assign_issue_to_user(issue_link_id: str, edit_assignee_id: str, assignee_id: str):
    """Assign an issue to a specific user.
    
    Args:
        issue_link_id: The ID of the issue link
        edit_assignee_id: The ID of the edit assignee button
        assignee_id: The ID of the assignee in the dropdown
        
    Returns:
        None
        
    Examples:
        assign_issue_to_user('810', '732', '987')
    """
    click(issue_link_id)  # Click on the issue
    click(edit_assignee_id)  # Click edit assignee
    click(assignee_id)  # Select assignee from dropdown

def navigate_to_repo_members(repo_id: str, settings_id: str, members_id: str):
    """Navigate from repository page to members management page.
    
    Args:
        repo_id: The ID of the repository link
        settings_id: The ID of the Settings link
        members_id: The ID of the Members link
        
    Returns:
        None
        
    Examples:
        navigate_to_repo_members('870', '395', '407')
    """
    click(repo_id)  # Click repository link
    click(settings_id)  # Click Settings link
    click(members_id)  # Click Members link

def invite_user_to_repo(search_box_id: str, username: str, user_result_id: str, add_button_id: str):
    """Search for and invite a user to the repository.
    
    Args:
        search_box_id: The ID of the member search box
        username: The username to invite
        user_result_id: The ID of the user search result
        add_button_id: The ID of the "Add to project" button
        
    Returns:
        None
        
    Examples:
        invite_user_to_repo('490', 'yjlou', '607', '512')
    """
    fill(search_box_id, username)  # Fill search box with username
    click(user_result_id)  # Click user search result
    click(add_button_id)  # Click add to project button

def navigate_to_merge_request(project_id: str, merge_requests_id: str, mr_title: str):
    """Navigate from homepage to a specific merge request page.
    
    Args:
        project_id: The ID of the project link
        merge_requests_id: The ID of the "Merge Requests" link
        mr_title: The title of the merge request to open
        
    Returns:
        None
        
    Examples:
        navigate_to_merge_request('440', '306', 'color utility')
    """
    click(project_id)  # Click project link
    click(merge_requests_id)  # Click Merge Requests link
    click(mr_title)  # Click specific merge request link

def post_comment(comment_box_id: str, comment_button_id: str, content: str):
    """Post a comment in a text box and submit it.
    
    Args:
        comment_box_id: The ID of the comment text box
        comment_button_id: The ID of the comment submit button
        content: The text content to post as comment
        
    Returns:
        None
        
    Examples:
        post_comment('739', '768', 'Good idea')
    """
    fill(comment_box_id, content)  # Fill comment box with content
    click(comment_button_id)  # Click comment button to submit

def create_milestone(project_selector_id: str, title_field_id: str, start_date_field_id: str, due_date_field_id: str, create_button_id: str, title: str, start_date: str, due_date: str):
    """Create a new milestone with title, start date, and due date.
    
    Args:
        project_selector_id: ID of the project selection element
        title_field_id: ID of the title input field
        start_date_field_id: ID of the start date input field
        due_date_field_id: ID of the due date input field
        create_button_id: ID of the create milestone button
        title: Milestone title text
        start_date: Start date in YYYY-MM-DD format
        due_date: Due date in YYYY-MM-DD format
        
    Returns:
        None
        
    Examples:
        create_milestone('223', '444', '515', '522', '526', 'Collective Code Review', '2023-01-16', '2023-02-05')
    """
    click(project_selector_id)  # Click project selector
    keyboard_press("Enter")  # Confirm project selection
    click(project_selector_id)  # Click "New milestone" link
    fill(title_field_id, title)  # Fill milestone title
    fill(start_date_field_id, start_date)  # Fill start date
    fill(due_date_field_id, due_date)  # Fill due date
    click(create_button_id)  # Click create button