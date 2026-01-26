# Engineering Rotation Management System

An automated system for managing rotating responsibilities across engineering tasks. This system automatically assigns team members to various tasks on a weekly basis, sends notifications, and tracks assignments via GitHub issues.

## Overview

The rotation system uses ISO week numbers to deterministically assign team members to tasks using a round-robin algorithm. Every week, the system:

- Calculates current and next week's assignments
- Creates a GitHub issue tracking the assignments
- Sends email notifications to all team members
- Posts a message to Slack with the assignments

## Features

- **Automated Weekly Rotation**: Runs automatically every Friday at 1:00 PM UTC
- **Deterministic Assignment**: Uses ISO week numbers for consistent, repeatable rotations
- **Multiple Tasks**: Support for multiple tasks with different staff rotations
- **Multi-Channel Notifications**: Email and Slack notifications
- **GitHub Integration**: Automatic issue creation and assignment
- **Manual Triggering**: Can be triggered manually for testing or special cases
- **Dry-Run Mode**: Test the system without sending notifications

## Quick Start

### 1. Configure Tasks and Staff

Edit `.github/rotation-config.yml` to define your tasks and staff:

```yaml
tasks:
  - name: "DevOps Duty"
    description: "Monitor production systems and handle deployments"
    staff:
      - alice-dev
      - bob-engineer
      - charlie-ops
    email_addresses:
      - alice@example.com
      - bob@example.com
      - charlie@example.com

notifications:
  slack_channel: "#engineering"
  timezone: "UTC"
```

**Important**: The number of `email_addresses` must match the number of `staff` members for each task.

### 2. Set Up Required Secrets

Configure the following secrets in your repository settings (Settings → Secrets and variables → Actions):

#### Email Configuration (Optional)
- `SMTP_HOST` - SMTP server hostname (e.g., `smtp.gmail.com`)
- `SMTP_PORT` - SMTP server port (e.g., `587`)
- `SMTP_USERNAME` - SMTP authentication username
- `SMTP_PASSWORD` - SMTP authentication password
- `SMTP_FROM_EMAIL` - Email address to send from

#### Slack Configuration (Optional)
- `SLACK_WEBHOOK_URL` - Slack incoming webhook URL

#### GitHub Token
- `GITHUB_TOKEN` - Automatically provided by GitHub Actions (no setup needed)

**Note**: Email and Slack notifications are optional. The system will work with GitHub issues only if these secrets are not configured.

### 3. Enable GitHub Actions

Ensure GitHub Actions is enabled for your repository:
1. Go to repository Settings → Actions → General
2. Under "Actions permissions", select "Allow all actions and reusable workflows"
3. Save changes

### 4. Test the System

Manually trigger the test workflow:
1. Go to Actions tab
2. Select "Test Rotation System" workflow
3. Click "Run workflow"
4. Enter a week number (e.g., `1`)
5. Click "Run workflow"

This will run in dry-run mode and show you what assignments would be made without sending notifications.

## Configuration Guide

### Configuration File Structure

The configuration file (`.github/rotation-config.yml`) has two main sections:

#### Tasks Section

Each task requires:
- `name`: Task name (displayed in notifications and issues)
- `description`: Brief description of the task responsibilities
- `staff`: List of GitHub usernames (in rotation order)
- `email_addresses`: List of email addresses (must match staff order and count)

Example:
```yaml
tasks:
  - name: "Code Review Champion"
    description: "Ensure timely code reviews and maintain quality standards"
    staff:
      - developer1
      - developer2
      - developer3
    email_addresses:
      - dev1@example.com
      - dev2@example.com
      - dev3@example.com
```

#### Notifications Section

Configure notification preferences:
- `slack_channel`: Slack channel to post messages (e.g., `#engineering`)
- `timezone`: Timezone for date/time display (e.g., `UTC`, `America/New_York`)

### Adding/Removing Staff

To modify staff assignments:

1. Edit `.github/rotation-config.yml`
2. Add or remove GitHub usernames from the `staff` list
3. Add or remove corresponding emails from the `email_addresses` list
4. Commit and push changes

The rotation will automatically adjust based on the new staff list.

### Adding New Tasks

To add a new task:

1. Edit `.github/rotation-config.yml`
2. Add a new task entry under the `tasks` section
3. Include all required fields (`name`, `description`, `staff`, `email_addresses`)
4. Commit and push changes

## How It Works

### Rotation Algorithm

The system uses a simple round-robin rotation based on ISO week numbers:

```
assigned_index = (week_number - 1) % number_of_staff
```

For example, with 3 staff members:
- Week 1: Staff member at index 0
- Week 2: Staff member at index 1
- Week 3: Staff member at index 2
- Week 4: Staff member at index 0 (rotation repeats)

### ISO Week Numbers

The system uses ISO 8601 week date system:
- Weeks run from Monday to Sunday
- Week 1 is the first week with a Thursday in the new year
- Most years have 52 weeks, some have 53

### Workflow Schedule

The main workflow runs automatically:
- **Schedule**: Every Friday at 1:00 PM UTC (`0 13 * * 5`)
- **Purpose**: Notify team about current week and upcoming week assignments

## Manual Operations

### Manual Trigger

To manually trigger the rotation assignment:

