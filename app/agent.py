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

import datetime
import json
import os
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

import dotenv
dotenv.load_dotenv()

from google import genai
from a2ui.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog
from app.a2ui_utils import a2ui_callback
from google.adk.agents.callback_context import CallbackContext
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

# Hardcoded GCP Project ID and GCS Bucket Name for Agent Platform compatibility
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-01-580706c5bcf8"
GCS_BUCKET_NAME = "travel-concierge-media-qwiklabs-gcp-01-580706c5bcf8"

# Resolve Agent Engine resource name from deployment_metadata.json for AgentEngineSandboxCodeExecutor and Memory Bank
deployment_metadata_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "deployment_metadata.json"
)
agent_engine_resource_name = "projects/406128335446/locations/us-central1/reasoningEngines/8511565251462823936"

if os.path.exists(deployment_metadata_path):
    try:
        with open(deployment_metadata_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
            if meta.get("remote_agent_runtime_id"):
                agent_engine_resource_name = meta["remote_agent_runtime_id"]
    except Exception:
        pass

MEMORY_BANK_ID = agent_engine_resource_name.split("/")[-1]

sandbox_code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=agent_engine_resource_name
)

# Configure Vertex AI Memory Bank Service for app/redeployment wiring
memory_service = VertexAiMemoryBankService(
    project=FIRESTORE_PROJECT_ID,
    location="us-central1",
    agent_engine_id=MEMORY_BANK_ID,
)


async def generate_memories_callback(callback_context: CallbackContext):
    """WRITE: Send session events to Memory Bank for extraction after each turn."""
    await callback_context.add_session_to_memory()
    return None


db = firestore.Client(project=FIRESTORE_PROJECT_ID)
destinations_ref = db.collection("destinations")
itineraries_ref = db.collection("user_itineraries")

storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
genai_image_client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT_ID, location="global")


def save_user_itinerary(
    destination_id: str,
    trip_title: str,
    duration_days: int,
    activities: list[str]
) -> str:
    """Save a customized trip itinerary to the user's saved itineraries in Firestore.

    Args:
        destination_id: The destination ID (e.g., 'kyoto-japan').
        trip_title: A descriptive title for the trip (e.g., '4-Day Cultural Highlights in Kyoto').
        duration_days: Duration of the trip in days.
        activities: List of planned daily activities or itinerary highlights.

    Returns:
        Confirmation message with the generated itinerary ID.
    """
    doc_id = f"itinerary-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    data = {
        "id": doc_id,
        "destination_id": destination_id,
        "trip_title": trip_title,
        "duration_days": int(duration_days),
        "activities": activities,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    itineraries_ref.document(doc_id).set(data)
    return f"Successfully saved itinerary '{trip_title}' (ID: {doc_id}) with {duration_days} days of activities to Firestore!"


def search_destinations(query: str = "", category: str = "") -> str:
    """Search for destinations in the Firestore database.

    Args:
        query: Optional search keyword to filter by name, city, country, or tags.
        category: Optional category filter (e.g., 'Culture', 'Nature', 'Landmarks', 'Food & Art').

    Returns:
        A list of matching destinations with basic summary info.
    """
    docs = destinations_ref.stream()
    results = []
    
    query_lower = query.lower().strip()
    category_lower = category.lower().strip()

    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        
        # Check category match
        if category_lower and category_lower not in data.get("category", "").lower():
            continue

        # Check keyword search match
        if query_lower:
            text_to_search = f"{data.get('name', '')} {data.get('city', '')} {data.get('country', '')} {data.get('description', '')} {' '.join(data.get('tags', []))}".lower()
            if query_lower not in text_to_search:
                continue

        results.append(data)

    if not results:
        return f"No destinations found matching query: '{query}' and category: '{category}'."

    summary_lines = [f"Found {len(results)} destination(s):"]
    for dest in results:
        summary_lines.append(
            f"- [{dest['id']}] {dest['name']} in {dest['city']}, {dest['country']} | Category: {dest['category']} | Avg Cost: ${dest.get('average_cost_per_day_usd', 0)}/day"
        )
    return "\n".join(summary_lines)


