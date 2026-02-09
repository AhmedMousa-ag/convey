import asyncio
import os
from configs.metadata import (
    MetadataConfig,
    StrategyType,
    add_metadata_pool,
)
from configs.paths import (
    METADATA_PATH,
    MODELS_DIR,
    DATASETS_TEST_DIR,
    STATIC_MODULES_PATH,
)
from controllers.networking.messages import send_msg_sender
from models.server import SubscribeTopic, ServerMessage, MessagesTypes
from controllers.networking.threads import start_threads
from datetime import datetime
from configs.config import DATEIME_FORMAT
from controllers.networking.req_rep import Requester
import shutil
from pathlib import Path
from controllers.networking.p2p import p2p_node
from controllers.verifier.update_verifier import ModelVerifier


def clear_screen():
    """Clear the terminal screen"""
    os.system("cls" if os.name == "nt" else "clear")


def print_header(title):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")


def print_menu(options):
    """Print a numbered menu"""
    for i, option in enumerate(options, 1):
        print(f"{i}. {option}")
    # print(f"{len(options) + 1}. Back to main menu")


async def trigger_file_menu():
    """Handle the trigger file functionality"""
    clear_screen()
    print_header("TRIGGER FILE")

    list_conv_files = os.listdir(METADATA_PATH)

    if len(list_conv_files) == 0:
        print("There's no available files, please upload one or create one.")
        input("\nPress Enter to continue...")
        return

    print("Available files:")
    for i, file in enumerate(list_conv_files, 1):
        print(f"{i}. {file}")

    print("\nEnter file numbers to transmit (comma-separated, e.g., 1,3,4):")
    print("Or press Enter to cancel")

    selection = input("\nYour choice: ").strip()

    if not selection:
        return

    try:
        indices = [int(x.strip()) - 1 for x in selection.split(",")]
        selected_files = [
            list_conv_files[i] for i in indices if 0 <= i < len(list_conv_files)
        ]

        if not selected_files:
            print("No valid files selected.")
            input("\nPress Enter to continue...")
            return

        print(f"\nTransmitting {len(selected_files)} file(s)...")
        for file in selected_files:
            metadata = MetadataConfig.parse_file(os.path.join(METADATA_PATH, file))

            weights_path = Path(metadata.weights_path)
            models_dir = Path(MODELS_DIR)

            if weights_path.exists() and weights_path.parent != models_dir:
                models_dir.mkdir(parents=True, exist_ok=True)
                dest_weights = models_dir / weights_path.name
                print(f"Moving {weights_path} to {dest_weights}")
                shutil.move(str(weights_path), str(dest_weights))
                metadata.weights_path = str(dest_weights)
            elif weights_path.parent == models_dir:
                print(f"Weights already in {models_dir}")
            else:
                print(f"Warning: {weights_path} does not exist")

            # Check and move dataset to DATASETS_TEST_DIR
            dataset_path = Path(metadata.dataset_path)
            datasets_dir = Path(DATASETS_TEST_DIR)

            if dataset_path.exists() and dataset_path.parent != datasets_dir:
                datasets_dir.mkdir(parents=True, exist_ok=True)
                dest_dataset = datasets_dir / dataset_path.name
                print(f"Moving {dataset_path} to {dest_dataset}")
                shutil.move(str(dataset_path), str(dest_dataset))
                metadata.dataset_path = str(dest_dataset)
            elif dataset_path.parent == datasets_dir:
                print(f"Dataset already in {datasets_dir}")
            else:
                print(f"Warning: {dataset_path} does not exist")

            hashed_metadata = metadata.hash_self()
            add_metadata_pool(hashed_metadata, metadata.get_before_hash())
            await send_msg_sender(
                ServerMessage(
                    msg_type=MessagesTypes.SUBSCRIBE.value,
                    message=SubscribeTopic(hashed_metadata=hashed_metadata),
                )
            )
            print(f"Sent {file} to the server")
            requester = Requester(metadata, p2p_node)
            latest_update = (
                datetime.min
                if metadata.latest_updated is None
                else datetime.strptime(metadata.latest_updated, DATEIME_FORMAT)
            )
            requester.ask_is_latest(
                hashed_metadata,
                latest_update,
            )
            if not os.path.exists(metadata.dataset_path):
                requester.sync_dataset(hashed_metadata)

        print("\nAll files transmitted successfully!")
        input("\nPress Enter to continue...")

    except (ValueError, IndexError) as e:
        print(f"Invalid selection: {e}")
        input("\nPress Enter to continue...")


