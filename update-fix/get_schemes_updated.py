import os
import requests
import re
import argparse
import configparser
from pathlib import Path
from rauth import OAuth1Session

# Argument parser for command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument('--exclude', help='Scheme name must not include provided term')
parser.add_argument('--match', help='Scheme name must include provided term')
parser.add_argument('--key_name', required=True, help='Name of API key')
parser.add_argument('--token_dir', default='./.bigsdb_tokens', help='Directory for tokens')
args = parser.parse_args()

BASE_API = "https://rest.pubmlst.org"

def main():
    # Ensure token directory exists and retrieve the session token
    check_dir(args.token_dir)
    token, secret = retrieve_token("session")
    if not token or not secret:
        token, secret = get_new_session_token()

    # Create an authenticated session
    session = create_authenticated_session(token, secret)

    # Retrieve resources and filter schemes
    resources = session.get(BASE_API).json()
    for resource in resources:
        if resource['databases']:
            for db in resource['databases']:
                get_matching_schemes(db, session)

def get_matching_schemes(db, session):
    if re.search(r'definitions', db['description'], flags=0):
        db_attributes = session.get(db['href']).json()
        if 'schemes' not in db_attributes:
            return
        schemes = session.get(db_attributes['schemes']).json()
        for scheme in schemes['schemes']:
            if args.match and not re.search(args.match, scheme['description'], flags=0):
                continue
            if args.exclude and re.search(args.exclude, scheme['description'], flags=0):
                continue
            output = f"{db['description']}\t{scheme['description']}\t{scheme['scheme']}"
            print(output)

def check_dir(directory):
    """Ensure the token directory exists and is writable."""
    path = Path(directory)
    if path.is_dir() and os.access(directory, os.W_OK):
        return
    elif not path.exists():
        path.mkdir(parents=True, mode=0o700)
    else:
        raise PermissionError(f"Token directory '{directory}' exists but is not writable.")

def retrieve_token(token_type):
    """Retrieve a saved token from the token directory."""
    token_file = Path(f"{args.token_dir}/{token_type}_tokens")
    if token_file.is_file():
        config = configparser.ConfigParser()
        config.read(token_file)
        if config.has_section(args.key_name):
            token = config[args.key_name]["token"]
            secret = config[args.key_name]["secret"]
            return token, secret
    return None, None

def get_new_session_token():
    """Retrieve a new session token using OAuth."""
    access_token, access_secret = retrieve_token("access")
    if not access_token or not access_secret:
        access_token, access_secret = get_new_access_token()

    service = OAuth1Service(
        name="BIGSdb_downloader",
        consumer_key=access_token,
        consumer_secret=access_secret,
        base_url=BASE_API,
    )

    url = f"{BASE_API}/db/oauth/get_session_token"
    session_request = OAuth1Session(
        access_token, access_secret, access_token=access_token, access_token_secret=access_secret
    )
    response = session_request.get(url)

    if response.status_code == 200:
        token = response.json()["oauth_token"]
        secret = response.json()["oauth_token_secret"]

        # Save session token
        save_token("session", token, secret)
        return token, secret
    else:
        raise RuntimeError("Failed to get session token.")

def get_new_access_token():
    """Retrieve a new access token via OAuth."""
    client_id = input("Enter client ID: ").strip()
    client_secret = input("Enter client secret: ").strip()

    service = OAuth1Service(
        name="BIGSdb_downloader",
        consumer_key=client_id,
        consumer_secret=client_secret,
        base_url=BASE_API,
    )

    request_token, request_secret = service.get_request_token()
    auth_url = service.get_authorize_url(request_token)
    print(f"Visit this URL to authorize the application: {auth_url}")
    verifier = input("Enter the verification code: ").strip()

    session = service.get_auth_session(
        request_token, request_secret, method="POST", data={"oauth_verifier": verifier}
    )

    token = session.access_token
    secret = session.access_token_secret

    save_token("access", token, secret)
    return token, secret

def save_token(token_type, token, secret):
    """Save a token to the token directory."""
    token_file = Path(f"{args.token_dir}/{token_type}_tokens")
    config = configparser.ConfigParser()
    if token_file.is_file():
        config.read(token_file)
    config[args.key_name] = {"token": token, "secret": secret}
    with token_file.open("w") as file:
        config.write(file)

def create_authenticated_session(token, secret):
    """Create an authenticated session using OAuth."""
    return OAuth1Session(
        consumer_key=token,
        consumer_secret=secret,
        access_token=token,
        access_token_secret=secret,
    )

if __name__ == "__main__":
    main()