def get_destination_details(destination_id: str) -> str:
    """Retrieve full details for a specific destination by its ID from Firestore.

    Args:
        destination_id: The document ID of the destination (e.g., 'kyoto-japan', 'paris-france').

    Returns:
        Detailed information about the destination.
    """
    doc_ref = destinations_ref.document(destination_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        return f"Destination with ID '{destination_id}' was not found in Firestore."

    data = doc.to_dict()
    details = [
        f"ID: {doc.id}",
        f"Name: {data.get('name')}",
        f"Location: {data.get('city')}, {data.get('country')}",
        f"Category: {data.get('category')}",
        f"Description: {data.get('description')}",
        f"Best Season: {data.get('best_season')}",
        f"Average Cost/Day: ${data.get('average_cost_per_day_usd')}",
        f"Tags: {', '.join(data.get('tags', []))}"
    ]
    return "\n".join(details)


def add_destination(
    destination_id: str,
    name: str,
    city: str,
    country: str,
    category: str,
    description: str,
    best_season: str = "Year-round",
    average_cost_per_day_usd: float = 150.0
) -> str:
    """Add or update a destination item in the Firestore database.

    Args:
        destination_id: Unique string key for the destination (e.g. 'rome-italy').
        name: Full name of the destination experience.
        city: City location.
        country: Country location.
        category: Primary category (e.g. 'Culture', 'Nature', 'Food').
        description: A rich description of the destination.
        best_season: Recommended time of year to visit.
        average_cost_per_day_usd: Estimated daily budget in USD.

    Returns:
        Confirmation message.
    """
    dest_data = {
        "id": destination_id,
        "name": name,
        "city": city,
        "country": country,
        "category": category,
        "description": description,
        "best_season": best_season,
        "average_cost_per_day_usd": float(average_cost_per_day_usd),
        "tags": [category.lower(), city.lower(), country.lower()]
    }
    
    destinations_ref.document(destination_id).set(dest_data)
    return f"Successfully saved destination '{name}' ({destination_id}) to Firestore database!"


def fetch_destination_live_weather(location_name: str) -> str:
    """Fetch real live weather conditions and coordinates for any travel destination using the Open-Meteo public API.

    Args:
        location_name: City or destination name (e.g., 'Kyoto', 'Paris', 'San Francisco', 'Rio de Janeiro').

    Returns:
        Live weather summary including temperature (°C / °F), wind speed, and location details.
    """
    api_key = os.environ.get("OPEN_METEO_API_KEY", "").strip()

    # Step 1: Geocode location to lat/lon
    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(location_name)}&count=1"
    if api_key:
        geo_url += f"&apikey={api_key}"

    req = urllib.request.Request(geo_url, headers={"User-Agent": "TravelConciergeAgent/1.0"})
    try:
        with urllib.request.urlopen(req) as resp:
            geo_data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return f"Error connecting to Open-Meteo geocoding API: {e}"

    results = geo_data.get("results")
    if not results:
        return f"Could not locate destination '{location_name}' via Open-Meteo geocoding API."

    location = results[0]
    lat = location["latitude"]
    lon = location["longitude"]
    city = location.get("name", location_name)
    country = location.get("country", "")

    # Step 2: Fetch live weather forecast
    wx_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
    if api_key:
        wx_url += f"&apikey={api_key}"

    req_wx = urllib.request.Request(wx_url, headers={"User-Agent": "TravelConciergeAgent/1.0"})
    try:
        with urllib.request.urlopen(req_wx) as resp_wx:
            wx_data = json.loads(resp_wx.read().decode("utf-8"))
    except Exception as e:
        return f"Error fetching live weather data from Open-Meteo API: {e}"

    current = wx_data.get("current_weather", {})
    temp_c = current.get("temperature", 0)
    temp_f = round((temp_c * 9 / 5) + 32, 1)
    windspeed = current.get("windspeed", 0)

    return (
        f"Live Weather for {city}, {country} (Lat: {lat}, Lon: {lon}):\n"
        f"• Temperature: {temp_c}°C ({temp_f}°F)\n"
        f"• Wind Speed: {windspeed} km/h\n"
        f"• Observation Time: {current.get('time', 'N/A')} UTC"
    )


