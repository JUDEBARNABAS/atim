from flask import Flask, render_template, request, jsonify, make_response
import os
import google.generativeai as genai
from dotenv import load_dotenv
import requests # For making HTTP requests to Colab

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# --- Language Definitions (Needed for UI and logic) ---
# These languages are supported by the Sunbird model on Colab
display_languages = {
    'eng': 'English', 'ach': 'Acholi', 'lgg': 'Lugbara',
    'lug': 'Luganda', 'nyn': 'Runyankole', 'teo': 'Ateso',
}
# Language tokens are used by the Colab server, not directly here anymore for translation.

# --- Google Gemini API Setup ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
gemini_model_pro = None
gemini_configured = False

if not GEMINI_API_KEY:
    print("Warning: GEMINI_API_KEY environment variable not found. Gemini Chatbot will not work.")
else:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model_pro = genai.GenerativeModel(model_name='gemini-1.5-flash-latest')
        gemini_configured = True
        print("Google Gemini API configured successfully!")
    except Exception as e:
        print(f"Error configuring Google Gemini API: {e}")

# --- Helper Function to Call Colab for Translation ---
def call_colab_translator(text, source_lang, target_lang):
    colab_translator_url_base = os.getenv("COLAB_TRANSLATOR_NGROK_URL")
    if not colab_translator_url_base:
        print("ERROR: COLAB_TRANSLATOR_NGROK_URL environment variable is not set.")
        return "Error: Translation service endpoint is not configured on the server."

    # The Colab server's translation endpoint is /translate
    full_colab_url = f"{colab_translator_url_base.rstrip('/')}/translate"

    payload = {
        'text': text,
        'source_language': source_lang,
        'target_language': target_lang,
    }
    print(f"Calling Colab: URL='{full_colab_url}', Payload='{payload}'")
    try:
        response = requests.post(full_colab_url, json=payload, timeout=90) # Increased timeout
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        data = response.json()
        if 'translated_text' in data:
            return data['translated_text']
        elif 'error' in data:
            print(f"Error from Colab server: {data['error']}")
            return f"Error from translation helper: {data['error']}"
        else:
            return "Error: Unexpected response from translation helper."
    except requests.exceptions.Timeout:
        print(f"Error: Timeout when trying to reach Colab server at {full_colab_url}")
        return "Error: Translation service timed out."
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Colab service at {full_colab_url}: {e}")
        return f"Error: Could not connect to translation service. Details: {e}"
    except Exception as e:
        print(f"An unexpected error occurred while calling Colab translation service: {e}")
        return f"Error: An unexpected error occurred during remote translation. Details: {e}"

# --- Gemini Chat Function with Delegated Translation ---
chat_sessions = {}

def ask_gemini_translated(user_message_original, source_lang, target_lang, system_instruction, session_id):
    if not gemini_configured or not gemini_model_pro:
        return "Error: Gemini AI is not configured. Cannot chat."

    user_message_english = user_message_original
    # Translate user message to English if not already English, using Colab
    if source_lang != 'eng':
        print(f"Translating user message from {source_lang} to eng via Colab: '{user_message_original}'")
        translated_to_eng = call_colab_translator(user_message_original, source_lang, 'eng')
        if "Error:" in translated_to_eng:
            return f"Error translating your message to English: {translated_to_eng}"
        user_message_english = translated_to_eng
        print(f"User message in English (from Colab): '{user_message_english}'")

    try:
        session_key = f"{session_id}_{system_instruction}"
        if session_key not in chat_sessions:
            print(f"Creating new Gemini chat session for key: {session_key} with instruction: '{system_instruction}'")
            current_gemini_model_instance = genai.GenerativeModel(
                model_name=gemini_model_pro.model_name, # Use the base model name
                system_instruction=system_instruction if system_instruction else None
            )
            chat_sessions[session_key] = current_gemini_model_instance.start_chat(history=[])
        
        chat = chat_sessions[session_key]
        response = chat.send_message(user_message_english)
        gemini_reply_english = response.text
        print(f"Gemini reply in English: '{gemini_reply_english}'")

        gemini_reply_final = gemini_reply_english
        # Translate Gemini's English reply to target language if not English, using Colab
        if target_lang != 'eng':
            print(f"Translating Gemini reply from eng to {target_lang} via Colab: '{gemini_reply_english}'")
            translated_to_target = call_colab_translator(gemini_reply_english, 'eng', target_lang)
            if "Error:" in translated_to_target:
                 # Return English reply with a warning if translation fails
                return f"{gemini_reply_english} (Note: Error translating this reply to {display_languages.get(target_lang, target_lang)}: {translated_to_target})"
            gemini_reply_final = translated_to_target
            print(f"Gemini reply in {target_lang} (from Colab): '{gemini_reply_final}'")
        
        return gemini_reply_final

    except Exception as e:
        print(f"Error communicating with Gemini or during its translation pipeline: {e}")
        return f"Sorry, an unexpected error occurred with the AI: {getattr(e, 'message', str(e))}"

