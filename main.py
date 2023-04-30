import speech_recognition as sr
import pyttsx3
import datetime
import wikipedia
import webbrowser
import os
import smtplib
import random
import requests
from newsapi import NewsApiClient
import spotify.sync as spotify
import time
from spotipy.oauth2 import SpotifyClientCredentials

# Initialize the recognizer and text-to-speech engine
r = sr.Recognizer()
engine = pyttsx3.init()

# Set the properties of the text-to-speech engine
voiceEngine = pyttsx3.init('sapi5')
voices = voiceEngine.getProperty('voices')
voiceEngine.setProperty('voice', voices[1].id)

# Define a function to speak the given text
def speak(text):
    engine.say(text)
    engine.runAndWait()

# Define a function to greet the user
def greet():
    hour = datetime.datetime.now().hour
    if hour >= 0 and hour < 12:
        speak("Good morning!")
    elif hour >= 12 and hour < 18:
        speak("Good afternoon!")
    else:
        speak("Good evening!")
    speak("How can I assist you?")

# Define a function to recognize user input and process it
def process_input():
    with sr.Microphone() as source:
        print("Listening...")
        r.pause_threshold = 1
        r.adjust_for_ambient_noise(source, duration=1)
        audio = r.listen(source)
        try:
            print("Recognizing...")
            query = r.recognize_google(audio, language='en-us')
            print(f"You said: {query}\n")
        except Exception as e:
            print("Sorry, I did not understand what you said.")
            return ""

    return query.lower()

# Define a function to send email
def send_email(to, content):
    server = smtplib.SMTP('2006010@kiit.ac.in', 587)
    server.ehlo()
    server.starttls()
    server.login('aranyaghoshriku2801email@gmail.com', 'riku2801@')
    server.sendmail('aranyaghoshriku2801email@gmail.com', to, content)
    server.close()

# Define a function to get the latest news
def get_news():
    newsapi = NewsApiClient(api_key='your-api-key')
    top_headlines = newsapi.get_top_headlines(language='en', country='us')
    articles = top_headlines['articles']
    for article in articles:
        speak(article['title'])

# Main loop
if __name__ == "__main__":
    greet()
    while True:
        query = process_input()
        if 'wikipedia' in query:
            speak('Searching Wikipedia...')
            query = query.replace("wikipedia", "")
            results = wikipedia.summary(query, sentences=2)
            speak("According to Wikipedia, ")
            speak(results)
        elif 'open youtube' in query:
            speak('Opening YouTube...')
            webbrowser.open("youtube.com")
        elif 'open google' in query:
            speak('Opening Google...')
            webbrowser.open("google.com")
        elif 'play music' in query:
            speak('Playing music...')
            music_dir = 'C:/Users/Public/Music/Sample Music'
            songs = os.listdir(music_dir)
            os.startfile(os.path.join(music_dir, songs[0]))
        elif 'what is the time' in query:
            strTime = datetime.datetime.now().strftime("%H:%M:%S")
            speak(f"The time is {strTime}")
        elif 'email' in query:
            try:
                speak("What should I say?")
                content = process_input()
                speak("To whom should I send it?")
                to = process_input()
                send_email(to, content)
                speak("Email has been sent!")
            except Exception as e:
                print(e)
                speak("Sorry Sorry, I could not send the email.")
elif 'what is the weather like' in query:
            speak('Checking the weather...')
            api_key = "your-api-key"
            base_url = "https://www.timeanddate.com/weather/india"
            city_name = "New York"
            complete_url = base_url + "appid=" + api_key + "&q=" + city_name
            response = requests.get(complete_url)
            data = response.json()
            if data["cod"] != "404":
                weather = data["weather"][0]["description"]
                temperature = round(float(data["main"]["temp"]) - 273.15, 1)
                humidity = data["main"]["humidity"]
                wind_speed = data["wind"]["speed"]
                speak(f"The weather in {city_name} is {weather}. The temperature is {temperature} degrees Celsius. The humidity is {humidity} percent. The wind speed is {wind_speed} meters per second.")
            else:
                speak("Sorry, I could not find the weather for that location.")
        # Add a function to tell a joke
def tell_joke():
    url = "https://official-joke-api.appspot.com/random_joke"
    response = requests.get(url)
    data = response.json()
    setup = data['setup']
    punchline = data['punchline']
    speak(setup)
    time.sleep(2) # Pause for effect
    speak(punchline)

# Add a conditional statement to trigger a joke
if 'tell me a joke' in query:
    tell_joke()

jokes = ["Why did the tomato turn red? Because it saw the salad dressing!", "Why do we tell actors to 'break a leg?' Because every play has a cast!", "What do you call a fake noodle? An impasta!"]
speak(random.choice(jokes))
# Define a function to read news headlines
def get_news():
    url = "https://newsapi.org/v2/top-headlines?country=us&apiKey=YOUR_API_KEY"
    response = requests.get(url)
    data = response.json()
    news = data['articles']
    for article in news:
        speak(article['title'])
        time.sleep(2) # Pause between headlines

# Add a conditional statement to trigger news headlines
if 'news' in query:
    speak('Getting the latest news...')
    get_news()

get_news()
        
