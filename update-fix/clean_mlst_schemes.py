import argparse
import re
from pathlib import Path
import sys

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Sanitise MLST schemes, extract species and scheme names, and provide filtering options."
    )
    parser.add_argument(
        "-i",
        "--input",
        type=str,
        required=True,
        help="Input file containing mlst_schemes.txt.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="sanitised_mlst_schemes.txt",
        help="Output file for sanitised MLST schemes. default: sanitised_mlst_schemes.txt",
    )
    parser.add_argument(
        "-d",
        "--dbases",
        type=str,
        required=True,
        help="Path to dbases.sh file for extracting scheme names.",
    )
    parser.add_argument(
        "-f",
        "--filter",
        type=str,
        help="Filter species or schemes using a wildcard pattern.",
    )
    parser.add_argument(
        "-c",
        "--count",
        action="store_true",
        help="Count occurrences of species and schemes (wildcard search supported).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable detailed log messages.",
    )
    return parser.parse_args()

def log(message, verbose):
    if verbose:
        print(message)

def sanitise_species(species_column):
    return species_column.replace("sequence/profile definitions", "").strip()

def extract_scheme_name(url, dbases_file):
    with open(dbases_file, "r") as db_file:
        for line in db_file:
            match = re.search(r"pubmlst/([^/]+)/", line)
            if match and url in line:
                return match.group(1)
    return None

def auto_generate_scheme_name(url, existing_schemes):
    base_name = re.search(r"pubmlst_([^_]+)_seqdef", url)
    if base_name:
        base_name = base_name.group(1)
        match = re.search(r"schemes/(\d+)", url)
        if match:
            scheme_id = match.group(1)
            if scheme_id == "1" and all(not scheme.startswith(base_name) for scheme in existing_schemes):
                return base_name
            return f"{base_name}_{scheme_id}"
    return "missing"

def process_file(input_file, output_file, dbases_file, filter_pattern, count, verbose):
    sanitised_data = []
    missing_schemes = []
    existing_schemes = set()

    with open(input_file, "r") as infile:
        for line in infile:
            columns = line.strip().split("\t")
            if len(columns) != 3:
                log(f"Skipping malformed line: {line}", verbose)
                continue

            species = sanitise_species(columns[0])

            if filter_pattern and not (
                re.search(filter_pattern, species, re.IGNORECASE) or
                re.search(filter_pattern, columns[2], re.IGNORECASE)
            ):
                log(f"Skipping entry due to filter mismatch: {line.strip()}", verbose)
                continue

            scheme_name = extract_scheme_name(columns[2], dbases_file)

            if scheme_name is None:
                missing_schemes.append(columns[2])

            existing_schemes.add(scheme_name if scheme_name else "missing")
            sanitised_data.append((species, scheme_name, columns[2]))

    if missing_schemes:
        log("\nThe following URLs have missing schemes:", verbose)
        for url in missing_schemes:
            log(url, verbose)

        user_choice = input("\nDo you want to set missing schemes as 'missing' or auto-generate them? (Type 'missing' or 'auto'): ").strip().lower()
        if user_choice == "auto":
            for idx, (species, scheme, url) in enumerate(sanitised_data):
                if scheme is None:
                    auto_scheme = auto_generate_scheme_name(url, existing_schemes)
                    log(f"Automatically generated scheme name: {auto_scheme} for URL: {url}", verbose)
                    sanitised_data[idx] = (species, auto_scheme, url)
        elif user_choice == "missing":
            sanitised_data = [
                (species, scheme if scheme else "missing", url)
                for species, scheme, url in sanitised_data
            ]
        else:
            log("Invalid choice. Defaulting to 'missing' for missing schemes.", verbose)
            sanitised_data = [
                (species, scheme if scheme else "missing", url)
                for species, scheme, url in sanitised_data
            ]

    if count:
        species_count = {}
        scheme_count = {}
        for species, scheme, _ in sanitised_data:
            species_count[species] = species_count.get(species, 0) + 1
            scheme_count[scheme] = scheme_count.get(scheme, 0) + 1

        print("Species count:")
        for species, count in species_count.items():
            print(f"{species}: {count}")

        print("\nScheme count:")
        for scheme, count in scheme_count.items():
            print(f"{scheme}: {count}")

    with open(output_file, "w") as outfile:
        for species, scheme, url in sanitised_data:
            outfile.write(f"{species}\t{scheme}\t{url}\n")

def main():
    args = parse_arguments()
    process_file(
        args.input,
        args.output,
        args.dbases,
        args.filter,
        args.count,
        args.verbose,
    )

if __name__ == "__main__":
    main()
