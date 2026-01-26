#!/usr/bin/env python3
"""
Rotation Manager Script

This script manages rotating responsibilities for engineering tasks.
It calculates assignments based on ISO week numbers and generates
notifications for GitHub, Email, and Slack.
"""

import os
import sys
import argparse
import yaml
import json
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from github import Github


def get_iso_week(date=None):
    """Get ISO week number for a given date (or current date)."""
    if date is None:
        date = datetime.now()
    return date.isocalendar()[1]


def get_iso_year(date=None):
    """Get ISO year for a given date (or current date)."""
    if date is None:
        date = datetime.now()
    return date.isocalendar()[0]


def calculate_assignment(week_number, staff_list):
    """
    Calculate who is responsible based on week number using round-robin.
    
    Args:
        week_number: ISO week number (1-52/53)
        staff_list: List of staff members
    
    Returns:
        The assigned staff member (GitHub username)
    """
    if not staff_list:
        return None
    
    index = (week_number - 1) % len(staff_list)
    return staff_list[index]


def get_assignments(config, week_number):
    """
    Get all assignments for a given week.
    
    Args:
        config: Configuration dictionary
        week_number: ISO week number
    
    Returns:
        List of assignment dictionaries
    """
    assignments = []
    
    for task in config.get('tasks', []):
        staff = task.get('staff', [])
        assigned_person = calculate_assignment(week_number, staff)
        
        # Get email for assigned person
        email_addresses = task.get('email_addresses', [])
        assigned_email = None
        if assigned_person and staff:
            try:
                person_index = staff.index(assigned_person)
                if person_index < len(email_addresses):
                    assigned_email = email_addresses[person_index]
            except ValueError:
                pass
        
        assignments.append({
            'task_name': task.get('name', 'Unknown Task'),
            'task_description': task.get('description', ''),
            'assigned_to': assigned_person,
            'assigned_email': assigned_email,
            'all_staff': staff,
            'all_emails': email_addresses
        })
    
    return assignments


def generate_github_issue_body(config, current_week, next_week, current_assignments, next_assignments):
    """Generate the body content for the GitHub issue."""
    current_year = get_iso_year()
    
    body = f"# Week {current_week} ({current_year}) - Rotating Responsibilities\n\n"
    body += f"This issue tracks the rotating responsibilities for this week.\n\n"
    
    body += "## Current Week Assignments\n\n"
    body += "| Task | Assigned To | Description |\n"
    body += "|------|-------------|-------------|\n"
    
    for assignment in current_assignments:
        task_name = assignment['task_name']
        assigned_to = assignment['assigned_to']
        assigned_display = f"@{assigned_to}" if assigned_to else "Unassigned"
        description = assignment['task_description']
        body += f"| {task_name} | {assigned_display} | {description} |\n"
    
    body += f"\n## Next Week (Week {next_week}) Preview\n\n"
    body += "| Task | Will Be Assigned To |\n"
    body += "|------|---------------------|\n"
    
    for assignment in next_assignments:
        task_name = assignment['task_name']
        assigned_to = assignment['assigned_to']
        assigned_display = f"@{assigned_to}" if assigned_to else "Unassigned"
        body += f"| {task_name} | {assigned_display} |\n"
    
    body += "\n---\n"
    body += f"*Automated rotation system - Week {current_week} of {current_year}*\n"
    
    return body


