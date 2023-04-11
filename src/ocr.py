from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from azure.cognitiveservices.vision.computervision.models import VisualFeatureTypes
from msrest.authentication import CognitiveServicesCredentials

from array import array
import os
from PIL import Image
import sys
import time

# Read subscription key and endpoint URL from environment variables
subscription_key = os.environ['AZURE_COMPUTER_VISION_SUBSCRIPTION_KEY']
endpoint = os.environ['AZURE_COMPUTER_VISION_ENDPOINT']

computervision_client = ComputerVisionClient(endpoint, CognitiveServicesCredentials(subscription_key))
    
def get_text(image_path):
    print("===== Read File - remote =====")
    # Call API with URL and raw response (allows you to get the operation location)
    read_response = computervision_client.read(image_path,  raw=True)

    # Get the operation location (URL with an ID at the end) from the response
    read_operation_location = read_response.headers["Operation-Location"]
    # Grab the ID from the URL
    operation_id = read_operation_location.split("/")[-1]

    # Call the "GET" API and wait for it to retrieve the results 
    while True:
        read_result = computervision_client.get_read_result(operation_id)
        if read_result.status not in ['notStarted', 'running']:
            break
        time.sleep(1)

    # Return the detected text
    if read_result.status == OperationStatusCodes.succeeded:
        out = ""
        for text_result in read_result.analyze_result.read_results:
            for line in text_result.lines:
                out = out + line.text + "\n"
    return out

def main():
    image_path = 'test.png'
    print(get_text(image_path))

if __name__ == '__main__':
    main()
