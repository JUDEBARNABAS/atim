from flask import Flask, render_template, request, jsonify, make_response # Added make_response
import os
import torch
import transformers
import google.generativeai as genai
from dotenv import load_dotenv # For loading .env file locally
import random # For random greetings or small talk if needed

# Load environment variables from .env file if it exists (for local development)
load_dotenv()

app = Flask(__name__)

# --- Hugging Face Translation Setup ---
HF_TOKEN = os.getenv("HF_TOKEN")
# Initialize model and tokenizer to None globally
translator_model = None
translator_tokenizer = None
translation_model_loaded = False

# Define the language tokens mapping
language_tokens = {
    'eng': 256047, 'ach': 256111, 'lgg': 256008,
    'lug': 256110, 'nyn': 256002, 'teo': 256006,
}
display_languages = {
    'eng': 'English', 'ach': 'Acholi', 'lgg': 'Lugbara',
    'lug': 'Luganda', 'nyn': 'Runyankole', 'teo': 'Ateso',
}

try:
    print("Loading Hugging Face translation model and tokenizer... This can take a while.")
    if HF_TOKEN: # Only attempt to load if token is present
        translator_model = transformers.M2M100ForConditionalGeneration.from_pretrained(
            "Sunbird/translate-nllb-1.3b-salt-4bit",
            device_map="auto", # Automatically uses GPU if available, otherwise CPU
            token=HF_TOKEN 
        )
        translator_tokenizer = transformers.NllbTokenizer.from_pretrained(
            "Sunbird/translate-nllb-1.3b-salt",
            token=HF_TOKEN
        )
        translation_model_loaded = True
        print("Hugging Face translation model and tokenizer loaded successfully!")
    else:
        print("Warning: HF_TOKEN not found. Translation model will not be loaded.")
        
except Exception as e:
    print(f"Error loading Hugging Face translation model or tokenizer: {e}")
    print("Translation functionality will be limited or unavailable.")

# --- Google Gemini API Setup ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
gemini_model_pro = None 
gemini_configured = False

if not GEMINI_API_KEY:
    print("Warning: GEMINI_API_KEY environment variable not found. Gemini Chatbot will not work.")
else:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # Using gemini-1.5-flash as it's faster and good for chat.
        gemini_model_pro = genai.GenerativeModel(
            model_name='gemini-1.5-flash-latest'
        )
        gemini_configured = True
        print("Google Gemini API configured successfully!")
    except Exception as e:
        print(f"Error configuring Google Gemini API: {e}")
        print("Gemini Chatbot functionality will be limited or unavailable.")


# --- Translation Function ---
def translate_text_internal(text, source_language_code, target_language_code):
    if not translation_model_loaded or not translator_model or not translator_tokenizer:
        return "Error: Translation model not loaded. Cannot translate."
    if source_language_code not in language_tokens or target_language_code not in language_tokens:
        return f"Error: Unsupported language(s). Supported: {', '.join(language_tokens.keys())}"
    if not text or not text.strip():
        return "" 

    device = translator_model.device 
    try:
        translator_tokenizer.src_lang = source_language_code
        inputs = translator_tokenizer(text, return_tensors="pt").to(device)

        generated_tokens = translator_model.generate(
            **inputs,
            forced_bos_token_id=language_tokens[target_language_code],
            max_length=256, 
            num_beams=5,
            early_stopping=True
        )
        result = translator_tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)[0]
        return result
    except Exception as e:
        print(f"Error during translation '{text}' from {source_language_code} to {target_language_code}: {e}")
        return f"Error during translation process: {e}"

# --- Gemini Chat Function with Translation and System Instruction ---
chat_sessions = {} # Store chat history {session_id: chat_object}

