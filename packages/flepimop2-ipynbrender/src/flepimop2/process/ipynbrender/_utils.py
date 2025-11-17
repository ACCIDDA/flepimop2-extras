from shutil import which


def _which_jupyter() -> str:
    """
    Find the 'jupyter' executable in the system PATH.

    Returns:
        The absolute path to the 'jupyter' executable as a string.

    Raises:
        FileNotFoundError: If 'jupyter' is not found in the system PATH.
    """
    jupyter = which("jupyter")
    if jupyter is None:
        msg = "jupyter executable not found in PATH"
        raise FileNotFoundError(msg)
    return jupyter