1. Go to Actions tab
2. Select "Rotation Assignment" workflow
3. Click "Run workflow"
4. Configure options:
   - **dry_run**: Check to run without sending notifications
   - **week_number**: Leave empty for current week, or specify a week number
5. Click "Run workflow"

### Testing Specific Weeks

To test assignments for a specific week:

```bash
python scripts/rotation-manager.py --dry-run --week 15
```

### Validating Configuration

To validate your configuration without running the rotation:

```bash
python scripts/rotation-manager.py --validate-only
```

## Setting Up Notifications

### Slack Setup

1. Create a Slack Incoming Webhook:
   - Go to https://api.slack.com/messaging/webhooks
   - Click "Create your Slack app"
   - Select "From scratch"
   - Name your app (e.g., "Rotation Bot")
   - Choose your workspace
   - Click "Incoming Webhooks"
   - Activate Incoming Webhooks
   - Click "Add New Webhook to Workspace"
   - Select the channel (e.g., `#engineering`)
   - Copy the webhook URL

2. Add the webhook URL to GitHub secrets:
   - Go to repository Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `SLACK_WEBHOOK_URL`
   - Value: Paste the webhook URL
   - Click "Add secret"

### Email Setup

For Gmail:
1. Enable 2-factor authentication on your Google account
2. Generate an App Password:
   - Go to Google Account settings
   - Security → 2-Step Verification → App passwords
   - Generate a password for "Mail"
3. Add secrets to GitHub:
   - `SMTP_HOST`: `smtp.gmail.com`
   - `SMTP_PORT`: `587`
   - `SMTP_USERNAME`: Your Gmail address
   - `SMTP_PASSWORD`: The app password you generated
   - `SMTP_FROM_EMAIL`: Your Gmail address

For other email providers, use their SMTP settings.

## Troubleshooting

### Configuration Validation Errors

**Error**: "Configuration must have 'tasks' key"
- **Solution**: Ensure your YAML file has a `tasks:` section

**Error**: "Task X must have same number of email_addresses as staff members"
- **Solution**: Make sure each task has exactly one email address per staff member

### Workflow Failures

**Issue**: Workflow fails with "GITHUB_TOKEN" error
- **Solution**: Ensure the workflow has `issues: write` permission (already configured in the workflow)

**Issue**: Slack notification fails
- **Solution**: Verify `SLACK_WEBHOOK_URL` is correctly set in repository secrets

**Issue**: Email notification fails
- **Solution**: 
  - Verify all SMTP secrets are set correctly
  - Check that SMTP_PORT is a number (e.g., `587`, not `"587"`)
  - For Gmail, ensure you're using an App Password, not your regular password

### Assignment Issues

**Issue**: Wrong person assigned to task
- **Solution**: 
  - Verify the staff list order in the configuration
  - The rotation is based on list order, not alphabetical
  - Use the test workflow to verify assignments for specific weeks

**Issue**: Someone assigned to multiple tasks
- **Solution**: This is expected behavior. One person can be assigned to multiple tasks in the same week if they appear in multiple task staff lists.

## Local Development

### Prerequisites

- Python 3.11 or higher
- pip (Python package installer)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/gbif/engineering.git
cd engineering
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables (for testing):
```bash
export GITHUB_TOKEN="your_github_token"
export SMTP_HOST="smtp.example.com"
export SMTP_PORT="587"
export SMTP_USERNAME="username"
export SMTP_PASSWORD="password"
export SMTP_FROM_EMAIL="from@example.com"
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
```

4. Run in dry-run mode:
```bash
python scripts/rotation-manager.py --dry-run
```

### Testing

Run configuration validation:
```bash
python scripts/rotation-manager.py --validate-only
```

Test specific week assignments:
```bash
python scripts/rotation-manager.py --dry-run --week 10
```

## Architecture

### Components

1. **Configuration File** (`.github/rotation-config.yml`)
   - Defines tasks, staff, and notification settings
   - YAML format for easy editing

2. **Rotation Manager Script** (`scripts/rotation-manager.py`)
   - Core logic for calculating assignments
   - Handles GitHub API, email, and Slack integrations
   - Validates configuration

3. **Main Workflow** (`.github/workflows/rotation-assignment.yml`)
   - Scheduled execution every Friday
   - Manual trigger support
   - Runs rotation manager script

4. **Test Workflow** (`.github/workflows/test-rotation.yml`)
   - Testing without side effects
   - Week-by-week rotation preview

### Data Flow

```
Configuration File
       ↓
Rotation Manager (calculates assignments)
       ↓
    ┌──┴──┐
    ↓     ↓     ↓
GitHub  Email  Slack
Issue   Notification
```

## Advanced Configuration

### Custom Cron Schedule

To change the schedule, edit `.github/workflows/rotation-assignment.yml`:

```yaml
schedule:
  # Run every Monday at 9:00 AM UTC
  - cron: '0 9 * * 1'
```

Cron format: `minute hour day_of_month month day_of_week`

### Timezone Configuration

The `timezone` setting in the configuration file is informational only. The system always uses UTC for week calculations to ensure consistency. If you want to display times in a different timezone in notifications, you would need to modify the script.

## Contributing

To contribute to this rotation system:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly using dry-run mode
5. Submit a pull request

## License

This project is part of the GBIF engineering repository. Refer to the main repository license for details.

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review the GitHub Actions logs for error messages
3. Open an issue in the repository with details about your problem