def geocode_address(address: str) -> str:
    """Convert an address, place name, or landmark into geographic coordinates (latitude and longitude) using Google Maps Geocoding API.

    Args:
        address: The address, landmark, or location string to geocode (e.g., 'Kyoto Station', 'Eiffel Tower', 'Golden Gate Bridge').

    Returns:
        Formatted location details including full formatted address, latitude, and longitude.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY is not configured in environment variables."

    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={urllib.parse.quote(address)}&key={api_key}"
    req = urllib.request.Request(url, headers={"User-Agent": "TravelConciergeAgent/1.0"})
    
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return f"Error calling Google Maps Geocoding API: {e}"

    if data.get("status") != "OK" or not data.get("results"):
        return f"Geocoding API failed with status '{data.get('status')}' for address: '{address}'."

    first_result = data["results"][0]
    formatted_address = first_result.get("formatted_address", address)
    location = first_result.get("geometry", {}).get("location", {})
    lat = location.get("lat")
    lng = location.get("lng")

    return (
        f"Geocoding result for '{address}':\n"
        f"• Address: {formatted_address}\n"
        f"• Latitude: {lat}\n"
        f"• Longitude: {lng}"
    )


def search_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "tourist_attraction",
    radius_meters: float = 2000.0
) -> str:
    """Search for nearby points of interest (attractions, restaurants, museums, lodging, etc.) near coordinates using Google Places API (New).

    Args:
        latitude: Center point latitude.
        longitude: Center point longitude.
        place_type: Type of places to search for (e.g., 'tourist_attraction', 'restaurant', 'museum', 'lodging', 'park').
        radius_meters: Search radius in meters (default is 2000m / 2km).

    Returns:
        List of nearby places with name, formatted address, location coordinates, and rating.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY is not configured in environment variables."

    url = "https://places.googleapis.com/v1/places:searchNearby"
    body = {
        "includedTypes": [place_type],
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": float(latitude),
                    "longitude": float(longitude)
                },
                "radius": float(radius_meters)
            }
        }
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.types,places.rating"
    }

    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return f"Error calling Google Places API (New): {e}"

    places = data.get("places", [])
    if not places:
        return f"No nearby places of type '{place_type}' found within {radius_meters}m of ({latitude}, {longitude})."

    results_lines = [f"Found {len(places)} nearby place(s) of type '{place_type}':"]
    for p in places[:10]:
        display_name = p.get("displayName", {}).get("text", "Unknown Name")
        address = p.get("formattedAddress", "No address provided")
        loc = p.get("location", {})
        rating = p.get("rating", "N/A")
        results_lines.append(
            f"- {display_name} | Address: {address} | Location: ({loc.get('latitude')}, {loc.get('longitude')}) | Rating: {rating}"
        )

    return "\n".join(results_lines)


def generate_destination_image(prompt: str, tool_context: ToolContext) -> str:
    """Generate a high-quality travel image using gemini-3.1-flash-lite-image in the global region, save it as an artifact, and upload it to public Cloud Storage.

    Args:
        prompt: Detailed description of the travel destination or experience image to generate (e.g., 'Scenic view of Kyoto temple during autumn season').
        tool_context: ToolContext instance injected by ADK to save artifacts to the Playground panel.

    Returns:
        The public HTTPS URL of the uploaded image in Cloud Storage (https://storage.googleapis.com/<bucket>/<filename>).
    """
    try:
        response = genai_image_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt
        )
    except Exception as e:
        return f"Error generating image with gemini-3.1-flash-lite-image: {e}"

    image_bytes = None
    mime_type = "image/jpeg"

    if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                image_bytes = part.inline_data.data
                if part.inline_data.mime_type:
                    mime_type = part.inline_data.mime_type
                break

    if not image_bytes:
        return f"Failed to extract generated image bytes for prompt: '{prompt}'."

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_slug = "".join(c if c.isalnum() else "_" for c in prompt[:20].lower()).strip("_")
    filename = f"destination_{clean_slug}_{timestamp}.jpg"

    # (1) Save artifact so it shows up in Playground's Artifacts panel
    try:
        artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        tool_context.save_artifact(filename=filename, artifact=artifact_part)
    except Exception:
        pass

    # (2) Upload image bytes to public Cloud Storage bucket and return public https URL
    try:
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type=mime_type)
        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
        return public_url
    except Exception as e:
        return f"Error uploading image bytes to Cloud Storage bucket '{GCS_BUCKET_NAME}': {e}"


