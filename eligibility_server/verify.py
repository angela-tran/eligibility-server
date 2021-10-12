"""
Eligibility Verification route
"""

import datetime
import json
import re
import time

from flask_restful import Resource, reqparse
from jwcrypto import jwe, jwk, jws, jwt
from eligibility_server.database import Database
from eligibility_server import app

with open("./keys/server.key", "rb") as pemfile:
    server_private_key = jwk.JWK.from_pem(pemfile.read())
with open("./keys/client.pub", "rb") as pemfile:
    client_public_key = jwk.JWK.from_pem(pemfile.read())


class Verify(Resource):

    db = Database()
    configs = app.configs

    def _check_headers(self):
        """Ensure correct request headers."""
        req_parser = reqparse.RequestParser()
        req_parser.add_argument(self.db.token_header, location="headers", required=True)
        req_parser.add_argument(self.db.auth_header, location="headers", required=True)
        headers = req_parser.parse_args()
        # verify auth_header's value
        if headers.get(self.db.auth_header) == self.db.auth_token:
            return headers
        else:
            return False

    def _get_token(self, headers):
        """Get the token from request headers"""
        token = headers.get(self.db.token_header, "").split(" ")
        if len(token) == 2:
            return token[1]
        elif len(token) == 1:
            return token[0]
        else:
            raise ValueError("Invalid token format")

    def _get_token_payload(self, token):
        """Decode a token (JWE(JWS))."""
        try:
            # decrypt
            decrypted_token = jwe.JWE(algs=[self.db.jwe_encryption_alg, self.db.jwe_cek_enc])
            decrypted_token.deserialize(token, key=server_private_key)
            decrypted_payload = str(decrypted_token.payload, "utf-8")
            # verify signature
            signed_token = jws.JWS()
            signed_token.deserialize(decrypted_payload, key=client_public_key, alg=self.db.jws_signing_alg)
            # return final payload
            payload = str(signed_token.payload, "utf-8")
            return json.loads(payload)
        except Exception:
            return False

    def _make_token(self, payload):
        """Wrap payload in a signed and encrypted JWT for response."""
        # sign the payload with server's private key
        header = {"typ": "JWS", "alg": self.db.jws_signing_alg}
        signed_token = jwt.JWT(header=header, claims=payload)
        signed_token.make_signed_token(server_private_key)
        signed_payload = signed_token.serialize()
        # encrypt the signed payload with client's public key
        header = {"typ": "JWE", "alg": self.db.jwe_encryption_alg, "enc": self.db.jwe_cek_enc}
        encrypted_token = jwt.JWT(header=header, claims=signed_payload)
        encrypted_token.make_encrypted_token(client_public_key)
        return encrypted_token.serialize()

    def get(self, configs):
        """Respond to a verification request."""
        # introduce small fake delay
        time.sleep(2)

        headers = {}

        # verify required headers and API key check
        try:
            headers = self._check_headers()
        except Exception:
            return "Unauthorized", 403

        # parse inner payload from request token
        try:
            token = self._get_token(headers)
            token_payload = self._get_token_payload(token)
        except Exception as ex:
            return str(ex), 400

        if token_payload:
            try:
                # craft the response payload using parsed request token
                sub, name, eligibility = token_payload["sub"], token_payload["name"], list(token_payload["eligibility"])
                resp_payload = dict(
                    jti=token_payload["jti"],
                    iss=configs.app_name(),
                    # iss="THIS IS STUBBED",
                    iat=int(datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).timestamp()),
                )
                # sub format check
                if re.match(r"^[A-Z]\d{7}$", sub):
                    # eligibility check against db
                    resp_payload["eligibility"] = self.db.check_user(sub, name, eligibility)
                    code = 200
                else:
                    resp_payload["error"] = {"sub": "invalid"}
                    code = 400
                # make a response token with appropriate response code
                return self._make_token(resp_payload), code
            except Exception as ex:
                return str(ex), 500
        else:
            return "Invalid token format", 400
