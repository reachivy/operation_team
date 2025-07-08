const startBtn = document.getElementById('startBtn');
const submitBtn = document.getElementById('submitBtn');
const micBtn = document.getElementById('micBtn');
const timerEl = document.getElementById('timer');
const sectionEl = document.getElementById('sectionArea');
const chatboxEl = document.getElementById('chatbox');
const statusEl = document.getElementById('status');
const textAnswer = document.getElementById('textAnswer');
const inputArea = document.getElementById('inputArea');
const greetingEl = document.getElementById('greeting');
const progressEl = document.getElementById('progress');
const wordCountEl = document.getElementById('wordCount');
const sectionCompleteArea = document.getElementById('sectionCompleteArea');
const sectionCompleteTitle = document.getElementById('sectionCompleteTitle');
const sectionScoreEl = document.getElementById('sectionScore');
const reattemptBtn = document.getElementById('reattemptBtn');
const nextSectionBtn = document.getElementById('nextSectionBtn');
const sectionLinks = document.querySelectorAll('.section-link');
const dropdownBtns = document.querySelectorAll('.dropdown-btn');
const questionLinks = document.querySelectorAll('.question-link');
const feedbackEl = document.createElement('p');
feedbackEl.id = 'sectionFeedback';
let synth = window.speechSynthesis;

const questionScoresEl = document.createElement('div');
questionScoresEl.id = 'questionScores';
questionScoresEl.style.display = 'flex';
questionScoresEl.style.flexWrap = 'wrap';
questionScoresEl.style.gap = '10px 20px';
questionScoresEl.style.marginBottom = '20px';
questionScoresEl.style.fontSize = '16px';
questionScoresEl.style.color = '#2c3e50';

sectionCompleteArea.insertBefore(feedbackEl, sectionScoreEl.nextSibling);
sectionCompleteArea.insertBefore(questionScoresEl, feedbackEl);

dropdownBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const dropdown = btn.parentElement.nextElementSibling;
        dropdown.classList.toggle('hidden');
        btn.classList.toggle('open');
    });
});

sectionLinks.forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        const section = parseInt(link.getAttribute('data-section'));
        console.log(`Section link clicked: Section ${section}`);
        jumpToSection(section);
    });
});

questionLinks.forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        const section = parseInt(link.getAttribute('data-section'));
        const questionNumber = parseInt(link.getAttribute('data-question'));
        console.log(`Question link clicked: Section ${section}, Question ${questionNumber}`);
        jumpToQuestion(section, questionNumber);
    });
});

startBtn.addEventListener('click', () => {
    console.log('Start button clicked');
    fetch('/start_assessment', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: 'intern1' })
    })
    .then(response => {
        console.log('Start response:', response);
        if (!response.ok) throw new Error('Network response was not ok');
        return response.json();
    })
    .then(data => {
        console.log('Start data received:', data);
        sectionEl.textContent = `Section ${data.section}: ${data.section_name}`;
        appendBotMessage(`Question ${data.display_question_number}: ${data.question}`);
        progressEl.textContent = `${data.answered}/${data.total_questions} answered`;
        currentQuestionNumber = data.question_number;
        speakQuestion(data.question);
        startBtn.style.display = 'none';
        greetingEl.parentElement.style.display = 'none';
        inputArea.style.display = 'block';
        sectionCompleteArea.style.display = 'none';
        chatboxEl.style.display = 'block';
    })
    .catch(error => console.error('Start error:', error));
});

micBtn.addEventListener('click', () => {
    if (!isRecording) {
        startRecording();
    } else {
        stopRecording();
    }
});

async function startRecording() {
    try {
        console.log('Starting recording');
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];
        transcriptBuffer = [];

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };

        mediaRecorder.onstop = () => {
            console.log('Recording stopped');
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            const finalTranscript = transcriptBuffer.join(' ').trim();
            if (finalTranscript) {
                const currentText = textAnswer.value.trim();
                textAnswer.value = currentText ? currentText + ' ' + finalTranscript : finalTranscript;
                const words = textAnswer.value.trim().split(/\s+/).filter(word => word.length > 0).length;
                wordCountEl.textContent = `${words} words`;
            }
        };

        if (recognition) {
            recognition.onresult = (event) => {
                const transcript = event.results[event.results.length - 1][0].transcript;
                console.log('Transcription received:', transcript);
                transcriptBuffer.push(transcript);
            };

            recognition.onerror = (event) => {
                console.error('Speech recognition error:', event.error);
                statusEl.textContent = 'Error with speech recognition: ' + event.error;
            };

            recognition.onend = () => {
                if (isRecording && timeLeft > 0) {
                    console.log('Restarting speech recognition due to pause');
                    recognition.start();
                }
            };

            recognition.start();
            console.log('Speech recognition started');
        } else {
            statusEl.textContent = 'Speech recognition not supported. Please type your answer.';
        }

        mediaRecorder.start();
        isRecording = true;
        micBtn.classList.add('recording');
        startTimer();
    } catch (error) {
        console.error('Error starting recording:', error);
        statusEl.textContent = 'Error accessing microphone. Please try again.';
    }
}