def create_github_issue(config, current_week, next_week, current_assignments, next_assignments, dry_run=False):
    """
    Create a GitHub issue for the current week's assignments.
    
    Args:
        config: Configuration dictionary
        current_week: Current ISO week number
        next_week: Next ISO week number
        current_assignments: List of current week assignments
        next_assignments: List of next week assignments
        dry_run: If True, don't actually create the issue
    
    Returns:
        The created issue object or None
    """
    github_token = os.environ.get('GITHUB_TOKEN')
    repo_name = os.environ.get('GITHUB_REPOSITORY')
    
    if not github_token or not repo_name:
        print("Warning: GITHUB_TOKEN or GITHUB_REPOSITORY not set")
        return None
    
    try:
        g = Github(github_token)
        repo = g.get_repo(repo_name)
        
        # Create issue title and body
        current_year = get_iso_year()
        title = f"Week {current_week} ({current_year}) - Rotating Responsibilities"
        body = generate_github_issue_body(config, current_week, next_week, current_assignments, next_assignments)
        
        if dry_run:
            print(f"\n[DRY RUN] Would create GitHub issue:")
            print(f"Title: {title}")
            print(f"Body:\n{body}")
            print(f"Assignees: {[a['assigned_to'] for a in current_assignments if a['assigned_to']]}")
            return None
        
        # Get or create the 'rotation' label
        try:
            label = repo.get_label("rotation")
        except Exception:
            # Label doesn't exist, create it
            label = repo.create_label("rotation", "4A90E2", "Rotating responsibilities tracking")
        
        # Close previous rotation issues
        open_issues = repo.get_issues(state='open', labels=[label])
        for issue in open_issues:
            if "Rotating Responsibilities" in issue.title and issue.title != title:
                issue.edit(state='closed')
                print(f"Closed previous issue: #{issue.number}")
        
        # Create new issue
        assignees = [a['assigned_to'] for a in current_assignments if a['assigned_to']]
        issue = repo.create_issue(
            title=title,
            body=body,
            labels=[label],
            assignees=assignees
        )
        
        print(f"Created GitHub issue: #{issue.number}")
        print(f"Issue URL: {issue.html_url}")
        
        return issue
        
    except Exception as e:
        print(f"Error creating GitHub issue: {e}")
        return None


def send_email_notification(config, current_week, next_week, current_assignments, next_assignments, dry_run=False):
    """
    Send email notifications to all staff members.
    
    Args:
        config: Configuration dictionary
        current_week: Current ISO week number
        next_week: Next ISO week number
        current_assignments: List of current week assignments
        next_assignments: List of next week assignments
        dry_run: If True, don't actually send emails
    """
    smtp_host = os.environ.get('SMTP_HOST')
    smtp_port = os.environ.get('SMTP_PORT', '587')
    smtp_username = os.environ.get('SMTP_USERNAME')
    smtp_password = os.environ.get('SMTP_PASSWORD')
    smtp_from = os.environ.get('SMTP_FROM_EMAIL')
    
    # Add debug output
    print(f"Debug - SMTP config check:")
    print(f"  SMTP_HOST: {'SET' if smtp_host else 'NOT SET'}")
    print(f"  SMTP_PORT: {'SET' if smtp_port else 'NOT SET'}")
    print(f"  SMTP_USERNAME: {'SET' if smtp_username else 'NOT SET'}")
    print(f"  SMTP_PASSWORD: {'SET' if smtp_password else 'NOT SET'}")
    print(f"  SMTP_FROM_EMAIL: {'SET' if smtp_from else 'NOT SET'}")
    
    if not all([smtp_host, smtp_port, smtp_username, smtp_password, smtp_from]):
        print("Warning: SMTP configuration not complete, skipping email notifications")
        return
    
    # Collect all unique email addresses
    all_emails = set()
    for task in config.get('tasks', []):
        all_emails.update(task.get('email_addresses', []))
    
    if not all_emails:
        print("No email addresses configured")
        return
    
    # Create email content
    current_year = get_iso_year()
    subject = f"Week {current_week} ({current_year}) - Rotating Responsibilities"
    
    # HTML body
    html_body = f"""
    <html>
    <body>
        <h2>Rotating Responsibilities - Week {current_week} ({current_year})</h2>
        
        <h3>Current Week Assignments</h3>
        <table border="1" cellpadding="5" cellspacing="0">
            <tr>
                <th>Task</th>
                <th>Assigned To</th>
                <th>Description</th>
            </tr>
    """
    
    for assignment in current_assignments:
        html_body += f"""
            <tr>
                <td>{assignment['task_name']}</td>
                <td>{assignment['assigned_to'] or 'Unassigned'}</td>
                <td>{assignment['task_description']}</td>
            </tr>
        """
    
    html_body += f"""
        </table>
        
        <h3>Next Week (Week {next_week}) Assignments</h3>
        <table border="1" cellpadding="5" cellspacing="0">
            <tr>
                <th>Task</th>
                <th>Will Be Assigned To</th>
            </tr>
    """
    
    for assignment in next_assignments:
        html_body += f"""
            <tr>
                <td>{assignment['task_name']}</td>
                <td>{assignment['assigned_to'] or 'Unassigned'}</td>
            </tr>
        """
    
    html_body += """
        </table>
        
        <p><em>This is an automated notification from the rotation management system.</em></p>
    </body>
    </html>
    """
    
    if dry_run:
        print(f"\n[DRY RUN] Would send email:")
        print(f"From: {smtp_from}")
        print(f"To: {', '.join(all_emails)}")
        print(f"Subject: {subject}")
        print(f"Body preview: [HTML content with current and next week assignments]")
        return
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = smtp_from
        msg['To'] = ', '.join(all_emails)
        
        html_part = MIMEText(html_body, 'html')
        msg.attach(html_part)
        
        # Send email
        with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
        
        print(f"Email notification sent to {len(all_emails)} recipients")
        
    except Exception as e:
        print(f"Error sending email: {e}")


