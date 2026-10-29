import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import io

st.set_page_config(page_title="NLP Powered Dashboard", layout="wide")

def apply_custom_css(file_path):  # connect to css
    with open(file_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
apply_custom_css("frontend/css/style.css")

search_api_url = "http://127.0.0.1:8000/search"  # connect to backend API
upload_api_url = "http://127.0.0.1:8000/upload"

#session for dataset
if "dataset_uploaded" not in st.session_state:
    st.session_state["dataset_uploaded"] = False

st.title("AI-Powered Dashboard Search")
st.write("Ask questions about your data while viewing the dashboard")

# dashboard image upload
st.header("Upload your PowerBI dashboard preview")
dashboard_image = st.file_uploader("Upload your dashboard preview image", type=["png", "jpg", "jpeg"])

if dashboard_image is not None:
    st.image(dashboard_image, caption="Dashboard preview", use_container_width=True)
else:
    st.warning("Dashboard preview image not found. Please upload.")

st.divider()

#dataset upload
st.header("Upload your data")
uploaded_file = st.file_uploader("Upload your dashboard dataset", type=["csv", "xlsx"])

if uploaded_file is not None and not st.session_state["dataset_uploaded"]:
    file_type = uploaded_file.name.split(".")[-1]
    if file_type in ["csv", "xlsx"]:
        with st.spinner("Uploading your dataset..."):

            try:
                file_bytes = uploaded_file.read()
                uploaded_file.seek(0)

                st.session_state["table_name"] = uploaded_file.name.rsplit('.', 1)[0].replace(' ', '_').lower()
                df = pd.read_csv(io.BytesIO(file_bytes)) if file_type == "csv" else pd.read_excel(io.BytesIO(file_bytes))
                st.session_state["columns"] = df.columns.tolist()

                files = {"file": (uploaded_file.name, io.BytesIO(file_bytes), "multipart/form-data")}
                response = requests.post(upload_api_url, files=files)

                if response.status_code == 200:
                    st.success("Your dataset has been uploaded and successfully loaded into the database")
                    st.session_state['dataset_uploaded'] = True

                else:
                    st.error(f"Upload failed: {response.text}")
            except Exception as e:
                st.error(f"Error uploading file: {e}")

st.divider()

st.header("Ask questions about your dashboard")
user_query = st.text_input("Ask a question:", placeholder="e.g.,Total sales in 2024")  # takes user input and sends it to the backend

if st.button("Search"):
    if user_query:
        with st.spinner("Processing your request..."):  # loading
            try:
                payload = {
                    "query": user_query,
                    "table_name": st.session_state.get("table_name", ""),
                    "columns": st.session_state.get("columns", [])
                }

                response = requests.post(search_api_url, json=payload)

                if response.status_code == 200:
                    data = response.json()

                    if isinstance(data.get("result", ""), str) and  data["result"].startswith("ERROR"):
                        st.error(f"Backend Error: {data['result']}")
                        st.stop()

                    sql_query = data["query"]
                    result = data["result"]
                    st.write("Raw result from backend:", result)

                    st.subheader("Generated SQL query")
                    st.code(sql_query, language="sql")

                    if result and isinstance(result, list):
                        try:
                            df = pd.DataFrame(result)
                            st.subheader("Your answer")
                            st.dataframe(df, use_container_width=True)

                            if len(df.columns) >= 2:
                                try:
                                    fig = px.bar(
                                        df,
                                        x=df.columns[0],
                                        y=df.columns[1],
                                        title="Data Visualization",
                                        labels={df.columns[0]: df.columns[0], df.columns[1]: df.columns[1]}
                                    )
                                    st.plotly_chart(fig, use_container_width=True)
                                except Exception as e:
                                    st.warning(f"Could not plot a chart: {e}")

                        except Exception as e:
                            st.error(f"Dataframe error: {e}")
                    else:
                        st.warning("The result is empty or not a valid list format.")
                else:
                    st.error("Failed to fetch data from backend.")
            except Exception as e:
                st.error(f"API Error: {e}")
    else:
        st.warning("Please enter a query.")
