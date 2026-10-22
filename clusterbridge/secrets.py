import keyring

SERVICE_NAME = "clusterbridge"


def save_password(connection_id: str, password: str) -> None:
    if not password:
        raise ValueError("密码不能为空")
    keyring.set_password(SERVICE_NAME, connection_id, password)


def load_password(connection_id: str) -> str | None:
    return keyring.get_password(SERVICE_NAME, connection_id)


def delete_password(connection_id: str) -> None:
    try:
        keyring.delete_password(SERVICE_NAME, connection_id)
    except keyring.errors.PasswordDeleteError:
        pass
