# Deployment Guide

This app is a Streamlit application. The recommended internal sharing path is:

1. Push this project to a GitHub repository.
2. Deploy the repository on Streamlit Community Cloud.
3. Configure model and search keys in Streamlit Cloud Secrets, not in Git.

## Streamlit Community Cloud

Use these settings:

- Repository: your GitHub repository for this project
- Branch: `main`
- Main file path: `app.py`
- Python dependencies: `requirements.txt`

## Secrets

Do not commit `.env.local`. It is intentionally ignored by Git.

In Streamlit Cloud, open the app settings and add secrets or environment variables for:

```toml
LLM_PROVIDER = "DeepSeek"
LLM_BASE_URL = "https://api.deepseek.com"
LLM_MODEL = "deepseek-chat"
LLM_API_KEY = "your-deepseek-api-key"
LLM_ENABLED = "true"

WEB_SEARCH_ENABLED = "true"
WEB_SEARCH_PROVIDER = "DuckDuckGo"
WEB_SEARCH_API_KEY = ""
```

If using Tavily for web search:

```toml
WEB_SEARCH_PROVIDER = "Tavily"
WEB_SEARCH_API_KEY = "your-tavily-api-key"
```

## Local Run

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Notes

- Uploaded business data stays in the Streamlit session unless users export reports.
- Generated HTML and Markdown reports are ignored by Git.
- The app does not connect to a production database, MaxCompute, or any company data warehouse in this MVP.
