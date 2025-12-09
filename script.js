// Global state
let sessionId = null;
let selectedRole = null;
let selectedExperience = null;
let candidateName = '';
let currentQuestion = null;
let currentQuestionNumber = 0;
let selectedDuration = null; // in minutes
let interviewTimer = null;
let remainingSeconds = 0;
let conversationHistory = [];
let askedQuestions = []; // Track asked questions to avoid repetition

// Recording / flow state
let isRecording = false;
let currentRecordingPromise = null;
let canStartRecording = false; // After question is spoken
let canGoNext = false;         // After answer + reply

// Show specific screen
function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(screen => {
        screen.classList.remove('active');
    });
    document.getElementById(screenId).classList.add('active');
}

// Welcome -> Role Selection
function showRoleSelection() {
    const nameInput = document.getElementById('candidate-name');
    candidateName = nameInput.value.trim();

    if (!candidateName) {
        alert('Please enter your name to continue');
        nameInput.focus();
        return;
    }

    showScreen('role-screen');
}

// Role Selection
function selectRole(role) {
    selectedRole = role;
    showScreen('experience-screen');
}

// Experience Selection
function selectExperience(exp) {
    selectedExperience = exp;
    showScreen('voice-screen');
}

// Duration Selection
function selectDuration(minutes, event) {
    selectedDuration = minutes;

    document.querySelectorAll('.duration-btn').forEach(btn => {
        btn.classList.remove('selected');
    });
    event.target.closest('.duration-btn').classList.add('selected');
}

// Start Interview
async function startInterview() {
    try {
        if (!selectedDuration) {
            alert('Please select an interview duration');
            return;
        }

        const response = await fetch('/api/start-interview', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                role: selectedRole,
                experience: selectedExperience,
                duration_minutes: selectedDuration,
                candidate_name: candidateName
            })
        });

        if (!response.ok) {
            throw new Error(`Server returned ${response.status}`);
        }

        const data = await response.json();

        if (data.success) {
            sessionId = data.session_id;
            remainingSeconds = selectedDuration * 60;

            showScreen('interview-screen');
            updateTimerDisplay();
            startTimer();

            await showIntroduction(data.intro_text);
            await getNextQuestion();
        } else {
            alert('Error: ' + (data.message || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error starting interview:', error);
        alert('Error starting interview: ' + error.message + '\n\nMake sure the Flask server is running:\npython app.py');
    }
}

// Start countdown timer
function startTimer() {
    interviewTimer = setInterval(() => {
        remainingSeconds--;
        updateTimerDisplay();

        if (remainingSeconds <= 0) {
            clearInterval(interviewTimer);
            interviewTimer = null;
            endInterviewDueToTime();
        }
    }, 1000);
}

// Update timer display
function updateTimerDisplay() {
    const minutes = Math.floor(remainingSeconds / 60);
    const seconds = remainingSeconds % 60;
    const display = `⏱️ ${minutes}:${seconds.toString().padStart(2, '0')}`;

    const timerElement = document.getElementById('timer-display');
    timerElement.textContent = display;

    timerElement.classList.remove('warning', 'danger');
    if (remainingSeconds <= 60) {
        timerElement.classList.add('danger');
    } else if (remainingSeconds <= 180) {
        timerElement.classList.add('warning');
    }
}

// End interview when time runs out
async function endInterviewDueToTime() {
    await stopSpeech();
    await completeInterview();
}

// Stop Speech
async function stopSpeech() {
    if (sessionId) {
        try {
            await fetch('/api/stop-speech', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({session_id: sessionId})
            });
            console.log('Speech stopped');
        } catch (error) {
            console.error('Error stopping speech:', error);
        }
    }
}

