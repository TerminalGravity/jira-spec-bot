import os
from flask import Flask, request, jsonify
import slack_sdk
import requests
import google.generativeai as genai
from dotenv import load_dotenv
import tempfile
import urllib.parse
from urllib.parse import urlparse
import mimetypes
from slack_sdk.signature import SignatureVerifier
import logging
import time
import sys
import hmac
import hashlib

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

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
model = genai.GenerativeModel('gemini-1.5-pro')

verifier = SignatureVerifier(slack_signing_secret)

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

def analyze_url_content(url):
    """Fetch and analyze content from a URL."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        content_type = response.headers.get('content-type', '').split(';')[0]
        
        if 'text/html' in content_type:
            return f"Web page content from {url}:\n\n{response.text[:5000]}"  # First 5000 chars
        elif 'application/pdf' in content_type:
            return f"PDF detected at {url} - PDF analysis coming soon"
        else:
            return f"Retrieved content from {url} (type: {content_type})"
            
    except requests.exceptions.RequestException as e:
        return f"Error fetching URL: {str(e)}"

def analyze_file_content(file_info):
    """Analyze content from a Slack file."""
    try:
        # Get file info
        file_id = file_info['id']
        file_type = file_info['filetype']
        
        # Download file
        response = slack_client.files_info(file=file_id)
        url = response['file']['url_private']
        
        # Download with Slack token in headers
        headers = {'Authorization': f'Bearer {slack_token}'}
        file_response = requests.get(url, headers=headers)
        file_response.raise_for_status()
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_type}') as temp_file:
            temp_file.write(file_response.content)
            temp_path = temp_file.name
        
        # Read and analyze based on file type
        with open(temp_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        # Clean up
        os.unlink(temp_path)
        
        return f"File content analysis:\n\n{content[:5000]}"  # First 5000 chars
        
    except Exception as e:
        return f"Error analyzing file: {str(e)}"

def generate_response(prompt, context="", model_name="gemini-1.5-pro"):
    """Generate a streaming response using the specified Gemini model."""
    logger.info(f"Generating response with model: {model_name}")
    logger.debug(f"Prompt: {prompt}")
    logger.debug(f"Context length: {len(context)}")
    
    try:
        start_time = time.time()
        # Create a new model instance with the specified model name
        model_instance = genai.GenerativeModel(model_name)
        full_prompt = f"""
        Context: {context}

        Question/Task: {prompt}

        Please provide a detailed and well-structured response.
        """
        
        # Generate the content with configuration
        generation_config = genai.types.GenerationConfig(
            temperature=0.7,
            top_p=0.8,
            top_k=40,
            max_output_tokens=2048,
        )
        
        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            }
        ]
        
        response = model_instance.generate_content(
            full_prompt,
            generation_config=generation_config,
            safety_settings=safety_settings,
            stream=True  # Enable streaming for faster initial response
        )
        
        # Yield each chunk as it arrives
        for chunk in response:
            if chunk.text:
                yield chunk.text
        
        generation_time = time.time() - start_time
        logger.info(f"Response generated in {generation_time:.2f} seconds")
        
    except Exception as e:
        logger.exception("Error in generate_response")
        raise Exception(f"Error generating response: {str(e)}")

def list_gemini_models():
    """List available Gemini models."""
    try:
        models = genai.list_models()
        model_list = []
        for model in models:
            model_list.append(f"- {model.name}")
        return "\n".join(model_list)
    except Exception as e:
        return f"Error listing models: {str(e)}"

@app.route("/slack/command", methods=["POST"])
def handle_slack_command():
    """Handle incoming Slack slash commands."""
    start_time = time.time()
    logger.info("Received Slack command request")
    logger.debug(f"Request headers: {dict(request.headers)}")

    try:
        # Get the raw request body for signature verification
        raw_body = request.get_data().decode('utf-8')
        logger.debug(f"Raw request body: {raw_body}")
        
        # Verify the request signature
        timestamp = request.headers.get('X-Slack-Request-Timestamp', '')
        signature = request.headers.get('X-Slack-Signature', '')
        
        logger.debug(f"Verifying request signature:")
        logger.debug(f"Timestamp: {timestamp}")
        logger.debug(f"Signature: {signature}")
        logger.debug(f"Signing secret: {slack_signing_secret[:4]}...{slack_signing_secret[-4:]}")

        # Form the base string as Slack does
        sig_basestring = f"v0:{timestamp}:{raw_body}"
        
        # Calculate expected signature
        my_signature = 'v0=' + hmac.new(
            slack_signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()
        
        logger.debug(f"Base string: {sig_basestring}")
        logger.debug(f"Expected signature: {my_signature}")
        logger.debug(f"Received signature: {signature}")
        
        # Compare signatures
        if not hmac.compare_digest(my_signature, signature):
            logger.error("Invalid request signature")
            return jsonify({"error": "Invalid request signature"}), 401

        # Now parse the form data
        data = request.form
        logger.debug(f"Form data: {dict(data)}")
        
        command = data.get('command', '')
        text = data.get('text', '').strip()
        channel_id = data.get('channel_id')
        response_url = data.get('response_url')  # Get the response_url for async responses
        
        logger.info(f"Processing command: {command} with text: {text}")
        
        # Send an immediate acknowledgment
        if command == "/ask":
            # Start a background thread to process the request
            import threading
            thread = threading.Thread(
                target=process_ask_command_async,
                args=(text, channel_id, response_url)
            )
            thread.start()
            
            return jsonify({
                "response_type": "in_channel",
                "text": "Processing your request... This may take a few seconds."
            })
        elif command == "/create-specs":
            return handle_create_specs(data)
        elif command == "/list-models":
            return handle_list_models()
        else:
            logger.warning(f"Unknown command received: {command}")
            return jsonify({
                "response_type": "ephemeral",
                "text": f"Unknown command: {command}"
            })
    except Exception as e:
        logger.exception("Error processing Slack command")
        return jsonify({
            "response_type": "ephemeral",
            "text": f"An error occurred: {str(e)}"
        }), 500
    finally:
        end_time = time.time()
        logger.info(f"Request processing time: {end_time - start_time:.2f} seconds")

def process_ask_command_async(text, channel_id, response_url):
    """Process the /ask command asynchronously and send the response to Slack."""
    try:
        logger.info("Processing /ask command asynchronously")
        logger.debug(f"Text: {text}, Channel ID: {channel_id}")

        if not text:
            logger.warning("No text provided for /ask command")
            send_delayed_response(response_url, {
                "response_type": "ephemeral",
                "text": "Please provide a question or task. Usage: /ask [model] [your question] or share a URL/file to analyze.\nAvailable models: gemini-1.5-pro, gemini-1.5-flash, gemini-2.0-flash"
            })
            return

        # Check if text starts with a valid model name
        valid_models = ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash"]
        model_name = "gemini-1.5-pro"  # Default model
        question = text
        
        # Only try to parse model if the text starts with "gemini-"
        if text.lower().startswith("gemini-"):
            parts = text.split(" ", 1)
            if len(parts) > 1 and parts[0] in valid_models:
                model_name = parts[0]
                question = parts[1]
            
        logger.debug(f"Selected model: {model_name}")
        logger.debug(f"Question: {question}")

        # Initialize the response message
        message_ts = None
        accumulated_text = ""
        
        # Send initial message with question
        initial_blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Model:* {model_name}\n*Question/Task:*\n{question}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Response:*\nThinking..."
                }
            }
        ]
        
        response = send_delayed_response(response_url, {
            "response_type": "in_channel",
            "blocks": initial_blocks
        })
        
        if response and response.ok:
            message_ts = response.json().get('ts')
        
        # Generate streaming response
        logger.info("Generating streaming response using Gemini")
        generation_start = time.time()
        try:
            for chunk in generate_response(question, "", model_name):
                accumulated_text += chunk
                
                # Update the message with accumulated text
                if message_ts:
                    update_blocks = [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"*Model:* {model_name}\n*Question/Task:*\n{question}"
                            }
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "*Response:*\n" + accumulated_text
                            }
                        }
                    ]
                    
                    send_delayed_response(response_url, {
                        "response_type": "in_channel",
                        "blocks": update_blocks,
                        "replace_original": True
                    })
                    
                    # Add a small delay to avoid rate limits
                    time.sleep(0.5)
                    
            logger.debug(f"Response generation time: {time.time() - generation_start:.2f} seconds")
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            send_delayed_response(response_url, {
                "response_type": "ephemeral",
                "text": f"Error generating response: {str(e)}"
            })
            return

    except Exception as e:
        logger.exception("Error in process_ask_command_async")
        send_delayed_response(response_url, {
            "response_type": "ephemeral",
            "text": f"An error occurred: {str(e)}"
        })

def send_delayed_response(response_url, message):
    """Send a delayed response to Slack using the response_url."""
    try:
        logger.info("Sending delayed response to Slack")
        response = requests.post(
            response_url,
            json=message,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        logger.debug("Successfully sent delayed response")
        return response
    except Exception as e:
        logger.error(f"Error sending delayed response: {str(e)}")
        return None

def extract_ticket_key_from_url(url):
    """Extract the Jira ticket key from a URL."""
    try:
        # Parse the URL
        parsed_url = urlparse(url)
        
        # Split the path into components
        path_parts = parsed_url.path.split('/')
        
        # Look for the 'browse' segment and get the next part
        if 'browse' in path_parts:
            browse_index = path_parts.index('browse')
            if browse_index + 1 < len(path_parts):
                return path_parts[browse_index + 1].upper()
        
        # Alternative format: look for ticket key pattern
        for part in path_parts:
            # Match common Jira ticket patterns (e.g., PROJ-123)
            if '-' in part and any(c.isdigit() for c in part):
                return part.upper()
        
        raise ValueError("Could not find ticket key in URL")
        
    except Exception as e:
        raise ValueError(f"Invalid Jira ticket URL: {str(e)}")

def handle_create_specs(data):
    """Handle the /create-specs command."""
    command_text = data.get("text", "").strip()
    if not command_text:
        return jsonify({
            "response_type": "ephemeral",
            "text": "Please provide a Jira ticket URL and optional prompt. Usage: /create-specs https://your-jira.atlassian.net/browse/PROJ-123 [prompt]"
        })

    # Split into URL and optional prompt
    parts = command_text.split(" ", 1)
    ticket_url = parts[0]
    user_prompt = parts[1] if len(parts) > 1 else ""

    try:
        # Extract ticket key from URL
        ticket_key = extract_ticket_key_from_url(ticket_url)
        logger.info(f"Extracted ticket key {ticket_key} from URL {ticket_url}")
        
        # Validate the URL is from the configured Jira instance
        if not ticket_url.startswith(jira_url):
            return jsonify({
                "response_type": "ephemeral",
                "text": f"Error: The provided URL must be from your configured Jira instance ({jira_url})"
            })

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
                "text": f"✅ Successfully added specifications to Jira ticket {ticket_key}\nTicket URL: {ticket_url}"
            })
        else:
            return jsonify({
                "response_type": "ephemeral",
                "text": f"Error adding comment to Jira: {result}"
            })
            
    except ValueError as e:
        return jsonify({
            "response_type": "ephemeral",
            "text": str(e)
        })
    except Exception as e:
        logger.exception("Error in handle_create_specs")
        return jsonify({
            "response_type": "ephemeral",
            "text": f"An unexpected error occurred: {str(e)}"
        })

def handle_list_models():
    """Handle the /list-models command."""
    models = list_gemini_models()
    return jsonify({
        "response_type": "in_channel",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Available Gemini Models:*\n" + models
                }
            }
        ]
    })

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port) 