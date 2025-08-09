import asyncio
from typing import Annotated
import os
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.providers.bearer import BearerAuthProvider, RSAKeyPair
from mcp import ErrorData, McpError
from mcp.server.auth.provider import AccessToken
from mcp.types import TextContent, ImageContent, INVALID_PARAMS, INTERNAL_ERROR
from pydantic import BaseModel, Field, AnyUrl

import markdownify
import httpx
import readabilipy

# --- Load environment variables ---
load_dotenv()

TOKEN = os.environ.get("AUTH_TOKEN")
MY_NUMBER = os.environ.get("MY_NUMBER")

assert TOKEN is not None, "Please set AUTH_TOKEN in your .env file"
assert MY_NUMBER is not None, "Please set MY_NUMBER in your .env file"

# --- Auth Provider ---
class SimpleBearerAuthProvider(BearerAuthProvider):
    def __init__(self, token: str):
        k = RSAKeyPair.generate()
        super().__init__(public_key=k.public_key, jwks_uri=None, issuer=None, audience=None)
        self.token = token

    async def load_access_token(self, token: str) -> AccessToken | None:
        if token == self.token:
            return AccessToken(
                token=token,
                client_id="puch-client",
                scopes=["*"],
                expires_at=None,
            )
        return None

# --- Rich Tool Description model ---
class RichToolDescription(BaseModel):
    description: str
    use_when: str
    side_effects: str | None = None

# --- Fetch Utility Class ---
class Fetch:
    USER_AGENT = "Puch/1.0 (Autonomous)"

    @classmethod
    async def fetch_url(
        cls,
        url: str,
        user_agent: str,
        force_raw: bool = False,
    ) -> tuple[str, str]:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    follow_redirects=True,
                    headers={"User-Agent": user_agent},
                    timeout=30,
                )
            except httpx.HTTPError as e:
                raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Failed to fetch {url}: {e!r}"))

            if response.status_code >= 400:
                raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Failed to fetch {url} - status code {response.status_code}"))

            page_raw = response.text

        content_type = response.headers.get("content-type", "")
        is_page_html = "text/html" in content_type

        if is_page_html and not force_raw:
            return cls.extract_content_from_html(page_raw), ""

        return (
            page_raw,
            f"Content type {content_type} cannot be simplified to markdown, but here is the raw content:\n",
        )

    @staticmethod
    def extract_content_from_html(html: str) -> str:
        """Extract and convert HTML content to Markdown format."""
        ret = readabilipy.simple_json.simple_json_from_html_string(html, use_readability=True)
        if not ret or not ret.get("content"):
            return "<error>Page failed to be simplified from HTML</error>"
        content = markdownify.markdownify(ret["content"], heading_style=markdownify.ATX)
        return content

    @staticmethod
    async def google_search_links(query: str, num_results: int = 5) -> list[str]:
        """
        Perform a scoped DuckDuckGo search and return a list of job posting URLs.
        (Using DuckDuckGo because Google blocks most programmatic scraping.)
        """
        ddg_url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
        links = []

        async with httpx.AsyncClient() as client:
            resp = await client.get(ddg_url, headers={"User-Agent": Fetch.USER_AGENT})
            if resp.status_code != 200:
                return ["<error>Failed to perform search.</error>"]

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", class_="result__a", href=True):
            href = a["href"]
            if "http" in href:
                links.append(href)
            if len(links) >= num_results:
                break

        return links or ["<error>No results found.</error>"]

# --- MCP Server Setup ---
mcp = FastMCP(
    "Job Finder MCP Server",
    auth=SimpleBearerAuthProvider(TOKEN),
)

# --- Tool: validate (required by Puch) ---
@mcp.tool
async def validate() -> str:
    return MY_NUMBER

# --- Tool: job_finder (now smart!) ---
JobFinderDescription = RichToolDescription(
    description="Smart job tool: analyze descriptions, fetch URLs, or search jobs based on free text.",
    use_when="Use this to evaluate job descriptions or search for jobs using freeform goals.",
    side_effects="Returns insights, fetched job descriptions, or relevant job links.",
)