function stopRecording() {
    console.log('Stopping recording');
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
    }
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
        stream = null;
    }
    if (recognition) {
        recognition.stop();
    }
    isRecording = false;
    micBtn.classList.remove('recording');
    stopTimer();
}

submitBtn.addEventListener('click', () => {
    const answer = textAnswer.value.trim();
    if (answer) {
        console.log('Text input:', answer);
        submitAnswer(answer);
        appendUserMessage(answer);
        textAnswer.value = '';
        wordCountEl.textContent = '0 words';
    } else {
        statusEl.textContent = 'Please enter an answer.';
    }
});

textAnswer.addEventListener('keypress', (event) => {
    if (event.key === 'Enter') {
        event.preventDefault();
        const answer = textAnswer.value.trim();
        if (answer) {
            console.log('Enter key pressed, submitting:', answer);
            submitAnswer(answer);
            appendUserMessage(answer);
            textAnswer.value = '';
            wordCountEl.textContent = '0 words';
        } else {
            statusEl.textContent = 'Please enter an answer.';
        }
    }
});

textAnswer.addEventListener('input', () => {
    const words = textAnswer.value.trim().split(/\s+/).filter(word => word.length > 0).length;
    wordCountEl.textContent = `${words} words`;
});

reattemptBtn.addEventListener('click', () => {
    console.log('Reattempt button clicked for current section');
    fetch('/start_assessment', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: 'intern1' })
    })
    .then(response => {
        if (!response.ok) throw new Error('Network response was not ok');
        return response.json();
    })
    .then(data => {
        console.log('Reattempt data received:', data);
        sectionEl.textContent = `Section ${data.section}: ${data.section_name}`;
        chatboxEl.innerHTML = '';
        appendBotMessage(`Question ${data.display_question_number}: ${data.question}`);
        progressEl.textContent = `${data.answered}/${data.total_questions} answered`;
        currentQuestionNumber = data.question_number;
        speakQuestion(data.question);
        sectionCompleteArea.style.display = 'none';
        chatboxEl.style.display = 'block';
        inputArea.style.display = 'block';
        statusEl.textContent = '';
    })
    .catch(error => console.error('Reattempt error:', error));
});

nextSectionBtn.addEventListener('click', () => {
    console.log('Next section button clicked');
    fetch('/start_assessment', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: 'intern1' })
    })
    .then(response => {
        if (!response.ok) throw new Error('Network response was not ok');
        return response.json();
    })
    .then(nextData => {
        console.log('Next section data received:', nextData);
        sectionEl.textContent = `Section ${nextData.section}: ${nextData.section_name}`;
        chatboxEl.innerHTML = '';
        appendBotMessage(`Question ${nextData.display_question_number}: ${nextData.question}`);
        progressEl.textContent = `${nextData.answered}/${data.total_questions} answered`;
        currentQuestionNumber = nextData.question_number;
        speakQuestion(nextData.question);
        sectionCompleteArea.style.display = 'none';
        chatboxEl.style.display = 'block';
        inputArea.style.display = 'block';
        statusEl.textContent = '';
    })
    .catch(error => console.error('Next section error:', error));
});

function startTimer() {
    timeLeft = 30;
    timerEl.textContent = `${timeLeft}s`;
    timerEl.classList.add('active');
    timerInterval = setInterval(() => {
        timeLeft--;
        timerEl.textContent = `${timeLeft}s`;
        if (timeLeft <= 0) {
            stopRecording();
        }
    }, 1000);
}

function stopTimer() {
    clearInterval(timerInterval);
    timerEl.classList.remove('active');
    timerEl.textContent = '30s';
    timeLeft = 30;
}

