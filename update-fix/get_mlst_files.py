import os
import requests
import argparse
import configparser
from pathlib import Path
from tqdm import tqdm
from rauth import OAuth1Session
import logging
import sys

BASE_API = {
    "PubMLST": "https://rest.pubmlst.org",
    "Pasteur": "https://bigsdb.pasteur.fr/api",
}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', required=True, help='Path to sanitised_mlst_schemes.txt containing MLST scheme URLs')
    parser.add_argument('-d', '--directory', default='pubmlst', help='Directory to save the downloaded MLST schemes (default: pubmlst)')
    parser.add_argument('-k', '--key_name', required=True, help='Key name to use for token')
    parser.add_argument('-t', '--token_dir', default="./.bigsdb_tokens",
                        help='Directory to store token (default: ./.bigsdb_tokens)')
    parser.add_argument('-b', '--base_api', default='PubMLST', choices=['PubMLST', 'Pasteur'],
                        help='Select the API source: PubMLST or Pasteur (default: PubMLST)')
    parser.add_argument('-v', '--verbose', action='store_true', 
                        help='Enable verbose logging for debugging')
    args = parser.parse_args()

    # Get required credentials and tokens
    client_key, client_secret = get_client_credentials(args.key_name, args.token_dir)
    session_token, session_secret = retrieve_session_token(args.key_name, args.token_dir)
    
    if not session_token or not session_secret:
        logging.error("No valid session token found. Please run bigsdb_downloader.py first to set up authentication.")
        sys.exit(1)
    
    check_dir(args.directory)

    # Read the input file and process each line
    with open(args.input, 'r') as infile:
        lines = infile.readlines()

    for line in tqdm(lines, desc="Downloading MLST schemes", unit="scheme"):
        parts = line.strip().split('\t')
        if len(parts) != 3:
            logging.warning(f"Skipping invalid line: {line}")
            continue

        db_name, scheme_name, url = parts
        scheme_dir = os.path.join(args.directory, sanitise_name(scheme_name))
        check_dir(scheme_dir)

        try:
            get_mlst_files(url, scheme_dir, client_key, client_secret, 
                          session_token, session_secret, scheme_name, 
                          verbose=args.verbose)
        except Exception as e:
            logging.error(f"Error downloading scheme for {db_name} - {scheme_name}: {e}")

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

def check_dir(directory):
    """Ensure the directory exists and is writable."""
    path = Path(directory)
    if not path.exists():
        path.mkdir(parents=True)
    if not (path.is_dir() and os.access(directory, os.W_OK)):
        raise PermissionError(f"Cannot write to directory: {directory}")

def sanitise_name(name):
    """Sanitise directory or file names by replacing invalid characters."""
    return name.replace('/', '_').replace('\\', '_').replace(':', '_')

def get_mlst_files(url, directory, client_key, client_secret, session_token, 
                   session_secret, scheme_name, verbose=False):
    """Download MLST data and save them in the given directory."""
    session = OAuth1Session(
        consumer_key=client_key,
        consumer_secret=client_secret,
        access_token=session_token,
        access_token_secret=session_secret,
    )
    
    # Add User-Agent header as required by the API
    session.headers.update({"User-Agent": "BIGSdb downloader"})

    if verbose:
        print(f"Fetching MLST scheme from {url}...")

    try:
        response = session.get(url)
        response.raise_for_status()
        mlst_scheme = response.json()
        
        if verbose:
            print(f"Retrieved MLST scheme: {mlst_scheme}")

        db_version = mlst_scheme.get('last_added', 'Not found')
        logging.info(f"Database version: {db_version}")

        # Save database version to a file
        db_version_path = os.path.join(directory, 'database_version.txt')
        with open(db_version_path, 'w') as version_file:
            version_file.write(db_version)

        # Download loci with progress bar
        for loci in tqdm(mlst_scheme['loci'], desc="Downloading loci", unit="locus"):
            name = loci.split('/')[-1]
            loci_fasta = session.get(loci + '/alleles_fasta')
            loci_fasta.raise_for_status()
            loci_file_name = os.path.join(directory, name + '.tfa')
            with open(loci_file_name, 'wb') as f:
                f.write(loci_fasta.content)

        # Download profiles CSV
        profiles_url = url + '/profiles_csv'
        profiles = session.get(profiles_url)
        profiles.raise_for_status()
        profiles_file_path = os.path.join(directory, f"{sanitise_name(scheme_name)}.txt")
        with open(profiles_file_path, 'w') as f:
            f.write(profiles.text)
            
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            logging.error("Authentication failed. Please check your credentials and tokens.")
            logging.error("Try running bigsdb_downloader.py first to refresh the session token.")
        raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()