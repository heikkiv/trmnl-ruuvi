# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python application that collects temperature data from Ruuvi sensors and sends it to the Terminal (TRMNL) dashboard service. The project consists of a simple script that:

1. Fetches temperature measurements from Ruuvi sensors via the Ruuvi Network API
2. Processes the data 
3. Posts the processed data to TRMNL's API endpoint
4. Runs on a continuous loop with a 15-minute interval between updates

## Repository Structure

- `measurement_updater.py`: Main script that fetches data from Ruuvi sensors and sends it to TRMNL
- `log.txt`: Log file containing application runtime information
- `notes.txt`: Contains API endpoint and sample curl command
- `updater.log`: Contains logs from previous runs
- `env/`: Python virtual environment directory

## Dependencies

The application depends on:
- Python 3.12
- `requests`: For making HTTP requests
- `ruuvi_decoders`: For decoding Ruuvi sensor data (custom module)

## Common Commands

### Setup Environment

```bash
# Activate the virtual environment
source env/bin/activate
```

### Run the Application

```bash
# Run the main script
python measurement_updater.py
```

### Install Dependencies

```bash
# With virtual environment activated
pip install requests
pip install ruuvi_decoders
```

## Development Workflow

1. Update the Ruuvi API token in `measurement_updater.py` if needed (line 31)
2. Modify the sensor mappings in the `update_measurements_trmnl` function if needed
3. Adjust the update interval by changing the sleep time (default: 15 minutes)
4. Run the script with `python measurement_updater.py`
5. Check `log.txt` for application logs

## Architecture Notes

- The application runs as a single-threaded process that periodically fetches and updates data
- Sensor data is fetched from the Ruuvi Network API using a bearer token
- Data is processed and mapped to specific variables for temperature readings
- Processed data is sent to TRMNL's API via POST requests
- Exception handling captures and logs errors, with a 60-second retry interval
- A custom logger writes output to both the console and a log file

## Code Patterns

- The main program flow is in the `update_measurements_trmnl` function
- The `get_measurements` function handles Ruuvi API interaction and data decoding
- Data is formatted as a JSON payload with the "merge_variables" structure required by TRMNL