import base64
import hmac
import io
import os.path as op
import zipfile
from functools import partial

import pandas as pd
import streamlit as st

# Set the website bar icon
st.set_page_config(page_title="Label Editor", page_icon=":pencil:")
st.title("Label Editor")

@st.cache_data
def image_to_data_url(_zip_file: zipfile.ZipFile, image_path: str) -> str:
    """Open an image and convert to base64 data url."""
    # Read image content in zip file.
    with _zip_file.open(image_path) as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode("utf-8")
    # Get image path extension.
    image_extension = image_path.split(".")[-1]
    # Generate data url.
    data_url = f"data:image/{image_extension};base64,{encoded_image}"
    return data_url


def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if hmac.compare_digest(st.session_state["password"], st.secrets["password"]):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store the password.
            st.toast("Login Successful 🎉", icon="🔓")
        else:
            st.session_state["password_correct"] = False

    # Return True if the password is validated.
    if st.session_state.get("password_correct", False):
        return True

    # Show input for password.
    st.text_input(
        "Password", type="password", on_change=password_entered, key="password"
    )
    if "password_correct" in st.session_state:
        st.error("😕 Password incorrect")
    return False


if not check_password():
    st.stop()

# Add example
with st.expander("Example"):
    st.write("Input zip file structure:")
    st.code(
    """
    input.zip
    ├── batch_01
    │   ├── image_01.jpg
    │   ├── image_02.jpg
    │   └── ...
    ├── batch_02
    │   ├── image_01.jpg
    │   ├── image_02.jpg
    │   └── ...
    ├── ...
    ├── batch_xx
    │   ├── image_01.jpg
    │   ├── image_02.jpg
    │   └── ...
    └── labels.tsv
    """
)

# File upload
file = st.file_uploader("Upload a zip file", type=["zip"])

# If no file is uploaded, stop the script
if file is None:
    st.stop()

# If file is not a zip file, stop the script
if not file.name.endswith(".zip"):
    st.error("Invalid file format. Please upload a ZIP file.")
    st.stop()

# Unzip the file to buffer
zip_file = zipfile.ZipFile(file)
files = zip_file.namelist()
# Remove all __MACOSX and .DS_Store files
files = [file for file in files if "__MACOSX" not in file and ".DS_Store" not in file]

# Find the tsv file or csv file
label_files = [file for file in files if file.endswith(".tsv") or file.endswith(".csv")]
if len(label_files) != 0:
    # Select the file
    label_file = st.selectbox("Select a file", label_files)
else:
    # Use the first file
    label_file = label_files[0]

if "df" not in st.session_state:

    # Get the file content from the zip file
    with zip_file.open(label_file) as f:
        label_content = f.read()
        label_bytes = io.BytesIO(label_content)

    # Read label file
    sep = "\t" if label_file.endswith(".tsv") else ","
    df = pd.read_csv(label_bytes, sep=sep, quoting=3)

    # Check if the file has a path and text column
    if not {"path", "text"}.issubset(df.columns):
        st.error(
            "The file must have 'path' and 'text' columns, but got: "
            + ", ".join(df.columns)
        )
        st.stop()

    # Use commonpath as root.
    root_dir = op.commonpath(files)

    # Create a partial function to convert image to data url
    image_to_data_url = partial(image_to_data_url, zip_file)

    # Create a temporary path column
    df["image"] = df["path"].apply(lambda x: op.join(root_dir, x))
    # Check if the image path exists
    for image_path in df["image"]:
        if image_path not in files:
            st.error(
                f"Image path '{image_path}' not found in the zip file. This is a corrupted file."
            )
            st.stop()
    # Create a base64 data url column
    df["image"] = df["image"].apply(image_to_data_url)
    # Fill NaN with empty string on text column
    df["text"] = df["text"].fillna("")
    # Cast column qc_confidence to float if exists
    if "qc_confidence" in df.columns:
        df["qc_confidence"] = df["qc_confidence"].astype(float)
    # Cast column qc_passed to bool if exists
    if "qc_passed" in df.columns:
        df["qc_passed"] = df["qc_passed"].astype(bool)
    # Save the DataFrame to session state
    st.session_state["df"] = df
else:
    df = st.session_state["df"]

# Find all batches in the df["path"] column
# batch_xx/image_xx.jpg
batches = df["path"].apply(lambda x: x.split("/")[0]).unique().tolist()
batches = sorted(batches, key=lambda x: int(x.split("_")[1]))

# Add batch_xx selection
batch = st.selectbox("Select a batch", batches)

if "batch_df" not in st.session_state or st.session_state["current_batch"] != batch:
    # Filter the DataFrame by batch
    batch_df = df[df["path"].str.contains(batch)]
    # Sort by qc_confidence if exists
    if "qc_confidence" in batch_df.columns:
        batch_df = batch_df.sort_values("qc_confidence", ascending=True)
    st.session_state["batch_df"] = batch_df
    st.session_state["current_batch"] = batch
else:
    batch_df = st.session_state["batch_df"]

# Column order for the DataFrame
column_order = ["image", "text"]
disabled_columns = ["image"]
column_config = {
    "image": st.column_config.ImageColumn(
        width="medium", label="Image Preview", help="Image Preview"
    ),
    "text": st.column_config.TextColumn(label="Text", help="Label of the image."),
}
if "qc_passed" in batch_df.columns:
    column_order.append("qc_passed")
    disabled_columns.append("qc_passed")
    column_config["qc_passed"] = st.column_config.CheckboxColumn(
        label="QC Passed",
        help="Quality Control Passed",
    )
if "qc_confidence" in batch_df.columns:
    column_order.append("qc_confidence")
    disabled_columns.append("qc_confidence")
    column_config["qc_confidence"] = st.column_config.NumberColumn(
        label="QC Confidence",
        help="Quality Control Confidence",
        min_value=0.0,
        max_value=1.0,
    )


# Display DataFrame
edited_df = st.data_editor(
    data=batch_df,
    use_container_width=True,
    num_rows="dynamic",
    column_order=column_order,
    height=500,
    disabled=disabled_columns,
    hide_index=False,
    column_config=column_config,
)
# Remove the image column from the edited DataFrame
edited_df.drop(columns=["image"], inplace=True)
# Sort the DataFrame by qc_confidence if exists
if "qc_confidence" in edited_df.columns:
    edited_df = edited_df.reset_index()

# Edited filename
save_filename = f"{batch}_labels.tsv"

# Download button
st.download_button(
    label="Download Label",
    data=edited_df.to_csv(sep="\t", index=False, quoting=3),
    file_name=save_filename,
    mime="text/csv",
)
