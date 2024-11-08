from flask import Flask, redirect, url_for, request, jsonify, stream_with_context
from flask_dance.contrib.google import make_google_blueprint, google

from flask_login import UserMixin, LoginManager, logout_user, login_user, login_required, current_user
from APIs.user_auth import auth, max_topic_messages_WO_sub, max_topic_topics_WO_sub #, blueprint
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
import os
from flask import render_template, make_response, stream_with_context, Response
from dotenv import load_dotenv
import time
from init_agent.Conv_Creator_basics import ConvCreator_stream
from config import *
from flask_cors import CORS
from datetime import timedelta
from code_excecution.code_execute import code_execution
from payment.stripe_subscription import payments_blueprint
from APIs.new_conv_public_apis import public_blueprint 
from APIs.User_Tutor_History import tutor_history_blueprint
from APIs.chat_history import chat_history_blueprint
from APIs.page_wise_chat_history import page_wise_chat_history_blueprint
from text_to_speech.TTS import TTS_blueprint
import random
import sys
from tinydb import Query
from tutor_agent.Conv_handler_improved_mem import TeachingAssistant_stream
import logging

# Configure logging globally
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Create a logger for this file
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

max_topic_messages_WO_sub = 5000
max_topic_topics_WO_sub = 200

app = Flask(__name__)

# Log startup information
logger.info("Starting Flask application...")