def send_slack_notification(config, current_week, next_week, current_assignments, next_assignments, issue_url=None, dry_run=False):
    """
    Send Slack notification to the configured channel.
    
    Args:
        config: Configuration dictionary
        current_week: Current ISO week number
        next_week: Next ISO week number
        current_assignments: List of current week assignments
        next_assignments: List of next week assignments
        issue_url: URL of the GitHub issue
        dry_run: If True, don't actually send Slack message
    """
    webhook_url = os.environ.get('SLACK_WEBHOOK_URL')
    
    # Add debug output
    print(f"Debug - Slack config check:")
    print(f"  SLACK_WEBHOOK_URL: {'SET' if webhook_url else 'NOT SET'}")
    
    if not webhook_url:
        print("Warning: SLACK_WEBHOOK_URL not set, skipping Slack notification")
        return
    
    slack_channel = config.get('notifications', {}).get('slack_channel', '#engineering')
    current_year = get_iso_year()
    
    # Build Slack message
    message = {
        "channel": slack_channel,
        "username": "Rotation Bot",
        "icon_emoji": ":repeat:",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🔄 Week {current_week} ({current_year}) - Rotating Responsibilities"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Current Week Assignments:*"
                }
            }
        ]
    }
    
    # Add current assignments
    for assignment in current_assignments:
        assigned_to = assignment['assigned_to']
        if assigned_to:
            message["blocks"].append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"• *{assignment['task_name']}*: @{assigned_to}\n  _{assignment['task_description']}_"
                }
            })
    
    message["blocks"].append({
        "type": "divider"
    })
    
    message["blocks"].append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"*Next Week (Week {next_week}) Assignments:*"
        }
    })
    
    # Add next week assignments
    for assignment in next_assignments:
        assigned_to = assignment['assigned_to']
        if assigned_to:
            message["blocks"].append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"• *{assignment['task_name']}*: @{assigned_to}"
                }
            })
    
    # Add issue link if available
    if issue_url:
        message["blocks"].append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"📋 <{issue_url}|View GitHub Issue>"
            }
        })
    
    if dry_run:
        print(f"\n[DRY RUN] Would send Slack message:")
        print(json.dumps(message, indent=2))
        return
    
    try:
        response = requests.post(webhook_url, json=message)
        response.raise_for_status()
        print("Slack notification sent successfully")
    except Exception as e:
        print(f"Error sending Slack notification: {e}")