async def upload_file_menu():
    """Handle the upload file functionality"""
    clear_screen()
    print_header("UPLOAD FILE")

    file_path = input(
        "Enter the path to your metadata file (or press Enter to cancel): "
    ).strip()

    if not file_path:
        return

    try:
        with open(file_path, "r") as f:
            metadata_file = MetadataConfig.parse_string(f.read())

        if METADATA_PATH not in metadata_file.weights_path:
            weights_path = Path(metadata_file.weights_path)
            metadata_file.weights_path = os.path.join(METADATA_PATH, weights_path.name)
            os.makedirs(metadata_file.weights_path, exist_ok=True)
        if DATASETS_TEST_DIR not in metadata_file.dataset_path:
            data_path = Path(metadata_file.dataset_path)
            metadata_file.dataset_path = os.path.join(
                DATASETS_TEST_DIR,
                data_path.parent.name if not data_path.is_dir() else data_path.name,
            )
            os.makedirs(metadata_file.dataset_path, exist_ok=True)
        print("\nMetadata content:")
        print(metadata_file.model_dump_json(indent=2))

        confirm = input("\nSave this metadata? (y/n): ").strip().lower()

        if confirm == "y":
            metadata_file.save()
            print(f"\n✓ File uploaded successfully at {METADATA_PATH}")
        else:
            print("\nUpload cancelled.")

        input("\nPress Enter to continue...")

    except FileNotFoundError:
        print(f"\nError: File not found at {file_path}")
        input("\nPress Enter to continue...")
    except Exception as e:
        print(f"\nError reading file: {e}")
        input("\nPress Enter to continue...")


async def create_metadata_menu():
    """Handle the create metadata functionality"""
    clear_screen()
    print_header("CREATE METADATA")

    print("Fill in the fields below to create your MetadataConfig instance.\n")

    try:
        # Get user inputs
        avg_count = int(input("Average Count (integer, default=1): ").strip() or "1")

        print("\nAvailable Merge Strategies:")
        strategies = [strategy.value for strategy in StrategyType]
        for i, strategy in enumerate(strategies, 1):
            print(f"{i}. {strategy}")

        strategy_choice = int(input("\nSelect merge strategy (number): ").strip())
        merge_strategy = strategies[strategy_choice - 1]

        dataset_path = input(
            "\nDataset Path (default=./data): "
        ).strip() or os.path.abspath(os.path.join(os.path.curdir, "data"))
        model_name = input("Model Name (default=my_model): ").strip() or "my_model"
        weights_path = input(
            "Weights Path (default=./saved_models/model_1.pth): "
        ).strip() or os.path.abspath(
            os.path.join(os.path.curdir, "saved_models", "model_1.pth")
        )
        default_static_modules_path = os.path.join(
            STATIC_MODULES_PATH, f"{model_name}_{merge_strategy}.dill"
        )
        static_modules_path = (
            input(
                f"Static Modules Path (default={default_static_modules_path})"
            ).strip()
            or default_static_modules_path
        )
        t_input = input("T - Threshold/Temperature (0.0-1.0, default=0.95): ").strip()
        t = float(t_input) if t_input else 0.95

        if not (0.0 <= t <= 1.0):
            print("\nError: T must be between 0.0 and 1.0")
            input("\nPress Enter to continue...")
            return

        # Display summary
        print("\n" + "-" * 60)
        print("CONFIGURATION SUMMARY:")
        print("-" * 60)
        print(f"Average Count:    {avg_count}")
        print(f"Merge Strategy:   {merge_strategy}")
        print(f"Dataset Path:     {dataset_path}")
        print(f"Model Name:       {model_name}")
        print(f"Weights Path:     {weights_path}")
        print(f"T:                {t}")
        print("-" * 60)

        confirm = input("\nCreate this MetadataConfig? (y/n): ").strip().lower()

        if confirm == "y":
            metadata = MetadataConfig(
                avg_count=avg_count,
                merge_strategy=merge_strategy,
                dataset_path=dataset_path,
                model_name=model_name,
                weights_path=weights_path,
                t=t,
                latest_updated=datetime.now().strftime(DATEIME_FORMAT),
                model_obj_path="",
                static_model_path=static_modules_path,
            )
            metadata.save()
            print(f"\n✓ MetadataConfig created successfully at {METADATA_PATH}")
        else:
            print("\nCreation cancelled.")

        input("\nPress Enter to continue...")

    except (ValueError, IndexError) as e:
        print(f"\nInvalid input: {e}")
        input("\nPress Enter to continue...")
    except Exception as e:
        print(f"\nError creating metadata: {e}")
        input("\nPress Enter to continue...")


