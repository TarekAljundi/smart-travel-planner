Smart Travel Planner
An AI‑powered travel assistant that matches travelers to destinations using a combination of retrieval‑augmented generation (RAG), machine learning classification, and live weather data – all built with production‑grade engineering practices.

Architecture
text
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   React      │────▶│   FastAPI    │────▶│  PostgreSQL  │
│  Frontend    │ SSE │   Backend    │     │  + pgvector  │
└──────────────┘     └──────┬───────┘     └──────────────┘
                            │
                   ┌────────┴────────┐
                   │   LangGraph     │
                   │   Agent         │
                   └───┬───┬───┬─────┘
                       │   │   │
              ┌────────┘   │   └──────────┐
              ▼            ▼               ▼
      ┌──────────┐  ┌───────────┐  ┌──────────────┐
      │   RAG    │  │ Classify  │  │Live Conditions│
      │  (pgvec) │  │ (ML Model)│  │ (Open‑Meteo)  │
      └──────────┘  └───────────┘  └──────────────┘
            │                              │
            ▼                              ▼
   ┌────────────────┐           ┌─────────────────┐
   │  Wikivoyage    │           │  Gmail Webhook  │
   │  Knowledge Base│           │  (trip delivery)│
   └────────────────┘           └─────────────────┘
The system ingests real destination content from Wikivoyage, chunks and embeds it, stores the vectors in PostgreSQL with pgvector, and serves them through an asynchronous FastAPI backend. A React frontend streams the agent’s reasoning via Server‑Sent Events, and a background webhook delivers the final trip plan to the user’s email.

Dataset and Labeling
Destination Data
Source: 12 real destinations fetched from Wikivoyage (CC‑BY‑SA) via the action=raw endpoint.

Document count: 24‑30 documents (original articles split into logical sections: Overview, Get in, See, Do, Stay, etc.).

Structure: Each destination has its own folder inside backend/knowledge_base/, with 2‑3 .txt files per destination.

Features
Eight features are used for classification:

Feature	Description	Source
avg_temperature	July average temperature	Open‑Meteo Archive API (5‑year mean)
cost_index	Cost of living, scaled 10‑100	Numbeo CSV from GitHub (mapped to country)
hiking_score	Hiking/trekking activity score (0‑10)	Wikivoyage “Do” section keyword analysis
beach_score	Beach & water activity score (0‑10)	Wikivoyage keyword analysis
culture_score	Cultural richness score (0‑10)	Wikivoyage “See” section keyword analysis
family_friendly_score	Family suitability (0‑10)	Derived from other scores
tourist_density	Crowd indicator (1‑10)	Article length + popularity keywords
continent	Categorical	Open‑Meteo geocoding → country code mapping
All features are fetched live from the internet at runtime – no values are hardcoded. The dataset generator (ml/generate_dataset.py) fetches these features for 150 destinations and saves them to data/destinations.csv.

Labeling Rules
Six travel styles are assigned using a deterministic rule‑based system:

Budget – cost_index ≤ 35

Luxury – cost_index ≥ 80

Adventure – hiking_score ≥ 7 AND beach_score ≤ 4

Relaxation – beach_score ≥ 7 AND tourist_density ≤ 7

Culture – culture_score ≥ 8 AND tourist_density ≥ 4

Family – family_friendly_score ≥ 7 AND tourist_density ≤ 7

If no rule matches, the highest activity score determines the label. The dataset is then expanded to 1,000 rows by adding Gaussian noise to numeric features (temperature ±1.5°C, cost ±4, scores ±0.4), preserving the original labels.

ML Classifier
Pipeline
Preprocessing: ColumnTransformer with StandardScaler for numeric features and OneHotEncoder for continent.

SMOTE: Synthetic Minority Oversampling applied inside the pipeline (only during fit()). Addresses class imbalance; minimal classes (1 sample) are dropped before training.

Models compared (5‑fold CV):

Logistic Regression

Random Forest

Gradient Boosting

Results
(saved in pipeline/results.csv)

Model	Accuracy (mean ± std)	F1 macro (mean ± std)
LogisticRegression: acc=0.944 ± 0.012, F1=0.921 ± 0.030
RandomForest: acc=0.977 ± 0.008, F1=0.972 ± 0.009
GradientBoosting: acc=0.994 ± 0.007, F1=0.992 ± 0.009

Tuning
Tuned model: Random Forest (20 iterations via RandomizedSearchCV, 5‑fold CV, scoring f1_macro).

Best parameters: {'clf__n_estimators': 200, 'clf__min_samples_split': 5, 'clf__min_samples_leaf': 2, 'clf__max_depth': 20}

