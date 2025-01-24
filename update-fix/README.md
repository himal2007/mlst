# MLST Database Update Scripts

This directory contains scripts designed to update the MLST (Multi-Locus Sequence Typing) database for the MLST tool via OAuth authentication. OAuth authentication is required to access data submitted to PubMLST and PasteurDB after 2024-12-31. These scripts allow you to search, prepare, download MLST schemes and update MLST database ensuring that your analyses use the most up-to-date mlst schemes.

These scripts are written to work best with the `mlst` tool. Therefore, it follows it's directory structure and requirements.

## Prerequisites
1. **Install Dependencies**  
   A `requirements.yml` file is provided for reproducibility. To install the required packages: 
   
   ```bash
   conda env create -f requirements.yml
   ```
   This should install all the necessary packages necessary to run the scripts and update the MLST database.

## Workflow Overview
Run the scripts in the following order to update the MLST database:

1. **`bigsdb_downloader.py`**: Set up OAuth authentication to access PubMLST and BIGSdb Pasteur databases.
2. **`get_schemes.py`**: Retrieve MLST schemes using OAuth authentication.
3. **`clean_mlst_schemes.py`**: Sanitise scheme names to align with the `mlst` tool's requirements. Also, fliter and count the number of schemes and species.
4. **`get_mlst_files.py`**: Download MLST schemes and organise them in the required directory structure.
5. **`mlst-make_blast_db`**: Create a BLAST database for the `mlst` tool.

---

## Script Details

