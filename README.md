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

4. **Set your environment variables in `.env`** (refer to `.env.example`):

   - `TOKEN`: Your bearer token for authentication.
   - `MY_NUMBER`: Your WhatsApp/phone number (for validation tool).

5. **Run the server:**

   ```bash
   python mcp_starter.py
   ```

   The server will start on `http://0.0.0.0:8086`.

6. **Expose your local server with ngrok**  
   a. **Install the ngrok CLI**

   - macOS (Homebrew):
     ```bash
     brew install ngrok/ngrok/ngrok
     ```
   - Linux / Windows: download the binary from https://ngrok.com/download and place it on your PATH.

   b. **Authenticate**  
   Copy your authtoken from the ngrok dashboard (https://dashboard.ngrok.com/get-started/your-authtoken) and run:

   ```bash
   ngrok config add-authtoken YOUR_NGROK_AUTHTOKEN
   ```

   c. **Get a ngrok domain**
   Visit [this](https://ngrok.com/blog-post/free-static-domains-ngrok-users) to learn how to get a free static ngrok domain. You can reserve your domain in the ngrok dashboard under **Domain Management → Domains**.

   c. **Start a tunnel**

   ```bash
   ngrok http --hostname=my-mcp-app.ngrok.app 8086
   ```
