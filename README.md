# MCP Starter

## Setup

1. **Create a virtual environment using [uv](https://github.com/astral-sh/uv):**
    ```bash
    uv venv
    ```

2. **Install dependencies with uv:**
    ```bash
    uv sync
    ```

3. **Activate your virtual environment:**
    ```bash
    source .venv/bin/activate
    ```

4. **Set your environment variables in `.env`** Refer to `.env.example`:
    - `TOKEN`: Your bearer token for authentication.
    - `MY_NUMBER`: Your WhatsApp/phone number (for validation tool).

5. **Run the server:**
    ```bash
    python mcp_starter.py
    ```
    The server will start on `http://0.0.0.0:8085`.
