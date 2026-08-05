"""
Zoho Flow Docs Chatbot — powered by Zia SearchLabs (helpassistant API)
------------------------------------------------------------------------
Calls the Zia SearchLabs "helpassistant" endpoint for each user query and
renders the response in a chat UI.
"""

import json
import socket
import requests
from requests.adapters import HTTPAdapter
import streamlit as st
from urllib3.util.retry import Retry

# --- FORCE IPV4 (Fixes IPv6 DNS hanging in Streamlit Cloud) ---
_old_getaddrinfo = socket.getaddrinfo


def _forced_ipv4_getaddrinfo(*args, **kwargs):
    responses = _old_getaddrinfo(*args, **kwargs)
    return [res for res in responses if res[0] == socket.AF_INET]


socket.getaddrinfo = _forced_ipv4_getaddrinfo


# --- Zia SearchLabs credentials (from Streamlit Cloud secrets) ---
ORG_ID = st.secrets.get("org_id", "")
API_CONFIG_KEY = st.secrets.get("api_config_key", "")

st.set_page_config(page_title="Zia Flow Docs Chatbot", page_icon="🤖", layout="wide")

BASE_URL = "https://zoho-search-proxy.kailashtest6.workers.dev//restapi/sitesearch/beta/{org_id}/helpassistant"


def get_requests_session():
    """Creates a requests session configured with retries and connection limits."""
    session = requests.Session()
    retries = Retry(
        total=2,
        backoff_factor=1,
        status_forcelist=[502, 503, 504],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    return session


def call_helpassistant(
    query, org_id, api_config_key, is_agentic=True, timeout=(5, 30)
):
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

    session = get_requests_session()

    # timeout=(connect_timeout, read_timeout)
    resp = session.get(url, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    try:
        return resp.json()
    except ValueError:
        return {"_raw_text": resp.text}


def render_answer(data):
    if not isinstance(data, dict) or "response" not in data:
        return (
            f"_(Unrecognized response shape)_\n```json\n{json.dumps(data, indent=2)}\n```"
        )

    resp = data["response"]
    status = resp.get("status")

    if status != "success":
        return f"⚠️ Zia returned status `{status}`.\n```json\n{json.dumps(resp, indent=2)}\n```"

    summary = resp.get("summary", "").strip()
    if not summary:
        return (
            f"_(No summary in response)_\n```json\n{json.dumps(resp, indent=2)}\n```"
        )

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


# ---------------- Config ----------------
org_id = ORG_ID
api_config_key = API_CONFIG_KEY
is_agentic = True
show_raw = False

st.title("🤖 Zoho Flow Docs Chatbot (Zia SearchLabs)")
st.caption(
    "Queries are sent live to your org's helpassistant endpoint — no local index."
)

if not org_id or not api_config_key:
    st.info("Org ID and API config key are not set in secrets.")
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
                    is_agentic=is_agentic,
                )
                answer = render_answer(data)
                chat_id = data.get("response", {}).get("chat_id")
                if chat_id:
                    st.session_state.last_chat_id = chat_id
                if show_raw:
                    answer += f"\n\n<details><summary>Raw response</summary>\n\n```json\n{json.dumps(data, indent=2)}\n```\n\n</details>"
            except requests.exceptions.ConnectTimeout:
                answer = (
                    "⚠️ **Connection Timeout:** Streamlit Cloud was unable to connect to `searchlabs.zoho.in` within 5 seconds. "
                    "This usually indicates that Zoho is firewall-blocking public cloud IPs (AWS/GCP)."
                )
            except requests.exceptions.HTTPError as e:
                answer = f"⚠️ Request failed: `{e.response.status_code}` — {e.response.text[:500]}"
            except requests.exceptions.RequestException as e:
                answer = f"⚠️ Request error: {e}"

        st.markdown(answer, unsafe_allow_html=True)

    st.session_state.messages.append({"role": "assistant", "content": answer})

if st.session_state.get("last_chat_id"):
    st.caption(f"Last chat_id: `{st.session_state.last_chat_id}`")

if st.button("Clear chat"):
    st.session_state.messages = []
    st.session_state.last_chat_id = None
    st.rerun()
