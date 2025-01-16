


import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import re
import openpyxl
from urllib.parse import urlparse
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO




# Function to parse event text
def parse_event_text(event_text):
    event_data = {
        "day": None,
        "date": None,
        "time": None,
        "group_name": None,
        "keywords": None
    }
    date_time_pattern = re.compile(r'(\w{3}), (\w{3} \d{1,2}) \u00b7 (\d{1,2}:\d{2} (?:AM|PM) UTC)')
    match = date_time_pattern.search(event_text)

    if match:
        event_data["day"] = match.group(1)
        event_data["date"] = match.group(2)
        event_data["time"] = match.group(3)

        utc_index = event_text.find("UTC")
        if utc_index != -1:
            event_data["keywords"] = event_text[utc_index + len("UTC"):].strip()

    return event_data

# Function to extract group name from URL
def extract_group_name_from_url(url):
    parsed_url = urlparse(url)
    path = parsed_url.path
    group_name = path.split('/')[1].replace('-', ' ').title()
    return group_name

# Function to process events
def process_events(events):
    processed_data = []
    appended_urls = set()  # To track unique events

    for event in events:
        if re.search(r'\w{3}, \w{3} \d{1,2} \u00b7 \d{1,2}:\d{2} (?:AM|PM) UTC', event['text']):
            parsed_event = parse_event_text(event['text'])
            group_name = extract_group_name_from_url(event['href'])

            # Avoid adding duplicate events
            if event['href'] not in appended_urls:
                processed_data.append({
                    "Day": parsed_event['day'],
                    "Date": parsed_event['date'],
                    "Time": parsed_event['time'],
                    "Keywords": parsed_event['keywords'],
                    "Group Name": group_name,
                    "Event URL": event['href']
                })
                appended_urls.add(event['href'])
    return processed_data

# Function to create Excel file
def create_excel(file_name,data):
    if file_name=="meetup":
        df = pd.DataFrame(data)
        output = BytesIO()
        df.to_excel(output, index=False, sheet_name="Events")
        output.seek(0)
        return output
    elif file_name=="eventbrite":
        new_df = pd.DataFrame(data, columns=['Event URL', 'Event Name', 'Event Location', 'Date and Time'])

        # Append new data and remove duplicates
        #combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        new_df.drop_duplicates(subset='Event Name', keep='first', inplace=True)
        output = BytesIO()
        new_df.to_excel(output, index=False, sheet_name="Events")
        return output
        #st.success(f"Events have been saved to {file_name}.")
# Function to scrape Meetup events for multiple keywords
def scrape_meetup_events(keywords, location=None, start_date=None, end_date=None, event_type=None):
    base_url = 'https://www.meetup.com/find/?'
    results = []

    # Split user-provided keywords by commas
    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]
    
    for keyword in keyword_list:
        params = []
        if keyword:
            params.append(f"keywords={keyword.replace(' ', '%20')}")
        if location:
            params.append(f"location={location}")
        if start_date and end_date:
            params.append(f"customStartDate={start_date}&customEndDate={end_date}")
        if event_type and event_type != "all":
            params.append(f"eventType={event_type}")

        url = base_url + '&'.join(params)
        st.write(f"Scraping URL for keyword '{keyword}': {url}")

        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            max_w_narrow = soup.find(class_="max-w-narrow")

            if max_w_narrow:
                child_elements = max_w_narrow.find_all(True)
                for child in child_elements:
                    links = child.find_all('a')
                    for link in links:
                        href = link.get('href')
                        text = link.get_text(strip=True)
                        # Append the scraped data with the associated keyword
                        results.append({'text': text, 'href': href, 'searched_keyword': keyword})
        else:
            st.error(f"Failed to retrieve data for keyword '{keyword}'. Status code: {response.status_code}")
    
    return results



# Function to construct the URL dynamically based on parameters for EventBrite
def construct_url(event_type=None, location='india--pune', keyword=None):
    base_url = "https://www.eventbrite.com/d/"
    if not keyword:
        raise ValueError("Keyword is required to construct the URL.")
    url_parts = []
    if event_type and event_type.lower() == 'online':
        url_parts.append('online/')
    url_parts.append(f"{location}/")
    url_parts.append(f"{keyword}/")
    final_url = base_url + ''.join(url_parts)
    return final_url

# Function to scrape EventBrite events
def scrape_eventbrite_events(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    event_data = []
    event_names = set()

    event_containers = soup.find_all('div', class_='Stack_root__1ksk7')
    for event in event_containers:
        event_info = {}
        event_link = event.find('a', class_='event-card-link')
        if event_link:
            event_name = event_link['aria-label']
            if event_name in event_names:
                continue
            event_info['Event URL'] = event_link['href']
            event_info['Event Name'] = event_name
            event_names.add(event_name)

        p_tags = event.find_all('p', class_='Typography_root__487rx')
        p_tags = [p for p in p_tags if 'EventCardUrgencySignal__label' not in p['class']]
        if p_tags:
            event_info['Date and Time'] = p_tags[0].text
            if len(p_tags) > 1:
                event_info['Event Location'] = p_tags[1].text
            else:
                event_info['Event Location'] = event_link.get('data-event-location', None)

        event_data.append(event_info)
    return event_data



# Streamlit app
st.sidebar.title("Options")
button = st.sidebar.radio("Choose an option:", 
                           ["Get Meetup Events", "Get EventBrite Events"])


download_data = None

if button == "Get Meetup Events":
    st.title("Meetup Event Finder")
    keywords = st.text_input("Enter the keywords (comma separated):")

    location = st.text_input("Location:")
    start_date = st.date_input("Start Date", min_value=datetime.today())
    end_date = st.date_input("End Date", min_value=start_date + timedelta(days=1))
    event_type = st.selectbox("Event Type", ["online", "in-person", "all", "indoor", "outdoor"])

    start_date_str = start_date.strftime('%Y-%m-%dT%H:%M:%S-05:00')
    end_date_str = end_date.strftime('%Y-%m-%dT%H:%M:%S-05:00')

    if st.button("Search Meetup Events"):
        if keywords:
            events = scrape_meetup_events(
                keywords=keywords,
                location=location,
                start_date=start_date_str,
                end_date=end_date_str,
                event_type=event_type
            )
            if events:
                processed_data = process_events(events)
                st.write("Processed Events:")
                st.dataframe(pd.DataFrame(processed_data))
                download_data = create_excel("meetup",processed_data)
        else:
            st.error("Please enter the keywords.")

elif button == "Get EventBrite Events":
    st.title("Eventbrite Event Finder")
    keywords = st.text_input("Enter the keywords (comma separated):")

    location = st.text_input("Location (e.g., india--pune):", value="india--pune")
    event_type = st.selectbox("Event Type", ["online", "in-person"])

    if st.button("Search EventBrite Events"):
        if keywords:
            event_list = []
            for keyword in [k.strip() for k in keywords.split(',') if k.strip()]:
                try:
                    url = construct_url(event_type=event_type, location=location, keyword=keyword)
                    events = scrape_eventbrite_events(url)
                    if events:
                        event_list.extend(events)
                    else:
                        st.warning(f"No events found for keyword '{keyword}'.")
                except Exception as e:
                    st.error(f"Error processing keyword '{keyword}': {e}")
        
            st.write("Processed Events:")
            st.dataframe(pd.DataFrame(event_list))
            download_data = create_excel("eventbrite",event_list)
        else:
            st.error("Please enter the keywords.")
                


# Add download button in the sidebar if data is available
if download_data:
    st.sidebar.download_button(
        label="Download Excel",
        data=download_data,
        file_name="Events.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