# Define a function to open websites
def open_website(query):
    # Define a dictionary of website names and URLs
    websites = {
        'google': 'https://www.google.com',
        'youtube': 'https://www.youtube.com',
        'facebook': 'https://www.facebook.com',
        'twitter': 'https://www.twitter.com',
        'instagram': 'https://www.instagram.com'
    }
    # Use a for loop to check if the query matches any of the website names
    for site in websites:
        if site in query:
            webbrowser.open(websites[site])
            speak(f"Opening {site}")
            return True
    return False

# Add a conditional statement to trigger website opening
if 'open' in query:
    open_website(query)

website = query.split('open ')[1]
url = f"https://www.{website}.com/"
webbrowser.open(url)
speak(f"Opening {website} in your browser")


scope = "user-read-playback-state,user-modify-playback-state"

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))

if 'play' in query:
    search_query = query.split('play ')[1]
    result = sp.search(q=search_query, type='track', limit=1)
    uri = result['tracks']['items'][0]['uri']
    sp.start_playback(uris=[uri])
    speak(f"Playing {search_query} on Spotify")


if 'remind me to' in query:
    reminder = query.split('remind me to ')[1]
    speak(f"I will remind you to {reminder}")
    reminder_time = datetime.datetime.now() + datetime.timedelta(minutes=10) # set the reminder time to 10 minutes from now
    while datetime.datetime.now() < reminder_time:
        time.sleep(1)
    speak(f"Reminder: {reminder}")


if 'search' in query:
    search_query = query.split('search ')[1]
    url = f"https://www.google.com/search?q={search_query}"
    webbrowser.open(url)
    speak(f"Here's what I found for {search_query} on Google")

if 'send email' in query:
    try:
        speak("What should I say?")
        content = take_command()
        server = smtplib.SMTP('2006010@kiit.ac.in', 587)
        server.ehlo()
        server.starttls()
        speak("Please enter your email address and password.")
        email = input("Email: ")
        password = input("Password: ")
        server.login(email, password)
        speak("Who should I send it to?")
        to = take_command()
        server.sendmail(email, to, content)
        server.close()
        speak("Email sent successfully.")
    except Exception as e:
        print(e)
        speak("Sorry, I could not send the email.")


if 'set an alarm for' in query:
    alarm_time = query.split('set an alarm for ')[1]
    hour = int(alarm_time.split(':')[0])
    minute = int(alarm_time.split(':')[1].split()[0])
    am_pm = alarm_time.split()[-1]
    if am_pm == 'pm' and hour != 12:
        hour += 12
    elif am_pm == 'am' and hour == 12:
        hour = 0
    while True:
        if time.localtime().tm_hour == hour and time.localtime().tm_min == minute:
            speak("Time's up!")
            break
        time.sleep(60)
        

if 'play' in query:
    song_name = query.split('play ')[1]
    client_credentials_manager = SpotifyClientCredentials(client_id='YOUR_CLIENT_ID', client_secret='YOUR_CLIENT_SECRET')
    sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
    results = sp.search(q=song_name, type='track')
    track_uri = results['tracks']['items'][0]['uri']
    sp.start_playback(uris=[track_uri])
    speak(f"Playing {song_name}")
import requests

if 'weather' in query:
    city = "Bhubaneswar"  # Replace with user's location
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid=YOUR_API_KEY&units=imperial"
    response = requests.get(url)
    data = response.json()
    temp = data['main']['temp']
    description = data['weather'][0]['description']
    speak(f"The temperature in {city} is {temp} degrees Fahrenheit and the weather is {description}.")
import requests

if 'turn on the lights' in query:
    url = "http://YOUR_HUE_BRIDGE_IP/api/YOUR_USERNAME/groups/1/action"
    data = '{"on":true}'
    headers = {'Content-type': 'application/json'}
    response = requests.put(url, data=data, headers=headers)
    speak("Turning on the lights.")

if 'turn off the lights' in query:
    url = "http://YOUR_HUE_BRIDGE_IP/api/YOUR_USERNAME/groups/1/action"
    data = '{"on":false}'
    headers = {'Content-type': 'application/json'}
    response = requests.put(url, data=data, headers=headers)
    speak("Turning off the lights.")
import random

# Define a list of motivational messages
motivational_messages = [
    "Believe in yourself and all that you are. Know that there is something inside you that is greater than any obstacle.",
    "Success is not final, failure is not fatal: it is the courage to continue that counts.",
    "You are never too old to set another goal or to dream a new dream.",
    "The only way to do great work is to love what you do.",
    "Success is not how high you have climbed, but how you make a positive difference to the world.",
    "Don't watch the clock; do what it does. Keep going.",
    "Believe you can and you're halfway there.",
    "I have not failed. I've just found 10,000 ways that won't work.",
    "The only limit to our realization of tomorrow will be our doubts of today.",
    "You miss 100% of the shots you don't take."
]

# Add a function to give motivational messages
def motivate():
    message = random.choice(motivational_messages)
    speak(message)

# Add a conditional statement to trigger motivational messages
if 'motivate me' in query:
    motivate()
    import random
import requests

# Define a function to get a random fact from an API
def get_fact():
    url = "https://useless-facts.sameerkumar.website/api"
    response = requests.get(url)
    data = response.json()
    fact = data['data']
    return fact

# Add a conditional statement to trigger interesting facts
if 'tell me an interesting fact' in query:
    fact = get_fact()
    speak(f"Here's an interesting fact for you: {fact}")

elif 'stop' in query or 'exit' in query:
            speak('Goodbye!')
            
        
