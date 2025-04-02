import gradio as gr
import google.generativeai as genai
import os
import requests
import dateparser
from geopy.geocoders import Nominatim
from datetime import datetime, timedelta

# Set API keys
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")
else:
    print("Warning: Google Gemini API key not found. Chatbot will not function.")

travel_guide_output = ""

def get_coordinates(location_name):
    geolocator = Nominatim(user_agent="travel_chatbot")
    try:
        location = geolocator.geocode(location_name)
        return (location.latitude, location.longitude) if location else (None, None)
    except Exception as e:
        print(f"Error getting coordinates: {e}")
        return None, None

def get_weather_forecast(latitude, longitude):
    if not OPENWEATHER_API_KEY:
        return None

    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"lat": latitude, "lon": longitude, "appid": OPENWEATHER_API_KEY, "units": "metric"}
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching weather data: {e}")
        return None

def parse_date(date_str):
    if not date_str:
        return None
    parsed_date = dateparser.parse(date_str, settings={'PREFER_DATES_FROM': 'future'})
    return parsed_date if parsed_date else None

def respond(your_location, destination, transportation, date, preference, include_options):
    global travel_guide_output

    if not GOOGLE_API_KEY:
        return "Error: Google Gemini API key not configured."
    
    latitude, longitude = get_coordinates(destination)
    weather_info = ""
    travel_date = parse_date(date)
    
    if latitude and longitude and travel_date:
        weather_data = get_weather_forecast(latitude, longitude)
        if weather_data and 'list' in weather_data:
            for forecast in weather_data['list']:
                forecast_date = datetime.fromtimestamp(forecast['dt'])
                if forecast_date.date() == travel_date.date() and forecast_date.hour == 12:
                    weather_info = f" The weather forecast for {travel_date.strftime('%B %d')} is {forecast['weather'][0]['description']} with a temperature of {forecast['main']['temp']}°C."
                    break

    prompt = f"""
    **Travel Plan Details:**
    - **From:** {your_location}
    - **To:** {destination}
    - **Transportation:** {transportation}
    - **Travel Date:** {date}
    - **Budget Preference:** {preference}
    - **Additional Info:** {', '.join(include_options) if include_options else 'None'}
    {weather_info}

    Provide a detailed travel guide based on these details.
    """
    
    try:
        response = model.generate_content([{"role": "user", "parts": [{"text": prompt}]}])
        travel_guide_output = response.text
        return response.text
    except Exception as e:
        return f"An error occurred: {e}"

def chatbot_respond(message, chat_history):
    global travel_guide_output
    if not travel_guide_output:
        return "No travel guide has been generated yet. Please enter your travel details first."
    
    prompt = f"""
    You are an AI travel assistant. The user has already generated a travel guide. Use the following details to assist them:
    
    {travel_guide_output}
    
    If the user asks a question related to their trip, provide an answer based on this guide.
    If the user asks general travel questions, respond accordingly.
    If they make casual conversation, respond naturally.
    
    User's message: {message}
    """
    
    try:
        response = model.generate_content([{"role": "user", "parts": [{"text": prompt}]}])
        return response.text
    except Exception as e:
        return f"An error occurred: {e}"

with gr.Blocks() as demo:
    with gr.Row():
        with gr.Column(scale=1):
            your_location_input = gr.Textbox(label="Your Current Location")
            destination_input = gr.Textbox(label="Travel Destination")
            transportation_dropdown = gr.Dropdown(["Bus", "Plane", "Train"], label="Preferred Transportation")
            date_input = gr.Textbox(label="Travel Date (e.g., tomorrow, March 15)")
            preference_dropdown = gr.Dropdown(["Luxurious", "Cheap", "Balanced"], label="Budget Preferences")
            include_checkboxes = gr.CheckboxGroup([
                "Restaurant recommendations", "Hotel suggestions", "Nearby attractions", "Local tips", "Packing guides"
            ], label="Include in Chat")
            send_button = gr.Button("Generate Guide")

        with gr.Column(scale=2):
            output_box = gr.Markdown(label="AI Output", value="Please enter your travel details and click 'Generate Guide'.")

        with gr.Column(scale=1):
            chatbot = gr.ChatInterface(fn=chatbot_respond, title="Travel Assistant Chatbot")

    send_button.click(
        respond,
        inputs=[your_location_input, destination_input, transportation_dropdown, date_input, preference_dropdown, include_checkboxes],
        outputs=[output_box]
    )

demo.launch()