Classification report on training data (with SMOTE):
              precision    recall  f1-score   support

      Budget       1.00      1.00      1.00       189
     Culture       0.99      1.00      1.00       114
      Family       1.00      1.00      1.00       679
      Luxury       1.00      1.00      1.00        16

    accuracy                           1.00       998
   macro avg       1.00      1.00      1.00       998
weighted avg       1.00      1.00      1.00       998

Production model saved as pipeline/classifier_pipeline.joblib, loaded once at startup via FastAPI lifespan.

Inference runs in asyncio.to_thread() to keep the event loop free (CPU‑bound work).

RAG Retrieval System
Knowledge Base
Content: 12 destinations, 24‑30 documents (Wikivoyage sections).

Chunking: Custom recursive splitter with chunk_size=500, chunk_overlap=50, separators ["\n\n", "\n", ". ", " ", ""].

Rationale: 500 characters keeps chunks self‑contained (a paragraph or two). 50‑character overlap prevents sentence truncation at boundaries. Splitting on paragraphs first ensures coherent chunks.

Embedding model: all-MiniLM-L6-v2 (384‑dimensional vectors), loaded once at startup.

Storage: PostgreSQL + pgvector extension, table destination_chunks.

Retrieval Strategy
Similarity: Cosine distance via pgvector’s <=> operator.

Query: The agent rewrites the user’s natural‑language request into a concise search query.

Top‑k: 3 chunks returned (configurable via Settings.rag_top_k).

Fallback: If no chunk is found, a structured “No information found” message is returned, prompting the agent to refuse gracefully.

Retrieval Testing
Hand‑written queries tested before integrating into the agent:

Query	Top destination	Similarity
“warm beach with hiking nearby”	Bali	0.62
“historic cultural European city”	Paris	0.71
“adventure activities in mountains”	Swiss Alps	0.68
“affordable tropical island”	Bali	0.59
“romantic coastal village in Italy”	Amalfi Coast	0.64
All queries return the expected destinations with high relevance, confirming the retrieval system works reliably.

Agent with Three Tools
The agent is built with LangGraph (using create_agent from langchain.agents). It uses a two‑model routing strategy to reduce cost:

Cheap model (meta-llama/llama-4-scout-17b-16e-instruct via Groq): handles reasoning and tool‑calling.

Strong model (llama-3.3-70b-versatile via Groq): synthesises the final trip plan from tool outputs.

Tools
All tool inputs are validated by Pydantic schemas before execution. If the LLM sends malformed data, the agent receives a validation error and can retry – it never crashes.

Tool	Description	Input schema
search_destinations	Queries the pgvector knowledge base.	RAGQuery (query string)
classify_destination	Accepts a city name, computes live features, and returns classification label + probabilities.	ClassifyByNameInput (destination name)
get_weather	Geocodes a city via Open‑Meteo, fetches current weather, caches results (10 min TTL), retries transient failures with exponential backoff.	LiveConditionsInput (city name)
Tool Allowlist
Only these three tools are bound to the agent. Any tool hallucinated by the model is refused by LangChain.

Failure Isolation
Weather tool returns a ToolError (with retryable flag) instead of raising exceptions.

RAG tool returns a clear “No information found” message when no chunks are retrieved.

The agent is instructed (via system prompt) to refuse planning if the knowledge base lacks data, returning: “I don't have enough information about this destination in my knowledge base.”

LangSmith Tracing
Every agent run is traced end‑to‑end via the free tier of LangSmith. The following screenshot shows a multi‑tool trace (search, classify, weather, synthesis):

https://github.com/TarekAljundi/smart-travel-planner/issues/1#issue-4363848479


Per‑Query Cost
Token usage is logged by Groq’s API. A typical full query (three tool calls + synthesis) consumes approximately:

Model	Input tokens	Output tokens	Estimated cost (USD)
Cheap (agent loop)	~2,500	~200	negligible
Strong (synthesis)	~1,500	~800	< $0.01
Actual numbers vary by query and retrieved content. Groq’s free tier comfortably handles development traffic.

Persistence
PostgreSQL (via SQLAlchemy 2.x async) stores:

users – registration and login credentials (passwords hashed with bcrypt)

agent_runs – query, final answer, timestamps

tool_calls – tool name, input, output, status

Alembic migrations manage schema changes.

pgvector extension is used for vector similarity search.

Auth
JWT‑based authentication (python‑jose + passlib/bcrypt).

Registration (/auth/register) and login (/auth/token) endpoints.

Passwords truncated to 72 bytes before hashing (bcrypt limit).

All agent runs are scoped to the logged‑in user.

Manual token verification for SSE endpoints (EventSource can’t send custom headers).

Frontend
React + Vite, dark theme with glass‑morphism design (CSS custom properties, no external UI library).

Streaming chat interface using Server‑Sent Events (SSE) – the user sees the agent “think” in real time.

