#!/usr/bin/env python3
import os
import requests
import re
import argparse
import configparser
from pathlib import Path
from tqdm import tqdm
from rauth import OAuth1Session
import sys
import logging

BASE_API = {
    "PubMLST": "https://rest.pubmlst.org",
    "Pasteur": "https://bigsdb.pasteur.fr/api",
}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-e', '--exclude', help='Scheme name must not include provided term (case sensitive)')
    parser.add_argument('-m', '--match', help='Scheme name must include provided term (case sensitive)')
    parser.add_argument('-k', '--key_name', required=True, help='Key name to use for token')
    parser.add_argument('-t', '--token_dir', default="./.bigsdb_tokens", 
                        help='Directory to store token (default: ./.bigsdb_tokens)')
    parser.add_argument('-b', '--base_api', default='PubMLST', choices=['PubMLST', 'Pasteur'],
                        help='Select the API source: PubMLST or Pasteur (default: PubMLST)')
    parser.add_argument('-o', '--output', default="mlst_schemes.txt", 
                        help='Output file to save results (default: mlst_schemes.txt)')
    parser.add_argument('-r', '--resume', action='store_true', 
                        help='Resume processing from where it stopped. Only to be used after the first run to resume the download.')
    parser.add_argument('-v', '--verbose', action='store_true', 
                        help='Enable verbose logging for debugging')
    args = parser.parse_args()

    # Get required credentials and tokens
    client_key, client_secret = get_client_credentials(args.key_name, args.token_dir)
    session_token, session_secret = retrieve_session_token(args.key_name, args.token_dir)
    
    if not session_token or not session_secret:
        logging.error("No valid session token found. Please run bigsdb_downloader.py first to set up authentication.")
        sys.exit(1)

    base_uri = BASE_API[args.base_api]

    # Initialise or clear files based on resume flag
    processed_file = "processed_dbs.txt"
    if not args.resume:
        # Clear both output and processed files if not resuming
        clear_file(args.output)
        clear_file(processed_file)
    
    processed_dbs = load_processed_databases(processed_file)

    resources = fetch_resources(base_uri, client_key, client_secret, 
                              session_token, session_secret, verbose=args.verbose)
    
    for resource in tqdm(resources, desc="Processing resources"):
        if 'databases' in resource:
            for db in resource['databases']:
                if db['description'] in processed_dbs:
                    if args.verbose:
                        print(f"Skipping already processed database: {db['description']}")
                    continue
                
                try:
                    get_matching_schemes(db, args.match, args.exclude, 
                                      client_key, client_secret,
                                      session_token, session_secret,
                                      args.output, processed_file, verbose=args.verbose)
                except Exception as e:
                    print(f"Error processing {db['description']}: {e}")
                    continue

def clear_file(file_path):
    """Clear the contents of a file or create it if it doesn't exist."""
    with open(file_path, 'w') as f:
        f.write('')

def get_client_credentials(key_name, token_dir):
    """Get OAuth client credentials from config file."""
    config = configparser.ConfigParser(interpolation=None)
    file_path = Path(f"{token_dir}/client_credentials")
    
    if file_path.is_file():
        config.read(file_path)
        if config.has_section(key_name):
            return (config[key_name]["client_id"], 
                   config[key_name]["client_secret"])
    
    raise ValueError(f"Client credentials not found for {key_name}")

def retrieve_session_token(key_name, token_dir):
    """Get OAuth session token from config file."""
    config = configparser.ConfigParser(interpolation=None)
    file_path = Path(f"{token_dir}/session_tokens")
    
    if file_path.is_file():
        config.read(file_path)
        if config.has_section(key_name):
            return (config[key_name]["token"], 
                   config[key_name]["secret"])
    
    return None, None

def fetch_resources(base_uri, client_key, client_secret, session_token, session_secret, verbose=False):
    if verbose:
        print(f"Fetching resources from {base_uri}")
    return fetch_json(base_uri, client_key, client_secret, session_token, session_secret, verbose)

def check_dir(directory):
    path = Path(directory)
    if not path.exists():
        path.mkdir(parents=True)
    if not (path.is_dir() and os.access(directory, os.W_OK)):
        raise PermissionError(f"Cannot write to directory: {directory}")

def load_processed_databases(file_path):
    if not os.path.exists(file_path):
        return set()
    with open(file_path, 'r') as f:
        return set(line.strip() for line in f)

def save_processed_database(file_path, db_description):
    with open(file_path, 'a') as f:
        f.write(f"{db_description}\n")

def get_matching_schemes(db, match, exclude, client_key, client_secret, 
                        session_token, session_secret, output_file, processed_file, verbose=False):
    # Check if this is a sequence definition database either by name or description
    is_seqdef = ('seqdef' in db['name'].lower() or 
                 'definitions' in db.get('description', '').lower())
    
    if is_seqdef:
        try:
            db_attributes = fetch_json(db['href'], client_key, client_secret, 
                                     session_token, session_secret, verbose=verbose)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                print(f"The token does not allow access to the `{db['description']}` database. "
                      f"So, the `{db['description']}` database will be skipped.\n"
                      "To download the data, please ensure your account has access to this database.")
                save_processed_database(processed_file, db['description'])
                return
            elif e.response.status_code == 404:
                print(f"The resource `{db['href']}` for the `{db['description']}` database was not found (404). "
                      "Skipping this database.")
                save_processed_database(processed_file, db['description'])
                return
            else:
                raise
        
        if not db_attributes or 'schemes' not in db_attributes:
            save_processed_database(processed_file, db['description'])
            return
        
        schemes = fetch_json(db_attributes['schemes'], client_key, client_secret, 
                           session_token, session_secret, verbose=verbose)
        
        if schemes and 'schemes' in schemes:
            matching_schemes = []
            for scheme in schemes['schemes']:
                if match and not re.search(match, scheme['description'], flags=0):
                    continue
                if exclude and re.search(exclude, scheme['description'], flags=0):
                    continue
                matching_schemes.append(f"{db['description']}\t{scheme['description']}\t{scheme['scheme']}\n")
            
            if matching_schemes:  # Only write to file if we found matching schemes
                with open(output_file, 'a') as f:
                    f.writelines(matching_schemes)
        
        save_processed_database(processed_file, db['description'])
def fetch_json(url, client_key, client_secret, session_token, session_secret, verbose=False):
    if verbose:
        print(f"Fetching JSON from {url}")
    
    session = OAuth1Session(
        consumer_key=client_key,
        consumer_secret=client_secret,
        access_token=session_token,
        access_token_secret=session_secret,
    )
    
    # Add User-Agent header as required by the API
    session.headers.update({"User-Agent": "BIGSdb downloader"})

    try:
        response = session.get(url)
        if verbose:
            print(f"Response code: {response.status_code}, URL: {url}")
        if response.status_code == 404:
            print(f"Resource not found at URL: {url}")
            return None
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            logging.error("Authentication failed. Please check your credentials and tokens.")
            logging.error("Try running bigsdb_downloader.py first to refresh the session token.")
        raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()