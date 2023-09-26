from flask import Flask, render_template, request, redirect, url_for
from googleapiclient.discovery import build
from textblob import TextBlob
from transformers import pipeline

app = Flask(__name__)

# Replace 'YOUR_YOUTUBE_API_KEY' with your actual YouTube API key

YOUTUBE_API_KEY = 'AIzaSyAaBdR1AsSJWy84kgqoCNLeve7Zf0YELuE'  # Replace with your API key

# Load the summarization and question-answering pipelines
summarizer = pipeline("summarization")
question_answering = pipeline("question-answering")


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    query = request.form.get('query')
    videos = search_youtube_videos(query)
    return render_template('index.html', videos=videos)

@app.route('/review/<string:video_id>')
def review(video_id):
    video_details = get_video_details(video_id)
    video_url = video_details['video_url']

    # Retrieve comments based on the video URL
    comments = get_video_comments(video_url)

    # Calculate average sentiment score and rate the video
    avg_sentiment = calculate_average_sentiment(comments)
    video_rating = calculate_video_rating(avg_sentiment)

    # Combine title, description, and transcript (if available) for summarization
    combined_text = video_details['title'] + " " + video_details['description']
    transcript = video_details.get('transcript', '')
    if transcript:
        combined_text += " " + transcript

    # Use the summarization pipeline to generate the summary
    video_summary = summarizer(combined_text, max_length=150, min_length=50, do_sample=False)

    # Extract the generated summary text
    summary_text = video_summary[0]['summary_text']

    return render_template('review.html', video_details=video_details, comments=comments, video_rating=video_rating, video_summary=summary_text)

@app.route('/summarize/<string:video_id>')
def summarize(video_id):
    print(f"Accessing /summarize/{video_id}")
    video_details = get_video_details(video_id)

    # Combine title, description, and transcript (if available) for summarization
    combined_text = video_details['title'] + " " + video_details['description']
    transcript = video_details.get('transcript', '')
    if transcript:
        combined_text += " " + transcript

    # Use the summarize_video function to generate the summary
    video_summary = summarize_video(combined_text)

    # Extract the generated summary text
    summary_text = video_summary[0]['summary_text']

    return render_template('summarize.html', video_summary=summary_text)




@app.route('/qna', methods=['GET', 'POST'])
def qna():
    if request.method == 'POST':
        video_id = request.form['video_id']
        question = request.form['question']

        # Answer the question using the Q&A pipeline
        answers = answer_question(video_id, question)

        return render_template('qna.html', video_id=video_id, answers=answers)

    return render_template('qna.html')

def answer_question(video_id, question):
    video_details = get_video_details(video_id)

    # Combine description and transcript for Q&A
    content = video_details['description'] + " " + video_details['transcript']

    # Use the Q&A pipeline to answer the question
    answers = question_answering(question=question, context=content)

    return answers['answer']

def search_youtube_videos(query):
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    search_response = youtube.search().list(
        q=query,
        type='video',
        part='snippet',
        maxResults=10
    ).execute()
    videos = []
    for search_result in search_response.get('items', []):
        video_id = search_result['id']['videoId']
        videos.append({
            'video_id': video_id,
            'thumbnail': search_result['snippet']['thumbnails']['default']['url'],
            'title': search_result['snippet']['title'],
        })
    return videos

def get_video_details(video_id):
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

    # First, fetch basic video details (title, description, etc.)
    video_response = youtube.videos().list(
        part='snippet',
        id=video_id
    ).execute()

    video_data = video_response['items'][0]['snippet']

    # Extract video details
    thumbnail_url = video_data['thumbnails']['default']['url']
    title = video_data['title']
    description = video_data['description']
    video_url = f'https://www.youtube.com/watch?v={video_id}'  # Construct the video URL

    # Next, fetch the transcript separately
    transcript_response = youtube.captions().list(
        part='snippet',
        videoId=video_id
    ).execute()

    transcript = ""

    # Check if there are captions available
    if 'items' in transcript_response:
        for item in transcript_response['items']:
            if 'snippet' in item:
                caption_text = item['snippet'].get('text', '')
                transcript += caption_text + " "

    return {
        'thumbnail': thumbnail_url,
        'title': title,
        'description': description,
        'video_url': video_url,
        'transcript': transcript  # Include the transcript in the returned dictionary
    }

def get_video_comments(video_url):
    # Extract the video ID from the video URL
    video_id = video_url.split('v=')[1]

    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    comment_response = youtube.commentThreads().list(
        part='snippet',
        videoId=video_id,
        textFormat='plainText',
        maxResults=20  # Adjust as needed
    ).execute()

    comments = []

    for comment in comment_response['items']:
        snippet = comment['snippet']['topLevelComment']['snippet']
        author = snippet['authorDisplayName']
        text = snippet['textDisplay']
        
        # Calculate sentiment for the comment
        analysis = TextBlob(text)
        sentiment = analysis.sentiment.polarity

        comments.append({'author': author, 'text': text, 'sentiment': sentiment})

    return comments

def calculate_average_sentiment(comments):
    sentiment_scores = []
    for comment in comments:
        text = comment['text']
        analysis = TextBlob(text)
        sentiment_scores.append(analysis.sentiment.polarity)

    if sentiment_scores:
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
        return avg_sentiment
    else:
        return 0  # Default sentiment score if there are no comments

def calculate_video_rating(avg_sentiment):
    # Map the sentiment score to a rating between 1 and 5
    rating = (avg_sentiment + 1) * 2.5
    return round(rating, 1)  # Round the rating to one decimal place

@app.context_processor
def utility_functions():
    def get_emoji_for_rating(rating):
        if rating >= 4.5:
            return '🌟🌟🌟🌟🌟'
        elif rating >= 4.0:
            return '🌟🌟🌟🌟'
        elif rating >= 3.5:
            return '🌟🌟🌟'
        elif rating >= 3.0:
            return '🌟🌟'
        elif rating >= 2.5:
            return '🌟'
        else:
            return '👎'

    def get_emoji_for_sentiment(sentiment):
        if sentiment > 0:
            return '😃'  # Positive sentiment
        elif sentiment < 0:
            return '😔'  # Negative sentiment
        else:
            return '😐'  # Neutral sentiment

    return dict(get_emoji_for_rating=get_emoji_for_rating, get_emoji_for_sentiment=get_emoji_for_sentiment)

if __name__ == '__main__':
    app.run(debug=True)
