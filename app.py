import streamlit as st
import pandas as pd
from pathlib import Path
import base64

def image_to_data_url(image_path: str) -> str:
    """Open an image and convert to base64 data url."""
    # Read image content.
    with open(image_path, "rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode("utf-8")
    # Get image path extension.
    image_extension = image_path.split(".")[-1]
    # Generate data url.
    data_url = f"data:image/{image_extension};base64,{encoded_image}"
    return data_url

def main():
    st.title("CSV/TSV File Editor")

    # File upload
    file = st.file_uploader("Upload a CSV or TSV file", type=["csv", "tsv"])

    if file is None:
        st.stop()

    # Get the path to image
    path_to_image = st.text_input("Path to image column")
    # Do not continue if path_to_image is empty
    if not path_to_image:
        st.stop()

    # Check if the path exists
    path = Path(path_to_image)
    if not path.exists():
        st.error(f"Path does not exist: {path}")
        st.stop()

    # Read the file
    if file.name.endswith('.csv'):
        sep = ','
    elif file.name.endswith('.tsv'):
        sep = '\t'
    else:
        st.error("Invalid file format. Please upload a CSV or TSV file.")
        st.stop()

    # Load the data
    df = pd.read_csv(file, sep=sep)

    # Check if the file has a path and text column
    if not {"path", "text"}.issubset(df.columns):
        st.error("The file must have 'path' and 'text' columns, but got: " + ", ".join(df.columns))
        st.stop()
        
    # Create a temporary path column
    df["image"] = df["path"].apply(lambda x: path.joinpath(x).as_posix())
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
            "image": st.column_config.ImageColumn(width="medium", label="Image Preview", help="Image Preview"),
            "text": st.column_config.TextColumn(label="Text", help="Label of the image."),
        },
    )
    # Remove the image column from the edited DataFrame
    edited_df.drop(columns=["image"], inplace=True)

    # Edited filename
    current_time = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    save_filename = file.name.replace(".", f"_{current_time}.")

    # Download button
    st.download_button(
        label="Download",
        data=edited_df.to_csv(sep="\t", index=False),
        file_name=save_filename,
        mime="text/csv"
    )

if __name__ == "__main__":
    main()