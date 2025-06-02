document.addEventListener('DOMContentLoaded', () => {
    // --- Toggle Settings Button ---
    const toggleSettingsButton = document.getElementById('toggle-settings-button');
    const collapsibleContent = document.getElementById('collapsible-content');

    if (toggleSettingsButton && collapsibleContent) {
        toggleSettingsButton.addEventListener('click', () => {
            collapsibleContent.classList.toggle('expanded');
            collapsibleContent.classList.toggle('collapsed');
            const icon = toggleSettingsButton.querySelector('i');
            if (collapsibleContent.classList.contains('expanded')) {
                icon.classList.remove('fa-cog');
                icon.classList.add('fa-times');
                toggleSettingsButton.setAttribute('aria-expanded', 'true');
            } else {
                icon.classList.remove('fa-times');
                icon.classList.add('fa-cog');
                toggleSettingsButton.setAttribute('aria-expanded', 'false');
            }
        });
    }

    // --- AI Chatbot Elements ---
    const aiChatMessages = document.getElementById('ai-chat-messages');
    const aiUserInput = document.getElementById('ai-user-input');
    const aiSendButton = document.getElementById('ai-send-button');
    const aiLoading = document.getElementById('ai-loading');
    const chatSourceLanguageSelect = document.getElementById('chat-source-language');
    const chatTargetLanguageSelect = document.getElementById('chat-target-language');
    const geminiSystemInstructionTextarea = document.getElementById('gemini-system-instruction');

    // --- Footer Current Year ---
    const currentYearSpan = document.getElementById('current-year');
    if (currentYearSpan) {
        currentYearSpan.textContent = new Date().getFullYear();
    }

    function addAiChatMessage(message, senderType, avatarUrlToUse) {
        if (!aiChatMessages) return;
        const messageContainer = document.createElement('div');
        messageContainer.classList.add('message-container', senderType);
        const avatarImg = document.createElement('img');
        avatarImg.classList.add('avatar');
        avatarImg.src = avatarUrlToUse;
        avatarImg.alt = senderType + ' avatar';
        avatarImg.onerror = () => { avatarImg.style.display = 'none'; };
        const messageBubble = document.createElement('div');
        messageBubble.classList.add('message');
        const paragraph = document.createElement('p');
        paragraph.textContent = message;
        messageBubble.appendChild(paragraph);
        if (senderType === 'user') {
            messageContainer.appendChild(messageBubble);
            messageContainer.appendChild(avatarImg);
        } else {
            messageContainer.appendChild(avatarImg);
            messageContainer.appendChild(messageBubble);
        }
        aiChatMessages.appendChild(messageContainer);
        aiChatMessages.scrollTop = aiChatMessages.scrollHeight;
    }

    if (aiChatMessages && typeof botAvatarUrl !== 'undefined') {
        const defaultSystemInstruction = "Atim is a friendly and empowering assistant from Gender Tech Initiative. She focuses on topics related to gender equality, tech, and community support. Respond in the target language selected by the user.";
        if (geminiSystemInstructionTextarea && !geminiSystemInstructionTextarea.value) {
            geminiSystemInstructionTextarea.value = defaultSystemInstruction;
        }
        addAiChatMessage("Hello! I'm Atim, your AI assistant from Gender Tech Initiative. How can I help you today?", 'bot', botAvatarUrl);
    }

    async function sendAiChatMessage() {
        if (!aiUserInput || !aiSendButton || !aiLoading || !chatSourceLanguageSelect || !chatTargetLanguageSelect || !geminiSystemInstructionTextarea) return;
        const messageText = aiUserInput.value.trim();
        if (messageText === '') return;

        const sourceLang = chatSourceLanguageSelect.value;
        const targetLang = chatTargetLanguageSelect.value;
        let systemInstruction = geminiSystemInstructionTextarea.value.trim();
        if (!systemInstruction) {
            systemInstruction = "Atim is a friendly and empowering assistant from Gender Tech Initiative. She focuses on topics related to gender equality, tech, and community support. Respond in the target language specified.";
        }

        addAiChatMessage(messageText, 'user', typeof userAvatarUrl !== 'undefined' ? userAvatarUrl : 'static/images/user_avatar.png'); // Provide default if undefined
        aiUserInput.value = '';
        aiUserInput.focus();
        aiLoading.style.display = 'block';
        aiSendButton.disabled = true;

        try {
            const response = await fetch('/chat_with_ai', { // Calls THIS server's backend
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: messageText,
                    source_language: sourceLang,
                    target_language: targetLang,
                    system_instruction: systemInstruction
                }),
            });
            const data = await response.json();
            if (response.ok) {
                addAiChatMessage(data.reply, 'bot', typeof botAvatarUrl !== 'undefined' ? botAvatarUrl : 'static/images/bot_avatar.png'); // Provide default
            } else {
                addAiChatMessage('Error: ' + (data.error || 'Failed to get response from Atim.'), 'bot', typeof botAvatarUrl !== 'undefined' ? botAvatarUrl : 'static/images/bot_avatar.png');
            }
        } catch (error) {
            console.error('AI chat fetch error:', error);
            addAiChatMessage('Error: Could not connect to Atim.', 'bot', typeof botAvatarUrl !== 'undefined' ? botAvatarUrl : 'static/images/bot_avatar.png');
        } finally {
            aiLoading.style.display = 'none';
            aiSendButton.disabled = false;
        }
    }

    if (aiSendButton) {
        aiSendButton.addEventListener('click', sendAiChatMessage);
    }
    if (aiUserInput) {
        aiUserInput.addEventListener('keypress', (event) => {
            if (event.key === 'Enter') {
                sendAiChatMessage();
            }
        });
    }

    // --- Simple Translator Functionality ---
    const translateButtonSimple = document.getElementById('translate-button-simple');
    const textToTranslateInputSimple = document.getElementById('text-to-translate-simple');
    const sourceLanguageSelectSimple = document.getElementById('source-language-simple');
    const targetLanguageSelectSimple = document.getElementById('target-language-simple');
    const translatedTextOutputSimple = document.getElementById('translated-text-output-simple');
    const translationLoadingSimple = document.getElementById('translation-loading-simple');

    if (translateButtonSimple) {
        translateButtonSimple.addEventListener('click', async () => {
            if (!textToTranslateInputSimple || !sourceLanguageSelectSimple || !targetLanguageSelectSimple || !translatedTextOutputSimple || !translationLoadingSimple) return;
            const text = textToTranslateInputSimple.value.trim();
            const sourceLanguage = sourceLanguageSelectSimple.value;
            const targetLanguage = targetLanguageSelectSimple.value;

            if (!text) { alert('Please enter text to translate.'); return; }
            if (!sourceLanguage) { alert('Please select source language.'); return; }
            if (!targetLanguage) { alert('Please select target language.'); return; }
            if (sourceLanguage === targetLanguage && sourceLanguage !== "") { alert('Source and target languages must be different.'); return; }

            translatedTextOutputSimple.textContent = '';
            translationLoadingSimple.style.display = 'block';
            translateButtonSimple.disabled = true;

            try {
                const response = await fetch('/translate_simple', { // Calls THIS server's backend
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        text: text,
                        source_language: sourceLanguage,
                        target_language: targetLanguage,
                    }),
                });
                const data = await response.json();
                if (response.ok) {
                    translatedTextOutputSimple.textContent = data.translated_text;
                } else {
                    translatedTextOutputSimple.textContent = 'Error: ' + (data.error || 'Translation failed.');
                }
            } catch (error) {
                console.error('Simple translation fetch error:', error);
                translatedTextOutputSimple.textContent = 'Error: Could not connect to translation service.';
            } finally {
                translationLoadingSimple.style.display = 'none';
                translateButtonSimple.disabled = false;
            }
        });
    }
});