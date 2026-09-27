# Travel Concierge AI Agent

An intelligent, multi-modal travel assistant built with the Google Agent Development Kit (ADK) and Vertex AI Agent Platform. It provides personalized travel planning, destination discovery, live exchange rate calculations, place geocoding, AI image & video generation, and rich interactive A2UI display cards.

![Travel Concierge Demo](demo.gif)

---

## 🌟 Implemented Features & Google Cloud Integrations

This agent incorporates the following verified tools and Google Cloud infrastructure integrations:

- **Cross-Session Memory Bank**: Powered by Vertex AI Memory Bank (`PreloadMemoryTool` & `generate_memories_callback`), preserving user travel preferences, budget constraints, and history across multiple sessions.
- **Firestore Database Catalog**: Queries (`list_destinations`, `search_destinations`) and inserts (`add_destination`) destination records directly into Google Cloud Firestore.
- **AI Image Generation**: Uses `gemini-3.1-flash-lite-image` in the `global` location to generate scenic destination artwork, saving artifacts to the ADK Playground and uploading public images to Cloud Storage.
- **AI Video Generation**: Uses `gemini-omni-flash-preview` in the `global` location to produce 3-second destination preview videos.
- **Google Maps & Places Integration**:
  - `geocode_address`: Converts location strings into latitude and longitude using Google Maps Geocoding API.
  - `search_nearby_places`: Searches for nearby attractions, restaurants, and museums using Google Places API.
- **Wikipedia Destination Details**: `get_destination_info` fetches encyclopedic summaries, coordinates, and thumbnail images.
- **Live Currency Conversion**: `convert_currency` calculates real-time currency exchange rates.
- **Rich A2UI Display Cards**: Emits structured A2UI UI payloads (`a2ui_callback`) rendered as custom visual cards (Card, Column, Row, Text, Image) in the web frontend.
- **Agent Engine Sandbox Code Executor**: Dynamically evaluates complex budget calculations and data analysis in an isolated sandbox (`AgentEngineSandboxCodeExecutor`).
- **Public Cloud Storage Bucket**: Stores generated media assets and serves them over public HTTPS URLs.

---

## 🛠️ Local Setup & Running Instructions

### Prerequisites

- Python 3.10+
- Google Cloud Project with Vertex AI, Firestore, and Cloud Storage APIs enabled
- Authenticated `gcloud` session (`gcloud auth application-default login`)

### Installation

1. Clone the repository and navigate to the project root:
   ```bash
   cd travel-concierge
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure required environment variables:
   ```bash
   export GOOGLE_MAPS_API_KEY=<YOUR_GOOGLE_MAPS_API_KEY>
   export AGENT_ENGINE_RESOURCE_NAME=<YOUR_AGENT_ENGINE_RESOURCE_NAME>
   export AGENT_DIRECTORY=app
   ```

### Running the Frontend Locally

1. Navigate to the `frontend/` directory and install frontend dependencies:
   ```bash
   cd frontend
   pip install -r requirements.txt
   ```

2. Launch the local FastAPI proxy and web chat UI:
   ```bash
   python main.py
   ```

3. Open your browser and navigate to port `8080` to interact with your agent locally.

---

## 📁 Project Structure

- `app/agent.py`: ADK Agent definition, tool definitions, system prompt, callbacks, and sandbox executor configuration.
- `frontend/`: FastAPI proxy (`main.py`) communicating with the deployed agent via A2A protocol and serving the custom chat UI (`static/index.html`).
- `agents-cli-manifest.yaml`: Agent CLI deployment configuration and metadata.
