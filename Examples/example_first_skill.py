"""/**********************************************************************
    Copyright 2021 Misty Robotics
    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at
        http://www.apache.org/licenses/LICENSE-2.0
    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
    **WARRANTY DISCLAIMER.**
    * General. TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, MISTY
    ROBOTICS PROVIDES THIS SAMPLE SOFTWARE "AS-IS" AND DISCLAIMS ALL
    WARRANTIES AND CONDITIONS, WHETHER EXPRESS, IMPLIED, OR STATUTORY,
    INCLUDING THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
    PURPOSE, TITLE, QUIET ENJOYMENT, ACCURACY, AND NON-INFRINGEMENT OF
    THIRD-PARTY RIGHTS. MISTY ROBOTICS DOES NOT GUARANTEE ANY SPECIFIC
    RESULTS FROM THE USE OF THIS SAMPLE SOFTWARE. MISTY ROBOTICS MAKES NO
    WARRANTY THAT THIS SAMPLE SOFTWARE WILL BE UNINTERRUPTED, FREE OF VIRUSES
    OR OTHER HARMFUL CODE, TIMELY, SECURE, OR ERROR-FREE.
    * Use at Your Own Risk. YOU USE THIS SAMPLE SOFTWARE AND THE PRODUCT AT
    YOUR OWN DISCRETION AND RISK. YOU WILL BE SOLELY RESPONSIBLE FOR (AND MISTY
    ROBOTICS DISCLAIMS) ANY AND ALL LOSS, LIABILITY, OR DAMAGES, INCLUDING TO
    ANY HOME, PERSONAL ITEMS, PRODUCT, OTHER PERIPHERALS CONNECTED TO THE PRODUCT,
    COMPUTER, AND MOBILE DEVICE, RESULTING FROM YOUR USE OF THIS SAMPLE SOFTWARE
    OR PRODUCT.
    Please refer to the Misty Robotics End User License Agreement for further
    information and full details:
        https://www.mistyrobotics.com/legal/end-user-license-agreement/
**********************************************************************/"""

# Add mistyPy directory to sys path
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from mistyPy.Robot import Robot
from mistyPy.Events import Events


def start_skill():
    misty.register_event("initTTSComplete", Events.TextToSpeechComplete, keep_alive=False, callback_function=tts_intro_completed)
    misty.display_image("e_defaultcontent.jpg")
    misty.move_head(0, 0, 0, 85)
    misty.speak("Hello! I'm ready to talk with you. What would you like to discuss?")

def tts_intro_completed(event):
    start_conversation()

def start_conversation():
    misty.register_event("conversationTTSComplete", Events.TextToSpeechComplete, keep_alive=False, callback_function=listen_for_speech)
    misty.speak("Please tell me something, and I'll repeat it back to you.", None, None, None, True, "conversation-tts")

def listen_for_speech(event):
    misty.register_event("userSpeechComplete", Events.VoiceRecord, callback_function=voice_record_complete)
    misty.capture_speech_azure(True, 2000, 15000, False, False, "en-us", "<azure_cognitive_services_key>", "eastus")

def voice_record_complete(event):
    if "message" in event:
        parsed_message = event["message"]
        misty_heard = parsed_message["speechRecognitionResult"]
        print(f"Misty heard: {misty_heard}")
        
        # Respond back with what was heard
        misty.register_event("responseTTSComplete", Events.TextToSpeechComplete, keep_alive=False, callback_function=continue_conversation)
        misty.speak(f"You said: {misty_heard}", None, None, None, True, "response-tts")
    else:
        # If no speech was detected, ask again
        misty.register_event("noSpeechTTSComplete", Events.TextToSpeechComplete, keep_alive=False, callback_function=listen_for_speech)
        misty.speak("I didn't hear anything. Please try again.", None, None, None, True, "no-speech-tts")

def continue_conversation(event):
    misty.register_event("continueTTSComplete", Events.TextToSpeechComplete, keep_alive=False, callback_function=ask_to_continue)
    misty.speak("Would you like to say something else? Just tell me yes or no.", None, None, None, True, "continue-tts")

def ask_to_continue(event):
    misty.register_event("continueResponseComplete", Events.VoiceRecord, callback_function=handle_continue_response)
    misty.capture_speech_azure(True, 2000, 10000, False, False, "en-us", "<azure_cognitive_services_key>", "eastus")

def handle_continue_response(event):
    if "message" in event:
        parsed_message = event["message"]
        response = parsed_message["speechRecognitionResult"].lower()
        print(f"User response: {response}")
        
        if "yes" in response or "yeah" in response or "sure" in response:
            misty.register_event("yesResponseComplete", Events.TextToSpeechComplete, keep_alive=False, callback_function=start_conversation)
            misty.speak("Great! Let's continue our conversation.", None, None, None, True, "yes-response-tts")
        else:
            misty.register_event("noResponseComplete", Events.TextToSpeechComplete, keep_alive=False, callback_function=end_conversation)
            misty.speak("Thank you for talking with me! Goodbye!", None, None, None, True, "no-response-tts")

def end_conversation(event):
    misty.display_image("e_joy.jpg")
    misty.speak("It was nice chatting with you!")


if __name__ == "__main__":
    ip_address = "10.66.239.83"
    misty = Robot(ip_address)
    start_skill()


def simulate_conversation():
    """Simulate the conversation when no Misty robot is available"""
    print("=== MISTY CONVERSATION SIMULATOR ===")
    print("Robot: Hello! I'm ready to talk with you. What would you like to discuss?")
    
    while True:
        try:
            user_input = input("You: ")
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("Robot: Thank you for talking with me! Goodbye!")
                break
            
            print(f"Robot: You said: {user_input}")
            
            continue_response = input("Robot: Would you like to say something else? (yes/no): ").lower()
            if continue_response in ['yes', 'yeah', 'sure']:
                print("Robot: Great! Let's continue our conversation.")
            else:
                print("Robot: Thank you for talking with me! Goodbye!")
                break
                
        except KeyboardInterrupt:
            print("\nRobot: Thank you for talking with me! Goodbye!")
            break
