from pathlib import Path


def normalize_path(path_value: str) -> str:
    return str(Path(path_value).expanduser())


def is_within_directory(path_value: str, directory: str) -> bool:
    try:
        Path(path_value).expanduser().resolve().relative_to(
            Path(directory).expanduser().resolve()
        )
        return True
    except ValueError:
        return False


def is_directory_has_files(path_value: str) -> bool:
    path = Path(path_value).expanduser()
    return path.is_dir() and any(path.iterdir())
