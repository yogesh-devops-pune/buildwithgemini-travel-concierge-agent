# Travel Concierge Agent

An intelligent, personalized travel assistant built on Google's **Agent Development Kit (ADK)** and deployed on **Google Cloud Agent Engine**. The agent combines cross-session memory, live external APIs, Google Cloud database storage, and multimodal generative AI models to curate personalized travel itineraries and generate custom destination media.

![Travel Concierge Demo](demo.gif)

---

## Key Capabilities

Based on the implemented tools and backend services in `app/`:

- **Cross-Session Memory & Safety Rules**:
  - Automatically records and recalls user allergies, dietary restrictions, and travel preferences across sessions using **Vertex AI Memory Bank**.
  - Strictly enforces dietary and safety guidelines when suggesting food, destinations, and activities.
- **AI Image Generation**:
  - Generates custom, photorealistic travel destination photos on demand using **Gemini Image Generation** (`gemini-3.1-flash-lite-image`).
  - Automatically uploads generated images to **Google Cloud Storage** and returns public HTTPS media links.
- **AI Video Generation**:
  - Produces cinematic short travel videos using Google's **Gemini Omni Model** (`gemini-omni-flash-preview`) in the `global` region via the Vertex AI Interactions API.
  - Saves videos to the Playground's Artifacts panel and uploads MP4 bytes to public **Google Cloud Storage**.
- **Live Weather & Location Intelligence**:
  - Fetches real-time weather forecasts and current conditions using the **Open-Meteo Public Weather API**.
  - Geocodes destination addresses and coordinates via the **Google Maps Geocoding API**.
  - Discovers nearby points of interest, dining, and attractions via the **Google Places API (New)**.
- **Firestore Database Persistence**:
  - Stores and queries the destination catalog from a **Google Cloud Firestore** database (`destinations` collection).
  - Saves custom user trip itineraries into Firestore (`user_itineraries` collection).
- **A2UI Rich Interface Cards**:
  - Emits structured **A2UI (Agent-to-User Interface)** JSON cards that natively render formatted travel summaries, weather widgets, and media directly in the chat UI.
- **Safe Code Execution**:
  - Runs custom Python logic securely within an **Agent Engine Sandbox Code Executor**.

---

## Google Cloud Architecture & Services

- **Vertex AI Agent Engine & ADK**: Core runtime framework hosting the travel concierge agent (`root_agent`).
- **Vertex AI Memory Bank**: Managed memory service handling automated fact extraction and long-term user context retention.
- **Google Cloud Firestore**: NoSQL document database storing destination records and saved user trip itineraries.
- **Google Cloud Storage**: Public bucket hosting generated destination images and MP4 video assets.
- **Google Generative AI Models**:
  - `gemini-flash-latest`: Core LLM orchestrating tool selection and conversational logic.
  - `gemini-3.1-flash-lite-image`: Multimodal image generation model.
  - `gemini-omni-flash-preview`: Multimodal video generation model.
- **Google Cloud Run**: Serverless container hosting for the FastAPI web proxy and chat interface.

---

## Implemented Agent Tools

| Tool | Description |
| :--- | :--- |
| `PreloadMemoryTool` | Retrieves user memory and allergies from Vertex AI Memory Bank prior to generating recommendations. |
| `search_destinations` | Queries Firestore destination records by country, activity tag, or budget. |
| `get_destination_details` | Fetches complete destination metadata, highlights, and cost estimates from Firestore. |
| `add_destination` | Saves a new destination into the Firestore catalog. |
| `save_user_itinerary` | Saves structured trip itineraries and user travel plans to Firestore. |
| `fetch_destination_live_weather` | Retrieves live weather and forecasts for a destination from Open-Meteo. |
| `geocode_address` | Converts city/address strings to latitude and longitude using Google Maps. |
| `search_nearby_places` | Finds nearby restaurants, attractions, and lodging using Google Places API (New). |
| `generate_destination_image` | Generates a travel photo with `gemini-3.1-flash-lite-image` and uploads it to Cloud Storage. |
| `generate_destination_video` | Generates a short MP4 video with `gemini-omni-flash-preview` and uploads it to Cloud Storage. |
| `AgentEngineSandboxCodeExecutor` | Executes Python code in a secure sandbox environment. |

---

## Project Structure

```
.
├── app/
│   ├── agent.py               # Main ADK agent definition, tools, and A2UI callbacks
│   ├── a2ui_utils.py          # A2UI card renderer and schema manager
│   └── __init__.py
├── frontend/
│   ├── main.py                # FastAPI web proxy server (talks A2A to deployed agent)
│   ├── requirements.txt       # Frontend Python dependencies
│   └── static/
│       └── index.html         # Custom chat frontend with native A2UI card rendering
├── agents-cli-manifest.yaml    # Agents CLI deployment manifest
├── requirements.txt           # Agent backend dependencies
├── GEMINI.md                  # Agent developer guidance and rules
├── demo.gif                   # Recorded video demonstration
└── README.md                  # Project documentation
```

---

## Local Setup & Running Instructions

### Prerequisites
- Python 3.11 or higher
- Google Cloud SDK (`gcloud`) installed and authenticated
- Google Cloud Project with Firestore, Cloud Storage, and Vertex AI APIs enabled

### 1. Environment Configuration

Authenticate with Google Cloud and set your target project:

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_GCP_PROJECT_ID
```

Set the required environment variables:

```bash
export FIRESTORE_PROJECT_ID="YOUR_GCP_PROJECT_ID"
export GCS_BUCKET_NAME="YOUR_PUBLIC_GCS_BUCKET_NAME"
export GOOGLE_API_KEY=<your-api-key>
```

### 2. Running the Agent Locally

Install backend dependencies and run the agent via ADK:

```bash
pip install -r requirements.txt
adk web app/
```

### 3. Running the Frontend Proxy Locally

Navigate to the `frontend/` directory, set your deployed agent resource name, and launch the server:

```bash
cd frontend
pip install -r requirements.txt
export AGENT_ENGINE_RESOURCE_NAME="projects/YOUR_PROJECT/locations/us-east1/reasoningEngines/YOUR_ENGINE_ID"
export AGENT_DIRECTORY="app"
python main.py
```

The frontend server will start and listen on port `8080`.

---

## Planned / Future Features

- **Automated Flight & Hotel Booking**: Integration with real-time flight search and lodging reservation APIs (*planned, not yet implemented*).
- **Interactive Multi-User Trip Planning**: Real-time collaborative itinerary sharing among travel groups (*planned, not yet implemented*).
