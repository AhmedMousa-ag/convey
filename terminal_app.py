import asyncio
import os
from configs.metadata import MetadataConfig, METADATA_PATH, StrategyType
from controllers.networking.messages import send_msg_sender
from models.server import SubscribeTopic
from controllers.networking.ws_client import server_ws_client
from threading import Thread
from controllers.networking.p2p import P2PNode


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
    print(f"{len(options) + 1}. Back to main menu")


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
            await send_msg_sender(SubscribeTopic(hashed_metadata=metadata.hash_self()))
            print(f"✓ Sent {file} to the server")

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

        dataset_path = input("\nDataset Path (default=./data): ").strip() or "./data"
        model_name = input("Model Name (default=my_model): ").strip() or "my_model"
        weights_path = (
            input("Weights Path (default=./saved_models/model_1.pth): ").strip()
            or "./saved_models/model_1.pth"
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


async def main():
    """Main application loop"""
    interactive_thread = Thread(
        target=lambda: asyncio.run(server_ws_client()), daemon=True
    )
    p2p_node = P2PNode()
    p2p_thread = Thread(target=lambda: p2p_node.start_server(), daemon=True)

    interactive_thread.start()
    p2p_thread.start()
    while True:
        clear_screen()
        print_header("CONVEY - Main Menu")

        options = ["Trigger file", "Upload file", "Create metadata", "Exit"]

        print_menu(options[:-1])
        print(f"{len(options)}. Exit")

        choice = input("\nEnter your choice: ").strip()

        if choice == "1":
            await trigger_file_menu()
        elif choice == "2":
            await upload_file_menu()
        elif choice == "3":
            await create_metadata_menu()
        elif choice == "4":
            print("\nGoodbye!")
            break
        else:
            print("\nInvalid choice. Please try again.")
            input("\nPress Enter to continue...")


if __name__ == "__main__":
    asyncio.run(main())
