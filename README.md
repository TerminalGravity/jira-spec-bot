# Jira Spec Bot

A Slack bot that generates detailed specifications for Jira tickets using Gemini Pro 2.5.

## Features

- Generates comprehensive specifications for Jira tickets using Gemini Pro 2.5
- Integrates with Slack for easy-to-use commands
- Adds specifications as comments to Jira tickets
- Supports custom prompts for specification generation
- Containerized for easy deployment
- Supports multiple Gemini models (1.5 Pro, 1.5 Flash, 2.0 Flash)

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

2. Run the container with ngrok:
   ```bash
   docker run -p 3000:3000 --env-file .env jira-spec-bot
   ```

3. The container will start both the Flask application and ngrok. The ngrok URL will be displayed in the container logs.

4. Update your Slack app's slash command URL with the ngrok URL + `/slack/command`

5. Test the commands:
   ```bash
   # Test /ask command with different models
   TIMESTAMP=$(date +%s) && SIGNING_SECRET="your_signing_secret" && BODY="command=/ask&text=gemini-1.5-flash hello&channel_id=test_channel" && SIG_BASESTRING="v0:${TIMESTAMP}:${BODY}" && SIGNATURE=$(echo -n "$SIG_BASESTRING" | openssl sha256 -hmac "$SIGNING_SECRET" | cut -d' ' -f2) && curl -X POST https://your-ngrok-url/slack/command -H "Content-Type: application/x-www-form-urlencoded" -H "X-Slack-Request-Timestamp: ${TIMESTAMP}" -H "X-Slack-Signature: v0=${SIGNATURE}" -d "${BODY}"
   ```

## Usage

1. In Slack, use the `/create-specs` command followed by a Jira ticket key and an optional prompt:
   ```
   /create-specs PROJ-123 Generate a detailed spec for implementing user authentication
   ```

2. Use the `/ask` command to interact with different Gemini models:
   ```
   # Using default model (gemini-1.5-pro)
   /ask What is the weather like?

   # Using specific models
   /ask gemini-1.5-flash What is the weather like?
   /ask gemini-2.0-flash What is the weather like?
   ```

   Available models:
   - `gemini-1.5-pro` (default) - Best for general text generation and reasoning
   - `gemini-1.5-flash` - Faster responses, good for simple queries
   - `gemini-2.0-flash` - Latest model with improved capabilities

3. The bot will:
   - For `/create-specs`: Generate specifications and add them to the Jira ticket
   - For `/ask`: Provide a detailed response using the specified model
   - Show feedback in the Slack channel

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