def ask_gemini_translated(user_message_original, source_lang, target_lang, system_instruction, session_id):
    if not gemini_configured or not gemini_model_pro:
        return "Error: Gemini AI is not configured. Cannot chat."

    user_message_english = user_message_original
    if source_lang != 'eng' and translation_model_loaded: # Only translate if not English and model is loaded
        print(f"Translating user message from {source_lang} to eng: '{user_message_original}'")
        user_message_english = translate_text_internal(user_message_original, source_lang, 'eng')
        if "Error:" in user_message_english:
            return f"Error translating your message to English: {user_message_english}"
        print(f"User message in English: '{user_message_english}'")
    elif source_lang != 'eng' and not translation_model_loaded:
        print("Warning: User message not in English, but translation model not loaded. Sending original to Gemini.")


    try:
        current_model_name = gemini_model_pro.model_name # Get base model name
        
        # Check if session exists and if system instruction has changed
        # If system instruction changes, we must create a new model instance and chat history
        session_key = f"{session_id}_{system_instruction}" # Unique key per session & system instruction

        if session_key not in chat_sessions:
            print(f"Creating new chat model for session_key: {session_key} with instruction: '{system_instruction}'")
            current_gemini_model_instance = genai.GenerativeModel(
                model_name=current_model_name,
                system_instruction=system_instruction if system_instruction else None # Pass None if empty
            )
            chat_sessions[session_key] = current_gemini_model_instance.start_chat(history=[])
        
        chat = chat_sessions[session_key]
        
        response = chat.send_message(user_message_english)
        gemini_reply_english = response.text
        print(f"Gemini reply in English: '{gemini_reply_english}'")

        gemini_reply_translated = gemini_reply_english
        if target_lang != 'eng' and translation_model_loaded: # Only translate if not English and model is loaded
            print(f"Translating Gemini reply from eng to {target_lang}: '{gemini_reply_english}'")
            gemini_reply_translated = translate_text_internal(gemini_reply_english, 'eng', target_lang)
            if "Error:" in gemini_reply_translated:
                return f"Error translating Gemini's reply: {gemini_reply_translated} (Original Eng: {gemini_reply_english})"
            print(f"Gemini reply in {target_lang}: '{gemini_reply_translated}'")
        elif target_lang != 'eng' and not translation_model_loaded:
             print("Warning: Target language not English, but translation model not loaded. Returning English reply.")

        return gemini_reply_translated

    except Exception as e:
        print(f"Error communicating with Gemini or during translation pipeline: {e}")
        if hasattr(e, 'message'):
            return f"Sorry, error with Gemini: {e.message}"
        return f"Sorry, an unexpected error occurred with the AI: {e}"

# --- Flask Routes ---
@app.route('/')
def home():
    session_id = request.cookies.get('session_id')
    if not session_id:
        session_id = os.urandom(16).hex()
    
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
    
    print(f"Chat Request: User='{user_message}', SrcLang='{source_lang}', TrgLang='{target_lang}', SysInstr='{system_instruction}', Session='{session_id}'")
    
    bot_reply = ask_gemini_translated(user_message, source_lang, target_lang, system_instruction, session_id)
    
    if isinstance(bot_reply, str) and "Error:" in bot_reply:
        return jsonify({'error': bot_reply}), 500 
    return jsonify({'reply': bot_reply})

@app.route('/translate_simple', methods=['POST'])
def translate_simple_endpoint():
    data = request.get_json()
    text = data.get('text')
    source_lang = data.get('source_language')
    target_lang = data.get('target_language')

    if not all([text, source_lang, target_lang]):
        return jsonify({'error': 'Missing parameters for translation'}), 400
    
    if not translation_model_loaded:
        return jsonify({'error': 'Simple translation service is unavailable because the model is not loaded.'}), 503

    translated_text = translate_text_internal(text, source_lang, target_lang)
    if "Error:" in translated_text:
        return jsonify({'error': translated_text}), 500
    return jsonify({'translated_text': translated_text})

if __name__ == '__main__':
    print("Starting Flask app...")
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv("PORT", 5000)))