// Quit Interview
async function quitInterview() {
    if (confirm('Are you sure you want to end the interview now? You will receive a report based on your answers so far.')) {
        // Force stop everything immediately
        isRecording = false;
        canStartRecording = false;
        canGoNext = false;

        // Cancel any ongoing recording (note: fetch can't be truly aborted once started, but we ignore the result)
        currentRecordingPromise = null;

        // Clear timer
        if (interviewTimer) {
            clearInterval(interviewTimer);
            interviewTimer = null;
        }

        // Stop any ongoing speech immediately
        try {
            await stopSpeech();
        } catch (e) {
            console.log('Error stopping speech during quit:', e);
        }

        // Hide recording indicators
        const recordingIndicator = document.getElementById('recording-indicator');
        const btnSend = document.getElementById('btn-send');
        const inputHint = document.getElementById('input-hint');

        if (recordingIndicator) recordingIndicator.style.display = 'none';
        if (btnSend) btnSend.style.display = 'none';
        if (inputHint) inputHint.textContent = 'Ending interview...';

        // Update status
        updateStatus('Ending interview...');

        // Go directly to report (don't wait for anything)
        try {
            await completeInterview();
        } catch (e) {
            console.error('Error completing interview:', e);
            // Even if there's an error, try to show report screen
            showScreen('report-screen');
        }
    }
}

// Add message to chat
function addMessage(text, type, options = {}) {
    const chatMessages = document.getElementById('chat-messages');

    if (type === 'interviewer') {
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble interviewer';
        bubble.innerHTML = `
            <div class="message-content">
                <div class="message-label">🎤 Interviewer</div>
                <div class="message-text-bubble" data-message-id="${Date.now()}"></div>
                ${options.showTyping ? '<div class="typing-indicator"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></div>' : ''}
            </div>
        `;
        chatMessages.appendChild(bubble);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return bubble.querySelector('.message-text-bubble');
    } else if (type === 'candidate') {
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble candidate';
        bubble.innerHTML = `
            <div class="message-content">
                <div class="message-label">📝 You</div>
                <div class="message-text-bubble" data-message-id="${Date.now()}"></div>
            </div>
        `;
        chatMessages.appendChild(bubble);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return bubble.querySelector('.message-text-bubble');
    } else if (type === 'evaluation') {
        const card = document.createElement('div');
        card.className = 'evaluation-card';
        card.innerHTML = `
            <div class="eval-header">
                <span class="eval-icon">📊</span>
                <span class="eval-title">INSTANT ANALYSIS</span>
                <span class="eval-score" id="eval-score-${Date.now()}">0/10</span>
            </div>
            <div class="eval-section">
                <div class="eval-section-title">✅ Strengths</div>
                <ul class="eval-list" id="eval-strengths-${Date.now()}"></ul>
            </div>
            <div class="eval-section">
                <div class="eval-section-title">⚠️ Areas to Improve</div>
                <ul class="eval-list" id="eval-weaknesses-${Date.now()}"></ul>
            </div>
            <div class="eval-section">
                <div class="eval-section-title">💡 Quick Tip</div>
                <div class="eval-tip" id="eval-suggestion-${Date.now()}"></div>
            </div>
            <button class="btn-next" onclick="nextQuestion()">Continue to Next Question →</button>
        `;
        chatMessages.appendChild(card);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return card;
    }
}

// Show Introduction (single continuous text)
async function showIntroduction(introText) {
    updateStatus('Speaking...');

    const messageElement = addMessage('', 'interviewer', {showTyping: true});
    await speakAndType(introText, messageElement);

    updateStatus('Ready');
    await sleep(2000);
}

// Speak and show text immediately (no typing animation)
async function speakAndType(text, element) {
    const typingIndicator = element.parentElement.querySelector('.typing-indicator');
    if (typingIndicator) typingIndicator.remove();

    element.textContent = text;

    const chatMessages = document.getElementById('chat-messages');
    chatMessages.scrollTop = chatMessages.scrollHeight;

    await fetch('/api/speak', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            session_id: sessionId,
            text: text
        })
    });
}

// Update interviewer status
function updateStatus(status) {
    const statusElement = document.getElementById('interviewer-status');
    if (status === 'Speaking...') {
        statusElement.innerHTML = '<span class="status-dot"></span> Speaking...';
    } else if (status === 'Listening...') {
        statusElement.innerHTML = '<span class="status-dot" style="background:#ef4444;"></span> Listening...';
    } else {
        statusElement.innerHTML = '<span class="status-dot"></span> Ready';
    }
}