# --- Flask Routes ---
@app.route('/')
def home():
    session_id = request.cookies.get('session_id')
    if not session_id:
        session_id = os.urandom(16).hex()
    
    # Pass the display_languages dictionary to the template
    resp = make_response(render_template('index.html', languages=display_languages))
    if not request.cookies.get('session_id'):
        resp.set_cookie('session_id', session_id, max_age=60*60*24*30) # 30 days
    return resp

@app.route('/chat_with_ai', methods=['POST'])
def chat_with_ai_endpoint():
    data = request.get_json()
    user_message = data.get('message')
    source_lang = data.get('source_language', 'eng')
    target_lang = data.get('target_language', 'eng')
    system_instruction = data.get('system_instruction', "You are a helpful AI assistant.")
    
    session_id = request.cookies.get('session_id')
    if not session_id:
        return jsonify({'error': 'Session ID missing. Please refresh the page.'}), 400

    if not user_message:
        return jsonify({'error': 'No message received for chat'}), 400
    
    print(f"Chat Request: User='{user_message}', SrcLang='{source_lang}', TrgLang='{target_lang}', Session='{session_id}'")
    
    bot_reply = ask_gemini_translated(user_message, source_lang, target_lang, system_instruction, session_id)
    
    if isinstance(bot_reply, str) and "Error:" in bot_reply:
        # Check if it's a critical error or just a translation note
        if "Error translating this reply" in bot_reply: # Non-critical, reply was still given
             return jsonify({'reply': bot_reply}) # Send the reply with the note
        return jsonify({'error': bot_reply}), 500 # Critical error
    return jsonify({'reply': bot_reply})

@app.route('/translate_simple', methods=['POST'])
def translate_simple_endpoint():
    data = request.get_json()
    text_to_translate = data.get('text')
    source_lang = data.get('source_language')
    target_lang = data.get('target_language')

    if not all([text_to_translate, source_lang, target_lang]):
        return jsonify({'error': 'Missing parameters for translation'}), 400
    
    # Call Colab for translation
    translated_text = call_colab_translator(text_to_translate, source_lang, target_lang)

    if "Error:" in translated_text:
        return jsonify({'error': translated_text}), 500 # Or appropriate error code from Colab
    return jsonify({'translated_text': translated_text})

if __name__ == '__main__':
    print("Starting Flask app for Atim...")
    # COLAB_TRANSLATOR_NGROK_URL and GEMINI_API_KEY must be in your .env file (or environment)
    if not os.getenv("COLAB_TRANSLATOR_NGROK_URL"):
        print("CRITICAL: COLAB_TRANSLATOR_NGROK_URL is not set in the environment!")
        print("The translation features that rely on Colab will fail.")
    if not os.getenv("GEMINI_API_KEY"):
        print("CRITICAL: GEMINI_API_KEY is not set in the environment!")
        print("The Gemini chatbot will fail.")
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv("PORT", 5001))) # Use a different port if 5000 is for Colab