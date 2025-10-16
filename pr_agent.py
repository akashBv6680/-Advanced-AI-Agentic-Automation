import os
import requests
import json
from github import Github

# --- Configuration ---
OLLAMA_URL = os.environ.get("OLLAMA_URL")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# --- 1. Robust PR Number and Object Retrieval ---

repo_name = os.environ.get("GITHUB_REPOSITORY")
g = Github(GITHUB_TOKEN)
repo = g.get_repo(repo_name)

# GITHUB_REF is the most reliable way to get the PR number in a pull_request event.
# It is typically formatted as "refs/pull/PR_NUMBER/merge"
github_ref = os.environ.get("GITHUB_REF")
pr_number = None

try:
    # Attempt to extract the PR number from the GITHUB_REF string
    # E.g., "refs/pull/42/merge" -> 42
    if github_ref and github_ref.startswith("refs/pull/"):
        pr_number = int(github_ref.split('/')[2])
except (IndexError, ValueError):
    # If GITHUB_REF parsing fails, try the original GITHUB_EVENT_PATH fallback
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if event_path and os.path.exists(event_path):
        try:
            with open(event_path, 'r') as f:
                event_payload = json.load(f)
                pr_number = event_payload.get('pull_request', {}).get('number')
        except Exception as e:
            print(f"WARNING: Could not parse GITHUB_EVENT_PATH payload: {e}")

if not pr_number:
    print("CRITICAL: Failed to retrieve PR number from both GITHUB_REF and event payload. Exiting.")
    exit(1)

# Now, initialize the Pull Request object using the validated number
pr = repo.get_pull(pr_number)
print(f"Successfully retrieved PR #{pr_number} for review.")


# --- 2. Define LLM Prompt and Structure (Remains the Same) ---
SYSTEM_PROMPT = """You are an expert Senior Software Engineer AI. Your task is to perform a concise code review of the provided Pull Request (PR) diff.
Focus on security, maintainability, and best practices. Respond ONLY with a JSON object that strictly adheres to the following structure:
{
  "summary": "A concise, 1-sentence description of the overall change.",
  "security_risks": ["List any security concerns or anti-patterns found (e.g., hardcoded secrets, unchecked input)."],
  "suggestions": ["List 1-3 specific suggestions for code improvement or best practices (e.g., add logging, use constants)."]
}
Do not include any introductory or concluding text outside of the JSON block. If no risks/suggestions are found, use empty lists."""

# Get the PR content and diff
pr_title = pr.title
pr_diff = pr.get_files() # Get files changed
diff_content = "\n\n".join([f"File: {f.filename}\nDiff:\n{f.patch}\n---" for f in pr_diff])

FULL_PROMPT = f"""PR Title: {pr_title}
--------------------------------------------------
CODE DIFF TO REVIEW:
{diff_content}
"""

def run_ollama_agent():
    """Runs the Ollama model with the structured prompt."""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": FULL_PROMPT,
        "system": SYSTEM_PROMPT,
        "format": "json",
        "stream": False
    }
    
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=300)
        response.raise_for_status()
        
        # Ollama wraps the JSON in a 'response' key
        result_text = response.json().get('response', '')
        
        # Clean up and parse the JSON output
        # Remove markdown fences (```json...```) if they exist
        result_text = result_text.strip().replace('```json', '').replace('```', '')
        
        return json.loads(result_text)
    
    except Exception as e:
        print(f"CRITICAL LLM ERROR: {e}")
        return None

# --- 3. Execute and Post Results (Remains the Same) ---
review_result = run_ollama_agent()

if review_result:
    # Format the reply for the PR comment
    # Ensure all list items are handled even if they are None or malformed
    security_risks_list = review_result.get('security_risks')
    if not isinstance(security_risks_list, list) or not security_risks_list:
        security_risks_list = ['None found.']
    
    suggestions_list = review_result.get('suggestions')
    if not isinstance(suggestions_list, list) or not suggestions_list:
        suggestions_list = ['No specific suggestions.']

    comment_body = f"""## 🤖 AI Code Review Summary

| Field | Details |
| :--- | :--- |
| **Summary** | {review_result.get('summary', 'N/A')} |
| **Security Risks** | <ul>{''.join([f'<li>{item}</li>' for item in security_risks_list])}</ul> |
| **Suggestions** | <ul>{''.join([f'<li>{item}</li>' for item in suggestions_list])}</ul> |

---
*Review powered by {OLLAMA_MODEL}*"""

    # Post the comment to the PR
    pr.create_issue_comment(comment_body)
    print("SUCCESS: AI review comment posted to PR.")
else:
    print("FAILURE: AI agent failed to generate and post a review.")