@mcp.tool(description=JobFinderDescription.model_dump_json())
async def job_finder(
    user_goal: Annotated[str, Field(description="The user's goal (can be a description, intent, or freeform query)")],
    job_description: Annotated[str | None, Field(description="Full job description text, if available.")] = None,
    job_url: Annotated[AnyUrl | None, Field(description="A URL to fetch a job description from.")] = None,
    raw: Annotated[bool, Field(description="Return raw HTML content if True")] = False,
) -> str:
    """
    Handles multiple job discovery methods: direct description, URL fetch, or freeform search query.
    """
    if job_description:
        return (
            f"📝 **Job Description Analysis**\n\n"
            f"---\n{job_description.strip()}\n---\n\n"
            f"User Goal: **{user_goal}**\n\n"
            f"💡 Suggestions:\n- Tailor your resume.\n- Evaluate skill match.\n- Consider applying if relevant."
        )

    if job_url:
        content, _ = await Fetch.fetch_url(str(job_url), Fetch.USER_AGENT, force_raw=raw)
        return (
            f"🔗 **Fetched Job Posting from URL**: {job_url}\n\n"
            f"---\n{content.strip()}\n---\n\n"
            f"User Goal: **{user_goal}**"
        )

    if "look for" in user_goal.lower() or "find" in user_goal.lower():
        links = await Fetch.google_search_links(user_goal)
        return (
            f"🔍 **Search Results for**: _{user_goal}_\n\n" +
            "\n".join(f"- {link}" for link in links)
        )

    raise McpError(ErrorData(code=INVALID_PARAMS, message="Please provide either a job description, a job URL, or a search query in user_goal."))

from datetime import datetime
from typing import Annotated
from pydantic import Field

