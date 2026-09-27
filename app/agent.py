# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import datetime
import io
import json
import os
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

import google.auth
from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google import genai
from google.genai import types

from app.a2ui_utils import a2ui_callback

load_dotenv()

# Hardcoded project ID and bucket name as required for Agent Platform compatibility
PROJECT_ID = "qwiklabs-gcp-02-2112d6d9642e"
BUCKET_NAME = "travel-concierge-media-qwiklabs-gcp-02-2112d6d9642e"


async def generate_memories_callback(callback_context: CallbackContext):
    """Callback to extract durable user memories across conversations after each turn."""
    await callback_context.add_session_to_memory()
    return None


def _get_sandbox_code_executor() -> AgentEngineSandboxCodeExecutor | None:
    meta_path = os.path.join(
        os.path.dirname(__file__), "..", "deployment_metadata.json"
    )
    if not os.path.exists(meta_path):
        meta_path = "deployment_metadata.json"

    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r") as f:
                meta = json.load(f)
            runtime_id = meta.get("remote_agent_runtime_id")
            if runtime_id:
                return AgentEngineSandboxCodeExecutor(
                    agent_engine_resource_name=runtime_id
                )
        except Exception as e:
            print(
                f"Warning: Could not initialize AgentEngineSandboxCodeExecutor: {e}"
            )
    return None


def _get_firestore_db() -> firestore.Client:
    credentials, _ = google.auth.default()
    return firestore.Client(project=PROJECT_ID, credentials=credentials)


def list_destinations() -> list[dict]:
    """Retrieve all travel destinations from the catalog database.

    Returns:
        A list of dictionaries representing travel destinations.
    """
    db = _get_firestore_db()
    docs = db.collection("destinations").stream()
    results = []
    for doc in docs:
        data = doc.to_dict()
        results.append(data)
    return results


def search_destinations(category: str = "", max_budget: int = 0) -> list[dict]:
    """Search for travel destinations filtered by category or maximum daily budget.

    Args:
        category: Filter by travel style/category (e.g., 'Culture & History', 'Nature & Adventure', 'Coastal & Luxury').
        max_budget: Filter for destinations with avg_daily_cost_usd <= max_budget. Pass 0 for no budget limit.

    Returns:
        A list of matching destination dictionaries.
    """
    db = _get_firestore_db()
    docs = db.collection("destinations").stream()
    results = []
    for doc in docs:
        data = doc.to_dict()
        match = True
        if category and category.lower() not in data.get("category", "").lower():
            match = False
        if max_budget > 0 and data.get("avg_daily_cost_usd", 0) > max_budget:
            match = False
        if match:
            results.append(data)
    return results


def add_destination(
    name: str,
    category: str,
    description: str,
    best_season: str,
    avg_daily_cost_usd: int,
    popular_activities: list[str],
) -> str:
    """Add a new travel destination to the catalog in Firestore.

    Args:
        name: Name of the destination (e.g., 'Paris, France').
        category: Travel category/style (e.g., 'Romance & Culture').
        description: Summary of the destination attractions and vibe.
        best_season: Best time of year to visit.
        avg_daily_cost_usd: Estimated average daily cost per person in USD.
        popular_activities: List of popular activities to experience.

    Returns:
        Confirmation message with the document ID.
    """
    db = _get_firestore_db()
    doc_id = name.lower().replace(" ", "-").replace(",", "")
    data = {
        "destination_id": doc_id,
        "name": name,
        "category": category,
        "description": description,
        "best_season": best_season,
        "avg_daily_cost_usd": avg_daily_cost_usd,
        "popular_activities": popular_activities,
    }
    db.collection("destinations").document(doc_id).set(data)
    return f"Successfully added destination '{name}' to Firestore database with ID: {doc_id}."


def geocode_address(address: str) -> dict:
    """Turn a location name or street address into geographic coordinates using Google Maps Geocoding API.

    Args:
        address: The address or place name to geocode (e.g. 'Kyoto, Japan', 'Eiffel Tower, Paris').

    Returns:
        A dictionary containing name, formatted address, and location coordinates (latitude, longitude).
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return {
            "error": "GOOGLE_MAPS_API_KEY environment variable is not configured."
        }

    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={urllib.parse.quote(address)}&key={api_key}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())

        if data.get("status") != "OK" or not data.get("results"):
            return {
                "error": f"Geocoding failed for '{address}': {data.get('status')}"
            }

        result = data["results"][0]
        location = result["geometry"]["location"]
        return {
            "name": address,
            "formatted_address": result.get("formatted_address"),
            "location": {
                "latitude": location.get("lat"),
                "longitude": location.get("lng"),
            },
        }
    except Exception as e:
        return {"error": f"Failed to geocode address: {e}"}


def search_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "tourist_attraction",
    radius_meters: float = 5000.0,
) -> list[dict]:
    """Find nearby points of interest or places of a given type near coordinates using Google Places API (New).

    Args:
        latitude: Geographic latitude coordinate.
        longitude: Geographic longitude coordinate.
        place_type: Type of place to search for (e.g. 'tourist_attraction', 'restaurant', 'museum', 'hotel').
        radius_meters: Radius in meters around the center location (default 5000 meters).

    Returns:
        A list of nearby places with name, formatted address, and location coordinates.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return [
            {
                "error": "GOOGLE_MAPS_API_KEY environment variable is not configured."
            }
        ]

    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
    }
    payload = {
        "includedTypes": [place_type],
        "maxResultCount": 10,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": radius_meters,
            }
        },
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())

        places = data.get("places", [])
        results = []
        for p in places:
            results.append({
                "name": p.get("displayName", {}).get("text"),
                "formatted_address": p.get("formattedAddress"),
                "location": p.get("location"),
            })
        return results
    except Exception as e:
        return [{"error": f"Failed to search nearby places: {e}"}]


