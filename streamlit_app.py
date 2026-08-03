"""
Zoho Flow Docs Chatbot — powered by Zia SearchLabs (helpassistant API)
------------------------------------------------------------------------
Calls the Zia SearchLabs "helpassistant" endpoint for each user query and
renders the response in a chat UI.

Endpoint:
    GET https://searchlabs.zoho.in/restapi/sitesearch/beta/{org_id}/helpassistant
        ?q={query}&api_config_key={api_key}&is_agentic=true

Run:
    pip install streamlit requests
    streamlit run zia_flow_chatbot.py

NOTE: I don't have a sample response payload for this endpoint, so this
app tries several common field names (answer/response/message, results/hits/
sources) and falls back to showing the raw JSON if none match. Once you
share a sample response, I can tighten the rendering to match it exactly.
If the endpoint also requires an OAuth token header (Authorization:
Zoho-oauthtoken ...), fill that in the sidebar too — it's sent only if
provided.
"""

import os
import json
import requests
import streamlit as st

LOCAL_PROXY = "http://127.0.0.1:3128"

# --- Hardcoded Zia SearchLabs credentials ---
ORG_ID = "60077360247"
API_CONFIG_KEY = "MjgyNjAwMDAwMDAwMjA5NQ=="


def get_proxies():
    """Use HTTPS_PROXY/https_proxy env var if set, else fall back to the
    known local proxy (e.g. corporate security agent intercepting traffic)."""
    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or LOCAL_PROXY
    http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy") or LOCAL_PROXY
    return {"http": http_proxy, "https": https_proxy}

st.set_page_config(page_title="Zia Flow Docs Chatbot", page_icon="🤖", layout="wide")

BASE_URL = "https://searchlabs.zoho.in/restapi/sitesearch/beta/{org_id}/helpassistant"


def call_helpassistant(query, org_id, api_config_key, oauth_token=None, is_agentic=True, timeout=30):
    url = BASE_URL.format(org_id=org_id)
    params = {
        "q": query,
        "api_config_key": api_config_key,
        "is_agentic": str(is_agentic).lower(),
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "application/json",
    }
    if oauth_token:
        headers["Authorization"] = f"Zoho-oauthtoken {oauth_token}"

    resp = requests.get(url, params=params, headers=headers, proxies=get_proxies(), timeout=timeout)
    resp.raise_for_status()
    try:
        return resp.json()
    except ValueError:
        return {"_raw_text": resp.text}


def render_answer(data):
    """Extract the display-friendly answer from the helpassistant API response.

    Expected shape:
        {
          "response": {
            "summary": "...",
            "is_full_response": true,
            "action": "helpassistant",
            "total_no_of_results": 1,
            "status": "success",
            "chat_id": "..."
          }
        }
    """
    if not isinstance(data, dict) or "response" not in data:
        return f"_(Unrecognized response shape)_\n```json\n{json.dumps(data, indent=2)}\n```"

    resp = data["response"]
    status = resp.get("status")

    if status != "success":
        return f"⚠️ Zia returned status `{status}`.\n```json\n{json.dumps(resp, indent=2)}\n```"

    summary = resp.get("summary", "").strip()
    if not summary:
        return f"_(No summary in response)_\n```json\n{json.dumps(resp, indent=2)}\n```"

    footer_bits = []
    if not resp.get("is_full_response", True):
        footer_bits.append("_partial response_")
    total_results = resp.get("total_no_of_results")
    if total_results is not None:
        footer_bits.append(f"_{total_results} source(s)_")

    text = summary
    if footer_bits:
        text += "\n\n" + " · ".join(footer_bits)

    return text


# ---------------- Sidebar: connection config ----------------

st.title("🤖 Zoho Flow Docs Chatbot (Zia SearchLabs)")
st.caption("Queries are sent live to your org's helpassistant endpoint — no local index.")

if not org_id or not api_config_key:
    st.info("Enter your Org ID and API config key in the sidebar to start chatting.")
    st.stop()

# ---------------- Chat state ----------------
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

query = st.chat_input("Ask about a Zoho Flow service, trigger, or action...")

if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Querying Zia..."):
            try:
                data = call_helpassistant(
                    query=query,
                    org_id=org_id,
                    api_config_key=api_config_key,
                    oauth_token=oauth_token or None,
                    is_agentic=is_agentic,
                )
                answer = render_answer(data)
                chat_id = data.get("response", {}).get("chat_id")
                if chat_id:
                    st.session_state.last_chat_id = chat_id
                if show_raw:
                    answer += f"\n\n<details><summary>Raw response</summary>\n\n```json\n{json.dumps(data, indent=2)}\n```\n\n</details>"
            except requests.exceptions.HTTPError as e:
                answer = f"⚠️ Request failed: `{e.response.status_code}` — {e.response.text[:500]}"
            except requests.exceptions.RequestException as e:
                answer = f"⚠️ Request error: {e}"

        st.markdown(answer, unsafe_allow_html=True)

    st.session_state.messages.append({"role": "assistant", "content": answer})

if st.session_state.get("last_chat_id"):
    st.sidebar.caption(f"Last chat_id: `{st.session_state.last_chat_id}`")

if st.sidebar.button("Clear chat"):
    st.session_state.messages = []
    st.session_state.last_chat_id = None
    st.rerun()
