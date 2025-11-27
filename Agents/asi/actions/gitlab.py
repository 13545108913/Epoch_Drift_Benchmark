from browsergym.core.action.functions import *

import playwright.sync_api
page: playwright.sync_api.Page = None


def search_issues(search_box_id: str, keyword: str):
    """Search for issues containing a specific keyword in their titles.
    
    Args:
        search_box_id: The ID of the search box element
        keyword: The keyword to search for in issue titles
        
    Returns:
        None
        
    Examples:
        search_issues('144', 'homepage content')
        search_issues('144', 'bug fix')
    """
    click(search_box_id)  # Click on the search box
    fill(search_box_id, keyword)  # Type the search keyword
    keyboard_press("Enter")  # Execute the search

def search_project(search_box_id: str | int, project_name: str):
    """Search for a GitLab project using the search box.
    
    Args:
        search_box_id: The ID of the search input element
        project_name: The name of the project to search for
        
    Returns:
        None
        
    Examples:
        search_project('241', 'Super_Awesome_Robot')
    """
    click(search_box_id)
    fill(search_box_id, project_name)
    keyboard_press("Enter")

def search_and_select_repo(search_id: str | int, repo_name: str, repo_link_id: str | int):
    """Search for a repository and select it from search results.
    
    Args:
        search_id: The ID of the search input field
        repo_name: The name of the repository to search for
        repo_link_id: The ID of the repository link in search results
        
    Returns:
        None
        
    Examples:
        search_and_select_repo('241', 'csvkit', '284')
        search_and_select_repo('142', 'pandas', '301')
    """
    click(search_id)
    fill(search_id, repo_name)
    keyboard_press("Enter")
    click(repo_link_id)

def navigate_to_contributors(commits_link_id: str | int, contributors_link_id: str | int):
    """Navigate from repository page to contributors statistics.
    
    Args:
        commits_link_id: The ID of the commits link
        contributors_link_id: The ID of the contributors link
        
    Returns:
        None
        
    Examples:
        navigate_to_contributors('522', '270')
        navigate_to_contributors('601', '315')
    """
    click(commits_link_id)
    click(contributors_link_id)

def search_repository(search_box_id: str | int, repo_name: str):
    """Search for a repository using the search box.
    
    Args:
        search_box_id: The ID of the search box element
        repo_name: The name of the repository to search for
        
    Returns:
        None
        
    Examples:
        search_repository('241', 'metaseq')
        search_repository('142', 'pytorch')
    """
    click(search_box_id)
    fill(search_box_id, repo_name)
    keyboard_press("Enter")

def navigate_to_contributors(repo_link_id: str | int, commits_link_id: str | int, contributors_link_id: str | int):
    """Navigate from repository page to contributors page.
    
    Args:
        repo_link_id: The ID of the repository link
        commits_link_id: The ID of the commits link
        contributors_link_id: The ID of the contributors link
        
    Returns:
        None
        
    Examples:
        navigate_to_contributors('284', '522', '270')
    """
    click(repo_link_id)
    click(commits_link_id)
    click(contributors_link_id)

def navigate_to_merge_request(project_id: str, mr_tab_id: str, mr_link_id: str):
    """Navigate from project page to specific merge request.
    
    Args:
        project_id: ID of project link
        mr_tab_id: ID of Merge Requests tab/link
        mr_link_id: ID of specific merge request link
        
    Returns:
        None
        
    Examples:
        navigate_to_merge_request('289', '306', '845')
    """
    click(project_id)  # Click project link
    click(mr_tab_id)  # Click Merge Requests tab
    click(mr_link_id)  # Click specific merge request

def post_merge_request_comment(comment_box_id: str, comment_text: str, action_button_id: str):
    """Post a comment and perform an action on a merge request.
    
    Args:
        comment_box_id: The ID of the comment textbox
        comment_text: The text to post as a comment
        action_button_id: The ID of the action button (e.g., Comment & close)
        
    Returns:
        None
        
    Examples:
        post_merge_request_comment('705', 'close because non reproducible', '751')
    """
    click(comment_box_id)  # Click comment textbox
    fill(comment_box_id, comment_text)  # Fill comment text
    click(action_button_id)  # Click action button

def update_project_title(settings_id: str, title_field_id: str, save_button_id: str, new_title: str):
    """Update the project site's title by navigating to settings, filling the title field, and saving.
    
    Args:
        settings_id: The ID of the Settings link
        title_field_id: The ID of the project title input field
        save_button_id: The ID of the Save changes button
        new_title: The new title text to set
    
    Returns:
        None
    
    Examples:
        update_project_title('395', '481', '503', 'New Project Title')
    """
    click(settings_id)  # Click Settings link
    fill(title_field_id, new_title)  # Fill title field with new title
    click(save_button_id)  # Click Save changes button

def navigate_to_member_management(project_id: str, settings_id: str, members_id: str):
    """Navigate from project page to member management section.
    
    Args:
        project_id: The ID of the project link
        settings_id: The ID of the Settings link
        members_id: The ID of the Members link
        
    Returns:
        None
        
    Examples:
        navigate_to_member_management('889', '395', '407')
    """
    click(project_id)  # Click on the project
    click(settings_id)  # Click Settings link
    click(members_id)  # Click Members link

def add_user_as_role(search_field_id: str, user_name: str, user_select_id: str, add_button_id: str, repo_name: str, role: str):
    """Search for and add a user with specific role to a repository.
    
    Args:
        search_field_id: The ID of the user search field
        user_name: The username to search for
        user_select_id: The ID to select the user from search results
        add_button_id: The ID of the add button
        repo_name: The name of the repository/project
        role: The role to assign to the user
        
    Returns:
        None
        
    Examples:
        add_user_as_role('490', 'yjlou', '607', '512', 'timeit', 'guest')
    """
    fill(search_field_id, user_name)  # Search for the user
    click(user_select_id)  # Select the user from search results
    click(add_button_id)  # Click add button
    send_msg_to_user(f"Successfully added user '{user_name}' as {role} to the {repo_name} project.")

