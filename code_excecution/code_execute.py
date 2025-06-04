import requests
import time
import base64
import os
from dotenv import load_dotenv

# Load the .env file
load_dotenv()

# Read the value from environment
# The README specifies `RAPID_API_TOKEN` so we
# read this variable to avoid case mismatch issues
rapid_api_token = os.getenv('RAPID_API_TOKEN')



def code_execution(lang_id,code,stdin):
    if lang_id >= 45:
        base_url = "judge0-ce.p.rapidapi.com"    
    else:
        base_url = "judge0-extra-ce.p.rapidapi.com"

    if not code:
        return ({"error": "No code provided!"}), 400
    encoded_code = base64.b64encode(code.encode()).decode()
    encoded_stdin = base64.b64encode(stdin.encode()).decode()
    
    SUBMISSION_URL = "https://" + base_url + "/submissions" 
    GET_SUBMISSION_URL = "https://" + base_url + "/submissions/{}"


    payload = {
        "language_id": lang_id,
        "source_code": encoded_code,
        "stdin": encoded_stdin
    }

    query_params = {
        "base64_encoded": "true",
        "fields": "*",
        }
    
    HEADERS = {
	"X-RapidAPI-Key": rapid_api_token,
	"X-RapidAPI-Host": base_url
    }

    response = requests.post(SUBMISSION_URL, json=payload, headers=HEADERS, params=query_params)
    if response.status_code != 201:
        return ({"error": "Failed to submit code for execution"}), 500
    
    token = response.json().get("token")

    # Fetching result (using a simple loop for waiting - can be optimized)
    for _ in range(10):  # try 10 times with a delay
        response = requests.get(GET_SUBMISSION_URL.format(token), headers=HEADERS, params=query_params)
        if response.status_code != 200:
            #return jsonify({"error": "Failed to get code execution result"}), 500
            return ({"error": "Failed to get code execution result"}), 500

        result = response.json()
        if result["status"]["id"] in [3, 11, 12, 13, 17]:  # Finished statuses
            decoded_output = base64.b64decode(result["stdout"]).decode() if result["stdout"] else ""
            decoded_error = base64.b64decode(result["stderr"]).decode() if result["stderr"] else ""

            return ({"output": decoded_output, "error": decoded_error, "status": result["status"]["description"]}), 200


        time.sleep(1)  # wait for a second before trying again

    return ({"error": "Code execution took too long"}), 408


