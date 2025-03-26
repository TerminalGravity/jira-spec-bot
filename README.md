# Jira Spec Bot

A Slack bot that generates detailed specifications for Jira tickets using Gemini Pro 2.5.

## Features

- Generates comprehensive specifications for Jira tickets using Gemini Pro 2.5
- Integrates with Slack for easy-to-use commands
- Adds specifications as comments to Jira tickets
- Supports custom prompts for specification generation
- Containerized for easy deployment

## Prerequisites

- Python 3.9 or higher
- Docker (for containerized deployment)
- Slack workspace with admin access
- Jira instance with API access
- Google Cloud project with Gemini Pro API enabled

## Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd jira-spec-bot
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Copy the example environment file and fill in your credentials:
   ```bash
   cp .env.example .env
   ```

4. Configure your Slack app:
   - Create a new Slack app at https://api.slack.com/apps
   - Add the following bot token scopes:
     - `chat:write`
     - `commands`
   - Create a slash command `/create-specs`
   - Install the app to your workspace
   - Copy the Bot User OAuth Token and Signing Secret to your `.env` file

5. Configure Jira:
   - Generate an API token at https://id.atlassian.com/manage-profile/security/api-tokens
   - Add your Jira URL, email, and API token to your `.env` file

6. Configure Google Cloud:
   - Create a project and enable the Gemini Pro API
   - Generate an API key and add it to your `.env` file

## Running Locally

1. Start the Flask application:
   ```bash
   flask run
   ```

2. Use a tool like ngrok to expose your local server:
   ```bash
   ngrok http 3000
   ```

3. Update your Slack app's slash command URL with the ngrok URL + `/slack/command`

## Docker Deployment

1. Build the Docker image:
   ```bash
   docker build -t jira-spec-bot .
   ```

2. Run the container:
   ```bash
   docker run -p 3000:3000 --env-file .env jira-spec-bot
   ```

## Usage

1. In Slack, use the `/create-specs` command followed by a Jira ticket key and an optional prompt:
   ```
   /create-specs PROJ-123 Generate a detailed spec for implementing user authentication
   ```

2. The bot will:
   - Fetch the ticket details from Jira
   - Generate specifications using Gemini Pro
   - Add the specifications as a comment to the Jira ticket
   - Provide feedback in the Slack channel

## Specification Format

The generated specifications include:
- Overview
- Requirements
- Technical Details
- Acceptance Criteria
- Dependencies

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 