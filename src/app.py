import os
from flask import Flask, request, jsonify
import slack_sdk
import requests
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Initialize clients
slack_token = os.environ.get("SLACK_BOT_TOKEN")
slack_signing_secret = os.environ.get("SLACK_SIGNING_SECRET")
jira_url = os.environ.get("JIRA_URL")
jira_email = os.environ.get("JIRA_EMAIL")
jira_api_token = os.environ.get("JIRA_API_TOKEN")
gemini_api_key = os.environ.get("GEMINI_API_KEY")

slack_client = slack_sdk.WebClient(token=slack_token)
genai.configure(api_key=gemini_api_key)
model = genai.GenerativeModel('gemini-pro')

def get_jira_ticket_details(ticket_key):
    """Retrieve ticket details from Jira API."""
    url = f"{jira_url}/rest/api/2/issue/{ticket_key}"
    auth = (jira_email, jira_api_token)
    headers = {"Accept": "application/json"}
    try:
        response = requests.get(url, auth=auth, headers=headers)
        response.raise_for_status()
        data = response.json()
        summary = data["fields"]["summary"]
        description = data["fields"]["description"] or ""
        return summary, description
    except requests.exceptions.RequestException as e:
        return None, str(e)

def generate_specs(ticket_summary, ticket_description, user_prompt):
    """Generate specifications using Gemini Pro."""
    prompt = f"""
    Generate detailed specifications for a Jira ticket with the following details:

    Ticket Summary: {ticket_summary}
    Ticket Description: {ticket_description}

    User Prompt: {user_prompt}

    Please provide a comprehensive and structured specification document that includes:
    1. Overview
    2. Requirements
    3. Technical Details
    4. Acceptance Criteria
    5. Dependencies
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return str(e)

def add_jira_comment(ticket_key, comment):
    """Add a comment to a Jira ticket."""
    url = f"{jira_url}/rest/api/2/issue/{ticket_key}/comment"
    auth = (jira_email, jira_api_token)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {"body": comment}
    try:
        response = requests.post(url, auth=auth, headers=headers, json=payload)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        return str(e)

@app.route("/slack/command", methods=["POST"])
def handle_slack_command():
    """Handle incoming Slack slash commands."""
    data = request.form
    
    # Verify Slack request signature
    if not slack_sdk.web.verify_slack_request(
        signing_secret=slack_signing_secret,
        body=request.get_data(),
        timestamp=request.headers.get("X-Slack-Request-Timestamp"),
        signature=request.headers.get("X-Slack-Signature")
    ):
        return jsonify({"response_type": "ephemeral", "text": "Invalid request signature"}), 401

    # Extract ticket key and user prompt
    command_text = data.get("text", "").strip()
    if not command_text:
        return jsonify({
            "response_type": "ephemeral",
            "text": "Please provide a Jira ticket key and optional prompt. Usage: /create-specs PROJ-123 [prompt]"
        })

    parts = command_text.split(" ", 1)
    ticket_key = parts[0].upper()
    user_prompt = parts[1] if len(parts) > 1 else ""

    # Get ticket details
    summary, description = get_jira_ticket_details(ticket_key)
    if summary is None:
        return jsonify({
            "response_type": "ephemeral",
            "text": f"Error retrieving Jira ticket: {description}"
        })

    # Generate specs
    specs = generate_specs(summary, description, user_prompt)
    if "Error" in specs:
        return jsonify({
            "response_type": "ephemeral",
            "text": f"Error generating specs: {specs}"
        })

    # Add comment to Jira
    result = add_jira_comment(ticket_key, specs)
    if result is True:
        return jsonify({
            "response_type": "in_channel",
            "text": f"✅ Successfully added specifications to Jira ticket {ticket_key}"
        })
    else:
        return jsonify({
            "response_type": "ephemeral",
            "text": f"Error adding comment to Jira: {result}"
        })

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port) 