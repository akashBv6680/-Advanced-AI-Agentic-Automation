import os
import requests
import json
from github import Github

# --- Configuration ---
OLLAMA_URL = os.environ.get("OLLAMA_URL")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# PR Context from GitHub Actions
repo_name = os.environ.get("GITHUB_REPOSITORY")
pr_number = os.environ.get("GITHUB_EVENT_PULL_REQUEST_NUMBER") or \
            json.loads(os.environ.get("GITHUB_EVENT_PATH")).get('pull_request', {}).get('number')

if not pr_number:
    print("CRITICAL: Could not determine PR number. Exiting.")
    exit(0)

# Initialize GitHub API
g = Github(GITHUB_TOKEN)
repo = g.get_repo(repo_name)
pr = repo.get_pull(pr_number)

# --- 1. Define LLM Prompt and Structure ---
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

# --- 2. Execute and Post Results ---
review_result = run_ollama_agent()

if review_result:
    # Format the reply for the PR comment
    comment_body = f"""## 🤖 AI Code Review Summary

| Field | Details |
| :--- | :--- |
| **Summary** | {review_result.get('summary', 'N/A')} |
| **Security Risks** | <ul>{''.join([f'<li>{item}</li>' for item in review_result.get('security_risks', ['None found.'])])}</ul> |
| **Suggestions** | <ul>{''.join([f'<li>{item}</li>' for item in review_result.get('suggestions', ['No specific suggestions.'])])}</ul> |

---
*Review powered by {OLLAMA_MODEL}*"""

    # Post the comment to the PR
    pr.create_issue_comment(comment_body)
    print("SUCCESS: AI review comment posted to PR.")
else:
    print("FAILURE: AI agent failed to generate and post a review.")
