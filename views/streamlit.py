import streamlit as st
from configs.metadata import MetadataConfig, METADATA_PATH, StrategyType
import os
from controllers.networking.messages import send_msg_sender
from models.server import SubscribeTopic, ServerMessage, MessagesTypes


async def streamlit_GUI():
    tabs = st.tabs(["Trigger file", "Upload file", "Create metadata"])
    st.title("Convey")
    with tabs[0]:
        list_conv_files = os.listdir(METADATA_PATH)
        if len(list_conv_files) > 0:
            selected_files = st.multiselect("Available files", list_conv_files)
            if len(selected_files) > 0:
                start_trans = st.button("Start transmitting")
                if start_trans:
                    for file in selected_files:
                        metadata = MetadataConfig.parse_file(
                            os.path.join(METADATA_PATH, file)
                        )
                        await send_msg_sender(
                            ServerMessage(
                                msg_type=MessagesTypes.SUBSCRIBE.value,
                                message=SubscribeTopic(
                                    hashed_metadata=metadata.hash_self()
                                ),
                            )
                        )
                        st.write("Sent file to the server.")
        else:
            st.write("There's no available files, please upload one or create one.")

    with tabs[1]:
        # File uploader widget
        uploaded_file = st.file_uploader("Choose a metadata file", type=None)
        # Display file information if a file is uploaded
        if uploaded_file is not None:
            metadata_file = MetadataConfig.parse_string(uploaded_file.read().decode())
            st.write(metadata_file.model_dump_json())
            metadata_file.save()
            st.success(f"File uploaded successfully at {METADATA_PATH}")
            # meta_data = metadata_file.hash_self()
            # asyncio.run(send_msg_sender(meta_data))
    with tabs[2]:
        st.markdown(
            "Fill in the fields below to create your `MetadataConfig` instance."
        )

        # Create input fields
        st.header("Configuration Parameters")

        col1, col2 = st.columns(2)

        with col1:
            avg_count = st.number_input(
                "Average Count",
                min_value=1,
                value=1,
                step=1,
                help="Integer value for average count",
            )

            merge_strategy = st.selectbox(
                "Merge Strategy",
                options=[strategy.value for strategy in StrategyType],
                help="Select the merge strategy type",
            )

            dataset_path = st.text_input(
                "Dataset Path",
                value="./data",
                help="Path to the dataset directory or file",
            )

        with col2:
            model_name = st.text_input(
                "Model Name", value="my_model", help="Name of the model"
            )

            weights_path = st.text_input(
                "Weights Path",
                value="./saved_models/model_1.pth",
                help="Path to the model weights file",
            )

            t = st.number_input(
                "T (Threshold/Temperature)",
                min_value=0.0,
                value=0.95,
                step=0.01,
                max_value=1.0,
                format="%.3f",
                help="Float value for t parameter",
            )

        # Create the config instance
        st.header("Generated Configuration")

        if st.button("Create MetadataConfig", type="primary"):
            # Create the config instance
            metadata = MetadataConfig(
                avg_count=avg_count,
                merge_strategy=merge_strategy,
                dataset_path=dataset_path,
                model_name=model_name,
                weights_path=weights_path,
                t=t,
            )
            metadata.save()
            # Display success message
            st.success(f"MetadataConfig created successfully at {METADATA_PATH}")
    return uploaded_file
