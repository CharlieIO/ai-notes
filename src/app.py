from io import BytesIO
import os
import uuid
from flask import Flask, render_template, request, jsonify, redirect, url_for, Markup
from PIL import Image
import boto3
import markdown
from processing import process_image


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
    existing_tables = dynamodbClient.list_tables()['TableNames']

    print(existing_tables)

    if DYNAMODB_TABLE_NAME not in existing_tables:
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

@app.route('/')
def index():
    img_uuid = request.args.get('img_uuid', None)
    return render_template('upload.html', img_uuid=img_uuid)

@app.route('/view_result', methods=['GET'])
def view_result():
    img_uuid = request.args.get('img_uuid', None)
    if img_uuid:
        image_url = get_image_url(img_uuid)
        processing_result = get_processing_result(img_uuid)

        # Convert processing_result to HTML using Markdown
        processing_result_html = Markup(markdown.markdown(processing_result))

        return render_template('result.html', image_url=image_url, processing_result=processing_result_html)
    return jsonify({"error": "Invalid img_uuid"}), 400

@app.route('/upload', methods=['GET', 'POST'])
def upload_image():
    if request.method == 'POST':
        img = request.files['image']
        img_buffer = compress_image(img)
        img_uuid = str(uuid.uuid4())

        bucket = boto3.resource('s3').Bucket(BUCKET_NAME)
        bucket.put_object(Body=img_buffer.getvalue(), Key=img_uuid)

        processing_result = process_image(get_image_url(img_uuid))
        store_processing_result(img_uuid, processing_result)

        return redirect(url_for('view_result', img_uuid=img_uuid))
    return render_template('upload.html')

def compress_image(img):
    im1 = Image.open(img)

    # create an empty string buffer    
    buffer = BytesIO()
    im1.save(buffer, "JPEG", quality=5)
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

if __name__ == '__main__':
    create_dynamodb_table()
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
