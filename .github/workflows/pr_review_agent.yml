name: 🤖 Code Review Agent (LLM)

on:
  pull_request:
    types: [opened, reopened, synchronize] # Runs when a PR is opened or updated

jobs:
  code-review:
    runs-on: ubuntu-latest
    
    # 1. Define Ollama service container
    services:
      ollama_service:
        image: ollama/ollama:latest
        ports:
          - 11434:11434
        options: --name ollama_service

    env:
      OLLAMA_URL: http://localhost:11434/api/generate
      OLLAMA_MODEL: mistral:7b-instruct-v0.2-q4_0
      # GitHub automatically provides this token for API calls
      GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      PYTHONUNBUFFERED: 1

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          
      - name: Install Dependencies
        run: |
          pip install requests PyGithub

      # 2. Pull the LLM Model
      - name: Pull LLM Model
        run: |
          sleep 10 # Wait for Ollama service to start
          docker exec ollama_service ollama pull ${{ env.OLLAMA_MODEL }}

      # 3. Execute the Review Agent Script
      - name: Run Code Review Agent
        run: python pr_agent.py