function appendBotMessage(message, className = '', detailedFeedback = '', correctAnswer = '') {
    if (!message) {
        console.log('Attempted to append empty message with class:', className);
        return;
    }
    const messageDiv = document.createElement('div');
    messageDiv.className = 'chat-message bot-message';
    const messageWrapper = document.createElement('div');
    messageWrapper.className = 'message-wrapper';
    const messageP = document.createElement('p');
    messageP.textContent = message;
    if (className) {
        messageP.className = className;
    }
    messageWrapper.appendChild(messageP);
    if (className === 'content-accuracy' && detailedFeedback) {
        const showMoreBtn = document.createElement('span');
        showMoreBtn.className = 'show-more-btn';
        showMoreBtn.textContent = '+';
        messageP.appendChild(showMoreBtn);
        const feedbackDiv = document.createElement('div');
        feedbackDiv.className = 'detailed-feedback hidden';
        feedbackDiv.textContent = detailedFeedback;
        messageWrapper.appendChild(feedbackDiv);
        showMoreBtn.addEventListener('click', () => {
            feedbackDiv.classList.toggle('hidden');
            showMoreBtn.textContent = feedbackDiv.classList.contains('hidden') ? '+' : '-';
        });

        // Add Show/Hide Answer button
        let answerShown = false;
        const answerBtn = document.createElement('button');
        answerBtn.className = 'show-answer-btn';
        answerBtn.textContent = 'Show Answer';
        answerBtn.addEventListener('click', () => {
            if (!answerShown) {
                const answerP = document.createElement('p');
                answerP.className = 'correct-answer';
                answerP.textContent = `Correct Answer: ${correctAnswer}`;
                messageWrapper.appendChild(answerP);
                answerBtn.textContent = 'Hide Answer';
                answerShown = true;
            } else {
                const answerP = messageWrapper.querySelector('.correct-answer');
                if (answerP) {
                    answerP.remove();
                }
                answerBtn.textContent = 'Show Answer';
                answerShown = false;
            }
        });
        messageWrapper.appendChild(answerBtn);
    }
    messageDiv.appendChild(messageWrapper);
    chatboxEl.appendChild(messageDiv);
    chatboxEl.scrollTop = chatboxEl.scrollHeight;
    console.log('Appended bot message:', message, 'with class:', className);
}

function appendUserMessage(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'chat-message user-message';
    const messageP = document.createElement('p');
    messageP.textContent = message;
    messageDiv.appendChild(messageP);
    chatboxEl.appendChild(messageDiv);
    chatboxEl.scrollTop = chatboxEl.scrollHeight;
    console.log('Appended user message:', message);
}

function submitAnswer(answer) {
    console.log('Submitting answer:', answer, 'for question number:', currentQuestionNumber);
    fetch('/submit_answer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            user_id: 'intern1',
            answer: answer,
            question_number: currentQuestionNumber
        })
    })
    .then(response => {
        console.log('Submit response:', response);
        if (!response.ok) {
            return response.json().then(errData => {
                throw new Error(errData.error || 'Network response was not ok');
            });
        }
        return response.json();
    })
    .then(data => {
        console.log('Submit data received:', data);
        if (data.status === 'section_completed') {
            progressEl.textContent = `${data.answered}/${data.total_questions} answered`;
            setTimeout(() => {
                chatboxEl.style.display = 'none';
                inputArea.style.display = 'none';
                sectionCompleteArea.style.display = 'block';
                sectionCompleteTitle.textContent = `Section ${data.section - (data.section_score >= 75 ? 1 : 0)} (${data.section_name}) Completed!`;
                sectionScoreEl.textContent = `Your Score: ${data.section_score.toFixed(2)}%`;
                questionScoresEl.innerHTML = '';
                const scores = data.question_scores || [];
                for (let i = 0; i < scores.length; i += 2) {
                    const rowDiv = document.createElement('div');
                    rowDiv.style.display = 'flex';
                    rowDiv.style.width = '100%';
                    rowDiv.style.justifyContent = 'space-between';
                    const leftDiv = document.createElement('div');
                    leftDiv.style.flex = '1';
                    leftDiv.textContent = `Question ${scores[i].question_number} (${scores[i].score} points)`;
                    rowDiv.appendChild(leftDiv);
                    if (i + 1 < scores.length) {
                        const rightDiv = document.createElement('div');
                        rightDiv.style.flex = '1';
                        rightDiv.style.textAlign = 'right';
                        rightDiv.textContent = `Question ${scores[i + 1].question_number} (${scores[i + 1].score} points)`;
                        rowDiv.appendChild(rightDiv);
                    }
                    questionScoresEl.appendChild(rowDiv);
                }
                if (data.feedback) {
                    feedbackEl.textContent = data.feedback;
                    feedbackEl.style.display = 'block';
                } else {
                    feedbackEl.textContent = '';
                    feedbackEl.style.display = 'none';
                }
                if (data.section_score >= 75) {
                    nextSectionBtn.style.display = 'inline-block';
                    reattemptBtn.style.display = 'none';
                } else {
                    reattemptBtn.style.display = 'inline-block';
                    nextSectionBtn.style.display = 'none';
                }
                statusEl.textContent = '';
            }, 2000);
        } else if (data.status === 'completed') {
            progressEl.textContent = `${data.answered}/${data.total_questions} answered`;
            setTimeout(() => {
                chatboxEl.style.display = 'none';
                inputArea.style.display = 'none';
                sectionCompleteArea.style.display = 'block';
                sectionCompleteTitle.textContent = 'Assessment Completed!';
                sectionScoreEl.textContent = 'Final Scores: ' + JSON.stringify(data.scores);
                questionScoresEl.innerHTML = '';
                feedbackEl.textContent = '';
                feedbackEl.style.display = 'none';
                reattemptBtn.style.display = 'none';
                nextSectionBtn.style.display = 'none';
                statusEl.textContent = '';
            }, 2000);
        } else {
            chatboxEl.style.display = 'block';
            const combinedFeedback = `(Match: ${data.match_percentage.toFixed(2)}%)\n${data.content_accuracy}`;
            if (data.content_accuracy) {
                appendBotMessage(combinedFeedback, 'content-accuracy', data.detailed_feedback, data.correct_answer);
            } else {
                appendBotMessage('Error: Content Accuracy feedback is missing.', 'content-accuracy');
            }
            setTimeout(() => {
                fetchNextQuestion();
            }, 2000); // Fetch next question after feedback is displayed
            statusEl.textContent = '';
            sectionCompleteArea.style.display = 'none';
            chatboxEl.style.display = 'block';
            inputArea.style.display = 'block';
        }
    })
    .catch(error => {
        console.error('Submit error:', error);
        const errorMessage = error.message === 'Network response was not ok' ? 'Error: Failed to submit answer.' : `Error: ${error.message}`;
        appendBotMessage(errorMessage, 'error-message');
    });
}