def get_destination_info(location_name: str) -> dict:
    """Fetch real-time encyclopedic details, description, coordinates, and background information for a travel destination or landmark from Wikipedia.

    Args:
        location_name: Name of the city, country, or landmark (e.g., 'Kyoto', 'Amalfi Coast', 'Eiffel Tower', 'Banff National Park').

    Returns:
        A dictionary containing title, description, summary extract, coordinates, thumbnail image URL, and official article link.
    """
    user_agent = os.getenv(
        "WIKIPEDIA_USER_AGENT",
        "TravelConciergeAgent/1.0 (contact@travelconcierge.local)",
    )
    formatted_query = location_name.strip().replace(" ", "_")
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(formatted_query)}"

    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            return {
                "title": data.get("title"),
                "description": data.get("description"),
                "summary": data.get("extract"),
                "coordinates": data.get("coordinates"),
                "thumbnail_url": data.get("thumbnail", {}).get("source"),
                "page_url": data.get("content_urls", {})
                .get("desktop", {})
                .get("page"),
            }
    except Exception as e:
        return {"error": f"Failed to fetch details for '{location_name}': {e}"}


async def generate_destination_image(
    item_name: str,
    prompt: str,
    tool_context: ToolContext,
) -> str:
    """Generate an image for a travel destination or item using gemini-3.1-flash-lite-image in the global region.

    Saves the generated image as an artifact in the Playground panel using tool_context.save_artifact
    and uploads the image bytes to public Cloud Storage returning the public HTTP URL.

    Args:
        item_name: Name of the travel destination or item (e.g., 'Banff National Park', 'Kyoto Pagoda').
        prompt: Detailed prompt describing the image scene to generate.
        tool_context: ADK ToolContext injected automatically.

    Returns:
        Public HTTP URL (https://storage.googleapis.com/travel-concierge-media-qwiklabs-gcp-02-2112d6d9642e/<object>) of the generated image.
    """
    try:
        client = genai.Client(
            vertexai=True, project=PROJECT_ID, location="global"
        )
        full_prompt = (
            f"A scenic, high-quality travel image of {item_name}: {prompt}"
        )
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=full_prompt,
        )

        if not response.candidates or not response.candidates[0].content.parts:
            return "Failed to generate image: No content generated."

        image_bytes = None
        mime_type = "image/jpeg"
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                image_bytes = part.inline_data.data
                if part.inline_data.mime_type:
                    mime_type = part.inline_data.mime_type
                break

        if not image_bytes:
            return "Failed to extract generated image bytes from model response."

        clean_id = item_name.lower().replace(" ", "_").replace(",", "")
        ext = "png" if "png" in mime_type else "jpg"
        filename = f"{clean_id}.{ext}"

        # 1. Save artifact into Playground Artifacts panel
        artifact_part = types.Part.from_bytes(
            data=image_bytes, mime_type=mime_type
        )
        await tool_context.save_artifact(
            filename=filename, artifact=artifact_part
        )

        # 2. Upload image bytes to public Cloud Storage bucket
        credentials, _ = google.auth.default()
        storage_client = storage.Client(
            project=PROJECT_ID, credentials=credentials
        )
        bucket = storage_client.bucket(BUCKET_NAME)
        object_path = f"generated_images/{filename}"
        blob = bucket.blob(object_path)
        blob.upload_from_string(image_bytes, content_type=mime_type)

        public_url = (
            f"https://storage.googleapis.com/{BUCKET_NAME}/{object_path}"
        )
        return public_url
    except Exception as e:
        return f"Error generating destination image: {e}"