# Enable CORS for all routes, accepting any localhost origin
CORS(app, resources={
    r"/*": {  # Changed from r"/api/*" to r"/*"
        "origins": [
            "http://localhost:*",
            "http://127.0.0.1:*"
        ],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})




## register APIs
app.register_blueprint(auth, url_prefix='/login')
app.register_blueprint(payments_blueprint, url_prefix='/payments')
app.register_blueprint(TTS_blueprint)
app.register_blueprint(public_blueprint)
app.register_blueprint(tutor_history_blueprint)
app.register_blueprint(chat_history_blueprint)
app.register_blueprint(page_wise_chat_history_blueprint)





@app.route('/api/v1/get_response_stream', methods=['POST'])
def get_response():
    current_user_email = request.args.get('email')  
    User_Query = Query()
    user = user_table.get(User_Query.email == current_user_email)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    subscribed = user.get('subscribed', {}).get('state', False)
    data = request.get_json()
    user_input = data['user_input']
    topic_id = data['id']
    
    Topic_Query = Query()
    topic = topics_table.get(
        (Topic_Query.userId == current_user_email) & 
        (Topic_Query.topics_id == topic_id)
    )
    if not topic:
        return jsonify({"error": "Topic not found"}), 404
        
    if not subscribed:   
        if len(topic.get('messages', [])) >= max_topic_messages_WO_sub:
            response = {
                "error": "You need a subscription to continue this conversation.",
                "subscriptionError": not subscribed
            }
            return make_response(jsonify(response), 403)

    if topic.get('category') == '3': 
        temperature = 0.8
    else:
        temperature = 0.4

    ta = TeachingAssistant_stream(api_keys=API_KEYS, conversation_model=conversation_model, extraction_model=extraction_model, temperature=temperature, max_tokens=5000)
    return Response(ta.handle_message(user_input, user['email'], topic_id), mimetype='text/event-stream')


@app.route('/api/v1/wizard_details', methods=['GET'])
def wizard_details():
    try:
        # Generate a random seed for variety
        seed = str(random.randint(1, 10000))
        image_url = f'https://api.dicebear.com/7.x/avataaars/svg?seed={seed}'
        
        return jsonify({
            'image': image_url,
            'name': 'Tutor Creator'
        }), 200
            
    except Exception as e:
        logger.error("Error generating avatar: %s", str(e))
        return jsonify({'error': 'Service unavailable'}), 500

@app.route('/api/v1/buddy_details', methods=['GET'])
def buddy_details():
    try:
        # Generate a random seed for variety
        seed = str(random.randint(1, 10000))
        
        # Using a different style for buddy to differentiate from wizard
        image_url = f'https://api.dicebear.com/7.x/bottts/svg?seed={seed}'  # Using bottts style for robot-like tutor
        # Or keep avataaars with different options:
        # image_url = f'https://api.dicebear.com/7.x/avataaars/svg?seed={seed}&backgroundColor=lightblue&mood=happy'
        
        return jsonify({
            'image': image_url,
            'name': 'Tutor'
        }), 200
            
    except Exception as e:
        logger.error("Error generating avatar: %s", str(e))
        return jsonify({'error': 'Service unavailable'}), 500
    

    


@app.route('/api/v1/Conv_first_massage', methods=['POST'])
def Conv_first_massage():
    current_user_email = request.args.get('email')  
    User_Query = Query()
    user = user_table.get(User_Query.email == current_user_email)
    if not user:
        return jsonify({"error": "User not found"}), 404
    subscribed = user.get('subscribed', {}).get('state', False)
    if not subscribed:
        if len(user['created_topics']) >= max_topic_topics_WO_sub:
            response = {
                "error": "You need a subscription to create new topics.",
                "subscriptionError": not subscribed
            }
            return make_response(jsonify(response), 403)
    CC = ConvCreator_stream(api_keys=API_KEYS, conversation_model = conversation_model, extraction_model = extraction_model, temperature=0)
    return Response(CC.handle_first_message(user), mimetype='text/event-stream')



@app.route('/api/v1/Conv_next_massage', methods=['POST'])
def Conv_next_massage():
    current_user_email = request.args.get('email')  
    User_Query = Query()
    user = user_table.get(User_Query.email == current_user_email)
    if not user:
        return jsonify({"error": "User not found"}), 404
    subscribed = user.get('subscribed', {}).get('state', False)
    if not subscribed:
        if len(user['created_topics']) >= max_topic_topics_WO_sub:
            response = {
                "error": "You need a subscription to create new topics.",
                "subscriptionError": not subscribed  # This will always be True in this block, but using `not subscribed` makes it clear.
            }
            return make_response(jsonify(response), 403)
    data = request.get_json()
    user_input = data['user_input']
    CC = ConvCreator_stream(api_keys=API_KEYS, conversation_model = conversation_model, extraction_model = extraction_model, temperature=0)
    return Response(CC.handle_message(user_input, user), mimetype='text/event-stream')

@app.route('/api/v1/Get_created_topic', methods=['POST'])
def get_created_topic():
    current_user_email = request.args.get('email')  
    User_Query = Query()
    user = user_table.get(User_Query.email == current_user_email)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    if not user['created_topics']:
        return jsonify({"error": "No topics found for the user"}), 404
    topic_id = user['created_topics'][-1]
    Topic_Query = Query()
    # Convert DynamoDB get_item to TinyDB query
    last_topic = topics_table.get(
        (Topic_Query.userId == user['email']) & 
        (Topic_Query.topics_id == topic_id)
    )
    if not last_topic:
        return jsonify({"error": "Topic not found"}), 404
        
    category = last_topic.get('category', "1")
    Asset_Query = Query()
    # Convert DynamoDB get_item to TinyDB query
    icons = asset_table.get(Asset_Query.asset_name == 'icon')
    return jsonify({"Topic": last_topic['topic'], "Goal": last_topic['goal'], "id": topic_id, "lang_id": last_topic['langid'], "lang_name": last_topic["lang_name"], "monaco_name": last_topic["monaco_name"], 'icon' : icons.get(category, icons['1']) if icons else None })




@app.route('/api/v1/user_details', methods=['GET'])
def get_user_profile_v2():
    try:
        
        current_user_email = request.args.get('email')


        
        User_Query = Query()
        user = user_table.get(User_Query.email == current_user_email)
        if not user:
            return jsonify({"error": "User not found"}), 404


        # Check topic creation permission
        subscribed = user.get('subscribed', {}).get('state', False)
        user_create_topic_permission = True
        if not subscribed:
            if len(user.get('created_topics', [])) >= max_topic_topics_WO_sub:
                user_create_topic_permission = False

        if 'screen_mode' not in user:
            user['screen_mode'] = 1

            User_Query = Query()
            user_table.update(
                {'screen_mode': 1},
                User_Query.email == current_user_email
            )

    

        # Prepare final response
        result = {
            'given_name': user.get('given_name'),
            'family_name': user.get('family_name'),
            'photo': user.get('photo'),
            'user_create_topic_permission': user_create_topic_permission,
            'isSubscribed': subscribed,
            'screen_mode': user.get('screen_mode')
        }

        return jsonify(result), 200

    except Exception as e:
        print(e)
        return jsonify({"error": "An unexpected error occurred."}), 500


@app.route('/api/v1/change_mode', methods=['POST'])
def change_user_mode():
    try:
        current_user_email = get_jwt_identity()
        data = request.get_json()

        User_Query = Query()
        user_table.update(
            {'screen_mode': data.get('screen_mode', 1)},
            User_Query.email == current_user_email
        )

        return jsonify({"message": "Mode updated successfully"}), 200

    except Exception as e:
        print(e)
        return jsonify({"error": "An unexpected error occurred."}), 500


    
@app.route('/api/v1/code_excecution', methods=['POST'])
def code_excecution():
    current_user_email = get_jwt_identity()
    User_Query = Query()
    user = user_table.get(User_Query.email == current_user_email)
    if not user:
        return jsonify({"error": "User not found"}), 404

    subscribed = user.get('subscribed', {}).get('state', False)
    '''if not subscribed:
        response = {
            "error": "You need a subscription to execute code.",
            "isSubscribed": subscribed
        }
        return make_response(jsonify(response), 403)'''
    data = request.get_json()
    topic_id = data.get('id')  
    code = data.get('code')
    stdin = data.get('stdin',"")
    
    if not code:
        return jsonify({"error": "code not provided"}), 400
    langid = data.get('lang_id')
    if not langid:
        return jsonify({"error": "lang_id not provided"}), 400
    try:
        langid = int(langid)
    except ValueError:
        return jsonify({"error": "lang_id should be an integer or a string representation of an integer"}), 400

    Topic_Query = Query()
    topics_table.update(
        {'code_editor_used': 1},
        (Topic_Query.userId == current_user_email) & 
        (Topic_Query.topics_id == topic_id)
    )
    
    result, status_code = code_execution(langid, code, stdin)
    return jsonify(result), status_code


@app.route('/api/v1/text_editor', methods=['POST'])
def text_editor():
    current_user_email = get_jwt_identity()
    User_Query = Query()
    user = user_table.get(User_Query.email == current_user_email)
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    data = request.get_json()
    topic_id = data.get('id')
    try:
        Topic_Query = Query()
        topics_table.update(
            {'text_editor_used': 1},
            (Topic_Query.userId == current_user_email) & 
            (Topic_Query.topics_id == topic_id)
        )
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/')
def home():
    return "Home Page"

@app.route('/health')
def health_check():
    return "OK", 200


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, debug=True)