def generate_destination_video(prompt: str, tool_context: ToolContext) -> str:
    """Generate a short travel video for a destination or experience using Google's Omni model (gemini-omni-flash-preview) in the global region, save it as an artifact, and upload it to public Cloud Storage.

    Args:
        prompt: Detailed description of the travel destination or experience video to generate (e.g., 'A cinematic short video of sunset over Kyoto temple garden').
        tool_context: ToolContext instance injected by ADK to save artifacts to the Playground panel.

    Returns:
        The public HTTPS URL of the uploaded video in Cloud Storage (https://storage.googleapis.com/<bucket>/<filename>).
    """
    import base64
    import google.auth
    import google.auth.transport.requests
    import requests

    try:
        credentials, project = google.auth.default()
        req_auth = google.auth.transport.requests.Request()
        credentials.refresh(req_auth)

        url = f"https://aiplatform.googleapis.com/v1beta1/projects/{FIRESTORE_PROJECT_ID}/locations/global/interactions"
        headers = {
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json"
        }
        body = {
            "model": "gemini-omni-flash-preview",
            "input": [
                {
                    "type": "text",
                    "text": prompt
                }
            ],
            "response_format": [
                {
                    "type": "video"
                }
            ],
            "generation_config": {
                "video_config": {
                    "task": "text_to_video"
                }
            }
        }

        resp = requests.post(url, headers=headers, json=body, timeout=180)
        if resp.status_code != 200:
            return f"Error calling Interactions API ({resp.status_code}): {resp.text}"

        data = resp.json()
    except Exception as e:
        return f"Error generating video with gemini-omni-flash-preview: {e}"

    video_bytes = None
    mime_type = "video/mp4"

    try:
        steps = data.get("steps", [])
        for step in steps:
            for item in step.get("content", []):
                if item.get("type") == "video":
                    if "bytesBase64Encoded" in item:
                        video_bytes = base64.b64decode(item["bytesBase64Encoded"])
                    elif "data" in item:
                        video_bytes = base64.b64decode(item["data"])
                    elif "inlineData" in item and "data" in item["inlineData"]:
                        video_bytes = base64.b64decode(item["inlineData"]["data"])
                    elif "uri" in item:
                        gcs_uri = item["uri"]
                        if gcs_uri.startswith("gs://"):
                            parts = gcs_uri[5:].split("/", 1)
                            b_name, o_name = parts[0], parts[1]
                            b = storage_client.bucket(b_name)
                            video_bytes = b.blob(o_name).download_as_bytes()
                    if item.get("mime_type"):
                        mime_type = item["mime_type"]
                    break
            if video_bytes:
                break
    except Exception as e:
        return f"Error parsing video output from model response: {e}"

    if not video_bytes:
        return f"Failed to extract video bytes from gemini-omni-flash-preview response for prompt: '{prompt}'."

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_slug = "".join(c if c.isalnum() else "_" for c in prompt[:20].lower()).strip("_")
    filename = f"destination_video_{clean_slug}_{timestamp}.mp4"

    # (1) Save artifact so it shows up in Playground's Artifacts panel
    try:
        artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
        tool_context.save_artifact(filename=filename, artifact=artifact_part)
    except Exception:
        pass

    # (2) Upload video bytes to public Cloud Storage bucket and return public https URL
    try:
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(video_bytes, content_type=mime_type)
        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
        return public_url
    except Exception as e:
        return f"Error uploading video bytes to Cloud Storage bucket '{GCS_BUCKET_NAME}': {e}"


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        query: The name of the city to get the current time for.

    Returns:
        Current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    elif "kyoto" in query.lower() or "japan" in query.lower() or "tokyo" in query.lower():
        tz_identifier = "Asia/Tokyo"
    elif "paris" in query.lower() or "france" in query.lower():
        tz_identifier = "Europe/Paris"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_system_prompt = schema_manager.generate_system_prompt(
    role_description="You are a personalized Travel Concierge Agent.",
    workflow_description="Analyze the user's travel request and return structured UI when appropriate.",
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

instruction = f"""{a2ui_system_prompt}

CRITICAL ALLERGY & SAFETY REQUIREMENT:
- Pay strict attention to all user allergies (e.g., food allergies like peanuts, tree nuts, shellfish, gluten, dairy; environmental or medical allergies) and dietary restrictions mentioned by the user.
- Always ensure any allergy or health preference stated by the user is recorded into memory and remembered across sessions.
- When recommending destinations, food/restaurants, activities, or itineraries, ALWAYS consult preloaded memory and NEVER suggest anything that conflicts with the user's stated allergies or dietary safety requirements.

Core Capabilities:
You help users discover destinations, generate travel destination photos and videos, look up live weather forecasts, geocode addresses, find nearby points of interest, view detailed destination guides, save custom trip itineraries, add new destinations to their travel catalog, and execute Python code in a safe Agent Engine sandbox. Always check preloaded memory, and use your search_destinations, get_destination_details, generate_destination_image, generate_destination_video, fetch_destination_live_weather, geocode_address, search_nearby_places, add_destination, save_user_itinerary tools, or Python code execution to fetch real data and manage user trips."""


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    code_executor=sandbox_code_executor,
    tools=[
        PreloadMemoryTool(),
        search_destinations,
        get_destination_details,
        add_destination,
        save_user_itinerary,
        fetch_destination_live_weather,
        geocode_address,
        search_nearby_places,
        generate_destination_image,
        generate_destination_video,
        get_current_time
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