### 1. `bigsdb_downloader.py`
This script is written by Keith Jolley and the script is availble at [BIGSdb_downloader GitHub Repository](https://github.com/kjolley/BIGSdb_downloader).   

**Purpose**: Sets up OAuth authentication for accessing PubMLST and BIGSdb Pasteur databases.  

**Usage**:  
```bash
python bigsdb_downloader.py --help
```
**Example setup for OAuth authentication**:
```bash
python bigsdb_downloader.py --key_name PubMLST --site PubMLST --db pubmlst_neisseria_isolates --setup

# Enter client id: xxxxxxxxxxxxxxxxx
# Enter client secret: xxxxxxxxxxxxxxxxx
# Please log in using your user account at https://pubmlst.org/bigsdb?db=pubmlst_neisseria_isolates&page=authorizeClient&oauth_token=xxxxxxxxxx using a web browser to obtain a verification code.
# Please enter verification code:
# Access Token:        xxxxxxxxxxxxxxxxx
# Access Token Secret: xxxxxxxxxxxxxxxxx

# This access token will not expire but may be revoked by the 
# user or the service provider. It will be saved to 
# .bigsdb_tokens/access_tokens.

# File structure:
# .bigsdb_tokens/
# ├── access_tokens
# ├── client_credentials
# └── session_tokens
```
Note that `--db` can be any database in the PubMLST/Pasteur BigsDB system. We just need to set it up once for PubMLST and for PasteurDB.

**Authentication Verification**:  
To confirm authenticated access, compare responses to the following:  
- Unauthenticated:  
  ```bash
  curl https://rest.pubmlst.org/db/pubmlst_neisseria_seqdef/schemes/1 | grep -i authenticate
  ```
  For unauthenticated access, we get a message on the json response saying `"message":"Please note that you are currently restricted to accessing data that was submitted on or prior to 2024-12-31. Please authenticate to access the full dataset."`
- Authenticated:  
  ```bash
  ./bigsdb_downloader.py --key_name PubMLST --site PubMLST --url "https://rest.pubmlst.org/db/pubmlst_neisseria_seqdef/schemes/1" | grep -i authenticate
  ```
  There should be no message about authentication in the response, if we have successfully authenticated.

---

### 2. `get_schemes.py`
This script is modified from the original script written by Keith Jolley and the script is availble at [BIGSdb GitHub Repository](https://github.com/kjolley/BIGSdb/tree/develop/scripts/rest_examples).

**Purpose**: Retrieves all available schemes in PubMLST/PasteurDB using OAuth authentication.  

**Usage**:  
```bash
python get_schemes.py --help
```

```
usage: get_schemes.py [-h] [-e EXCLUDE] [-m MATCH] -k KEY_NAME [-t TOKEN_DIR]
                      [-b {PubMLST,Pasteur}] [-o OUTPUT] [-r] [-v]

optional arguments:
  -h, --help            show this help message and exit
  -e EXCLUDE, --exclude EXCLUDE
                        Scheme name must not include provided term (case
                        sensitive)
  -m MATCH, --match MATCH
                        Scheme name must include provided term (case
                        sensitive)
  -k KEY_NAME, --key_name KEY_NAME
                        Key name to use for token
  -t TOKEN_DIR, --token_dir TOKEN_DIR
                        Directory to store token (default: ./.bigsdb_tokens)
  -b {PubMLST,Pasteur}, --base_api {PubMLST,Pasteur}
                        Select the API source: PubMLST or Pasteur (default:
                        PubMLST)
  -o OUTPUT, --output OUTPUT
                        Output file to save results (default:
                        mlst_schemes.txt)
  -r, --resume          Resume processing from where it stopped. Only to be used after the first run to resume the download
  -v, --verbose         Enable verbose logging for debugging
```

**Example**:
```bash
python get_schemes.py --exclude cgMLST --match MLST --key_name PubMLST
```

**Key Features**:
- `--exclude`: Exclude schemes containing specific terms.
- `--match`: Include only schemes containing specific terms.
- `--resume`: Resume the process if interrupted (requires `processed_dbs.txt`). Note: This is only to be used after the first run to resume the download.
- `--output`: Save output to a specified file (default: `mlst_schemes.txt`).

This takes quite a while to execute. Therefore, `--resume` flag has been added to resume the download if it gets interrupted.

---

### 3. `clean_mlst_schemes.py`
The `get_schemes.py` script downloads the db name and scheme name which are not parsed properly (scheme names can be: `MLST (Oxford)`, `MLST` etc). We need a unique scheme name for each scheme. This script processes the downloaded mlst_schemes.txt file and sanitises the scheme names and species names as per the mlst tool requirements.

**Purpose**: Sanitises MLST scheme names for consistency and compatibility with the `mlst` tool.  

**Usage**:  
```bash
python clean_mlst_schemes.py --help
```

```bash
usage: clean_mlst_schemes.py [-h] -i INPUT [-o OUTPUT] -d DBASES [-f FILTER]
                            [-c] [-v]

Sanitise MLST schemes, extract species and scheme names, and provide filtering
options.

optional arguments:
  -h, --help            show this help message and exit
  -i INPUT, --input INPUT
                        Input file containing mlst_schemes.txt.
  -o OUTPUT, --output OUTPUT
                        Output file for sanitised MLST schemes.
  -d DBASES, --dbases DBASES
                        Path to dbases.sh file for extracting scheme names.
  -f FILTER, --filter FILTER
                        Filter species or schemes using a wildcard pattern.
  -c, --count           Count occurrences of species and schemes.
  -v, --verbose         Enable detailed log messages.
```

**Example**:
```bash
python clean_mlst_schemes.py -i mlst_schemes.txt -d ../db/pubmlst/dbases.sh -o sanitised_mlst_schemes.txt
# filter by species/scheme
python clean_mlst_schemes.py -i mlst_schemes.txt -d ../db/pubmlst/dbases.sh -f acinetobacter -o acinetobacter_schemes.txt
# filter by species/scheme and count
python clean_mlst_schemes.py -i mlst_schemes.txt -d ../db/pubmlst/dbases.sh -f acinetobacter --count
```

**Key Features**:
- Automatically extracts scheme names from `dbases.sh`. Provides option to automatically assign scheme names for new schemes absed on the API URL.
- Automatically extracts species names from the downloaded schemes.
- Allows filtering by species or scheme names using wildcard patterns.
- Counts occurrences of species and schemes.


<details>
    <summary> Auto extraction of scheme?🤔 </summary> 

        First, the script automatically tries to extract the scheme names from the `dbases.sh` file. If the scheme name is not found, it will prompt the user to either print `missing` in the output file or automatically create a scheme name based on the URL. For eg, for URL `https://rest.pubmlst.org/db/pubmlst_afumigatus_seqdef/schemes/1`, the scheme name will be `afumigatus`. If there are multiple schemes, it will append a number to the scheme name. For eg, for URLs `https://rest.pubmlst.org/db/pubmlst_blastocystis_seqdef/schemes/1` and `https://rest.pubmlst.org/db/pubmlst_blastocystis_seqdef/schemes/2`, the scheme names will be `blastocystis_1` and `blastocystis_2` respectively.

  </details>


The script offers feature to filter for particular species/schemes. It is recommended to run with filter option and thus, download only the required schemes so as not to tamper with the existing DBs and schemes.

---

### 4. `get_mlst_files.py`
This script is based on the functions available in [`pyMLST` tool](https://github.com/bvalot/pyMLST).

**Purpose**: Downloads MLST scheme files and organises them in the required directory structure.  

**Usage**:  
```bash
python get_mlst_files.py --help
```


```bash
usage: get_mlst_files.py [-h] -i INPUT [-d DIRECTORY] -k KEY_NAME
                         [-t TOKEN_DIR] [-b {PubMLST,Pasteur}] [-v]

optional arguments:
  -h, --help            show this help message and exit
  -i INPUT, --input INPUT
                        Path to sanitised_mlst_schemes.txt containing MLST
                        scheme URLs
  -d DIRECTORY, --directory DIRECTORY
                        Directory to save the downloaded MLST schemes
                        (default: pubmlst)
  -k KEY_NAME, --key_name KEY_NAME
                        Key name to use for token
  -t TOKEN_DIR, --token_dir TOKEN_DIR
                        Directory to store token (default: ./.bigsdb_tokens)
  -b {PubMLST,Pasteur}, --base_api {PubMLST,Pasteur}
                        Select the API source: PubMLST or Pasteur (default:
                        PubMLST)
  -v, --verbose         Enable verbose logging for debugging
```

**Example**:
```bash
python get_mlst_files.py --input sanitised_mlst_schemes.txt --key_name PubMLST --base_api PubMLST --verbose
```

**Directory Structure**:
The `get_mlst_files.py` script takes the sanitised schemes as an input and updates the pubmlst database. It organises the downloaded files in the default `pubmlst` directory and the file structure is as follows:

```
pubmlst
├── <MLST_scheme_name>
│   ├── loci1.fasta
│   ├── loci2.fasta
│   ├── loci3.fasta
│   └── locin.fasta
│   └── MLST_scheme_name.txt  # MLST profile designations
│   └── database_version.txt  # Last "added" value from JSON
```

---

### 5. `makeblastdb`
The original `mlst-make_blast_db` is modified to accept input and output directory arguments.

**Purpose**: Creates a BLAST database from the downloaded MLST files.  

**Usage**:  
```bash
bash mlst-make_blast_db -h
```

```bash
Usage: ./mlst-make_blast_db [options]

Options:
  -i INPUT_DIR      Path to input directory containing MLST schemes (required)
  -o OUTPUT_DIR     Path to output directory for BLAST database (default: relative to input_dir as ../blast)
  -t TITLE          Title for the BLAST database (default: PubMLST)
  -v                Enable verbose mode
  --dry-run         Simulate actions without creating files
  -h                Display this help message and exit
```

**Example**:
```bash
bash mlst-make_blast_db -i ./pubmlst -t PubMLST -v
```

By default, creates or updates `mlst.*` files in the `blast` directory which can be changed using the `-o` option.

---

## Final Steps
After running all scripts, verify the database setup by running the `mlst` tool with the updated database:
```bash
mlst --blastdb <path_to_blast/mlst.fa> --datadir <path_to_pubmlst_dir>
```

## Troubleshooting
If you encounter issues, check the following:
1. Ensure all scripts were executed in order.
2. Verify OAuth authentication using the steps in `bigsdb_downloader.py`.
3. Confirm directory structure matches the `mlst` tool's requirements.

For additional support, please raise an issue.

