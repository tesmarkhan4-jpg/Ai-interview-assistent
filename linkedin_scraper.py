import requests
import re

def scrape_linkedin_text(url: str) -> str:
    """
    Attempts to fetch the public text of a LinkedIn profile.
    Returns cleaned text or an empty string if it fails.
    """
    if not url or len(url) < 5:
        return ""

    # Normalize URL
    if not url.startswith("http"):
        url = "https://" + url

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            print(f"[LinkedIn] Could not fetch profile: {response.status_code}")
            return ""

        # Basic text extraction without external BS4 requirement
        html = response.text
        
        # Remove script/style blocks
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
        
        # Convert tags to spaces
        text = re.sub(r'<[^>]+>', ' ', html)
        
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Keep only the relevant middle section (profile data)
        # Truncate to 3000 chars to avoid token overload
        return text[:3000]

    except Exception as e:
        print(f"[LinkedIn] Scrape error: {e}")
        return ""


def enrich_brain_with_linkedin(url: str, groq_client, kb) -> bool:
    """
    Scrapes LinkedIn profile and uses AI to extract structured data
    into the knowledge base. Returns True if successful.
    """
    if not url or len(url.strip()) < 5:
        return False

    print(f"[LinkedIn] Enriching brain from: {url}")
    raw_text = scrape_linkedin_text(url)
    
    if not raw_text or len(raw_text) < 100:
        print("[LinkedIn] No usable data scraped — LinkedIn may require login.")
        return False

    # Use AI to extract structured data
    prompt = (
        "TASK: From this LinkedIn profile HTML text, extract professional data as JSON.\n"
        "FORMAT: { \"headline\": \"\", \"summary\": \"\", \"skills\": [], \"endorsements\": [] }\n"
        "PROFILE TEXT: " + raw_text[:2000]
    )

    try:
        import json
        response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-specdec",
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        
        # Store LinkedIn enrichment in the brain
        kb.add_identity("linkedin_headline", data.get("headline", ""))
        kb.add_identity("linkedin_summary", data.get("summary", ""))
        kb.add_identity("linkedin_skills", ", ".join(data.get("skills", [])))
        kb.add_identity("linkedin_url", url)
        
        print(f"[LinkedIn] Brain enriched with {len(data.get('skills', []))} skills.")
        return True

    except Exception as e:
        print(f"[LinkedIn] AI enrichment error: {e}")
        return False