def validate_config(config):
    """
    Validate the configuration file.
    
    Args:
        config: Configuration dictionary
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(config, dict):
        return False, "Configuration must be a dictionary"
    
    if 'tasks' not in config:
        return False, "Configuration must have 'tasks' key"
    
    tasks = config['tasks']
    if not isinstance(tasks, list):
        return False, "'tasks' must be a list"
    
    if len(tasks) == 0:
        return False, "At least one task must be defined"
    
    for i, task in enumerate(tasks):
        if not isinstance(task, dict):
            return False, f"Task {i} must be a dictionary"
        
        if 'name' not in task:
            return False, f"Task {i} must have a 'name'"
        
        if 'staff' not in task:
            return False, f"Task {i} ({task.get('name')}) must have 'staff' list"
        
        staff = task['staff']
        if not isinstance(staff, list):
            return False, f"Task {i} ({task.get('name')}) 'staff' must be a list"
        
        if len(staff) == 0:
            return False, f"Task {i} ({task.get('name')}) must have at least one staff member"
        
        email_addresses = task.get('email_addresses', [])
        if email_addresses and not isinstance(email_addresses, list):
            return False, f"Task {i} ({task.get('name')}) 'email_addresses' must be a list if provided"
        
        # Allow optional email addresses, but if provided, must match staff count
        if email_addresses and len(email_addresses) != len(staff):
            print(f"Warning: Task '{task.get('name')}' has {len(staff)} staff but {len(email_addresses)} email addresses")
    
    return True, None


def main():
    parser = argparse.ArgumentParser(description='Rotation Manager')
    parser.add_argument('--config', default='.github/rotation-config.yml',
                        help='Path to configuration file')
    parser.add_argument('--dry-run', action='store_true',
                        help='Run without sending notifications or creating issues')
    parser.add_argument('--validate-only', action='store_true',
                        help='Only validate configuration and exit')
    parser.add_argument('--week', type=int,
                        help='Specify week number (for testing)')
    
    args = parser.parse_args()
    
    # Load configuration
    try:
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file not found: {args.config}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing configuration file: {e}")
        sys.exit(1)
    
    # Validate configuration
    is_valid, error_message = validate_config(config)
    if not is_valid:
        print(f"Configuration validation failed: {error_message}")
        sys.exit(1)
    
    print("✓ Configuration is valid")
    
    if args.validate_only:
        print("Validation complete. Exiting.")
        sys.exit(0)
    
    # Calculate week numbers
    if args.week:
        current_week = args.week
        # For manual week specification, use simple rollover
        next_week = current_week + 1
        if next_week > 53:
            next_week = 1
    else:
        # For automatic mode, use actual date arithmetic
        current_date = datetime.now()
        current_week = get_iso_week(current_date)
        next_date = current_date + timedelta(weeks=1)
        next_week = get_iso_week(next_date)
    
    current_year = get_iso_year()
    
    print(f"\n{'='*60}")
    print(f"Rotation Manager - Week {current_week} ({current_year})")
    print(f"{'='*60}\n")
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made\n")
    
    # Get assignments
    current_assignments = get_assignments(config, current_week)
    next_assignments = get_assignments(config, next_week)
    
    # Display assignments
    print("Current Week Assignments:")
    for assignment in current_assignments:
        print(f"  - {assignment['task_name']}: {assignment['assigned_to']}")
    
    print(f"\nNext Week (Week {next_week}) Assignments:")
    for assignment in next_assignments:
        print(f"  - {assignment['task_name']}: {assignment['assigned_to']}")
    
    print()
    
    # Create GitHub issue
    issue = create_github_issue(config, current_week, next_week, current_assignments, next_assignments, dry_run=args.dry_run)
    issue_url = issue.html_url if issue else None
    
    # Send notifications
    send_email_notification(config, current_week, next_week, current_assignments, next_assignments, dry_run=args.dry_run)
    send_slack_notification(config, current_week, next_week, current_assignments, next_assignments, issue_url, dry_run=args.dry_run)
    
    print(f"\n{'='*60}")
    print("✓ Rotation management completed successfully")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
