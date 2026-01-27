# import streamlit as st
# from langchain_core.messages import HumanMessage
# from agents import get_agent

# st.title("SRE Agent - LangGraph Monitoring")

# # Chat history
# if "messages" not in st.session_state:
#     st.session_state.messages = []

# # Chat UI
# for message in st.session_state.messages:
#     with st.chat_message(message["role"]):
#         st.markdown(message["content"])

# if prompt := st.chat_input("Ask about cluster alerts..."):
#     st.session_state.messages.append({"role": "user", "content": prompt})
#     with st.chat_message("user"):
#         st.markdown(prompt)
    
#     with st.chat_message("assistant"):
#         agent = get_agent()
#         inputs = {"messages": [HumanMessage(content=prompt)]}
        
#         with st.spinner("Agent thinking..."):
#             full_response = ""
#             for event in agent.stream(inputs, config={"recursion_limit": 15}):
#                 for key, value in event.items():
#                     last_msg = value["messages"][-1]
#                     if last_msg.type == "ai" and not last_msg.tool_calls:
#                         full_response = last_msg.content
            
#             st.markdown(full_response)
#             st.session_state.messages.append({"role": "assistant", "content": full_response})


import streamlit as st
from langchain_core.messages import HumanMessage
from agents import get_agent

st.title("SRE Remediation Agent (Task 3)")

# 1. Initialize Graph ONLY ONCE using cache
@st.cache_resource
def load_agent_graph():
    return get_agent()

agent_graph = load_agent_graph()

# 2. Initialize Chat History in Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
# 3. Initialize Thread ID for LangGraph (Critical for continuity)
if "thread_id" not in st.session_state:
    import uuid
    st.session_state.thread_id = str(uuid.uuid4())

# Render Chat
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Enter command..."):
    # Add user message to UI state
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("Agent is diagnosing..."):
            # Config for the graph execution
            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            
            # Stream the response
            full_response = ""
            # IMPORTANT: Pass the new message into the graph
            inputs = {"messages": [HumanMessage(content=prompt)]}
            
            for event in agent_graph.stream(inputs, config=config):
                for key, value in event.items():
                    # The value['messages'] is a LIST of messages. We want the last one.
                    if "messages" in value and len(value["messages"]) > 0:
                        last_msg = value["messages"][-1]
                        if last_msg.type == "ai" and last_msg.content:
                            full_response = last_msg.content
            
            st.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})
