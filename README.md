# Akask.ai: AI-Powered Educational Assistant

**Akask.ai** is a Telegram-based AI assistant designed to support students by providing class notes, video links, and answering educational queries. It integrates multiple services including FastAPI for the web server, Telegram for user interaction, Google Sheets for logging, Google APIs for spreadsheet access, and OpenAI’s models for natural language understanding and content generation.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Technical Details](#technical-details)
  - [Components](#components)
  - [Flow Diagrams](#flow-diagrams)
- [Installation and Setup](#installation-and-setup)
- [Environment Variables](#environment-variables)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

Akask.ai serves as a digital study buddy that:
- Processes user messages via Telegram.
- Screens messages for inappropriate content.
- Classifies intent and responds using predefined tools for retrieving notes or video links.
- Logs each interaction into a Google Sheet for auditing and analysis.
- Utilizes asynchronous programming to handle API calls and external service integrations effectively.

The system is built on Python and leverages asynchronous frameworks and API clients to ensure scalability and responsiveness.

---

## Features

- **Telegram Bot Integration:** Receives and responds to student queries via Telegram.
- **AI-Powered Intent Classification:** Uses OpenAI models to understand and process user queries.
- **Content Screening:** Filters out inappropriate content using a specialized screening function.
- **Dynamic Tool Invocation:** Calls dedicated functions (`get_notes` and `get_videos`) based on the user’s intent.
- **Google Sheets Logging:** Records user queries and responses with timestamps.
- **Asynchronous Execution:** Utilizes `asyncio` and `uvicorn` with FastAPI for non-blocking I/O operations.
- **YouTube API Integration:** Retrieves video data from YouTube for additional educational content.

---

## Architecture

The system consists of several integrated components that work together to deliver a seamless experience.

### Components

1. **Telegram Bot Application:**
   - Listens for incoming messages and commands.
   - Uses the Telegram API to send responses.

2. **FastAPI Web Server:**
   - Exposes endpoints (including a webhook endpoint) to receive and process updates.
   - Manages lifecycle events, such as setting up webhooks on deployment.

3. **AI Intent Classifier:**
   - Screens user inputs.
   - Classifies intent to decide if the query relates to notes or videos.
   - Routes the request to the corresponding function.

4. **External API Integrations:**
   - **Google Sheets & gspread:** Logs conversation details.
   - **Google API Client:** Opens and accesses the specified Google Spreadsheet.
   - **YouTube API:** Searches and retrieves video details.
   - **OpenAI API:** Generates responses and assists in content screening.

### Flow Diagrams

Below are two Mermaid diagrams illustrating the overall system architecture and the internal query processing flow.

#### System Architecture

```mermaid
flowchart TD
    A[User sends message on Telegram] --> B[Telegram Bot]
    B --> C[FastAPI Webhook Endpoint]
    C --> D[AI Intent Classifier]
    D --> |Screening & Tool Selection| E{Intent: Notes? Videos?}
    E -- Notes --> F[get_notes Function]
    E -- Videos --> G[get_videos Function]
    F --> H[Retrieve notes from index JSON]
    G --> I[YouTube API Request]
    H & I --> J[Format Response]
    J --> K[Send reply via Telegram Bot]
    K --> L[Log conversation in Google Sheets]
