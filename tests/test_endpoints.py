import pytest
from api_test_utils.apigee_api_apps import ApigeeApiDeveloperApps
from api_test_utils.apigee_api_products import ApigeeApiProducts
import uuid
from time import time
import jwt
import requests
from .configuration import config
import json

SESSION = requests.Session()


class TestEndpoints:

    @pytest.fixture()
    async def test_app_and_product(self):
        """Create a fresh test app and product consuming the patient-care-aggregator-reporting proxy
        The app and products are destroyed at the end of the test
        """
        print("\nCreating Default App and Product..")
        apigee_product = ApigeeApiProducts()
        await apigee_product.create_new_product()
        await apigee_product.update_proxies(
            [config.PROXY_NAME, f"identity-service-{config.ENVIRONMENT}"]
        )
        await apigee_product.update_scopes(
            ["urn:nhsd:apim:app:level3:patient-care-aggregator-reporting"]
        )
        # Product ratelimit
        product_ratelimit = {
            f"{config.PROXY_NAME}": {
                "quota": {
                    "limit": "300",
                    "enabled": True,
                    "interval": 1,
                    "timeunit": "minute",
                },
                "spikeArrest": {"ratelimit": "100ps", "enabled": True},
            }
        }
        await apigee_product.update_attributes({"ratelimiting": json.dumps(product_ratelimit)})

        await apigee_product.update_environments([config.ENVIRONMENT])

        apigee_app = ApigeeApiDeveloperApps()
        await apigee_app.create_new_app()

        # Set default JWT Testing resource url and app ratelimit
        app_ratelimit = {
            f"{config.PROXY_NAME}": {
                "quota": {
                    "limit": "300",
                    "enabled": True,
                    "interval": 1,
                    "timeunit": "minute",
                },
                "spikeArrest": {"ratelimit": "100ps", "enabled": True},
            }
        }
        await apigee_app.set_custom_attributes(
            {
                "jwks-resource-url": "https://raw.githubusercontent.com/NHSDigital/"
                "identity-service-jwks/main/jwks/internal-dev/"
                "9baed6f4-1361-4a8e-8531-1f8426e3aba8.json",
                "ratelimiting": json.dumps(app_ratelimit),
            }
        )

        await apigee_app.add_api_product(api_products=[apigee_product.name])

        yield apigee_product, apigee_app

        # Teardown
        print("\nDestroying Default App and Product..")
        await apigee_app.destroy_app()
        await apigee_product.destroy_product()

    @pytest.fixture()
    async def get_token(self, test_app_and_product):
        test_product, test_app = test_app_and_product

        """Call identity server to get an access token"""

        # Create jwt for client assertion (APIM-authentication)
        client_assertion_private_key = config.ENV["client_assertion_private_key"]
        with open(client_assertion_private_key, "r") as f:
            private_key = f.read()
        url = "https://internal-dev.api.service.nhs.uk/oauth2/token"
        claims = {
            "sub": test_app.client_id,  # TODO:save this on secrets manager or create app on the fly
            "iss": test_app.client_id,
            "jti": str(uuid.uuid4()),
            "aud": url,
            "exp": int(time()) + 300,  # 5mins in the future
        }

        additional_headers = {"kid": "test-1"}
        client_assertion = jwt.encode(
            claims, private_key, algorithm="RS512", headers=additional_headers
        )

        # Get token using token client credentials with signed JWT
        resp = SESSION.post(
            url,
            headers={"foo": "bar"},
            data={
                "grant_type": "client_credentials",
                "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                "clientId": test_app.client_id,
                "client_assertion": client_assertion,
                "header": additional_headers,
                "algorithm": "RS512"
            }
        )

        print(f'Auth server response: {resp.json()}')

        return resp.json()["access_token"]

    def test_happy_path(self, get_token):
        # Given I have a token
        token = get_token
        expected_status_code = 200
        proxy_url = f"https://internal-dev.api.service.nhs.uk/{config.ENV['base_path']}"
        print(f'Proxy URL: {proxy_url}')
        # When calling the proxy
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Correlation-ID": "apim-unit-test",
            "client-id": "apim-unit-test"
        }
        payload = [
            {
                "EventCode": "APPT-VIEW",
                "Timestamp": "2023-08-22T11:00:00+00:00",
                "SessionId": "apim-unit-test",
                "AppointmentId": "apim-unit-test"
            }
        ]
        resp = SESSION.post(url=proxy_url, headers=headers, json=json.dumps(payload))
        print(f'Proxy response: {resp.json()}')
        # Then
        assert resp.status_code == expected_status_code