// Get Next Question
// Get Next Question
async function getNextQuestion() {
    // If interview is already on the report screen, do nothing
    const reportScreen = document.getElementById('report-screen');
    if (reportScreen && reportScreen.classList.contains('active')) {
        return;
    }

    try {
        if (remainingSeconds <= 0) {
            await endInterviewDueToTime();
            return;
        }

        updateStatus('Thinking...');

        const response = await fetch('/api/get-question', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                session_id: sessionId,
                asked_questions: askedQuestions
            })
        });

        if (!response.ok) {
            // No popup – just log and stop
            console.warn('get-question returned status', response.status);
            updateStatus('Ready');
            return;
        }

        const data = await response.json();

        if (data.success) {
            currentQuestion = data.question;
            currentQuestionNumber = data.question_number;

            // Track this question to avoid repetition
            askedQuestions.push(currentQuestion);

            // Update counter (no total, just current number)
            document.getElementById('question-counter').textContent =
                `Question ${currentQuestionNumber}`;

            // Add question message
            updateStatus('Speaking...');
            const messageElement = addMessage('', 'interviewer', {showTyping: true});
            await speakAndType(currentQuestion, messageElement);

            // After question is spoken, wait for user to start answering
            updateStatus('Ready');
            document.getElementById('input-hint').textContent =
                'Press Enter when you are ready to answer.';

            canStartRecording = true;
        } else {
            // Backend said error – no alert, just log
            console.warn('Backend error getting question:', data.message);
            updateStatus('Ready');
        }
    } catch (error) {
        console.error('Error getting question (ignored):', error);
        updateStatus('Ready');
    }
}


// Record Answer
async function recordAnswer() {
    try {
        // Only start if we're allowed and not already recording
        if (!canStartRecording || isRecording) return;

        isRecording = true;
        canStartRecording = false;

        updateStatus('Listening...');
        document.getElementById('recording-indicator').style.display = 'flex';
        document.getElementById('input-hint').textContent = 'Speak now, I am recording your answer. I will stop when you pause.';
        document.getElementById('btn-send').style.display = 'none';

        // Start recording in background
        currentRecordingPromise = fetch('/api/record-answer', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({session_id: sessionId})
        });

        // Wait for recording to complete
        const response = await currentRecordingPromise;

        isRecording = false;
        document.getElementById('recording-indicator').style.display = 'none';
        document.getElementById('btn-send').style.display = 'none';
        document.getElementById('input-hint').textContent = 'Processing...';

        if (!response.ok) {
            throw new Error(`Server returned ${response.status}`);
        }

        const data = await response.json();

        if (data.success) {
            const answer = data.answer;

            // Show candidate's answer bubble
            const answerElement = addMessage('', 'candidate');
            answerElement.textContent = answer;

            const chatMessages = document.getElementById('chat-messages');
            chatMessages.scrollTop = chatMessages.scrollHeight;

            // Generate feedback: show + SPEAK
            await generateConversationalResponse(answer);

            // Save answer
            await saveAnswer(currentQuestion, answer);

            // Time check
            if (remainingSeconds <= 0) {
                await endInterviewDueToTime();
            } else {
                // Auto go to next question (no Enter for this)
                document.getElementById('input-hint').textContent = 'Preparing next question...';
                await nextQuestion();
            }
        } else {
            updateStatus('Ready');
            document.getElementById('input-hint').textContent = 'Press Enter to try answering again.';
            alert('Could not understand: ' + (data.message || 'Unknown error') + '\n\nTrying again...');
            // Let user press Enter again to retry
            canStartRecording = true;
        }
    } catch (error) {
    console.error('Error recording answer (ignored):', error);
    updateStatus('Ready');
    document.getElementById('recording-indicator').style.display = 'none';
    document.getElementById('input-hint').textContent = 'Press Enter to try answering again.';
    canStartRecording = true;
}

}


// Generate Conversational Response (fast, text only)
async function generateConversationalResponse(answer) {
    try {
        const response = await fetch('/api/conversational-response', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                session_id: sessionId,
                answer: answer,
                question_num: currentQuestionNumber
            })
        });

        if (!response.ok) return;

        const data = await response.json();

        if (data.success && data.response) {
            updateStatus('Speaking...');
            const messageElement = addMessage('', 'interviewer', {showTyping: true});
            await speakAndType(data.response, messageElement);
            updateStatus('Ready');
        }
    } catch (error) {
        console.error('Error generating conversational response:', error);
    }
}