async def update_others_weights_menu():
    # List all metadata files and let user choose which one to update.
    clear_screen()
    print_header("UPDATE NETWORK WEIGHTS")
    list_conv_files = os.listdir(METADATA_PATH)
    if len(list_conv_files) == 0:
        print("There's no available files, please upload one or create one.")
        input("\nPress Enter to continue...")
        return
    print("Available files:")
    for i, file in enumerate(list_conv_files, 1):
        print(f"{i}. {file}")
    print("\nEnter file number to update (e.g., 1):")
    print("Or press Enter to cancel")
    selection = input("\nYour choice: ").strip()
    if not selection:
        return
    try:
        index = int(selection.strip()) - 1
        if not (0 <= index < len(list_conv_files)):
            print("Invalid selection.")
            input("\nPress Enter to continue...")
            return
        selected_file = list_conv_files[index]
        metadata = MetadataConfig.parse_file(os.path.join(METADATA_PATH, selected_file))
        print(f"\nSelected file: {selected_file}")
        print(f"Metadata content:\n{metadata.model_dump_json(indent=2)}")
        confirm = input("\nUpdate this model's weights? (y/n): ").strip().lower()
        if confirm != "y":
            print("\nUpdate cancelled.")
            input("\nPress Enter to continue...")
            return
        # Let the user decide where is the new weights file.
        new_weights_path = input(
            "\nEnter the path to the new weights file (or press Enter to cancel): "
        ).strip()

        if not new_weights_path:
            print("\nUpdate cancelled.")
            input("\nPress Enter to continue...")
            return
        if not os.path.exists(new_weights_path):
            print(f"\nError: File not found at {new_weights_path}")
            input("\nPress Enter to continue...")
            return
        if not ModelVerifier(metadata).is_better_model(new_weights_path):
            print("\nThe new model does not have a better score. Update cancelled.")
            return
        # If verified, send update message to others.
        requester = Requester(metadata, p2p_node)
        requester.update_new_weights()
        print("\nUpdate message sent to the network.")
    except (ValueError, IndexError) as e:
        print(f"Invalid selection: {e}")


async def main():
    """Main application loop"""
    start_threads()
    while True:
        clear_screen()
        print_header("CONVEY - Main Menu")

        options = [
            "Trigger file",
            "Upload file",
            "Create metadata",
            "Update network weights",
            "Exit",
        ]

        print_menu(options)
        # print(f"{len(options)}. Exit")

        choice = input("\nEnter your choice: ").strip()

        if choice == "1":
            await trigger_file_menu()
        elif choice == "2":
            await upload_file_menu()
        elif choice == "3":
            await create_metadata_menu()
        elif choice == "4":
            await update_others_weights_menu()
        elif choice == "5":
            print("\nGoodbye!")
            break
        else:
            print("\nInvalid choice. Please try again.")
            input("\nPress Enter to continue...")


if __name__ == "__main__":
    asyncio.run(main())
