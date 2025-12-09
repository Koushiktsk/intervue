
from flask import Flask, send_file, request, jsonify
import time
from web_interview import WebInterviewAgent

app = Flask(__name__, static_folder=None, template_folder=None)
sessions = {}

# Global error handler to return JSON instead of HTML
@app.errorhandler(Exception)
def handle_error(error):
    print(f"Unhandled error: {str(error)}")
    return jsonify({'success': False, 'message': str(error)}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'message': 'Endpoint not found'}), 404

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/style.css')
def style():
    return send_file('style.css', mimetype='text/css')

@app.route('/script.js')
def script():
    return send_file('script.js', mimetype='application/javascript')


@app.route('/api/start-interview', methods=['POST'])
def start_interview():
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        session_id = str(time.time())

        agent = WebInterviewAgent()
        role_key = data.get('role', '1')
        exp_key = data.get('experience', '1')
        duration_minutes = data.get('duration_minutes', 5)
        candidate_name = data.get('candidate_name', '')

        sessions[session_id] = {
            'agent': agent,
            'role': role_key,
            'experience': exp_key,
            'current_question': 0,
            'duration_minutes': duration_minutes,
            'candidate_name': candidate_name,
            'asked_questions': []
        }

        # Store name in agent for use in responses
        agent.candidate_name = candidate_name

        role_name = agent.ROLES[role_key]['name']
        exp_name = agent.EXPERIENCE_LEVELS[exp_key]['name']
        exp_desc = agent.EXPERIENCE_LEVELS[exp_key]['description']

        # Create short introduction with name
        greeting = f"Welcome, {candidate_name}!" if candidate_name else "Welcome!"
        intro_text = f"{greeting} This is your {duration_minutes}-minute {role_name} interview at {exp_name}. I'll ask questions, you answer using your voice. Use headphones to avoid echo. Let's begin!"

        return jsonify({
            'success': True,
            'session_id': session_id,
            'role_name': role_name,
            'experience_name': exp_name,
            'intro_text': intro_text,
            'duration_minutes': duration_minutes
        })
    except Exception as e:
        print(f"Error in start_interview: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/speak', methods=['POST'])
def speak():
    """Speak text and return only AFTER speech has finished"""
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        session_id = data.get('session_id')
        text = data.get('text', '')

        if session_id not in sessions:
            return jsonify({'success': False, 'message': 'Session not found'}), 404

        agent = sessions[session_id]['agent']

        # Speak the text synchronously (wait until voice finishes)
        agent.speaker.Speak(text, async_mode=False)

        return jsonify({'success': True})
    except Exception as e:
        print(f"Error in speak: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/stop-speech', methods=['POST'])
def stop_speech():
    """Stop any ongoing speech"""
    try:
        data = request.json or {}
        session_id = data.get('session_id')

        if session_id and session_id in sessions:
            agent = sessions[session_id]['agent']
            agent.speaker.stop()
            print("[STOP SPEECH] Speech stopped for session:", session_id)

        return jsonify({'success': True})
    except Exception as e:
        print(f"Error in stop_speech: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/conversational-response', methods=['POST'])
def conversational_response():
    """Generate a conversational follow-up based on candidate's answer"""
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        session_id = data.get('session_id')
        answer = data.get('answer', '')
        question_num = data.get('question_num', 1)

        if session_id not in sessions:
            return jsonify({'success': False, 'message': 'Session not found'}), 404

        session = sessions[session_id]
        agent = session['agent']
        candidate_name = session.get('candidate_name', '')

        # Generate conversational response with name
        response_text = agent.generate_conversational_response(answer, question_num, candidate_name)

        return jsonify({'success': True, 'response': response_text})
    except Exception as e:
        print(f"Error in conversational_response: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/get-question', methods=['POST'])
def get_question():
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        session_id = data.get('session_id')
        asked_questions = data.get('asked_questions', [])

        if session_id not in sessions:
            return jsonify({'success': False, 'message': 'Session not found'}), 404

        session = sessions[session_id]
        agent = session['agent']
        session['current_question'] += 1
        session['asked_questions'] = asked_questions

        # Generate a new unique question
        question = agent.generate_question(
            session['role'],
            session['experience'],
            session['current_question'],
            asked_questions
        )

        return jsonify({
            'success': True,
            'question': question,
            'question_number': session['current_question']
        })
    except Exception as e:
        print(f"Error in get_question: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/record-answer', methods=['POST'])
def record_answer():
    try:
        data = request.json or {}
        session_id = data.get('session_id')

        if not session_id or session_id not in sessions:
            return jsonify({'success': False, 'message': 'Session not found'}), 404

        agent = sessions[session_id]['agent']

        import speech_recognition as sr

        try:
            # Open microphone and record
            with sr.Microphone() as source:
                # Calibrate for background noise
                agent.recognizer.adjust_for_ambient_noise(source, duration=2)
                audio = agent.recognizer.listen(
                    source,
                    timeout=None,
                    phrase_time_limit=None
                )

            # Try to recognize using Google
            try:
                text = agent.recognizer.recognize_google(audio)
                return jsonify({'success': True, 'answer': text}), 200

            except sr.UnknownValueError:
                # Heard something but couldn't understand
                return jsonify({
                    'success': False,
                    'message': 'Sorry, I could not clearly understand your speech. Please try speaking again.'
                }), 200

            except sr.RequestError as e:
                # API/network problem
                return jsonify({
                    'success': False,
                    'message': f'Speech recognition service error: {e}'
                }), 200

        except OSError as e:
            # Typical: no default input device / microphone issue
            print(f"Microphone error: {e}")
            return jsonify({
                'success': False,
                'message': 'Microphone not available. Please check your input device and try again.'
            }), 200

    except Exception as e:
        # Truly unexpected error
        print(f"Error in record_answer: {str(e)}")
        return jsonify({'success': False, 'message': 'Unexpected error while recording.'}), 500


@app.route('/api/save-answer', methods=['POST'])
def save_answer():
    """Save answer without evaluation (evaluation happens at the end)"""
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        session_id = data.get('session_id')

        if session_id not in sessions:
            return jsonify({'success': False, 'message': 'Session not found'}), 404

        session = sessions[session_id]
        agent = session['agent']

        # Just save the Q&A, don't evaluate yet
        agent.interview_data['responses'].append({
            'question': data.get('question'),
            'answer': data.get('answer')
        })

        return jsonify({'success': True})
    except Exception as e:
        print(f"Error in save_answer: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/complete-interview', methods=['POST'])
def complete_interview():
    try:
        data = request.json or {}
        session_id = data.get('session_id')

        if not session_id:
            return jsonify({'success': False, 'message': 'No session_id provided'}), 400

        if session_id not in sessions:
            return jsonify({'success': False, 'message': 'Session not found'}), 404

        session = sessions[session_id]
        agent = session['agent']

        # Get responses list
        responses = agent.interview_data.get('responses', [])

        # Evaluate all responses now
        evaluated_responses = []
        scores = []

        for r in responses:
            answer = r['answer']
            is_empty = answer == '[No answer provided]' or not answer or answer.strip() == ''

            try:
                if is_empty:
                    # No answer provided - give score of 0
                    evaluated_responses.append({
                        'question': r['question'],
                        'answer': '[No answer provided]',
                        'score': 0.0,
                        'empty': True
                    })
                    scores.append(0.0)
                else:
                    # Valid answer - evaluate normally
                    evaluation = agent.evaluate(r['question'], answer, session['role'])
                    score = float(evaluation.get('score', 0))
                    scores.append(score)

                    evaluated_responses.append({
                        'question': r['question'],
                        'answer': answer,
                        'score': score,
                        'empty': False
                    })
            except Exception as e:
                print(f"Error evaluating response: {e}")
                evaluated_responses.append({
                    'question': r['question'],
                    'answer': answer,
                    'score': 5.0,
                    'empty': False
                })
                scores.append(5.0)

        avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0

        # Generate final feedback with all evaluations
        try:
            final_feedback = agent.final_feedback_formatted(evaluated_responses)
        except Exception as fe:
            print(f"final_feedback error: {fe}")
            final_feedback = "Could not generate detailed feedback."

        # Clean up session
        try:
            del sessions[session_id]
        except KeyError:
            pass

        return jsonify({
            'success': True,
            'report': {
                'avg_score': avg_score,
                'total_questions': len(evaluated_responses),
                'responses': evaluated_responses,
                'final_feedback': final_feedback
            }
        }), 200

    except Exception as e:
        print(f"Error in complete_interview: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Unexpected error while generating report.'
        }), 500


if __name__ == '__main__':
    print("\n🎯 Starting Interview Practice Partner Server...")
    print("✅ Open browser: http://127.0.0.1:5000\n")
    app.run(debug=True, port=5000)