// Save Answer
async function saveAnswer(question, answer) {
    try {
        const response = await fetch('/api/save-answer', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                session_id: sessionId,
                question: question,
                answer: answer
            })
        });

        if (!response.ok) {
            throw new Error(`Server returned ${response.status}`);
        }

        const data = await response.json();

        if (!data.success) {
            console.error('Error saving answer');
        }
    } catch (error) {
        console.error('Error saving answer:', error);
    }
}

// Next Question
async function nextQuestion() {
    document.getElementById('input-hint').textContent = 'Preparing next question...';
    await getNextQuestion();
}

// Complete Interview
async function completeInterview() {
    try {
        await stopSpeech();

        const response = await fetch('/api/complete-interview', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({session_id: sessionId})
        });

        if (!response.ok) {
            throw new Error(`Server returned ${response.status}`);
        }

        const data = await response.json();

        if (data.success) {
            const report = data.report;

            showScreen('report-screen');
            document.getElementById('final-score').textContent = report.avg_score + '/10';

            let reportHTML = '<div style="margin-bottom: 30px;">';
            reportHTML += '<h3 style="margin-bottom: 20px; color: #1a1a1a;">Question-by-Question Scores</h3>';

            report.responses.forEach((resp, index) => {
                const isEmpty = resp.empty || resp.answer === '[No answer provided]';
                const scoreColor = isEmpty ? '#dc2626' : (resp.score >= 7 ? '#059669' : (resp.score >= 5 ? '#d97706' : '#dc2626'));

                reportHTML += '<div class="report-item">';
                reportHTML += '<div class="report-item-header">';
                reportHTML += `<span class="report-item-number">Question ${index + 1}</span>`;
                reportHTML += `<span class="report-item-score" style="color: ${scoreColor};">${resp.score}/10</span>`;
                reportHTML += '</div>';
                reportHTML += `<div class="report-item-question">Q: ${resp.question}</div>`;

                if (isEmpty) {
                    reportHTML += `<div class="report-item-answer" style="color: #dc2626; font-style: italic;">A: No answer provided</div>`;
                } else {
                    const answerPreview = resp.answer.substring(0, 200);
                    reportHTML += `<div class="report-item-answer">A: ${answerPreview}${resp.answer.length > 200 ? '...' : ''}</div>`;
                }

                reportHTML += '</div>';
            });

            reportHTML += '</div>';

            if (report.final_feedback) {
                const feedbackHTML = report.final_feedback
                    .replace(/\n\n/g, '</p><p>')
                    .replace(/\n/g, '<br>');

                reportHTML += '<div style="background: #f0f4f8; padding: 28px; border-radius: 12px; border-left: 4px solid #1e3a8a;">';
                reportHTML += '<h3 style="margin-bottom: 20px; color: #1e3a8a; font-size: 20px;">📊 Summary</h3>';
                reportHTML += `<div style="line-height: 1.8; color: #374151; font-size: 15px;"><p>${feedbackHTML}</p></div>`;
                reportHTML += '</div>';
            }

            document.getElementById('report-content').innerHTML = reportHTML;
        } else {
            alert('Error generating report: ' + (data.message || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error completing interview:', error);
        alert('Error generating report: ' + error.message);
    }
}

// Helper function
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Stop speech when page is closed or refreshed
window.addEventListener('beforeunload', function(e) {
    if (sessionId) {
        stopSpeech();
        if (interviewTimer) {
            clearInterval(interviewTimer);
        }
    }
});

// Stop speech when navigating away from interview screen
window.addEventListener('pagehide', function(e) {
    if (sessionId) {
        stopSpeech();
    }
});

// Enter key: start answer OR go to next question
// Press Enter to start speaking (only)
document.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
        const interviewScreen = document.getElementById('interview-screen');
        const isActive = interviewScreen && interviewScreen.classList.contains('active');
        if (!isActive) return;

        // Only use Enter when we are allowed to start recording
        if (canStartRecording && !isRecording) {
            e.preventDefault(); // avoid accidental form submit / reload
            recordAnswer();
        }
    }
});