def navigate_to_new_issue(repo_id: str, issues_id: str, new_issue_id: str):
    """Navigate from repository page to new issue creation form.
    
    Args:
        repo_id: The ID of the repository link
        issues_id: The ID of the Issues tab/link
        new_issue_id: The ID of the "New issue" button
        
    Returns:
        None
        
    Examples:
        navigate_to_new_issue('663', '253', '453')
    """
    click(repo_id)  # Click repository link
    click(issues_id)  # Click Issues tab
    click(new_issue_id)  # Click New issue button

def create_issue_with_details(title_id: str, title: str, due_date_id: str, due_date: str, submit_id: str):
    """Fill issue details and submit the issue.
    
    Args:
        title_id: The ID of the title input field
        title: The issue title text
        due_date_id: The ID of the due date input field
        due_date: The due date in YYYY-MM-DD format
        submit_id: The ID of the submit button
        
    Returns:
        None
        
    Examples:
        create_issue_with_details('440', 'Bug fix', '649', '2024-12-31', '655')
    """
    fill(title_id, title)  # Fill issue title
    fill(due_date_id, due_date)  # Set due date
    click(submit_id)  # Submit the issue

def search_and_select_repository(search_bar_id: str | int, repo_name: str, result_id: str | int):
    """Search for a repository and select it from search results.
    
    Args:
        search_bar_id: ID of the search bar element
        repo_name: Name of the repository to search for
        result_id: ID of the repository search result to click
        
    Returns:
        None
        
    Examples:
        search_and_select_repository('241', 'aem-hacker', '284')
        search_and_select_repository('142', 'my-project', '300')
    """
    click(search_bar_id)
    fill(search_bar_id, repo_name)
    keyboard_press("Enter")
    click(result_id)

def navigate_to_new_issue(issues_link_id: str | int, new_issue_link_id: str | int):
    """Navigate from repository page to new issue creation form.
    
    Args:
        issues_link_id: ID of the Issues link
        new_issue_link_id: ID of the New issue link
        
    Returns:
        None
        
    Examples:
        navigate_to_new_issue('279', '429')
        navigate_to_new_issue('300', '450')
    """
    click(issues_link_id)
    click(new_issue_link_id)

def create_issue(title_field_id: str | int, description_field_id: str | int, submit_button_id: str | int, title: str, description: str):
    """Create a new issue with title and description.
    
    Args:
        title_field_id: ID of the title input field
        description_field_id: ID of the description textarea
        submit_button_id: ID of the submit button
        title: Issue title text
        description: Issue description text
        
    Returns:
        None
        
    Examples:
        create_issue('419', '460', '505', 'Bug Report', 'Detailed bug description')
        create_issue('500', '550', '600', 'Feature Request', 'Feature details')
    """
    fill(title_field_id, title)
    fill(description_field_id, description)
    click(submit_button_id)

def create_repository_from_template(new_project_id: str, template_tab_id: str, template_id: str, project_name: str):
    """Create a new repository using a template.
    
    Args:
        new_project_id: ID of the "New project" button
        template_tab_id: ID of the "Create from template" tab
        template_id: ID of the specific template to use
        project_name: Name for the new repository
        
    Returns:
        None
        
    Examples:
        create_repository_from_template('223', '242', '441', 'web_agent_index')
    """
    click(new_project_id)  # Click New project button
    click(template_tab_id)  # Click Create from template tab
    click(template_id)  # Select specific template
    fill('543', project_name)  # Fill project name field
    click('586')  # Click Create project button

def create_project_from_template(new_project_id: str, create_from_template_id: str, template_id: str, use_template_id: str, project_name: str):
    """Create a new project using a specific template.
    
    Args:
        new_project_id: ID of the "New project" button/link
        create_from_template_id: ID of the "Create from template" tab
        template_id: ID of the specific template to use
        use_template_id: ID of the "Use template" button/label
        project_name: Name for the new project
        
    Returns:
        None
        
    Examples:
        create_project_from_template('223', '242', '429', '428', '11711_gitlab')
    """
    click(new_project_id)  # Click New project
    click(create_from_template_id)  # Click Create from template tab
    click(template_id)  # Click specific template
    click(use_template_id)  # Click Use template
    fill('543', project_name)  # Fill project name field
    click('586')  # Click Create project button

def navigate_to_commits_page(repo_link_id: str):
    """Navigate from repository page to commits page.
    
    Args:
        repo_link_id: The ID of the repository link
        
    Returns:
        None
        
    Examples:
        navigate_to_commits_page('284')
    """
    click(repo_link_id)  # Click repository link
    click("249")  # Click Activity link
    click("479")  # Click Push events filter
    click("255")  # Click Repository section
    click("270")  # Click Commits link

def filter_commits_by_author(search_box_id: str, author_name: str):
    """Filter commits by author name.
    
    Args:
        search_box_id: The ID of the search box
        author_name: The name of the author to filter by
        
    Returns:
        None
        
    Examples:
        filter_commits_by_author('500', 'kilian')
    """
    fill(search_box_id, author_name)  # Fill search box with author name

def switch_to_main_branch(branch_selector_id: str, main_branch_id: str):
    """Switch from current branch to main branch.
    
    Args:
        branch_selector_id: The ID of the branch selector
        main_branch_id: The ID of the main branch option
        
    Returns:
        None
        
    Examples:
        switch_to_main_branch('477', '1466')
    """
    click(branch_selector_id)  # Click branch selector
    click(main_branch_id)  # Click main branch option