async def generate_destination_video(
    item_name: str,
    prompt: str,
    tool_context: ToolContext,
) -> str:
    """Generate a short video preview for a travel destination or item using gemini-omni-flash-preview in the global region.

    Saves the generated video as an artifact in the Playground panel using tool_context.save_artifact
    and uploads the video bytes directly to public Cloud Storage returning the public HTTP URL.

    Args:
        item_name: Name of the travel destination or item (e.g., 'Kyoto Bamboo Grove', 'Banff Lake Louise').
        prompt: Detailed prompt describing the video scene to generate.
        tool_context: ADK ToolContext injected automatically.

    Returns:
        Public HTTP URL (https://storage.googleapis.com/travel-concierge-media-qwiklabs-gcp-02-2112d6d9642e/<object>) of the generated video.
    """
    try:
        client = genai.Client(
            vertexai=True, project=PROJECT_ID, location="global"
        )
        full_prompt = (
            f"A short 3-second scenic travel video of {item_name}: {prompt}"
        )
        interaction = client.interactions.create(
            model="gemini-omni-flash-preview",
            input=full_prompt,
        )

        video_bytes = None
        if hasattr(interaction, "output_video") and interaction.output_video:
            data = getattr(interaction.output_video, "data", None)
            if data:
                if isinstance(data, bytes):
                    video_bytes = data
                elif isinstance(data, str):
                    try:
                        video_bytes = base64.b64decode(data)
                    except Exception:
                        video_bytes = data.encode("utf-8")

        if not video_bytes:
            return "Failed to extract generated video bytes from model response."

        clean_id = item_name.lower().replace(" ", "_").replace(",", "")
        filename = f"{clean_id}_video.mp4"
        mime_type = "video/mp4"

        # 1. Save artifact into Playground Artifacts panel
        artifact_part = types.Part.from_bytes(
            data=video_bytes, mime_type=mime_type
        )
        await tool_context.save_artifact(
            filename=filename, artifact=artifact_part
        )

        # 2. Upload video bytes to public Cloud Storage bucket without writing to local disk
        credentials, _ = google.auth.default()
        storage_client = storage.Client(
            project=PROJECT_ID, credentials=credentials
        )
        bucket = storage_client.bucket(BUCKET_NAME)
        object_path = f"generated_videos/{filename}"
        blob = bucket.blob(object_path)
        blob.upload_from_string(video_bytes, content_type=mime_type)

        public_url = (
            f"https://storage.googleapis.com/{BUCKET_NAME}/{object_path}"
        )
        return public_url
    except Exception as e:
        return f"Error generating destination video: {e}"


def convert_currency(
    amount: float, from_currency: str = "USD", to_currency: str = "EUR"
) -> str:
    """Convert a monetary amount from one currency to another using live foreign exchange rates.

    Args:
        amount: The numerical monetary amount to convert.
        from_currency: 3-letter currency code to convert from (e.g., 'USD', 'EUR', 'GBP').
        to_currency: 3-letter currency code to convert to (e.g., 'JPY', 'EUR', 'GBP', 'CAD', 'AUD').

    Returns:
        A string summarizing the conversion result and rate.
    """
    from_code = from_currency.upper().strip()
    to_code = to_currency.upper().strip()
    url = f"https://open.er-api.com/v6/latest/{from_code}"

    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "TravelConciergeAgent/1.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())

        if data.get("result") != "success":
            return f"Error fetching exchange rates for base currency '{from_code}'."

        rates = data.get("rates", {})
        if to_code not in rates:
            return f"Currency '{to_code}' is not supported."

        rate = rates[to_code]
        converted_amount = amount * rate
        last_updated = data.get("time_last_update_utc", "Recently")

        return (
            f"{amount:,.2f} {from_code} = {converted_amount:,.2f} {to_code} "
            f"(Exchange rate: 1 {from_code} = {rate:,.4f} {to_code}, updated: {last_updated})"
        )
    except Exception as e:
        return f"Failed to retrieve live exchange rates: {e}"


def get_weather(query: str) -> str:
    """Simulates a web search to get weather information.

    Args:
        query: Location query string.

    Returns:
        A string with simulated weather information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting current time for a location.

    Args:
        query: Location query string.

    Returns:
        Current time string.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        tz_identifier = "UTC"

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


_schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = _schema_manager.generate_system_prompt(
    role_description="You are the Travel Concierge AI Assistant. You help users discover, search, and manage travel destinations and itineraries.",
    workflow_description=(
        "Analyze the request and return structured UI when appropriate. "
        "You remember all stated user preferences, dietary restrictions, food/drug/environmental allergies, and travel history from previous conversations and use them to personalize responses across sessions. "
        "Always pay strict attention to any allergies mentioned by the user (e.g., peanut, shellfish, gluten, penicillin, etc.), store them into long-term memory, and ensure all recommended destinations, activities, and places strictly accommodate those allergies. "
        "Use geocode_address to get exact coordinates for an address or city. "
        "Use search_nearby_places to search for nearby tourist attractions, museums, or restaurants using Google Places. "
        "Use get_destination_info to fetch real Wikipedia background details for destinations. "
        "Use your Firestore tools (list_destinations, search_destinations, add_destination) to query or update the database. "
        "Use convert_currency for live currency conversions. "
        "Use generate_destination_image to generate destination images saved as artifacts and uploaded to Cloud Storage. "
        "Use generate_destination_video to generate destination videos saved as artifacts and uploaded to Cloud Storage using gemini-omni-flash-preview. "
        "You can also safely execute Python code in your Agent Engine sandbox code execution environment when data analysis or calculations are required."
    ),
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    code_executor=_get_sandbox_code_executor(),
    instruction=instruction,
    tools=[
        PreloadMemoryTool(),
        geocode_address,
        search_nearby_places,
        list_destinations,
        search_destinations,
        add_destination,
        get_destination_info,
        generate_destination_image,
        generate_destination_video,
        convert_currency,
        get_weather,
        get_current_time,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
