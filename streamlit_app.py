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

import json
import requests
import streamlit as st

st.set_page_config(page_title="Zia Flow Docs Chatbot", page_icon="🤖", layout="wide")

BASE_URL = "https://searchlabs.zoho.in/restapi/sitesearch/beta/60077360247/helpassistant"
api_config_key = "MjgyNjAwMDAwMDAwMjA5NQ==";

def call_helpassistant(query, org_id, api_config_key, oauth_token=None, is_agentic=True, timeout=30):
    url = BASE_URL.format(org_id=org_id)
    params = {
        "q": query,
        "api_config_key": api_config_key,
        "is_agentic": str(is_agentic).lower(),
    }
    headers = {}
    if oauth_token:
        headers["Authorization"] = f"Zoho-oauthtoken {oauth_token}"

    resp = requests.get(url, params=params, headers=headers, timeout=timeout)
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
st.sidebar.header("🔧 Zia SearchLabs config")
org_id = st.sidebar.text_input("Org ID", help="Your Zoho org ID (path param in the URL)")
api_config_key = st.sidebar.text_input("API config key", type="password")
oauth_token = st.sidebar.text_input(
    "OAuth token (optional)",
    type="password",
    help="Only needed if the endpoint requires Authorization: Zoho-oauthtoken header",
)
is_agentic = st.sidebar.checkbox("is_agentic", value=True)
show_raw = st.sidebar.checkbox("Always show raw JSON response", value=False)

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