function speakQuestion(text) {
    console.log('Speaking:', text);
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-US';
    synth.speak(utterance);
}

function fetchNextQuestion() {
    console.log('Fetching next question for user_id: intern1, current question:', currentQuestionNumber);
    fetch('/get_question', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: 'intern1', question_number: currentQuestionNumber + 1 })
    })
    .then(response => {
        console.log('Next question response:', response);
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        console.log('Next question data received:', data);
        sectionEl.textContent = `Section ${data.section}: ${data.section_name}`;
        appendBotMessage(`Question ${data.display_question_number}: ${data.question}`);
        progressEl.textContent = `${data.answered}/${data.total_questions} answered`;
        currentQuestionNumber = data.question_number;
        speakQuestion(data.question);
        statusEl.textContent = '';
    })
    .catch(error => {
        console.error('Fetch next question error:', error);
        appendBotMessage('Error: Unable to fetch the next question.', 'error-message');
    });
}

function jumpToSection(section) {
    fetch('/start_assessment', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: 'intern1', section: section })
    })
    .then(response => {
        if (!response.ok) throw new Error('Network response was not ok');
        return response.json();
    })
    .then(data => {
        console.log('Jump to section data received:', data);
        sectionEl.textContent = `Section ${data.section}: ${data.section_name}`;
        chatboxEl.innerHTML = '';
        appendBotMessage(`Question ${data.display_question_number}: ${data.question}`);
        progressEl.textContent = `${data.answered}/${data.total_questions} answered`;
        currentQuestionNumber = data.question_number;
        speakQuestion(data.question);
        sectionCompleteArea.style.display = 'none';
        chatboxEl.style.display = 'block';
        inputArea.style.display = 'block';
        statusEl.textContent = '';
        startBtn.style.display = 'none';
        greetingEl.parentElement.style.display = 'none';
    })
    .catch(error => console.error('Jump to section error:', error));
}

function jumpToQuestion(section, questionNumber) {
    fetch('/start_assessment', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: 'intern1', section: section })
    })
    .then(response => {
        if (!response.ok) throw new Error('Network response was not ok');
        return response.json();
    })
    .then(() => {
        fetch('/get_question', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: 'intern1', question_number: questionNumber })
        })
        .then(response => {
            if (!response.ok) throw new Error('Network response was not ok');
            return response.json();
        })
        .then(data => {
            console.log('Jump to question data received:', data);
            sectionEl.textContent = `Section ${data.section}: ${data.section_name}`;
            chatboxEl.innerHTML = '';
            appendBotMessage(`Question ${data.display_question_number}: ${data.question}`);
            progressEl.textContent = `${data.answered}/${data.total_questions} answered`;
            currentQuestionNumber = data.question_number;
            speakQuestion(data.question);
            sectionCompleteArea.style.display = 'none';
            chatboxEl.style.display = 'block';
            inputArea.style.display = 'block';
            statusEl.textContent = '';
            startBtn.style.display = 'none';
            greetingEl.parentElement.style.display = 'none';
        })
        .catch(error => console.error('Jump to question error:', error));
    })
    .catch(error => console.error('Set section error:', error));
}

let currentQuestionNumber = 0;
let timerInterval = null;
let timeLeft = 30;
let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];
let stream = null;
let transcriptBuffer = [];
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = 'en-US';
} else {
    console.error('SpeechRecognition API not supported in this browser.');
}