@mcp.tool(
    description="Zodiac + uplifting timeline: enter your birthdate (YYYY-MM-DD), and I’ll share your sign, marriage age range, potential success ages, and a warm message from the stars."
)
async def astro_timeline(
    birthdate: Annotated[str, Field(description="Your birthdate, format YYYY-MM-DD, e.g. 2002-08-09")],
) -> str:
    try:
        dt = datetime.strptime(birthdate.strip(), "%Y-%m-%d")
    except Exception:
        return "Please enter your birthdate in YYYY-MM-DD format (e.g. 2002-08-09)."

    m, d = dt.month, dt.day

    def zodiac_from_md(m, d):
        if (m == 3 and d >= 21) or (m == 4 and d <= 19): return "Aries"
        if (m == 4 and d >= 20) or (m == 5 and d <= 20): return "Taurus"
        if (m == 5 and d >= 21) or (m == 6 and d <= 20): return "Gemini"
        if (m == 6 and d >= 21) or (m == 7 and d <= 22): return "Cancer"
        if (m == 7 and d >= 23) or (m == 8 and d <= 22): return "Leo"
        if (m == 8 and d >= 23) or (m == 9 and d <= 22): return "Virgo"
        if (m == 9 and d >= 23) or (m == 10 and d <= 22): return "Libra"
        if (m == 10 and d >= 23) or (m == 11 and d <= 21): return "Scorpio"
        if (m == 11 and d >= 22) or (m == 12 and d <= 21): return "Sagittarius"
        if (m == 12 and d >= 22) or (m == 1 and d <= 19): return "Capricorn"
        if (m == 1 and d >= 20) or (m == 2 and d <= 18): return "Aquarius"
        return "Pisces"

    sign = zodiac_from_md(m, d)

    marriage_ranges = {
        "Aries": "25–30", "Taurus": "22–28", "Gemini": "24–29", "Cancer": "24–30",
        "Leo": "26–32", "Virgo": "28–35", "Libra": "24–30", "Scorpio": "27–35",
        "Sagittarius": "25–33", "Capricorn": "28–35", "Aquarius": "26–34", "Pisces": "24–30"
    }

    success_ages = {
        "Aries": "23, 30, 38", "Taurus": "28, 35, 40", "Gemini": "22, 29, 36", "Cancer": "27, 34, 40",
        "Leo": "20, 28, 35", "Virgo": "19, 27, 35", "Libra": "26, 33, 40", "Scorpio": "25, 33, 40",
        "Sagittarius": "24, 30, 38", "Capricorn": "30, 38", "Aquarius": "27, 35, 40", "Pisces": "23, 31, 39"
    }

    traits = {
        "Aries": "You’ve moved forward with bold intention, even on harder days.\nThat spark inside you gently grows—it’s building toward something bright.\nTrust your momentum—it’s your journey unfolding toward light and smile.",
        "Taurus": "You’ve patient-crafted beauty and strength from quiet persistence.\nSoon, that grounded growth lifts you—solid, seen, deeply rooted.\nTrust the peace within—it’s blossoming into calm joy.",
        "Gemini": "Your curiosity has sparked many ideas, even when clarity felt distant.\nSoon, those inspired thoughts will coalesce into purpose and warmth.\nLet wonder guide you—it’s weaving meaning and smiles.",
        "Cancer": "Your care has comforted quietly, from the heart toward others.\nSoon, that kindness returns as gentle light surrounding you.\nYou’re seen, you’re felt, and your warmth invites a soft smile.",
        "Leo": "You’ve glowed in little ways—as creativity, as kindness, as courage.\nSoon that inner light shines outward—noticed, appreciated, radiant.\nLet yourself be seen—you’re radiance is meant to spread joy.",
        "Virgo": "You have been refining, shaping, and caring in the small thankless ways.\nSoon, that thoughtful precision becomes recognition and gentle pride.\nYour quiet mastery blooms—softly, powerfully, into success.",
        "Libra": "You’ve balanced and soothed, harmonizing worlds with your grace.\nSoon, that harmony circles back to you—calm, mirrored, comforting.\nYou’re bridge, you’re calm, and your presence brings smiles.",
        "Scorpio": "You’ve navigated depths with courage—braving truth and feeling.\nSoon, that clarity becomes your strength, steady and sure.\nYour depth is power—and it’s lighting your path forward.",
        "Sagittarius": "Your spirit has wandered far—through dreams, ideas, distant places.\nSoon, that wanderlust turns into direction and laughter.\nYour journey unfolds with purpose—and joy is waiting there.",
        "Capricorn": "You’ve climbed with steady steps toward a future only you see.\nSoon, your work becomes visible, honored, and quietly celebrated.\nYou’ve shaped success from effort—it’s emerging, and it feels warm.",
        "Aquarius": "You’ve dreamed beyond now—ideas sparkling with possibility.\nSoon, those ideas find audience, connection, and movement.\nYour vision matters—it’s gently ushering change and smiles.",
        "Pisces": "You feel deeply, dreaming from the heart into the world.\nSoon, that empathy guides you to beauty made real, tender, true.\nYour intuition is compass—and it’s pointing toward gentle joy.",
    }

    msg = (
        f"You are a *{sign}*.\n\n"
        f"🔮 *Likely marriage (under 35):* {marriage_ranges.get(sign, '—')}.\n"
        f"🚀 *Potential success ages (under 40):* {success_ages.get(sign, '—')}.\n\n"
        f"{traits.get(sign, '')}"
    )
    return msg

# Image inputs and sending images

MAKE_IMG_BLACK_AND_WHITE_DESCRIPTION = RichToolDescription(
    description="Convert an image to black and white and save it.",
    use_when="Use this tool when the user provides an image URL and requests it to be converted to black and white.",
    side_effects="The image will be processed and saved in a black and white format.",
)

@mcp.tool(description=MAKE_IMG_BLACK_AND_WHITE_DESCRIPTION.model_dump_json())
async def make_img_black_and_white(
    puch_image_data: Annotated[str, Field(description="Base64-encoded image data to convert to black and white")] = None,
) -> list[TextContent | ImageContent]:
    import base64
    import io

    from PIL import Image

    try:
        image_bytes = base64.b64decode(puch_image_data)
        image = Image.open(io.BytesIO(image_bytes))

        bw_image = image.convert("L")

        buf = io.BytesIO()
        bw_image.save(buf, format="PNG")
        bw_bytes = buf.getvalue()
        bw_base64 = base64.b64encode(bw_bytes).decode("utf-8")

        return [ImageContent(type="image", mimeType="image/png", data=bw_base64)]
    except Exception as e:
        raise McpError(ErrorData(code=INTERNAL_ERROR, message=str(e)))

# --- Run MCP Server ---
async def main():
    print("🚀 Starting MCP server on http://0.0.0.0:8086")
    await mcp.run_async("streamable-http", host="0.0.0.0", port=8086)

if __name__ == "__main__":
    asyncio.run(main())
