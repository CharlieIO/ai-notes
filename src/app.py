from io import BytesIO
import os
import uuid
from flask import Flask, render_template, request, jsonify, redirect, url_for, Markup
from PIL import Image
import boto3
import markdown
import logging
from processing import process_image

# Logging setup
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

BUCKET_NAME = 'notes-helper-imgstore'
DYNAMODB_TABLE_NAME = 'notes-helper-image-processing-results'

AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', None)
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', None)

s3 = boto3.client('s3', region_name=AWS_REGION, aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION, aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
dynamodbClient = boto3.client('dynamodb', region_name=AWS_REGION, aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

def create_dynamodb_table():
    logging.info("Checking for existing tables...")
    existing_tables = dynamodbClient.list_tables()['TableNames']

    logging.info("Existing tables: %s", existing_tables)

    if DYNAMODB_TABLE_NAME not in existing_tables:
        logging.info("Creating new DynamoDB table: %s", DYNAMODB_TABLE_NAME)
        table = dynamodb.create_table(
            TableName=DYNAMODB_TABLE_NAME,
            KeySchema=[
                {
                    'AttributeName': 'img_uuid',
                    'KeyType': 'HASH'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'img_uuid',
                    'AttributeType': 'S'
                }
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )
        table.meta.client.get_waiter('table_exists').wait(TableName=DYNAMODB_TABLE_NAME)
        logging.info("Table %s created successfully", DYNAMODB_TABLE_NAME)

@app.route('/')
def index():
    logging.info("Calling the index...")
    img_uuid = request.args.get('img_uuid', None)
    logging.info("img_uuid: %s", img_uuid)
    return render_template('upload.html', img_uuid=img_uuid)

@app.route('/view_result', methods=['GET'])
def view_result():
    img_uuids = request.args.get('img_uuids', None)
    logging.info("img_uuids: %s", img_uuids)
    if img_uuids:
        uuids = img_uuids.split("|")
        image_urls = []
        processing_results = []

        if len(uuids) > 1:  # If we have more than one UUID, we're dealing with a multi-image upload
            image_urls.extend(get_image_url(img_uuid) for img_uuid in uuids)
            processing_results.extend(get_processing_result(img_uuid) for img_uuid in uuids)

            # Also get the combined commentary
            combined_commentary = get_combined_commentary(uuids)
            combined_commentary_html = Markup(markdown.markdown(combined_commentary))
        else:  # If we only have one UUID, it's a single-image upload
            img_uuid = uuids[0]
            image_urls.append(get_image_url(img_uuid))
            processing_result = get_processing_result(img_uuid)
            processing_results.append(Markup(markdown.markdown(processing_result)))
            combined_commentary_html = ""

        return render_template('result.html', 
                                image_urls=image_urls, 
                                processing_results=processing_results, 
                                combined_commentary=combined_commentary_html)
    return jsonify({"error": "Invalid img_uuid"}), 400

@app.route('/upload', methods=['POST'])
def upload_image():
    if request.method == 'POST':
        images = request.files.getlist("image")
        group_images = 'groupImages' in request.form  # boolean flag
        logging.info("Group images: %s", group_images)

        combined_images_text = ""
        images_uuids = []
        for img in images:
            img_buffer = compress_image(img)
            img_uuid = str(uuid.uuid4())
            bucket = boto3.resource('s3').Bucket(BUCKET_NAME)
            bucket.put_object(Body=img_buffer.getvalue(), Key=img_uuid)

            processing_result = process_image(get_image_url(img_uuid))
            store_processing_result(img_uuid, processing_result)
            images_uuids.append(img_uuid)

            if group_images:
                combined_images_text += processing_result + " "

        if group_images:
            # If grouped, pass the combined text of all the images to GPT-4
            combined_commentary = get_commentary(combined_images_text)
            # Store the combined commentary
            store_combined_commentary(img_uuid, combined_commentary)

        return jsonify({'img_uuids': images_uuids})

    return render_template('upload.html')

def compress_image(img):
    im1 = Image.open(img)

    # create an empty string buffer    
    buffer = BytesIO()
    rgb_im = im1.convert('RGB')
    rgb_im.save(buffer, "JPEG", quality=5)
    return buffer

@app.route('/get_image_url', methods=['POST'])
def get_image_url_route():
    if request.method == 'POST':
        img_uuid = request.json.get('img_uuid', None)
        if img_uuid:
            image_url = get_image_url(img_uuid)
            return jsonify({"image_url": image_url})
        return jsonify({"error": "Invalid img_uuid"}), 400
    return jsonify({"error": "Invalid request method"}), 405

@app.route('/get_processing_result', methods=['POST'])
def get_processing_result_route():
    if request.method == 'POST':
        img_uuid = request.json.get('img_uuid', None)
        if img_uuid:
            processing_result = get_processing_result(img_uuid)
            if processing_result:
                return jsonify({"processing_result": processing_result})
            return jsonify({"error": "Processing result not found"}), 404
        return jsonify({"error": "Invalid img_uuid"}), 400
    return jsonify({"error": "Invalid request method"}), 405

def get_image_url(img_uuid):
    image_url = s3.generate_presigned_url(
        'get_object',
        Params={'Bucket': BUCKET_NAME, 'Key': img_uuid},
        ExpiresIn=3600
    )
    return image_url

def store_processing_result(img_uuid, processing_result):
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    logging.info("Storing processing result in DynamoDB...")
    table.put_item(
        Item={
            'img_uuid': img_uuid,
            'processing_result': processing_result
        }
    )

def get_processing_result(img_uuid):
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    response = table.get_item(
        Key={
            'img_uuid': img_uuid
        }
    )
    return response['Item']['processing_result'] if 'Item' in response else None

def store_combined_commentary(img_uuids, commentary):
    logging.info("Storing combined commentary...")
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)

    # Join the image UUIDs with a known delimiter
    key = "|".join(img_uuids)

    table.put_item(
        Item={
            'img_uuid': key,
            'combined_commentary': commentary
        }
    )

def get_combined_commentary(img_uuids):
    logging.info("Getting combined commentary...")
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    key = "|".join(img_uuids)

    response = table.get_item(
        Key={
            'img_uuid': key
        }
    )
    return response['Item']['combined_commentary'] if 'Item' in response else None

if __name__ == '__main__':
    create_dynamodb_table()
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
