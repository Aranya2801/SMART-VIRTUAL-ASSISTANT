import speech_recognition as sr
import pyttsx3
import smtplib
import random
import requests
import json

# Initialize the speech recognition engine
r = sr.Recognizer()

# Initialize the text-to-speech engine
engine = pyttsx3.init()

# Set the email credentials
smtp_server = "smtp.gmail.com"
port = 587
sender_email = "your_email_address"
password = "your_email_password"

# Define a function to send emails


def send_email(recipient, subject, body):
    with smtplib.SMTP(smtp_server, port) as server:
        server.starttls()
        server.login(sender_email, password)
        message = f"Subject: {subject}\n\n{body}"
        server.sendmail(sender_email, recipient, message)

# Define a function to tell jokes


def tell_joke():
    jokes = ["Why did the tomato turn red? Because it saw the salad dressing!",
             "What do you get when you cross a snowman and a shark? Frostbite!",
             "Why did the chicken cross the playground? To get to the other slide!"]
    joke = random.choice(jokes)
    engine.say(joke)
    engine.runAndWait()

# Define a function to offer motivational messages


def offer_motivation():
    messages = ["Believe you can and you're halfway there.",
                "Success is not final, failure is not fatal: it is the courage to continue that counts.",
                "You miss 100% of the shots you don't take."]
    message = random.choice(messages)
    engine.say(message)
    engine.runAndWait()

# Define a function to get weather information


def get_weather(city):
    api_key = "your_api_key"
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}"
    response = requests.get(url)
    data = json.loads(response.text)
    description = data["weather"][0]["description"]
    temperature = data["main"]["temp"] - 273.15
    return f"The weather in {city} is {description} and the temperature is {temperature:.1f} degrees Celsius."

# Define the main function


def voice_assistant():
    with sr.Microphone() as source:
        print("Speak now!")
        r.adjust_for_ambient_noise(source)
        audio = r.listen(source)

        try:
            text = r.recognize_google(audio)
            print(f"You said: {text}")
            if "play music" in text:
                # TODO: Add music playback functionality
                pass
            elif "email" in text:
                # TODO: Add email sending functionality
                pass
            elif "tell me a joke" in text:
                tell_joke()
            elif "motivate me" in text:
                offer_motivation()
            elif "weather" in text:
                city = text.split(" ")[-1]
                weather = get_weather(city)
                engine.say(weather)
                engine.runAndWait()
            else:
                engine.say("Sorry, I didn't understand that.")
                engine.runAndWait()
        except:
            engine.say("Sorry, I couldn't understand you.")
            engine.runAndWait()


# Call the main function
voice_assistant()
