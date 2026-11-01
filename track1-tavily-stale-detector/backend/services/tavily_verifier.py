import os
from pathlib import Path
from tavily import TavilyClient
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

TAVILY_KEY = os.getenv("TAVILY_API_KEY") or os.environ.get("TAVILY_API_KEY")
tavily = TavilyClient(api_key=TAVILY_KEY)


def search_claim(search_query: str, max_results: int = 5) -> tuple[list[dict], str]:
    """Search live web for evidence about a claim."""
    try:
        response = tavily.search(
            query=search_query,
            search_depth="advanced",
            max_results=max_results,
            include_answer=True,
            include_raw_content=False,
        )
        results = []
        for r in response.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", "")[:500],  # truncate for token efficiency
                "published_date": r.get("published_date", ""),
            })
        return results, response.get("answer", "")
    except Exception as e:
        print(f"[Tavily Search Error] {e}")
        return [], ""
