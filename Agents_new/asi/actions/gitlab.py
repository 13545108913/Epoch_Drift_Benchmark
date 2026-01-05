from browsergym.core.action.functions import *

import playwright.sync_api
page: playwright.sync_api.Page = None


def search_project(search_field_id: str, project_name: str, submit_key: str = 'Enter'):
    """Search for a project by name using a page search field.

    Args:
        search_field_id: The ID of the search or filter input element (string).
        project_name: The project name to enter into the search field (string).
        submit_key: The key to press to submit the search, default is 'Enter' (string).

    Returns:
        None

    Examples:
        search_project('238', '2019-nCov')
        search_project('236', 'example-repo', submit_key='Enter')
    """
    click(search_field_id)
    fill(search_field_id, project_name)
    keyboard_press(submit_key)


def fork_project(project_link_id: str, fork_button_id: str, confirm_button_id: str):
    """Open a project and perform the fork flow by clicking the fork and confirm controls.

    Args:
        project_link_id: The ID for the project link or entry to open (string).
        fork_button_id: The ID of the fork button on the project page (string).
        confirm_button_id: The ID of the final confirm/submit button to complete the fork (string).

    Returns:
        None

    Examples:
        fork_project('304', '472', '412')
        fork_project('project-entry-1', 'fork-btn', 'confirm-fork')
    """
    click(project_link_id)
    click(fork_button_id)
    click(confirm_button_id)

def search_and_open_repo(search_bar_id: str | int, repo_name: str, repo_result_id: str | int):
    """Search for a repository using the search bar and open it from the results.

    Args:
        search_bar_id: The ID of the search input element to click and fill.
        repo_name: The repository name to search for.
        repo_result_id: The ID of the search result element to click to open the repo.

    Returns:
        None

    Examples:
        search_and_open_repo('241', 'aem-hacker', '237')
    """
    click(search_bar_id)
    fill(search_bar_id, repo_name)
    keyboard_press('Enter')
    click(repo_result_id)

def open_issues_and_new(issue_tab_id: str | int, new_issue_button_id: str | int, title_field_id: str | int):
    """Navigate to a repository's Issues tab and start a new issue.

    Args:
        issue_tab_id: The ID of the repository's "Issues" tab to click.
        new_issue_button_id: The ID of the "New issue" button to click.
        title_field_id: The ID of the issue title field to focus/click.

    Returns:
        None

    Examples:
        open_issues_and_new('279', '429', '419')
    """
    click(issue_tab_id)
    click(new_issue_button_id)
    click(title_field_id)

def submit_issue(title_field_id: str | int, title_text: str, body_field_id: str | int, body_text: str, submit_button_id: str | int):
    """Fill in issue title and body, then submit the new issue.

    Args:
        title_field_id: The ID of the title input field.
        title_text: The issue title text to fill.
        body_field_id: The ID of the body/description textarea.
        body_text: The issue body text to fill.
        submit_button_id: The ID of the button to submit the issue.

    Returns:
        None

    Examples:
        submit_issue('419', 'Bug: ...', '460', 'Steps to reproduce: ...', '505')
    """
    fill(title_field_id, title_text)
    fill(body_field_id, body_text)
    click(submit_button_id)

def open_new_group_page(menu_id: str | int, new_group_url: str, wait_ms: int = 500):
    """Open the UI and navigate to the new-group creation page.

    Args:
        menu_id: ID of the menu or link to click before navigation (e.g., "76").
        new_group_url: The URL for creating a new group.
        wait_ms: Milliseconds to wait after navigation to allow the page to load.

    Returns:
        None

    Examples:
        open_new_group_page('76', 'http://example.com/groups/new')
    """
    click(menu_id)
    goto(new_group_url)
    noop(wait_ms)


def set_group_basic_info(name_field_id: str | int, path_field_id: str | int, submit_button_id: str | int, group_name: str, path: str | None = None):
    """Fill in the group's name and path/slug, then submit the basic info.

    Args:
        name_field_id: Field ID for the group name.
        path_field_id: Field ID for the group path/slug.
        submit_button_id: ID of the button to confirm/submit the basic info.
        group_name: Desired group name.
        path: Optional explicit path/slug; if None, group_name will be used.

    Returns:
        None

    Examples:
        set_group_basic_info('235', '245', '287', 'x-lab')
    """
    fill(name_field_id, group_name)
    fill(path_field_id, path or group_name)
    click(submit_button_id)


def add_group_members(member_input_id: str | int, member_names: list, confirm_button_id: str | int, pause_ms: int = 300):
    """Add multiple members to the group by typing each name and confirming.

    Args:
        member_input_id: Input field ID used to search/type member names.
        member_names: List of member username strings to add.
        confirm_button_id: Button ID to click after selecting/entering a member.
        pause_ms: Milliseconds to wait after each addition to allow UI updates.

    Returns:
        None

    Examples:
        add_group_members('363', ['alice','bob'], '385')
    """
    for mn in member_names:
        fill(member_input_id, mn)
        keyboard_press("Enter")
        click(confirm_button_id)
        noop(pause_ms)