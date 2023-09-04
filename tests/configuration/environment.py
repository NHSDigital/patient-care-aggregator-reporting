import os


def get_env(variable_name: str) -> str:
    """Returns a environment variable"""
    try:
        var = os.environ[variable_name]
        if not var:
            raise RuntimeError(f"Variable is null, Check {variable_name}.")
        return var
    except KeyError:
        raise RuntimeError(f"Variable is not set, Check {variable_name}.")


ENV = {
    # Apigee
    "environment": get_env("APIGEE_ENVIRONMENT"),
    "base_path": get_env("SERVICE_BASE_PATH"),
    "id_token_private_key": get_env("ID_TOKEN_NHS_LOGIN_PRIVATE_KEY_ABSOLUTE_PATH"),
    "client_assertion_private_key": get_env("JWT_PRIVATE_KEY_ABSOLUTE_PATH"),
    "proxy_name": get_env("FULLY_QUALIFIED_SERVICE_NAME")
}