Tool call display: each tool invocation is shown with expandable details (input, output, status).

Sectioned trip plan: the final answer is parsed and rendered as separate, styled cards (Recommended Destination, Current Weather, Itinerary, Budget, Caveats) with icons.

Fully responsive layout (clamp() sizing, media queries, flex‑wrap), works on mobile and desktop.

Webhook Delivery (Gmail)
After the agent finishes, the trip plan is emailed to the user via Gmail SMTP.

Delivery is offloaded to a separate thread (ThreadPoolExecutor), so it survives client disconnections.

Uses a Gmail App Password (not the account password) for secure authentication.

The email is skipped if the agent refused due to missing knowledge (final answer contains “I don't have enough information”).

Transient SMTP errors are logged (structlog) but never propagated to the user.

Engineering Standards
This project strictly follows the companion guide’s standards:

Standard	Implementation
Async All the Way Down	Every route, tool, and database call is async. No requests, no time.sleep, no blocking I/O.
Dependency Injection	FastAPI Depends() for sessions, LLM client, classifier, embedder, current user. No module‑level globals.
Singletons Done Right	Heavy resources (database engine, ML model, embedder, LLM client) are loaded once in lifespan and exposed via dependencies.
Caching	lru_cache on get_settings(). TTL cache on weather (10 min) with asyncio.Lock to prevent thundering herd.
Configuration	Single Settings class with pydantic‑settings. All values typed and validated at startup. extra="ignore" allows LangSmith keys.
Pydantic Boundaries	Every external input (HTTP body, tool arguments, LLM outputs) is a Pydantic model. Tools validate inputs before execution.
Errors & Retries	tenacity with exponential backoff on transient HTTP errors. Tools return structured ToolError objects – the agent never crashes.
Code Hygiene	Project split into routes/, services/, tools/, models/, prompts/. Structured JSON logging with structlog. Ruff for linting/formatting.
Tests	Pydantic schema tests, tool isolation tests (mocked external calls), end‑to‑end agent test (mocked LLM, weather, classifier, database). All tests run in CI via GitHub Actions.
How to Run (Docker)
Clone the repository.

Copy backend/.env.example to backend/.env and fill in:

database_url, groq_api_key, secret_key

Gmail credentials (webhook_gmail_address, webhook_gmail_app_password)

(Optional) LangSmith keys (langsmith_tracing, langsmith_api_key, etc.)

From the project root, start the whole stack:

bash
docker compose up --build
Access the frontend at http://localhost:3000.

The Docker setup starts PostgreSQL (with pgvector), the FastAPI backend, and an Nginx‑served React frontend. A named volume preserves database data across restarts.

How to Run (Local Development)
Clone the repository and navigate to backend/.

Create a virtual environment and install dependencies:

bash
uv sync
Set up the database and run migrations:

bash
docker compose up -d db          # or use a local PostgreSQL with pgvector
uv run alembic upgrade head
(First time) Load the knowledge base and train the model:

bash
uv run python scripts/fetch_wikivoyage.py
uv run python scripts/split_docs.py
uv run python scripts/load_rag.py
uv run python ml/generate_dataset.py
uv run python ml/train.py
Start the backend:

bash
uv run uvicorn app.main:app --reload
In a separate terminal, start the frontend:

bash
cd frontend
npm install
npm run dev
Open http://localhost:3000.

Tests
The test suite covers the critical path as required by the engineering standards:

Pydantic schema validation – valid and invalid inputs for all models.

Tool isolation – RAG search (with mocked database), classifier (mocked ML model), weather (mocked API and timeouts).

End‑to‑end agent – mocked LLM, tools, and external APIs; verifies correct tool call events and synthesis.

Retrieval quality – manual queries tested against the real knowledge base (skipped if DB is unavailable).

Run the tests with:

bash
cd backend
uv run pytest -v
CI is configured via .github/workflows/test.yml – tests run automatically on every push and pull request.

Optional Extensions
SMOTE for class imbalance in classifier training.

Gmail webhook instead of a generic HTTP webhook.

Two‑model agent routing (cheap LLM for tool‑calling, strong LLM for synthesis) to reduce cost.

LangSmith tracing for observability.

Structured JSON output from the agent, parsed into section cards on the frontend.

Thread‑based persistence to survive client disconnections.

Demo Video
A 3‑minute walkthrough showing a complete end‑to‑end user journey (registration, streaming agent, tool calls, email delivery) is available at:

[Link to demo video]

(Replace with the actual URL after recording.)

Acknowledgments
Destination content sourced from Wikivoyage (CC‑BY‑SA).

Weather data from Open‑Meteo (free, no API key required).

Embedding model all-MiniLM-L6-v2 by Sentence‑Transformers.

LLMs served by Groq (free tier).
