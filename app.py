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


def image_to_data_url(zip_file: zipfile.ZipFile, image_path: str) -> str:
    """Open an image and convert to base64 data url."""
    # Read image content in zip file.
    with zip_file.open(image_path) as image_file:
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

# File upload
file = st.file_uploader("Upload a CSV or TSV file", type=["zip"])

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

# Get the file content from the zip file
with zip_file.open(label_file) as f:
    label_content = f.read()
    label_bytes = io.BytesIO(label_content)

# Read label file
sep = "\t" if label_file.endswith(".tsv") else ","
df = pd.read_csv(label_bytes, sep=sep)

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

# Display DataFrame
edited_df = st.data_editor(
    data=df,
    use_container_width=True,
    num_rows="dynamic",
    column_order=["image", "text"],
    height=500,
    disabled=("image",),
    hide_index=False,
    column_config={
        "image": st.column_config.ImageColumn(
            width="medium", label="Image Preview", help="Image Preview"
        ),
        "text": st.column_config.TextColumn(label="Text", help="Label of the image."),
    },
)
# Remove the image column from the edited DataFrame
edited_df.drop(columns=["image"], inplace=True)

# Edited filename
current_time = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
label_filename = op.basename(label_file)
save_filename = label_filename.replace(".", f"_{current_time}.")

# Download button
st.download_button(
    label="Download Label",
    data=edited_df.to_csv(sep="\t", index=False),
    file_name=save_filename,
    mime="text/csv",
)
