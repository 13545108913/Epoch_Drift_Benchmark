from browsergym.core.action.functions import *

import playwright.sync_api
page: playwright.sync_api.Page = None


def search_repository(search_box_id: str, repo_name: str):
    """Search for a repository by name.
    
    Args:
        search_box_id: The ID of the search box element
        repo_name: The name of the repository to search for
        
    Examples:
        search_repository('142', '2019-nCov')
        search_repository('150', 'tensorflow')
    """
    fill(search_box_id, repo_name)  # Fill search box with repository name
    noop(1500)  # Wait for search results to load
    keyboard_press('Enter')  # Execute the search

def navigate_to_contributors(commits_link_id: str, contributors_link_id: str):
    """Navigate to the contributors page from repository main page.
    
    Args:
        commits_link_id: The ID of the commits link element
        contributors_link_id: The ID of the contributors link element
        
    Examples:
        navigate_to_contributors('522', '270')
        navigate_to_contributors('500', '265')
    """
    click(commits_link_id)  # Click on commits link
    click(contributors_link_id)  # Click on contributors link

def navigate_to_project_merge_requests(project_id: str):
    """Navigate to the merge requests page of a project.
    
    Args:
        project_id: The ID of the project link to click
        
    Examples:
        navigate_to_project_merge_requests('357')
    """
    click(project_id)  # Click on the project
    merge_requests_link = page.get_by_label("Merge Requests")
    merge_requests_link.click()  # Click on Merge Requests in sidebar

def post_comment_on_merge_request(comment_area_id: str, comment_text: str, submit_button_id: str):
    """Post a comment on a merge request.
    
    Args:
        comment_area_id: The ID of the comment text area
        comment_text: The text content to post as a comment
        submit_button_id: The ID of the submit/comment button
        
    Examples:
        post_comment_on_merge_request('671', 'Thanks, working on reviews', '700')
    """
    click(comment_area_id)  # Click on comment text area
    fill(comment_area_id, comment_text)  # Fill in the comment text
    click(submit_button_id)  # Click the Comment button to submit

def navigate_to_project_issues(project_id: str, issues_id: str):
    """Navigate to the issues page of a specific project.
    
    Args:
        project_id: The ID of the project link to click
        issues_id: The ID of the "Issues" link in the sidebar
        
    Examples:
        navigate_to_project_issues('323', '283')
    """
    click(project_id)  # Click on the project
    click(issues_id)  # Click on Issues in the sidebar

def assign_issue_to_user(issue_id: str, assignee_edit_id: str, user_id: str):
    """Assign a specific issue to a user.
    
    Args:
        issue_id: The ID of the issue to click and open
        assignee_edit_id: The ID of the "Edit" link next to Assignee
        user_id: The ID of the user to assign the issue to
        
    Examples:
        assign_issue_to_user('901', '809', '1064')
    """
    click(issue_id)  # Open the issue
    click(assignee_edit_id)  # Click Edit next to Assignee
    click(user_id)  # Select the user from dropdown

def navigate_to_new_issue(issues_tab_id: str, new_issue_button_id: str):
    """Navigate to the new issue creation page from a repository.
    
    Args:
        issues_tab_id: The ID of the Issues tab link
        new_issue_button_id: The ID of the New issue button
        
    Examples:
        navigate_to_new_issue('283', '491')
    """
    click(issues_tab_id)  # Click on Issues tab
    click(new_issue_button_id)  # Click on New issue button

def create_issue(title_field_id: str, description_field_id: str, submit_button_id: str, title: str, description: str):
    """Create a new issue with title and description.
    
    Args:
        title_field_id: The ID of the title input field
        description_field_id: The ID of the description textarea
        submit_button_id: The ID of the submit button
        title: The issue title
        description: The issue description
        
    Examples:
        create_issue('478', '521', '693', 'Bug: Login fails', 'Users cannot login...')
    """
    fill(title_field_id, title)  # Fill in the issue title
    fill(description_field_id, description)  # Fill in the issue description
    click(submit_button_id)  # Submit the issue

def navigate_to_project_issues(project_id: str, issues_sidebar_id: str):
    """Navigate to the issues page of a project.
    
    Args:
        project_id: The ID of the project link to click
        issues_sidebar_id: The ID of the Issues link in the sidebar
        
    Examples:
        navigate_to_project_issues('846', '370')
        navigate_to_project_issues('123', '456')
    """
    click(project_id)  # Click on the project
    click(issues_sidebar_id)  # Click on Issues in sidebar
    
def create_new_issue(new_issue_button_id: str, title: str, description: str, submit_button_id: str):
    """Create a new issue with title and description.
    
    Args:
        new_issue_button_id: The ID of the "New issue" button
        title: The title of the issue
        description: The description/body of the issue
        submit_button_id: The ID of the submit button
        
    Examples:
        create_new_issue('491', 'Bug: Login fails', 'Users cannot login', '693')
        create_new_issue('500', 'Feature request', 'Add dark mode', '700')
    """
    click(new_issue_button_id)  # Click New issue button
    fill('478', title)  # Fill in the title field
    fill('521', description)  # Fill in the description field
    click(submit_button_id)  # Submit the issue

def navigate_to_branch_contributors(branches_link_id: str, branch_name: str):
    """Navigate from repository page to the contributors page of a specific branch.
    
    Args:
        branches_link_id: The ID of the branches overview link
        branch_name: Name of the branch to view contributors for
        
    Examples:
        navigate_to_branch_contributors('526', 'gh-pages')
        navigate_to_branch_contributors('420', 'main')
    """
    click(branches_link_id)  # Click on branches overview link
    branch_element = page.get_by_text(branch_name)
    branch_element.click()  # Click on the specific branch
    contributors_element = page.get_by_label("Contributors")
    contributors_element.click()  # Navigate to Contributors page